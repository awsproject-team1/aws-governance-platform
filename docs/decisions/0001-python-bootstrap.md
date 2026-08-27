# Python Bootstrap Toolchain

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #10](https://github.com/awsproject-team1/aws-governance-platform/issues/10)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The repository defines Python linting and testing requirements but does not yet define a Python version, dependency installation method, test runner, executable validation commands, or CI workflow. Product APIs, domain contracts, frontend tooling, and AWS resources are still open decisions and must not be inferred from a tooling bootstrap.

## Decision

- Use Python 3.14 for the initial Python toolchain. It matches the approved local environment and is an AWS Lambda supported runtime.
- Use standard `pip` with exact direct dependency pins in `requirements-dev.txt` for the initial bootstrap.
- Use the standard-library `unittest` runner until a test framework requiring third-party dependencies is justified.
- Use Ruff for Python linting and formatting, configured in the root `pyproject.toml`.
- Run Python lint, format checking, and unit tests in a path-filtered GitHub Actions workflow.
- Run Gitleaks CLI 8.30.1 for every pull request targeting `dev` or `main`; verify the downloaded Linux archive against its published SHA-256 checksum before execution.
- On pull requests, scan every commit introduced by the exact base-to-head range so unrelated remote branches cannot contaminate the result. Keep `workflow_dispatch` as an explicit full-history audit.
- Pin Python packages to exact versions, GitHub Actions to immutable commit SHAs, and downloaded CI tools by version and checksum.

## Consequences

- Local development and CI require Python 3.14.
- The first validation path has one external Python development dependency: Ruff.
- This decision establishes repository tooling only. It does not select a backend framework, domain schema library, frontend package manager, LangGraph runtime, AWS resource, or public API endpoint.
- Application dependencies and a transitive lock strategy must be reconsidered when the first executable application slice is approved.
- The secret-scan workflow downloads the pinned Gitleaks CLI release from GitHub and rejects the archive if its SHA-256 checksum differs from the accepted value.

## Alternatives considered

- **Python 3.13:** Supported by AWS Lambda, but it would differ from the already approved local Python 3.14 environment.
- **uv, Poetry, or pip-tools:** Deferred because the repository does not yet need a multi-package lock strategy.
- **pytest:** Deferred because the initial import smoke test does not require a third-party test framework.
- **Frontend and Python bootstrap together:** Rejected to avoid fixing unrelated Node, bundler, and frontend test decisions in the same change.

## References

- [AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
- [Repository agent guide](../../AGENTS.md)
- [Contributing guide](../../CONTRIBUTING.md)
