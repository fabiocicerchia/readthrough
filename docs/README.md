<div class="hero" markdown>

# readthrough

<p class="hero-tagline">Multi-pass LLM code audit with resumable state and explicit coverage accounting.</p>

[Get started](getting-started.md){ .md-button .md-button--primary }
[Architecture](architecture.md){ .md-button }

</div>

Built for the case where you have many repositories and need to know not just
what was found, but what was actually looked at. Every discovered file gets a
recorded status, failed passes are recorded rather than dropped, and the report
names the files they left unreviewed — so a clean report and an empty report
are distinguishable.

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } __Get started__

    ---

    Install it, dry-run the whole pipeline for free, then spend on a real scan.

    [:octicons-arrow-right-24: Getting Started](getting-started.md)

-   :material-target:{ .lg .middle } __Lenses__

    ---

    Seven focused passes instead of one general "find bugs" prompt, and how to
    choose between them.

    [:octicons-arrow-right-24: Usage](usage.md)

-   :material-currency-usd:{ .lg .middle } __Cost control__

    ---

    What drives the bill, which lever to pull first, and how to estimate before
    you spend.

    [:octicons-arrow-right-24: Configuration](configuration.md)

-   :material-sitemap:{ .lg .middle } __Architecture__

    ---

    How discovery, chunking, passes, merge and reporting fit together — and
    what the tool structurally cannot see.

    [:octicons-arrow-right-24: Architecture](architecture.md)

-   :material-book-open-variant:{ .lg .middle } __Examples__

    ---

    A pull-request review workflow you can drop into any repository.

    [:octicons-arrow-right-24: examples/](https://github.com/fabiocicerchia/readthrough/tree/main/examples)

-   :material-shield-check:{ .lg .middle } __Security__

    ---

    How to report a vulnerability and what's in scope.

    [:octicons-arrow-right-24: Security policy](https://github.com/fabiocicerchia/readthrough/blob/main/SECURITY.md)

</div>
