---
name: pr-validation
description: Review a local change or PR candidate in this repository, run only available path-relevant checks, and report readiness or blockers. Use for diff review, CI readiness, or PR preparation; not to implement unrelated fixes unless requested.
---

# PR Validation

## Inspect

1. Refresh volatile facts: current branch, `git status`, intended base, and the diff against that base. Do not assume `main` is the base.
2. Classify changed paths and read the relevant `CONTRIBUTING.md` section first.
3. Use the root `AGENTS.md` router to open a product or technical Source of Truth only when the diff requires semantic review.

## Validate

- Use the validation locations in root `AGENTS.md` and the changed-path categories in `CONTRIBUTING.md`. Run only checks the repository actually defines.
- Always inspect `git diff --check`, the final diff, and `git status`.
- For Skill changes, validate each changed Skill with the available Codex Skill validator when present.

## Review

- For a Sub-issue PR, check that Sub-issue's Scope, Acceptance Criteria, and Test / Validation rather than the full Parent completion criteria. Re-open the Parent earlier only when the Sub-issue is insufficient or the Parent Scope or dependencies changed.
- Check the Parent's full Acceptance Criteria and deliverables only at Parent closure after all of its Sub-issues are complete.
- Check unintended changes, ownership boundaries, backward compatibility, required fixtures/tests, and documentation synchronization.
- Confirm the PR path, base/head, related Issue, validation evidence, and Architecture/Contract/Security impact against `CONTRIBUTING.md`.
- Treat missing required CI, review, unresolved secrets, or validation failures as blockers. Root `AGENTS.md` guardrails remain mandatory.

## Output

Report findings in severity order with file references, then list commands and results, unavailable checks, and the final readiness decision. Do not fix findings unless the user also asks for implementation.
