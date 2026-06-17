"""Minimal, dependency-free unified-diff applier for the opt-in apply-fix path.

Applying an LLM-proposed diff to the user's source is deliberately conservative:
it is atomic (the new content is built fully in memory and only then written),
strict (a hunk whose context does not match raises rather than guessing), and it
always writes a ``<file>.husk-bak`` backup first. Applying at all requires an
explicit human confirm at the API layer; this module just does the mechanics.
"""

from __future__ import annotations

import re
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


class PatchError(ValueError):
    """The proposed diff could not be applied cleanly to the source."""


def apply_unified_diff(original: str, diff: str) -> str:
    """Apply a unified diff to ``original`` text and return the new text.

    Strict: raises :class:`PatchError` if a hunk's context/removed lines do not
    match the original at the expected location.
    """
    src = original.splitlines(keepends=False)
    out: list[str] = []
    cursor = 0  # index into src already copied to out
    diff_lines = diff.splitlines()
    i = 0
    applied_any = False

    while i < len(diff_lines):
        line = diff_lines[i]
        m = _HUNK_RE.match(line)
        if not m:
            i += 1
            continue
        applied_any = True
        old_start = int(m.group(1))
        # Unified diffs are 1-based; a 0 start means "before line 1".
        hunk_start = max(old_start - 1, 0)
        if hunk_start < cursor:
            raise PatchError("overlapping or out-of-order hunks")
        # Copy untouched lines up to the hunk.
        out.extend(src[cursor:hunk_start])
        cursor = hunk_start
        i += 1
        # Consume hunk body.
        while i < len(diff_lines) and not _HUNK_RE.match(diff_lines[i]):
            h = diff_lines[i]
            if h.startswith("\\"):  # "\ No newline at end of file"
                i += 1
                continue
            tag, content = (h[0], h[1:]) if h else (" ", "")
            if tag == " ":
                if cursor >= len(src) or src[cursor] != content:
                    raise PatchError(f"context mismatch at source line {cursor + 1}")
                out.append(src[cursor])
                cursor += 1
            elif tag == "-":
                if cursor >= len(src) or src[cursor] != content:
                    raise PatchError(f"removed line does not match at line {cursor + 1}")
                cursor += 1
            elif tag == "+":
                out.append(content)
            else:
                # Unknown prefix — treat as context to be safe.
                if cursor < len(src) and src[cursor] == h:
                    out.append(src[cursor])
                    cursor += 1
            i += 1

    if not applied_any:
        raise PatchError("no @@ hunks found in diff")

    out.extend(src[cursor:])
    trailing_nl = "\n" if original.endswith("\n") else ""
    return "\n".join(out) + trailing_nl


def apply_to_file(path: str, diff: str) -> str:
    """Apply ``diff`` to the file at ``path``, writing a ``.husk-bak`` backup.

    Returns the absolute path written. Raises :class:`PatchError` on any mismatch
    (the file is left untouched in that case).
    """
    p = Path(path)
    original = p.read_text(encoding="utf-8")
    new_text = apply_unified_diff(original, diff)  # may raise before any write
    backup = p.with_suffix(p.suffix + ".husk-bak")
    backup.write_text(original, encoding="utf-8")
    p.write_text(new_text, encoding="utf-8")
    return str(p.resolve())
