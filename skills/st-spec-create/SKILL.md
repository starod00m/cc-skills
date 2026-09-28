---
name: st-spec-create
description: "Turn the current conversation into a spec at docs/plans/<yyyymmdd>-<slug>-spec.md: no interview, just synthesis of what you've already discussed. The spec names the slug that /st-plan-create reuses for the plan."
---

This skill takes the current conversation context and codebase understanding and produces a spec. Do NOT interview the user; just synthesize what you already know.

## Where the spec goes

The spec is a file in this repo at `docs/plans/<yyyymmdd>-<slug>-spec.md`. There is no issue tracker in this setup: do not look for one, do not ask about one, and do not apply triage labels.

**The spec names the pair.** It is written before the implementation plan, so the `<slug>` it picks is the one `/st-plan-create` will reuse for `docs/plans/<yyyymmdd>-<slug>.md`. Derive it yourself, never ask the user:

- Prefix `<yyyymmdd>` is today's date.
- `<slug>` comes from the parsed intent plus the Jira key when there is one (`proj-123-add-login`, `md-link-patcher`). Lowercase, hyphen-separated.
- English equivalents only. Never transliterate Cyrillic (`oshibka`, `zadacha`).

## Process

1. Explore the repo to understand the current state of the codebase, if you haven't already. Use the project's domain glossary vocabulary throughout the spec, and respect any ADRs in the area you're touching.

2. Sketch out the seams at which you're going to test the feature. Existing seams should be preferred to new ones. Use the highest seam possible. If new seams are needed, propose them at the highest point you can. The fewer seams across the codebase, the better - the ideal number is one.

Check with the user that these seams match their expectations.

3. Write the spec using the template below to `docs/plans/<yyyymmdd>-<slug>-spec.md`, creating `docs/plans/` if it does not exist.

4. Commit the spec, print its path in one line (`Спека: docs/plans/<yyyymmdd>-<slug>-spec.md`), then close with the **gate**. Annotation comes first in the options: an error in the requirements costs more than an error in the steps, because the plan, the tests, and the review all measure themselves against this file. This is the last cheap moment to catch it.

```json
{
  "questions": [{
    "question": "Спека готова. Что дальше?",
    "header": "Next step",
    "options": [
      {"label": "nvim annotate", "description": "/st-plan-annotate <путь спеки> — открою в $EDITOR, правки применю"},
      {"label": "plannotator annotate", "description": "/plannotator-annotate <путь спеки> — аннотации в UI plannotator, отработаю их"},
      {"label": "Писать план", "description": "/st-plan-create на основе спеки, план ляжет рядом как docs/plans/<yyyymmdd>-<slug>.md"},
      {"label": "Имплементировать", "description": "Сразу в код по спеке, без плана"}
    ],
    "multiSelect": false
  }]
}
```

The choice is the approval; run it without a confirmation round:

- **nvim annotate** — invoke `st-plan-annotate` with the spec path, apply the changes, commit, and ask the gate again: edits often open new questions.
- **plannotator annotate** — invoke `plannotator-annotate` with the spec path, work the returned annotations, commit, and ask the gate again.
- **Писать план** — invoke `st-plan-create`, naming the spec path as its input.
- **Имплементировать** — implement straight from the spec. The Testing Decisions list is the test budget: one test per line, nothing added.

A bare "давай" / "ок" is agreement with the last message, not a pick: answer it with the gate.

<spec-template>

## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.

## Testing Decisions

The behaviors that get a test, one line each, named as a behavior rather than a method: `<behavior> — at <seam>`. This list is the plan's test budget: `/st-plan-create` turns each line into exactly one test checkbox and adds none of its own. Also include:

- What deliberately gets no test and why (a case no caller can produce, delegation without logic, library behavior)
- Prior art for the tests (similar tests in the codebase to copy the shape from)

## Out of Scope

A description of the things that are out of scope for this spec.

## Further Notes

Any further notes about the feature.

</spec-template>
