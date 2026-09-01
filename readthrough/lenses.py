"""Analytical lenses. Each lens is one focused pass over a chunk of code.

Multiple *different* lenses beat multiple identical passes: an undirected
"find bugs" prompt drifts toward whatever is most salient in the file and
misses whole categories. Narrow scope per pass, union the results.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Lens:
    id: str
    title: str
    focus: str
    categories: tuple = field(default=())


LENSES = {
    "injection": Lens(
        id="injection",
        title="Untrusted input and injection",
        focus="""Trace every value that could originate outside this process
(HTTP request bodies/params/headers, CLI args, environment, files, message
queues, database rows written by users, third-party API responses) and follow
it to every sink where it is interpreted rather than merely stored.

Sinks to check: SQL/ORM raw fragments, shell and subprocess invocation, file
paths, template rendering, HTML/JS output, deserialization (pickle, YAML load,
Java/PHP unserialize), XML parsers with entity resolution, regex compiled from
input, redirect targets, outbound URLs (SSRF), LDAP/NoSQL query construction,
eval-like constructs, log statements that are later parsed.

For each, state whether validation or escaping happens on EVERY path to the
sink, not just the common one.""",
        categories=(
            "sql-injection", "command-injection", "path-traversal", "ssrf",
            "xss", "deserialization", "template-injection", "xxe",
            "open-redirect", "log-injection", "missing-input-validation",
        ),
    ),
    "authz": Lens(
        id="authz",
        title="Authentication, authorization and tenancy",
        focus="""For every entry point (route, handler, RPC method, exported
function reachable from a request, background job consuming user-supplied ids):

- Is the caller authenticated, and is that enforced here or only assumed from
  a middleware that may not cover this path?
- Is the caller authorized for THIS specific object, not merely logged in?
  Object ids taken from the request and used without an ownership check are
  IDOR.
- In multi-tenant code: is the tenant/org id derived from the session, or
  accepted from the client? Does every query filter on it?
- Are privileged operations distinguishable from unprivileged ones, and is the
  check on the server side of the trust boundary?
- Session and token handling: fixation, missing expiry, missing revocation,
  tokens in URLs, unsafe cookie flags, JWT verified with the right algorithm
  and key.

Also flag mass-assignment: request payloads bound directly to models where a
client could set a role, owner, price, or status field.""",
        categories=(
            "missing-authn", "missing-authz", "idor", "tenancy-leak",
            "privilege-escalation", "mass-assignment", "session-handling",
            "csrf",
        ),
    ),
    "secrets": Lens(
        id="secrets",
        title="Secrets, crypto and configuration",
        focus="""Look for hardcoded credentials, API keys, tokens, private keys
and connection strings, including ones that look like test or placeholder
values. Look for secrets that reach logs, error messages, stack traces,
analytics payloads, or client-side bundles.

Crypto: home-rolled primitives, ECB mode, static or reused IVs/nonces, weak
hashes for passwords (any unsalted digest, or a fast hash instead of
bcrypt/scrypt/argon2), non-constant-time comparison of secrets, predictable
randomness from a non-CSPRNG used for tokens/ids/resets, disabled certificate
verification, and downgraded TLS.

Configuration: debug modes, permissive CORS (reflected origin, wildcard with
credentials), disabled auth in a code path guarded only by an env flag,
overly broad file permissions, default credentials.""",
        categories=(
            "hardcoded-secret", "secret-in-logs", "weak-crypto",
            "weak-randomness", "cert-validation-disabled", "insecure-config",
            "permissive-cors",
        ),
    ),
    "logic": Lens(
        id="logic",
        title="Invariants and business logic",
        focus="""Do not look for style problems. Look for places where the code
does something other than what it evidently intends.

Work out the invariants this code assumes: what must be true on entry, what it
guarantees on exit, what ordering it depends on, what ranges values must fall
in. Then find inputs or call orders that violate them.

Specifically: off-by-one and boundary handling; inverted or short-circuited
conditionals; loops that skip the last element or never terminate; state
machines that permit an illegal transition; arithmetic that can overflow,
underflow, or lose precision (especially money — flag float arithmetic on
currency); unit and timezone confusion; comparisons between values of
different types; early returns that skip required cleanup or a required
audit/log write; duplicated logic that has drifted between copies; retry or
idempotency logic that can double-apply an effect.""",
        categories=(
            "off-by-one", "inverted-condition", "invariant-violation",
            "state-machine-bug", "arithmetic-overflow", "precision-loss",
            "unit-confusion", "non-idempotent-retry", "unreachable-code",
            "logic-error",
        ),
    ),
    "errors": Lens(
        id="errors",
        title="Error handling, resources and failure modes",
        focus="""Assume every external call fails, hangs, or returns something
unexpected. Then check this code's behaviour.

Find: swallowed exceptions (bare except/catch that continues as if success);
return values and error codes that are never checked; errors caught and logged
but the caller proceeds with a null/partial value; resources (files, sockets,
locks, cursors, transactions) not released on the error path; missing timeouts
on network and subprocess calls; unbounded retries or retries without backoff;
partial writes that leave state inconsistent because there is no transaction
or compensating action; error messages that leak internals to the caller;
null/None/undefined dereferences on paths that only occur when something
upstream failed; and cleanup that assumes setup succeeded.""",
        categories=(
            "swallowed-error", "unchecked-return", "resource-leak",
            "missing-timeout", "unbounded-retry", "partial-failure",
            "null-dereference", "info-leak-in-error",
        ),
    ),
    "concurrency": Lens(
        id="concurrency",
        title="Concurrency and shared state",
        focus="""Identify state shared across requests, threads, goroutines,
