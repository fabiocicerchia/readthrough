# Contributing

Thanks for wanting to help. The full, authoritative guide lives at the repo root
in [CONTRIBUTING.md](https://github.com/fabiocicerchia/readthrough/blob/main/CONTRIBUTING.md).

## The short version

1. Fork and clone the repo.
2. Install the pre-commit hook: `make setup`.
3. Branch: `git checkout -b feat/short-description`.
4. Make your change; keep it focused (one logical change per PR).
5. Update `docs/`, `examples/` and the `## [Unreleased]` section of the
   changelog when behavior changes.
6. Run the checks locally: `make lint`.
7. Open a pull request.

By participating you agree to the
[Code of Conduct](https://github.com/fabiocicerchia/readthrough/blob/main/CODE_OF_CONDUCT.md).

!!! note
    `CHANGELOG.md` is generated from commit messages by release-please — don't
    edit it by hand except for the `## [Unreleased]` section.
