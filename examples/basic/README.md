# Basic Example

What it shows: the complete pipeline — discovery, chunking, every lens pass,
merge, and all four report formats — without a single API call or an API key.

`--fake` swaps the Anthropic client for a deterministic offline stub, so this
costs nothing and produces the same output shape a real scan does. Run it first
to see what you would be paying for.

## Run

```sh
./run.sh
```

## Then

```sh
# Price a real run of the same configuration, still without calling anything.
readthrough scan . --estimate-only

# The real thing.
export ANTHROPIC_API_KEY=sk-ant-...
readthrough scan . --out reports/readthrough
```
