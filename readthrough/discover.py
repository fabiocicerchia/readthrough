"""Repository walking, filtering and chunking.

Every file discovered gets a recorded status. A file is never silently
dropped -- if it is skipped, the reason lands in the coverage report.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

LANG_BY_EXT = {
    ".py": "Python", ".pyi": "Python",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP",
    ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin", ".scala": "Scala",
    ".cs": "C#", ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++",
    ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C++",
    ".ex": "Elixir", ".exs": "Elixir", ".erl": "Erlang",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".pl": "Perl", ".lua": "Lua", ".dart": "Dart",
    ".tf": "Terraform", ".hcl": "HCL",
    ".yml": "YAML", ".yaml": "YAML",
    ".vue": "Vue", ".svelte": "Svelte",
    ".gradle": "Gradle", ".groovy": "Groovy",
}

# Directories that are never source under review.
IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv",
    "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", "target", "out", "bin", "obj", ".next", ".nuxt",
    "coverage", ".terraform", ".gradle", ".idea", ".vscode", "site-packages",
    "bower_components", ".tox", ".eggs", "migrations",
}

IGNORE_NAME_PARTS = (
    ".min.js", ".min.css", ".bundle.js", ".map", "-lock.json",
    ".pb.go", "_pb2.py", ".generated.", ".g.dart", ".d.ts",
)


@dataclass
class FileInfo:
    path: str          # absolute
    rel: str           # relative to repo root
    sha256: str
    lang: str
    loc: int
    size: int
    status: str        # "pending" | "skipped"
    note: str = ""


@dataclass
class Chunk:
    rel: str
    sha256: str
    chunk_idx: int
    n_chunks: int
    start_line: int    # 1-based inclusive
    end_line: int      # 1-based inclusive
    lang: str
    numbered: str      # code with line-number prefixes


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_probably_binary(data: bytes) -> bool:
    if b"\x00" in data[:8192]:
        return True
    if not data:
        return False
    sample = data[:8192]
    printable = sum(1 for b in sample if 9 <= b <= 13 or 32 <= b <= 126 or b >= 128)
    return printable / len(sample) < 0.85


def _git_tracked(root: Path) -> list[str] | None:
    """Use git's index when available -- it already honours .gitignore."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            capture_output=True, timeout=60,
        )
        if out.returncode != 0:
            return None
        return [p for p in out.stdout.decode("utf-8", "replace").split("\0") if p]
    except (OSError, subprocess.SubprocessError):
        return None


def _walk(root: Path) -> list[str]:
    rels = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS
                       and not d.startswith(".")]
        for fn in filenames:
            full = Path(dirpath) / fn
            rels.append(str(full.relative_to(root)))
    return rels


def discover_files(
    root: Path,
    max_bytes: int = 400_000,
    include_exts: set[str] | None = None,
    exclude_globs: tuple[str, ...] = (),
    min_loc: int = 3,
) -> list[FileInfo]:
    """Return every candidate file with an explicit status.

    Skipped files are returned too, with the reason in `note`, so the report
    can account for the whole tree rather than only what was scanned.
    """
    root = root.resolve()
    rels = _git_tracked(root)
    if rels is None:
        rels = _walk(root)

    results: list[FileInfo] = []
    seen: set[str] = set()

    for rel in sorted(rels):
        if rel in seen:
            continue
        seen.add(rel)

        full = root / rel
        parts = Path(rel).parts
        if any(p in IGNORE_DIRS for p in parts):
            continue
        if any(marker in rel for marker in IGNORE_NAME_PARTS):
            continue
        if any(Path(rel).match(g) for g in exclude_globs):
            continue

        ext = full.suffix.lower()
        if include_exts is not None:
            if ext not in include_exts:
                continue
        elif ext not in LANG_BY_EXT:
            continue

        try:
            if not full.is_file() or full.is_symlink():
                continue
            size = full.stat().st_size
            data = full.read_bytes()
        except OSError as exc:
            results.append(FileInfo(str(full), rel, "", LANG_BY_EXT.get(ext, "?"),
                                    0, 0, "skipped", f"unreadable: {exc}"))
            continue

        lang = LANG_BY_EXT.get(ext, ext.lstrip(".") or "text")
        digest = _sha256_bytes(data)

        if _is_probably_binary(data):
            results.append(FileInfo(str(full), rel, digest, lang, 0, size,
                                    "skipped", "binary"))
            continue
        if size > max_bytes:
            results.append(FileInfo(str(full), rel, digest, lang, 0, size,
                                    "skipped",
                                    f"exceeds --max-file-bytes ({size} > {max_bytes})"))
            continue

        text = data.decode("utf-8", "replace")
        loc = text.count("\n") + 1
        if loc < min_loc:
            results.append(FileInfo(str(full), rel, digest, lang, loc, size,
                                    "skipped", "too short to review"))
            continue

        results.append(FileInfo(str(full), rel, digest, lang, loc, size, "pending"))

    return results


def chunk_file(info: FileInfo, chunk_lines: int = 350,
               overlap: int = 60) -> list[Chunk]:
    """Split into overlapping windows carrying true line numbers.

    Overlap matters: a defect straddling a boundary would otherwise be
    invisible to both windows. The dedupe step collapses the duplicates it
    creates.
    """
    try:
        text = Path(info.path).read_text("utf-8", errors="replace")
    except OSError:
        return []

    lines = text.splitlines()
    if not lines:
        return []

    if len(lines) <= chunk_lines:
        spans = [(0, len(lines))]
    else:
        spans = []
        step = max(1, chunk_lines - overlap)
        start = 0
        while start < len(lines):
            end = min(start + chunk_lines, len(lines))
            spans.append((start, end))
            if end == len(lines):
                break
            start += step

    width = len(str(len(lines)))
    chunks = []
    for idx, (s, e) in enumerate(spans):
        body = "\n".join(f"{i + 1:>{width}}| {lines[i]}" for i in range(s, e))
        chunks.append(Chunk(
            rel=info.rel, sha256=info.sha256, chunk_idx=idx,
            n_chunks=len(spans), start_line=s + 1, end_line=e,
            lang=info.lang, numbered=body,
        ))
    return chunks


def read_span(path: str, start: int, end: int, pad: int = 25) -> str:
    """Numbered source around a line range, for the verification pass."""
    try:
        lines = Path(path).read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    s = max(0, start - 1 - pad)
    e = min(len(lines), end + pad)
    width = len(str(len(lines)))
    return "\n".join(f"{i + 1:>{width}}| {lines[i]}" for i in range(s, e))
