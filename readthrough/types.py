"""The shapes this package passes between its modules.

They are dicts rather than dataclasses on purpose: a finding is written by a
model, stored as a sqlite row, merged with other findings, rendered into four
report formats and read back by `readthrough verify`. Every one of those steps
adds a key, and a class that has to be widened at each of them would describe
the pipeline less honestly than a dict does.

The aliases exist so a reader (and the type checker) can tell which dict is
which at a signature, which a bare `dict` cannot say.
"""

from typing import Any

# One finding: as a model returned it, as sqlite stored it, or as merge.py
# collapsed it -- the same bag of keys, growing as it moves down the pipeline.
Finding = dict[str, Any]
# The whole run's results, as report.py assembles them for rendering.
Results = dict[str, Any]
# One decoded JSON object from a model's reply, before anything validates it.
Json = dict[str, Any]
