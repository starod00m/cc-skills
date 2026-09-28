---
name: st-grill
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. Ends at a hard stop where the user picks the next step; never slides into implementation on its own.
disable-model-invocation: true
---

Call the Skill tool twice, for "grilling" and "domain-modeling".

## Interactive by design — auto mode override

This skill is **interactive by design**. The user invoked it to be interviewed, not to have you design the thing and build it. Therefore, **inside this skill, auto mode does NOT apply**:

- **Every round is a hard stop.** Ask the frontier, then WAIT. Never answer your own question as a "reasonable assumption" and move on.
- **The closing `AskUserQuestion` is a hard stop too.** It is the gate: until the user picks an option, the design is not approved for anything.
- **Writing `CONTEXT.md` and ADRs is not implementation.** That is `domain-modeling` doing its job mid-session; do it inline as terms and decisions crystallise. The gate below is about code and tests, nothing else.
- The outer session may be in auto mode. Ignore that while inside this skill. Hand control back to auto only when the skill completes.

## When the frontier is empty

The session ends when every branch of the design tree is visited and the user confirms you reached a shared understanding. **Do not act on the design yourself.** Summarise what was settled, then ask:

```json
{
  "questions": [{
    "question": "Дерево решений пройдено. Что дальше?",
    "header": "Next step",
    "options": [
      {"label": "Спека", "description": "/st-spec-create — соберёт спеку из этого разговора без повторного интервью в docs/plans/<yyyymmdd>-<slug>-spec.md, оттуда /st-plan-create возьмёт слаг для плана"},
      {"label": "План напрямую", "description": "/st-plan-create — без спеки, сразу план реализации в docs/plans/"},
      {"label": "Реализовать сейчас", "description": "Идти прямо в код, без спеки и плана"}
    ],
    "multiSelect": false
  }]
}
```

Deferring the design entirely goes through the automatic "Other" option; it needs no button of its own.

### The gate

**A bare "давай" / "го" / "ок" / "поехали" is not an answer to this question.** It reads like approval and is not one: the user is agreeing with the last thing you said, which was analysis, not a proposal to write code. Treat it as the cue to ask the question, never as its answer.

Until an option is chosen, **do not touch code or tests** — no `Edit`, no `Write`, no fixes "while we're here". The design being obvious to you is not approval; the whole reason this gate exists is that it looked obvious the previous times too.

Picking an option **is** explicit approval. Do not ask a second time, and do not add a confirmation round on top of it: choosing "Реализовать сейчас" costs a deliberate click on that exact word, which is precisely what "давай" does not.

### After the choice

Start the chosen step at once, in this session. The grilling context is the input each step needs:

- **Спека**: invoke `st-spec-create`. It synthesises the spec from this conversation, so it must run here and not in a fresh session.
- **План напрямую**: invoke `st-plan-create`, naming what the grilling settled (ticket doc, ADRs, `CONTEXT.md` terms) as its input.
- **Реализовать сейчас**: implement the settled design straight away.
