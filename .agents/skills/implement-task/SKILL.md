---
name: implement-task
description: Implement a scoped issue or development request in this repository with progressive context loading, minimal changes, and only relevant available validation. Use for code, fixture, infrastructure, or documentation changes; not for review-only requests.
---

# Implement Task

## Context

- Follow the root `AGENTS.md` minimal-context procedure and Source of Truth router.
- Inspect the task or Issue and existing user changes, then locate affected code, nearby tests, and fixtures with `rg` or `rg --files`.
- For a Sub-issue, use its Scope, Acceptance Criteria, and Test / Validation as the implementation boundary. Re-open the Parent Issue only when the Sub-issue is insufficient or the Parent Scope or dependencies changed; do not revalidate the full Parent for each Sub-issue.

## Implement

- Derive the smallest change that satisfies the requested Acceptance Criteria.
- Preserve existing ownership boundaries and `Open Decision` items; do not invent fields, enums, AWS services, or naming.
- For Contract work, identify Producer and Consumer, update `packages/contracts/` with `docs/CONTRACTS.md`, and add or update fixtures and contract tests when those areas exist.
- Add focused tests with behavior changes. Do not perform unrelated refactoring or formatting.
- Use `apply_patch` for file edits and review the resulting diff.

## Validate

- Use the validation locations in root `AGENTS.md` and run only checks relevant to changed paths. Report undefined commands as unavailable.
- Inspect `git diff --check`, the final diff, and `git status`.
- Summarize changed files, validations run, skipped checks with reasons, and remaining decisions.

## Guardrails

- All common guardrails in root `AGENTS.md` apply. Do not modify unrelated files or weaken validation.
- Do not add customer Workload Terraform under `infrastructure/`.
