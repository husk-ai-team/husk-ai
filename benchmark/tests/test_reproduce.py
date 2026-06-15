"""The published hero numbers must reproduce offline from the committed fixture.

This guards Phase 2 of the hardening: a fresh clone (no API key, no network)
must be able to regenerate D1-D5 and get the figures in `hero_metrics.json`.
It goes red if the fixture, the metric pipeline, or the committed numbers drift
apart.
"""

from __future__ import annotations

import json
from pathlib import Path

from benchmark import hero_report
from benchmark.fixtures import CANONICAL_RUN, load_fixture
from benchmark.reproduce import COMMITTED, _checks

TOL = 0.01


def test_fixture_reproduces_committed_hero_metrics(tmp_path: Path) -> None:
    db = load_fixture(tmp_path / "fixture.db", fixture_dir=CANONICAL_RUN)
    got = hero_report.collect(db)
    want = json.loads(COMMITTED.read_text(encoding="utf-8"))

    drifted = [
        (label, g, w)
        for label, g, w in _checks(got, want)
        if abs(float(g) - float(w)) > TOL
    ]
    assert not drifted, f"hero metrics drifted from committed fixture: {drifted}"


def test_fixture_has_expected_shape(tmp_path: Path) -> None:
    db = load_fixture(tmp_path / "fixture.db", fixture_dir=CANONICAL_RUN)
    data = hero_report.collect(db)
    # 500 true parents (618 total recorded traces) and 118 replays.
    assert data["n_parents"] == 500
    assert data["n_runs"] == 618
    assert data["d4_replay_success"]["n_total_branches"] == 118
    # Headline point estimates, pinned (Husk-engine run).
    assert data["d5_mean_bypass"]["mean_pct"] == 42.07
    assert data["d4_replay_success"]["success_pct"] == 100.0
