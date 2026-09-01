# CLAUDE.md

Guidance for Claude Code (and other AI agents) working in this repo.

## Project

`readthrough` is a Python 3.10+ CLI that audits a codebase by running several
narrowly focused LLM passes over every file and merging the results. Entry
point: `readthrough/cli.py:main`, exposed as the `readthrough` console script and as
`python -m readthrough`. Eight modules, one SQLite state file, no server.

`discover` → `chunk` → `engine` (one call per lens per chunk) → `store` →
`merge` → `verify` → `report`. See `docs/architecture.md`.

## Commands

```sh
make help      # Show this help
make setup     # Editable install with dev extras + the pre-commit hook
make lint      # Run all pre-commit checks on the whole tree
make test      # pytest
make build     # Container image (override IMAGE=, TAG=)
make dist      # Wheel + sdist into dist/
make install   # Put this working tree on your PATH (pipx, else pip --user)
make selfscan  # Audit this repo with itself, offline and free
make clean     # Remove build, cache and scan output
```

## The rules that are not style preferences

- **Nothing may be silently dropped.** Every discovered file gets a recorded
  status; every failed pass is a row with an error, never an absence. A clean
  report and an empty report must stay distinguishable. Any change that can
  make work disappear without a trace is wrong, however tidy it looks.
- **`--fake` must exercise the whole pipeline.** It is how the tests run and how
  a user evaluates the tool for free. If a code path only runs against the real
  API, it is untested.
- **Findings never set the exit code.** Whether a finding fails a build is
  policy and belongs to the caller.
- **`Store` is per-thread connections plus a write lock.** Do not consolidate
  back to one shared connection: the worker pool reads and writes concurrently,
  and a read inside another thread's transaction is the `bad parameter or other
  API misuse` crash that shape already caused once.
- **Claim only what the tool can back.** The README's "what this does not do"
  section is load-bearing, not modesty. Keep it accurate.

## Tooling

- `make setup` installs the pre-commit hook, and that is the whole of it.
  Don't add a `.githooks/` directory: `core.hooksPath` replaces `.git/hooks/`
  wholesale, so setting it silently stops every pre-commit hook from running.
- Hooks are pinned by commit SHA with the tag in a trailing comment. A tag can
  be moved, a SHA cannot.
- CI runs this same `.pre-commit-config.yaml` through `pre-commit/action`, so
  what passes locally is what gates the pull request.
- `ruff-format` is deliberately off. The tree is not ruff-formatted and
  reformatting it is not a lint change.

## Conventions

- Match existing style; don't reformat unrelated code.
- Conventional Commits for messages (see CONTRIBUTING.md).
- Update `docs/`, `examples/` and the `## [Unreleased]` section of the
  changelog with behavior changes.
- Never commit secrets; CI runs gitleaks. `ANTHROPIC_API_KEY` comes from the
  environment — there is no dotenv loading, so don't document a `.env` file.

## Guardrails

- Don't add dependencies without a clear reason; prefer stdlib. The only
  runtime dependency is the `anthropic` SDK, and it should stay that way.
- Don't touch generated files or lockfiles by hand.
- Ask before large refactors or destructive operations.
