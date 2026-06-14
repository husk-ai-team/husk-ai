"""Regenerate the published hero numbers OFFLINE from the committed fixture.

This is the one command a fresh cloner runs to verify Husk's headline claims
without a provider API key, a network call, or a live run:

    uv run python benchmark/reproduce.py

It rebuilds a throwaway SQLite DB from `benchmark/fixtures/canonical_run/`,
recomputes D1–D5 with `hero_report.collect`, prints them next to the committed
`hero_metrics.json`, and exits non-zero if any headline figure drifts. The
metric pipeline sorts samples before its (seeded) bootstrap, so the values are
byte-reproducible from the fixture.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from benchmark import hero_report  # noqa: E402
from benchmark.fixtures import CANONICAL_RUN, load_fixture  # noqa: E402

COMMITTED = Path(__file__).resolve().parent / "hero_metrics.json"


def _checks(got: dict, want: dict) -> list[tuple[str, float, float]]:
    """(label, regenerated, committed) for every headline figure we assert."""
    g, w = got, want
    return [
        ("D5 mean token bypass %", g["d5_mean_bypass"]["mean_pct"], w["d5_mean_bypass"]["mean_pct"]),
        ("D5 CI low %", g["d5_mean_bypass"]["ci95_low_pct"], w["d5_mean_bypass"]["ci95_low_pct"]),
        ("D5 CI high %", g["d5_mean_bypass"]["ci95_high_pct"], w["d5_mean_bypass"]["ci95_high_pct"]),
        ("D1 mean speed-up x", g["d1_wall_time_speedup"]["mean_x"], w["d1_wall_time_speedup"]["mean_x"]),
        ("D1 median speed-up x", g["d1_wall_time_speedup"]["p50_x"], w["d1_wall_time_speedup"]["p50_x"]),
        ("D4 replay success %", g["d4_replay_success"]["success_pct"], w["d4_replay_success"]["success_pct"]),
        ("D3 max bypass %", g["d3_max_bypass"]["max_pct"], w["d3_max_bypass"]["max_pct"]),
        ("D2 N4 bypass %", g["d2_bypass_by_failure_mode"]["N4"]["mean_pct"], w["d2_bypass_by_failure_mode"]["N4"]["mean_pct"]),
        ("D2 N3 bypass %", g["d2_bypass_by_failure_mode"]["N3"]["mean_pct"], w["d2_bypass_by_failure_mode"]["N3"]["mean_pct"]),
    ]


def main() -> int:
    p = argparse.ArgumentParser(description="Offline reproduction of Husk hero metrics.")
    p.add_argument("--fixture", type=Path, default=CANONICAL_RUN)
    p.add_argument("--tolerance", type=float, default=0.01, help="max abs diff per metric")
    args = p.parse_args()

    if not COMMITTED.exists():
        print(f"ERROR: committed {COMMITTED} not found.", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as td:
        db = load_fixture(Path(td) / "fixture.db", fixture_dir=args.fixture)
        got = hero_report.collect(db)
    want = json.loads(COMMITTED.read_text(encoding="utf-8"))

    print(f"Offline reproduction from {args.fixture.name} "
          f"({got['n_parents']} parents / {got['d4_replay_success']['n_total_branches']} replays)\n")
    print(f"  {'metric':<26} {'regenerated':>12} {'committed':>12}   ok")
    print("  " + "-" * 60)
    ok = True
    for label, g, w in _checks(got, want):
        passed = abs(float(g) - float(w)) <= args.tolerance
        ok = ok and passed
        print(f"  {label:<26} {g:>12} {w:>12}   {'OK' if passed else 'DRIFT'}")

    print()
    if ok:
        print("PASS - every headline figure reproduces from committed data, no API key.")
        return 0
    print("FAIL - a headline figure drifted from hero_metrics.json.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
