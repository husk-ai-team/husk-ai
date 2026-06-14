"""Failure injection for the 10k-run synthetic benchmark.

Produces a deterministic schedule of `failure_mode` assignments matching the
distribution described in the case-study plan:

    Outcome                                       %    Count (n=10000)
    ────────────────────────────────────────────────────────────────────
    Success clean                                 80%       8.000
    Fail N3 — synthesize (hallucination)            8%         800
    Fail N4 — cite_check (citation mismatch)        6%         600
    Fail N2 — retrieve (empty result)               4%         400
    Fail N1 — query_expansion (malformed output)    2%         200
    ────────────────────────────────────────────────────────────────────
    Total failures                                20%       2.000

The schedule is seeded by topic index so re-runs produce identical
assignments. The output is a list of (topic_index, failure_mode) tuples that
`run_benchmark.py` zips with `topics.jsonl` rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

# Realistic production mix (use for the POOLED headline bypass number).
DISTRIBUTION: list[tuple[str | None, float]] = [
    (None, 0.80),
    ("N3", 0.08),
    ("N4", 0.06),
    ("N2", 0.04),
    ("N1", 0.02),
]

# Balanced, elevated-failure mix for the PER-MODE breakdown: equal weight per
# mode so a supplementary run reaches >=30 replays/mode without needing
# thousands of parents (the natural N1 rate of 2% would need ~1,500). Bypass per
# mode is independent of how often the mode is injected, so this does not bias
# D2; only the pooled D5 depends on the mix, which is why the headline uses
# DISTRIBUTION above.
DISTRIBUTION_BALANCED: list[tuple[str | None, float]] = [
    (None, 0.40),
    ("N1", 0.15),
    ("N2", 0.15),
    ("N3", 0.15),
    ("N4", 0.15),
]


def _bucket_for(
    idx: int, seed: int, dist: list[tuple[str | None, float]] = DISTRIBUTION
) -> str | None:
    """Stable hash-based bucket assignment for run index `idx`."""
    h = hashlib.sha256(f"{seed}:{idx}".encode()).hexdigest()
    # First 16 hex chars → unsigned 64-bit int → float in [0, 1).
    r = int(h[:16], 16) / 2**64
    acc = 0.0
    for mode, frac in dist:
        acc += frac
        if r < acc:
            return mode
    return None


def schedule(
    n: int, seed: int = 42, dist: list[tuple[str | None, float]] = DISTRIBUTION
) -> list[tuple[int, str | None]]:
    """Return [(topic_index, failure_mode), …] for `n` runs."""
    out: list[tuple[int, str | None]] = []
    for i in range(n):
        out.append((i, _bucket_for(i, seed, dist)))
    return out


def shuffled_schedule(n: int, seed: int = 42) -> list[tuple[int, str | None]]:
    """Same distribution but shuffled so failures don't cluster."""
    base = schedule(n, seed)
    rng = random.Random(seed ^ 0xBEEF)
    rng.shuffle(base)
    return base


def summarise(sched: list[tuple[int, str | None]]) -> dict[str | None, int]:
    counts: dict[str | None, int] = {}
    for _, mode in sched:
        counts[mode] = counts.get(mode, 0) + 1
    return counts


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-n", "--count", type=int, default=10_000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--out", type=Path, default=Path("benchmark/failure_schedule.jsonl")
    )
    p.add_argument(
        "--balanced",
        action="store_true",
        help="Use the balanced/elevated per-mode mix (for the D2 per-mode run).",
    )
    args = p.parse_args()

    dist = DISTRIBUTION_BALANCED if args.balanced else DISTRIBUTION
    sched = schedule(args.count, args.seed, dist)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for idx, mode in sched:
            fh.write(json.dumps({"index": idx, "failure_mode": mode}) + "\n")

    counts = summarise(sched)
    print(f"Wrote {args.out} ({args.count} entries, seed={args.seed})")
    for k, v in sorted(counts.items(), key=lambda kv: (kv[0] or "")):
        label = "success" if k is None else f"fail_{k}"
        pct = v / args.count * 100
        print(f"  {label:>11}: {v:>6} ({pct:5.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
