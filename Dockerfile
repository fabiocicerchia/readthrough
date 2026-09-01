# readthrough as a container, for CI runners that would rather mount a repo than
# install Python packages.
#
#   docker build -t readthrough .
#   docker run --rm -e ANTHROPIC_API_KEY --user "$(id -u):$(id -g)" \
#     -v "$PWD:/src:ro" -v "$PWD/reports:/out" \
#     readthrough scan /src --out /out
#
# The scanned tree is mounted read-only: readthrough only ever reads source. The
# output directory has to be writable — it holds scan.db, which is what makes a
# re-run resume instead of re-spending.
#
# `--user "$(id -u):$(id -g)"` is not optional in practice. The image runs as
# uid 10001, a bind-mounted output directory belongs to whoever created it on
# the host, and without the override the first write fails with EACCES. The
# alternative is chowning the directory to 10001 first, which is why the uid is
# fixed rather than assigned by the distro.

# --- build stage: resolve the wheel, so the runtime image needs no compiler ---
FROM python:3.13-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24 AS build

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY readthrough ./readthrough

RUN python -m pip install --no-cache-dir --upgrade pip build \
    && python -m build --wheel --outdir /dist

# --- runtime stage ---
FROM python:3.13-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24

# OCI labels: what this image is, and where its source lives. The digest above
# is bumped by dependabot's docker ecosystem entry.
LABEL org.opencontainers.image.title="readthrough" \
      org.opencontainers.image.description="Multi-pass LLM code audit with resumable state and coverage accounting" \
      org.opencontainers.image.source="https://github.com/fabiocicerchia/readthrough" \
      org.opencontainers.image.licenses="Apache-2.0"

# Unbuffered so the progress line reaches `docker logs` as it happens rather
# than in one burst at exit.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/*.whl

# Non-root. The uid is fixed so a bind-mounted output directory can be chowned
# to it ahead of time; 10001 is outside the range any distro assigns.
RUN useradd --create-home --uid 10001 app
USER app
WORKDIR /work

# No HEALTHCHECK: this is a batch command, not a service. It runs, writes its
# reports, and exits.
ENTRYPOINT ["readthrough"]
CMD ["--help"]
