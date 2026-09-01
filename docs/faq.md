# FAQ

Short answers to the questions people actually ask.

## What is readthrough?

A multi-pass LLM code audit tool. It runs several independent, narrowly focused
passes over every source file rather than one general "find bugs" prompt, merges
the results, and reports what it actually looked at alongside what it found.

## How do I install it?

See [Getting Started](getting-started.md). One line:

```sh
curl -fsSL https://raw.githubusercontent.com/fabiocicerchia/readthrough/main/install.sh | sh
```

## Can I try it without spending anything?

Yes — that is what `--fake` is for. It swaps the API client for a deterministic
offline stub and exercises the entire pipeline, so you see the full shape of the
output before committing to a real run. `--estimate-only` then prices a real run
without making one.

## Why several passes instead of one good prompt?

An undirected review drifts toward whatever is most obvious in the file. Ask for
"bugs" in a file with an obvious SQL injection and that is what you get back,
every time, while the missing authorization check three functions down goes
unmentioned. A pass that is only allowed to look for authorization problems has
nowhere else to drift.

## Does a clean report mean the code is fine?

No. It means these passes found nothing. LLM review is sampling: more passes
raise recall but never to 100%, the tool cannot execute your code, and it sees
one file at a time. Read the coverage section before the findings section —
that is why the report puts coverage first.

## Should I replace Semgrep or CodeQL with this?

No. Those are deterministic, free, and catch the boring majority. Get them into
CI first. This is for the reasoning-dependent defects a pattern language cannot
express, and it costs money per run — the two are complements.

## What does it cost to run?

Cost scales with `lines × lenses × repeats`. `--estimate-only` prints projected
token counts for a given configuration without calling anything. Run it against
your largest repository before scanning a fleet, and see
[Configuration](configuration.md) for the levers.

## I interrupted a scan. Do I have to start over?

No. State lives in SQLite keyed by file content hash. Re-run the identical
command and it continues from where it stopped, without re-spending on completed
passes. Edit a file and only that file is rescanned.

## Does it send my code to a third party?

Yes — that is what it is. Source is sent to the Anthropic API for review. Do not
point it at a repository whose contents you are not permitted to send to an
external service. `--fake` sends nothing at all.

## How is it licensed?

[Apache 2.0](https://github.com/fabiocicerchia/readthrough/blob/main/LICENSE).

## How do I report a bug or a security issue?

Bugs: open an issue on
[GitHub](https://github.com/fabiocicerchia/readthrough/issues). Security
vulnerabilities: follow the
[Security policy](https://github.com/fabiocicerchia/readthrough/blob/main/SECURITY.md)
— please don't open a public issue.

## How can I contribute?

See
[CONTRIBUTING.md](https://github.com/fabiocicerchia/readthrough/blob/main/CONTRIBUTING.md).
