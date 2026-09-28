---
name: st-plan-annotate
description: Use when user wants to manually review and annotate a plan file in an editor before implementing it. Opens the plan in $EDITOR in a tmux split, applies user's changes back to the file, and loops until no more changes.
allowed-tools: Bash(python3:*), Read, Edit, Grep, Glob
---

# Plan Annotate

## Overview

Opens a plan file in `$EDITOR` in a tmux split, reads the diff of user's edits, applies changes to the plan file, and repeats until the user closes the editor without making changes.

**Announce at start:** "I'm using the st-plan-annotate skill."

## Interactive by design — auto mode override

This skill is **interactive by design**. The whole point is that the user edits the plan by hand in $EDITOR. Therefore, **inside this skill, auto mode does NOT apply**:

- **The annotation loop is a hard stop.** The editor is launched in the background (Step 2) — end the turn and let the completion notification come back, however long the user takes. Do not poll, do not sleep, do not "assume the user is done".
- **Do NOT skip the loop** because "the plan looks fine already". The user invoked this skill precisely to review and annotate the plan — their judgment replaces yours here.
- **Discuss-записи (`?`) — это hard stop.** Когда находишь аннотацию с ведущим `?` (см. Step 3a), показывай её пользователю и **жди явного ответа и апрува**. Не отвечай за пользователя «по разумному предположению», не правь файл по своей интерпретации.
- The outer session may be in auto mode. Ignore that while inside this skill.

## Process

### Step 1: Find Plan File

If user provided a path — use it.

Otherwise search for plans:

```bash
find docs/plans -name "*.md" -not -path "*/completed/*" -not -name "*-spec.md" 2>/dev/null
```

`*-spec.md` is excluded on purpose: it is the spec a plan was built from, annotated at its own stage, not here.

If multiple plans found — ask user which one to annotate.

### Step 2: Run Annotation Loop

The editor outlives a foreground tool call (the Bash tool caps at 10 minutes), so launch the script **in the background** — Bash tool with `run_in_background: true`:

```bash
python3 "${CLAUDE_SKILL_DIR}/hooks/plan-annotate.py" <plan-file>
```

Then say one sentence ("Редактор открыт — закрой его, и я подхвачу правки.") and **end the turn**. Claude Code notifies you when the command exits; read its output:

- **exit 0, stdout is a path to a patch file** — the user saved changes. Go to Step 3.
- **exit 0, empty stdout** — the user closed the editor without changes. Go to Step 4.
- **non-zero exit** — the editor never opened. Report the actual error from stderr to the user; do **not** treat it as "no changes". The usual cause is that no tmux client is attached.

### Step 3: Apply Diff

The script's stdout is **a single line with the path to the patch file** (e.g. `/var/folders/.../plan-diff-xxxx.patch`).

1. Read the patch file with the Read tool
2. Read the current plan file
3. **Classify each added comment as discuss (`?`) or fix** (see Step 3a). Обработай все discuss-записи **до** применения любых правок.
4. Apply the diff: the diff shows what the user wants changed
   - Lines starting with `+` (not `+++`) = additions the user wants
   - Lines starting with `-` (not `---`) = removals the user wants
   - **Не вставляй в план строки, классифицированные как discuss-записи в Step 3a** — это инструмент обсуждения, а не контент плана
   - Apply all other changes to the plan file using Edit tool
5. **Report changes** — after applying all edits, output a summary list grouped by section headings. Format:

   ```
   Применённые изменения:
   - «<заголовок секции>»: <краткое описание замечания>
   - «<заголовок секции>»: <краткое описание замечания>
   ...
   ```

   Where `<заголовок секции>` is the nearest markdown heading (`#`, `##`, `###`, etc.) above the changed lines in the plan file. If multiple changes fall under the same heading, list each as a separate bullet under that heading. This helps the user quickly navigate to the applied changes.

6. **Go back to Step 2** — run annotation loop again

### Step 3a: Detect and Handle Questions

Пользователь маркирует **вопросы для обсуждения** ведущим символом `?` в начале добавленной аннотации. Всё остальное — **инструкции для правки**, которые применяются как есть.

#### Что считается аннотацией для классификации

Любая добавленная пользователем строка-комментарий *о* плане, а не сам контент плана. Типичные формы: markdown-комментарий (`<!-- ... -->`), цитата (`> ...`), отдельная строка-замечание, явно адресованная тебе. Правки существующего текста плана, новые шаги, перестановка структуры, блоки кода, переформулированные предложения — это **не** комментарии-аннотации, применяй их обычным порядком.

