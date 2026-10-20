# Contributing to Soundline

Thank you for your interest! Soundline is built **test-first, spec-first and eval-first**. This guide explains what that means for your contribution.

## Before you start

1. Read the [specification index](docs/spec/README.md) and the [testing strategy](docs/spec/11-testing-strategy.md).
2. For anything beyond a small fix, **open an issue first** to discuss the behavior change and which spec IDs it touches.
3. Look for issues labeled `good first issue`. Each one references the spec behaviors involved.

## The workflow

```
spec change (if behavior changes)
   └─► failing acceptance test referencing the spec ID       (red)
        └─► inner loop: unit test → code → refactor           (red → green → refactor)
             └─► acceptance test passes                        (green)
                  └─► evaluation comparison (if quality-related)
```

### Rules

- **No production code without a failing test that requires it.** Reviewers will ask which test drove a given line.
- **Behavior changes update the spec** in the same pull request. New behaviors get new IDs. IDs are never reused.
- **Refactorings are separate commits** from behavior changes, and change no tests except renames.
- **Quality claims need numbers.** If your change aims to improve retrieval or answers, include the `soundline eval compare` output in the PR description.
- **Structural decisions need an ADR** ([template](docs/adr/README.md)).
- **Fakes over mocks.** If you need a new port, it comes with a fake and a contract suite.

## Development setup

```bash
git clone https://github.com/soundline-dev/soundline && cd soundline
uv sync
uv run pytest                 # default suite: offline, < 60 s
uv run pyright
uv run ruff check && uv run ruff format --check
uv run lint-imports           # architecture rules
uv run python scripts/spec_coverage.py
```

## Commits and pull requests

- [Conventional Commits](https://www.conventionalcommits.org/): `feat(retrieval): add per-document hit cap (RET-063)`.
- Sign off your commits (`git commit -s`) to certify the [Developer Certificate of Origin](https://developercertificate.org/).
- Every commit on `main` is green. Keep PRs small and focused, with one behavior or one refactoring.
- The PR template asks for: spec IDs, the red test, evaluation impact (if any), documentation updates.

## Documentation

Documentation follows the [Diátaxis](https://diataxis.fr/) framework: tutorials, how-to guides, reference, explanation. A user-visible change is not done until it is documented.

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md) (Contributor Covenant 2.1).

## Security

Please do not report vulnerabilities in public issues. See [SECURITY.md](SECURITY.md) for private reporting.
