"""The opt-in unified-diff applier: applies clean hunks, refuses mismatches."""

from __future__ import annotations

from pathlib import Path

import pytest

from husk_studio_backend.debugger.patcher import (
    PatchError,
    apply_to_file,
    apply_unified_diff,
)

_ORIGINAL = "line1\nline2\nline3\n"
_DIFF = """\
--- a/x.py
+++ b/x.py
@@ -1,3 +1,3 @@
 line1
-line2
+line2-fixed
 line3
"""


def test_apply_clean_diff() -> None:
    out = apply_unified_diff(_ORIGINAL, _DIFF)
    assert out == "line1\nline2-fixed\nline3\n"


def test_context_mismatch_raises() -> None:
    with pytest.raises(PatchError):
        apply_unified_diff("totally\ndifferent\ncontent\n", _DIFF)


def test_no_hunks_raises() -> None:
    with pytest.raises(PatchError):
        apply_unified_diff(_ORIGINAL, "no hunks here")


def test_apply_to_file_writes_backup_and_is_atomic_on_failure(tmp_path: Path) -> None:
    f = tmp_path / "x.py"
    f.write_text(_ORIGINAL, encoding="utf-8")

    written = apply_to_file(str(f), _DIFF)
    assert Path(written).read_text(encoding="utf-8") == "line1\nline2-fixed\nline3\n"
    assert (tmp_path / "x.py.husk-bak").read_text(encoding="utf-8") == _ORIGINAL

    # A non-applying diff leaves the file untouched (no partial write).
    f.write_text(_ORIGINAL, encoding="utf-8")
    with pytest.raises(PatchError):
        apply_to_file(str(f), "@@ -1,1 +1,1 @@\n-nope\n+x\n")
    assert f.read_text(encoding="utf-8") == _ORIGINAL