#### Правило классификации (единственное)

**Discuss-запись (вопрос).** Аннотация, у которой после очистки от ведущих пробелов/табов и markdown-маркеров (`- `, `* `, `1. `, `> `, `<!-- `) **первым непробельным смысловым символом** идёт `?`. Примеры:

- `? расскажи подробнее про эту часть`
- `?почему именно так, а не через X?`
- `> ? не лучше ли вынести в отдельный шаг`
- `<!-- ? стоит ли тут добавить ретраи -->`
- одиночная строка `?` с многострочным телом ниже — всё это discuss-запись

**Fix-запись (инструкция).** Всё остальное. В том числе аннотации с вопросительной интонацией в середине текста («давай переименуем foo? и ещё проверим bar») — здесь `?` стоит **не** в начале, значит это указание с вопросительной окраской, а не запрос обсуждения.

#### Чего не делать

- Не пытайся «угадать» вопрос по интонации, наличию слов «почему/зачем/стоит ли», окончанию строки на `?` и т.п. Если ведущего `?` нет — это инструкция.
- Не путай `?` внутри цитируемой plan-строки с маркером пользователя — маркер ищется именно в **теле комментария**, который добавил пользователь, а не в окружающем контексте.
- Старые маркеры `#ASK` / `#FIX` / `#DO` больше не имеют специального значения — если пользователь их использует, классифицируй по тому же правилу `?` в начале.

#### Process

1. Пройди по всем добавленным строкам в диффе. Для каждой comment-like аннотации определи: **discuss** (ведущий `?`) или **fix** (всё остальное).
2. Собери полный список discuss-записей в порядке появления в диффе и полный список fix-записей.
3. **Сначала покажи пользователю краткую сводку**: сколько найдено `?`-обсуждений, сколько обычных правок, и о чём примерно каждая (одна строка на запись). Это даёт пользователю шанс заметить ошибку классификации (например, аннотация просто начинается с риторического вопроса, но по смыслу это правка) и поправить тебя.
4. Если discuss-записей нет — сразу переходи к пункту 9.
5. Бери **первую** discuss-запись. Покажи её пользователю с контекстом (заголовок секции, окружающие строки, тело комментария дословно). Если нужно — прочитай упомянутые в записи файлы/код, чтобы ответить по делу. Сформулируй ответ или предложение.
6. **Жди явного апрува** пользователя на текущую запись. Явный апрув — утвердительная реплика на конкретное предложение: «да», «ок», «апрув», «го», «согласен», «делаем так», «договорились». Содержательный встречный комментарий или новый вопрос — **не** апрув; продолжай обсуждать ту же запись.
7. После апрува — короткое резюме договорённости (1–2 строки: «по [тема записи] договорились: [суть решения]»). Это нужно, потому что решения discuss-фазы могут менять план правок (см. п. 9) — резюме фиксирует, что именно решили.
8. Спроси: «Перейти к следующему вопросу?» (если ещё есть discuss-записи) или «Перейти к применению правок?» (если discuss-записи закончились). Не двигайся дальше без подтверждения. Повторяй пп. 5–8 для оставшихся discuss-записей.
9. **Не правь файлы во время discuss-фазы.** Совсем. Даже если кажется, что обсуждение очевидно ведёт к мелкой правке — пользователь поставил `?` именно чтобы обсудить, а не получить молчаливую правку.
10. Когда все discuss-записи закрыты — покажи **итоговый сводный план правок** с учётом решений discuss-фазы (новые правки, изменённые или отменённые из исходного списка fix-записей). Дождись подтверждения пользователя на применение.
11. Только после подтверждения — применяй fix-записи. Discuss-записи (строки с ведущим `?`) **не вставляй** в файл плана: они были инструментом обсуждения, а не контентом плана.
12. После применения изменений **возвращайся к Step 2** — запусти цикл аннотации снова, чтобы пользователь мог пересмотреть план с учётом резолва.

### Step 4: Done

On empty output (no diff), tell the user:
"Plan review complete, no further changes."

## Requirements

- a running tmux server with an attached client (kitty and wezterm are **not** supported)
- `$EDITOR` set (defaults to `micro`)

## Notes

- The script opens a **copy** of the plan in the editor — it does not modify the file directly
- The diff is between the original content and what the user saved
- A session started as a Claude Code background job does not inherit `$TMUX`/`$TMUX_PANE`; the script then splits off the active pane of the most recently active attached client, so the pane still shows up where the user is looking
- If the script fails, it exits non-zero and prints the error to stderr
