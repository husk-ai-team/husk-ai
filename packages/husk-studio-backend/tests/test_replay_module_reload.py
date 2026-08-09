"""The replay module cache must follow the file on disk.

Caching by path alone pinned the first version of an agent for the life of the
backend process. That silently broke the product's core loop: the debugger writes
a proposed fix into the agent's source (`apply-fix`), you replay to check it, and
the replay re-executed the *pre-fix* module and reported the old behaviour.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from husk_studio_backend.replay import graph_replay
from husk_studio_backend.replay.graph_replay import GraphModuleNotAllowed


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    graph_replay._module_cache.clear()


def _write(path: Path, version: str) -> None:
    path.write_text(f"VERSION = {version!r}\n")
    # Guarantee a distinct mtime even on filesystems with coarse timestamps.
    stamp = time.time() + 1
    os.utime(path, (stamp, stamp))


def test_editing_the_agent_source_invalidates_the_cached_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUSK_ALLOWED_GRAPH_DIRS", str(tmp_path))
    agent = tmp_path / "agent.py"

    _write(agent, "BEFORE FIX")
    assert graph_replay._load_module(str(agent)).VERSION == "BEFORE FIX"

    _write(agent, "AFTER FIX")  # as `apply-fix` would
    assert graph_replay._load_module(str(agent)).VERSION == "AFTER FIX"


def test_unchanged_file_is_served_from_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cache still has to work — reloading on every replay would be slow and
    would discard module state between a resume and its own successors."""
    monkeypatch.setenv("HUSK_ALLOWED_GRAPH_DIRS", str(tmp_path))
    agent = tmp_path / "agent.py"
    _write(agent, "v1")

    first = graph_replay._load_module(str(agent))
    assert graph_replay._load_module(str(agent)) is first


def test_cache_does_not_grow_when_a_file_is_reloaded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HUSK_ALLOWED_GRAPH_DIRS", str(tmp_path))
    agent = tmp_path / "agent.py"
    for i in range(5):
        _write(agent, f"v{i}")
        graph_replay._load_module(str(agent))
    assert len(graph_replay._module_cache) == 1


def test_module_outside_the_allowed_roots_is_still_refused(tmp_path: Path) -> None:
    """The mtime check must not have widened the import gate."""
    outside = tmp_path / "elsewhere.py"
    _write(outside, "x")
    with pytest.raises(GraphModuleNotAllowed):
        graph_replay._load_module(str(outside))
