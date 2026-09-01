# Deployment

readthrough is a CLI, not a service. "Deploying" it means wiring it into CI where
its output reaches someone who can act on it.

## Prerequisites

- `ANTHROPIC_API_KEY` stored as a repository or organization secret.
- `security-events: write` permission on the job, to upload SARIF.
- GitHub code scanning available on the repository (public repos, or private
  repos with GitHub Advanced Security). Without it, drop the SARIF step and
  keep the job summary.

## Per-pull-request review

The highest-value placement, by a distance: scope is small, cost is bounded by
the diff, and the author still has the code in their head.

```sh
cp examples/github-actions/readthrough-pr-review.yml \
   ../your-repo/.github/workflows/
```

The workflow stages only the files changed in the pull request, scans that
subset, uploads SARIF so findings appear as inline annotations, and writes
`report.md` to the job summary. It is advisory by default; the last step in the
file shows how to make critical findings block the merge.

## Scheduled fleet audit

For a periodic sweep across many repositories, run `readthrough multi` on a
schedule and publish the rollup:

```sh
readthrough multi ~/src --out reports/ \
  --lenses injection,authz,logic,errors --workers 8
```

`rollup.md` ranks every repository by severity count, with the top findings for
each. Treat it as a work queue, not a score.

## Cost at deployment scale

The per-PR workflow is bounded by the diff, which is what makes it affordable
to leave on. A scheduled full-tree scan is bounded by the tree, which is not —
tier your repositories first and use `--estimate-only` to price a configuration
before scheduling it. See [Configuration](configuration.md).

## Container image

`.github/workflows/docker-build.yml` publishes to
`ghcr.io/fabiocicerchia/readthrough` on pushes to the default branch and on tags.
Pull requests build the image without publishing, so a broken Dockerfile fails
the PR rather than the release.

Until a tag has been pushed, build locally rather than pulling something that
does not exist yet:

```sh
make build          # docker build -t readthrough:dev .

docker run --rm -e ANTHROPIC_API_KEY --user "$(id -u):$(id -g)" \
  -v "$PWD:/src:ro" -v "$PWD/reports:/out" \
  readthrough:dev scan /src --out /out
```

Two details that will bite otherwise:

- **`--user "$(id -u):$(id -g)"`.** The image runs as uid 10001. A bind-mounted
  output directory belongs to whoever created it on the host, so without the
  override the first write fails with `EACCES`. The alternative is chowning the
  directory to 10001 up front — which is why the uid is fixed rather than
  assigned by the distro.
- **The output mount must be writable.** It holds `scan.db`, and that file is
  the whole of resume. Mount the source `:ro` and the output read-write.

For CI, installing the package is usually simpler than pulling the image — it
is a `pip install` and a few seconds:

```sh
pip install 'git+https://github.com/fabiocicerchia/readthrough.git@v1.0.0'
```

## Configuration

Deployment-time settings and secrets are covered in
[Configuration](configuration.md). Never bake the API key into an image or a
committed values file — pass it as a secret at run time.

## Rollback

Pin the workflow to a tag rather than `main`:

```sh
pip install 'git+https://github.com/fabiocicerchia/readthrough.git@v1.0.0'
```

Reverting is then a one-line change to the pinned ref. Scan state in `scan.db`
is forward-compatible within a major version; if a schema change ever breaks
it, delete the file and re-scan.
