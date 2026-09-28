---
name: st-git-review
description: Process code review annotations from .review/ files. Handles FIX (applies changes) and ASK (discusses with user) entries created in Emacs. Activates on "git review", "review changes", "review my changes", "annotate changes", "interactive review", "ревью изменений", "посмотри изменения", or when user passes a .review/*.md file path.
allowed-tools: Bash(git *, codex *), Read, Edit, Write, Grep, Glob, Agent(quality-reviewer)
---

# Git Review

Process code review annotations from `.review/` files created by the user in Emacs.

## Activation Triggers

- "git review", "review changes", "review my changes"
- "annotate changes", "interactive review"
- "ревью изменений", "посмотри изменения"
- User passes a `.review/*.md` file path as argument

## Review File Format

The review file (`.review/<hash>[-dirty].md`) contains entries in two formats:

### Format 1: File buffer annotations (standard)

```markdown
## FIX src/handler.py:42-45
```python
def process(data):
    result = data + 1
`` `
переименовать в process_batch

## ASK src/models.py:58
```python
    retry(action, times=3)
`` `
зачем тут retry? какой сценарий отказа?
```

### Format 2: Magit diff annotations

Created when user annotates code while viewing a diff in magit (commit, staged, unstaged, or range diff).

```markdown
## FIX src/handler.py (diff: abc1234^..abc1234)
Lines in NEW: 42-45
```diff
 def process(data):
-    result = data + 1
+    result = process_item(data)
     return result
`` `
process_item неправильно обрабатывает None

## ASK src/models.py (diff: (working tree))
Lines in OLD: 58
```diff
-    retry(action, times=3)
`` `
зачем убрали retry?
```

Key differences from Format 1:
- **`(diff: REF)`** — indicates the diff context: `abc1234^..abc1234` for a commit, `main..feature` for a range, `(working tree)` for staged/unstaged changes
- **`Lines in SIDE: N-M`** — real file line numbers with side indicator: `NEW` (added/context lines), `OLD` (removed lines), `OLD+NEW` (mixed selection)
- **Code uses diff format** with `+`/`-`/` ` prefixes showing what changed
- **Renamed files** shown as `old/path.py → new/path.py`
- **File-level annotations** may have no code block (when cursor was on file header, not inside a hunk)

### Format 3: File-level annotations

Created when the user wants to comment on a file as a whole — rename, remove, redesign, move to another module — rather than on specific lines. No line range, no code block.

```markdown
## FIX src/handler.py
переименовать модуль в handler_legacy.py и развести обработку на два отдельных класса

## ASK src/models.py
зачем этот файл вообще существует? его содержимое дублирует src/schema.py
```

Key traits:
- Header has **no line range** (no `:N-M` suffix) and **no `(diff: ...)` marker**
- **No code block** follows — directly the user's comment after the heading
- Applies to the entire file, not a specific location

### Handling file-level annotations

When processing Format 3 entries:
1. **FIX without lines/code** — the user wants a change that affects the file as a whole. Common cases:
   - Rename / move the file → use `git mv` and update all imports
   - Delete the file → `git rm` and remove references
   - Split the file into multiple modules → analyse responsibilities, plan the split, confirm with user before acting
   - Restructure the file (change approach, swap pattern) → read the full file, propose a plan, confirm before rewriting
   If the requested action has a large blast radius (deletion, rename touching many callers, substantial rewrite) — **propose the plan and wait for user confirmation before applying**. Do not silently refactor a whole file from a one-line directive.
2. **ASK without lines/code** — the user is asking a question about the file as a whole (purpose, necessity, relation to other modules). Handle the same way as Format 1/2 ASK entries: discuss one at a time, wait for user's reaction before moving on.
3. **Locate the target** — resolve the file path relative to project root. If the file was moved/renamed since the annotation was created, try the new path (check `git log --follow`).

### Handling magit diff annotations

When processing Format 2 entries:
1. **For `(working tree)` diffs** — the file is the current working version, edit it directly
2. **For committed diffs** — the annotation references a specific commit's changes. Find the corresponding code in the **current** file version (it may have shifted). Use the code block content to locate it, not just line numbers
3. **Side=OLD** means the user is commenting on code that was **removed** — the fix may involve restoring it or explaining why it was removed
4. **Side=NEW** means the user is commenting on code that was **added** — standard fix
5. **Side=OLD+NEW** means the user selected both old and new code — understand the full change context

### Common fields

- `## FIX` — directive to change code. Claude must fix it.
- `## ASK` — question for discussion. Claude must answer before proceeding.
- Code block shows the context (what the annotation refers to).
- Text after code block is the user's comment/instruction.
- File path and line numbers are relative to project root.

## Workflow

### Step 1: Read the review file

Read the file passed as argument (e.g. `.review/a1b2c3d-dirty.md`).

#### Locating the file in a worktree

The review file is normally created in the **current worktree**'s root (where the user is editing). The Emacs integration uses `git rev-parse --show-toplevel` to detect that root, so when running this skill from a worktree the path passed in is relative to the worktree and resolves directly.

Fallback for legacy / misplaced review files: if the file is not found under the current working directory, also check the **common repo root**. In a git worktree this is a different directory:

```bash
# Common repo root (parent of the shared .git directory)
COMMON_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
```

Look for `<COMMON_ROOT>/<relative-path>`. If found there, use it (and remember its location for the archive step). Reason: older versions of the Emacs helper resolved project root via `projectile-project-root`, which in a worktree returned the main repo path — old review files may still live there.

### Step 2: Separate FIX and ASK entries

Parse all entries. Group them into two lists: FIX entries and ASK entries.

### Step 3: Handle ASK entries one by one

Process ASK entries sequentially, one at a time:

1. Show the first ASK: code context + user's question
2. Provide your answer/explanation
3. Wait for user's reaction — they may:
   - Agree and move on → take next ASK
   - Disagree or ask follow-up → continue discussion on this ASK
   - Ask to convert this ASK into a FIX → add it to FIX list
4. Only after user confirms, move to the next ASK entry
5. After all ASK entries are resolved → proceed to Step 4 (FIX entries)

**Important:** Do NOT show multiple ASK entries at once. One question — one discussion.

### Step 4: Handle FIX entries

For each FIX entry:
1. Read the actual source file
2. Find the code fragment referenced in the entry (use the code block content to locate it — line numbers may have shifted)
3. Apply the requested change
4. Report what was changed

### Step 5: Commit changes

After all FIX entries are applied:
1. Stage only the files that were changed during review (`git add <file1> <file2> ...`)
2. Commit with message: `ревью: <краткое описание изменений>`
3. If multiple unrelated fixes — ask user: one commit or separate commits per fix

### Step 5.5: Автоматическое ревью исправлений

После коммита запусти ревью сделанных исправлений **без подтверждения пользователя**. Оба ревьюера запускаются **параллельно в одном сообщении**.

#### Сбор контекста

Определи diff исправлений — это diff последнего коммита (того, что создан в Step 5):

```bash
git diff HEAD~1...HEAD
```

Получи список изменённых файлов: `git diff --name-only HEAD~1...HEAD`.

#### Запуск Claude-агента

Запусти `quality-reviewer` через Agent tool (`subagent_type: quality-reviewer`). Передай в prompt:

```
## Задача
Проведи ревью исправлений, сделанных по результатам ручного code review.

## База для diff
HEAD~1 (предыдущий коммит) → HEAD

## Изменённые файлы
[список из git diff --name-only HEAD~1...HEAD]

## Инструкции
У тебя есть доступ к Read, Grep, Glob и Bash. Для анализа:
1. Получи diff: `git diff HEAD~1...HEAD`
2. Читай полные файлы через Read для понимания контекста

Проведи ревью согласно своей специализации. Выдай ТОЛЬКО найденные проблемы. Если проблем не найдено — ответь "Замечаний нет".
```

#### Запуск Codex-агента

**В том же сообщении** запусти Codex через Bash tool.

##### Sandbox: вложенные sandbox-ы конфликтуют на macOS

Claude Code и Codex оба используют Seatbelt sandbox на macOS. При запуске codex внутри sandbox Claude Code происходит паника с exit code 101 (`Attempted to create a NULL object`). Решение — запускать Bash tool call с параметром `dangerouslyDisableSandbox: true`. Это отключает внешний sandbox Claude Code для данного вызова, и codex создаёт свой собственный sandbox через `--sandbox read-only`.

Также **НЕ** перенаправляй вывод codex в файл (`> /tmp/...`) — без этого параметра sandbox Claude Code блокирует запись. Захватывай stdout напрямую из результата Bash tool.

##### Формат вызова

```bash
codex exec -C <путь к репозиторию> --sandbox read-only "Ты — quality-reviewer. Проведи ревью исправлений по результатам ручного code review. Diff: git diff HEAD~1...HEAD. Читай файлы и анализируй изменения. Выдай ТОЛЬКО найденные проблемы. Если проблем не найдено — ответь 'Замечаний нет'."
```

Параметры Bash tool call:
- **`dangerouslyDisableSandbox: true`** — ОБЯЗАТЕЛЬНО, иначе exit code 101
- **`timeout: 600000`** (10 минут)
- **Без перенаправления в файл** — stdout вернётся в результате Bash tool

**КРИТИЧНО:** Agent tool call и Bash tool call ОБЯЗАНЫ быть в **одном сообщении** для параллельного запуска.

#### Обработка результатов

1. Собери замечания от обоих ревьюеров.
2. Если замечания есть — покажи пользователю сводку:
   ```
   ### Ревью исправлений
   
   **Claude (quality-reviewer):** [замечания или "Замечаний нет"]
   **Codex (quality-reviewer):** [замечания или "Замечаний нет"]
   ```
3. Если есть критические проблемы (баги, security) — предложи пользователю исправить их перед продолжением.
4. Если замечаний нет или только минорные — перейди к Step 6.

#### Обработка ошибок Codex

Если Codex вернул ошибку (исчерпанная квота, пустой stdout, `operation not permitted`, ненулевой exit code) — продолжай с результатами только Claude-агента. Сообщи пользователю о сбое Codex.

### Step 6: Clean up

After all entries are processed and committed:
1. **Archive the review file** before removing it — move it into `<review-dir>/.history/<timestamp>-<original-name>`, where `<review-dir>` is the **directory where the review file actually lives** (worktree root in the normal case, common repo root if it was found there via the Step 1 fallback). Keep a record of all annotations in case the automated fixes need to be inspected later.
   ```bash
   # REVIEW_FILE is the absolute path resolved in Step 1
   REVIEW_DIR="$(dirname "$REVIEW_FILE")"
   mkdir -p "$REVIEW_DIR/.history"
   mv "$REVIEW_FILE" "$REVIEW_DIR/.history/$(date +%Y%m%d-%H%M%S)-$(basename "$REVIEW_FILE")"
   ```
   `.review/` is already in `.gitignore` (created by the Emacs integration), so the history directory inherits the ignore — no extra .gitignore edits needed.
2. Report: "Ревью завершено. Обработано N правок, M вопросов. Архив: <относительный путь к архивному файлу>"

## Requirements

- git
- codex (OpenAI Codex CLI) — для кросс-ревью исправлений
- Редактор с интеграцией для создания review-файлов (в набор не входит; формат файла описан выше)