tasks, or processes: module-level mutables, caches, singletons, connection
pools, class attributes, closures captured by handlers, files and database
rows.

Then find: check-then-act races (TOCTOU) on files, database rows, and cache
entries; read-modify-write sequences without a transaction, lock, or atomic
operation; lock ordering that can deadlock; locks held across I/O; async code
that awaits while holding an invariant broken; missing idempotency on handlers
that can be delivered twice; and assumptions that a single instance of the
process is running.""",
        categories=(
            "race-condition", "toctou", "deadlock", "shared-mutable-state",
            "non-atomic-update", "lock-held-across-io",
        ),
    ),
    "data": Lens(
        id="data",
        title="Data handling, boundaries and types",
        focus="""Focus on what happens at the edges of this code: parsing,
serialization, encoding, and type conversion.

Find: parsing without size or depth limits (zip bombs, deeply nested JSON,
unbounded reads into memory); encoding mismatches and unicode normalization
issues that break comparisons or filters; implicit type coercion that changes
meaning; nullable values treated as non-null; collections indexed without a
bounds check; pagination that can be driven to return everything; queries
without a limit; N+1 query patterns and unbounded loops over external results;
and data written in one format and read in another.""",
        categories=(
            "unbounded-input", "encoding-issue", "type-confusion",
            "missing-bounds-check", "unbounded-query", "n-plus-one",
            "schema-mismatch",
        ),
    ),
}

DEFAULT_LENSES = ["injection", "authz", "logic", "errors"]

SEVERITIES = ["critical", "high", "medium", "low"]
CONFIDENCES = ["high", "medium", "low"]

SYSTEM_PROMPT = """You are a senior application security engineer and systems \
programmer performing a focused audit. You are reviewing one file (or one \
section of one file) at a time.

Rules you follow without exception:

1. Report only defects you can point at. Every finding must name a specific \
line range in the code shown and describe a concrete sequence of events that \
produces the bad outcome. If you cannot describe how it goes wrong, it is not \
a finding.
2. Do not report style, naming, formatting, missing docstrings, or "consider \
refactoring" observations. A linter covers those. You are looking for defects \
that change behaviour or expose the system.
3. Do not speculate about code you cannot see. If a call to an unseen function \
might be safe or unsafe, only report it if the surrounding code would be \
wrong under any reasonable implementation, and say explicitly what you are \
assuming.
4. Prefer a small number of real findings to a long list of maybes. Returning \
an empty findings list is a correct and expected answer for most files.
5. Severity reflects impact if exploited or triggered, not how interesting the \
bug is. Confidence reflects how certain you are given only the code shown.

You reply with JSON only. No prose, no markdown fences, no commentary."""

USER_TEMPLATE = """# Audit pass: {lens_title}

## What to look for in this pass

{lens_focus}

Stay inside this pass. If you notice a defect belonging to a different \
category, ignore it; another pass covers it.

## File under review

Path: `{path}`
Language: {lang}
{chunk_note}

Line numbers below are the real line numbers in the file. Use them exactly.

```
{code}
```
{context_note}
## Required output

Return a single JSON object, nothing else:

{{
  "findings": [
    {{
      "title": "short specific description, under 90 chars",
      "category": "one of: {categories}",
      "severity": "critical | high | medium | low",
      "confidence": "high | medium | low",
      "start_line": <int>,
      "end_line": <int>,
      "symbol": "enclosing function/method/class name, or null",
      "explanation": "what is wrong and why, referring to the actual identifiers in the code",
      "trigger": "the concrete sequence of events or the input that causes it",
      "assumptions": "what you are assuming about code not shown, or null",
      "suggested_fix": "specific change, not generic advice",
      "suggested_test": "a test that fails before the fix and passes after"
    }}
  ]
}}

If you find nothing in this pass, return {{"findings": []}}."""

VERIFY_SYSTEM = """You are reviewing a claimed defect found by an earlier \
automated pass. Your job is to determine whether it is real, not to be polite \
about it. Many claimed findings are wrong: the guard exists elsewhere in the \
shown code, the input is not actually attacker-controlled, the framework \
handles it, or the described sequence cannot occur.

Judge only from the code shown. Reply with JSON only."""

VERIFY_TEMPLATE = """## Claimed finding

File: `{path}` lines {start_line}-{end_line}
Category: {category}
Severity claimed: {severity}
Title: {title}

Explanation given:
{explanation}

Trigger given:
{trigger}

## Code

```
{code}
```

## Your task

Decide whether this defect is real in the code as shown.

Return a single JSON object, nothing else:

{{
  "verdict": "confirmed | rejected | uncertain",
  "reasoning": "why, citing specific lines",
  "corrected_severity": "critical | high | medium | low",
  "corrected_lines": [<start>, <end>]
}}

Use "rejected" when the code shown already prevents the described outcome, or \
the described sequence cannot occur. Use "uncertain" only when the answer \
genuinely depends on code not shown, and say which."""
