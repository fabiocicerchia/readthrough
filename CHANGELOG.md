# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases are cut by release-please from Conventional Commit messages — don't
edit the released sections by hand.

## [Unreleased]

### Added
- Container image: multi-stage `Dockerfile` (digest-pinned base, non-root uid
  10001, wheel built in the build stage so the runtime image carries no
  compiler), `.dockerignore`, `.hadolint.yaml`, and a `docker-build` workflow
  publishing to `ghcr.io/fabiocicerchia/readthrough`.
- Apache 2.0 licensing (`LICENSE`), contribution and security policy, code of
  conduct, issue and pull-request templates.
- One-line installer (`install.sh`) and a packaged console entry point.
- MkDocs Material documentation site (`docs/`, `mkdocs.yml`) plus a standalone
  GitHub Pages landing page, published by `.github/workflows/docs.yml`.
- CI, CodeQL, code-quality, security, dependency-review, SBOM, Sigstore
  signing, OpenSSF Scorecard, carbon-badge and release-please workflows.
- `tests/test_smoke.py`: an end-to-end run of the pipeline against `--fake`,
  covering report generation, coverage accounting, SARIF validity and resume.
- `make selfscan` audits this repo with itself, offline and free.

### Fixed
- Concurrent passes crashed with `sqlite3.InterfaceError: bad parameter or
  other API misuse`. `Store` shared one connection across the worker pool while
  only the writers took the lock, so a worker's read could land inside another
  worker's open transaction. Each thread now gets its own connection, and
  explicit transaction control no longer fights the driver's implicit one.
- `readthrough.report` imported `SEV_RANK` without using it.

[Unreleased]: https://github.com/fabiocicerchia/readthrough/commits/main
