"""Generate `topics.jsonl` — 10.000 deterministic synthetic research topics.

We want topics that are diverse enough to look realistic on the Husk Studio
("recent advances in CRISPR base editing" rather than "topic_0001") but
generated entirely offline so the benchmark is reproducible.

Strategy: pick a domain from a curated list, a sub-domain modifier, and a
focus angle, then combine into a topic string. With ~60 × ~30 × ~10 building
blocks we get ~18.000 distinct topics — plenty for 10k unique runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

DOMAINS = [
    "CRISPR base editing",
    "vaccine adjuvants",
    "graph neural networks",
    "reinforcement learning from human feedback",
    "post-quantum cryptography",
    "carbon capture and storage",
    "perovskite solar cells",
    "fusion reactor confinement",
    "synthetic biology biosensors",
    "neuromorphic computing",
    "AI alignment research",
    "open-weight language models",
    "speech foundation models",
    "robotic surgery autonomy",
    "edge inference accelerators",
    "federated learning privacy",
    "differential privacy",
    "battery solid-state electrolytes",
    "hydrogen electrolysis cost curves",
    "low-orbit satellite constellations",
    "supply chain resilience",
    "industrial policy and semiconductors",
    "central bank digital currencies",
    "decentralised exchanges",
    "zero-knowledge proofs",
    "automated theorem proving",
    "explainable AI in radiology",
    "drug repurposing pipelines",
    "mRNA cancer vaccines",
    "antibiotic resistance surveillance",
    "ocean acidification monitoring",
    "wildfire detection from satellites",
    "agricultural digital twins",
    "indoor vertical farming yield",
    "lab-grown meat scale-up",
    "longevity research interventions",
    "psychedelic-assisted therapy trials",
    "wearable continuous glucose monitors",
    "brain–computer interfaces consumer",
    "augmented reality optics",
    "spatial audio for accessibility",
    "open-source hardware silicon",
    "RISC-V server adoption",
    "embedded AI compilers",
    "data lineage in lakehouses",
    "vector database benchmarks",
    "retrieval augmented generation evaluation",
    "agent frameworks comparison",
    "MLOps observability standards",
    "AI red teaming methodologies",
    "biometric spoof detection",
    "deepfake provenance",
    "C2PA content credentials",
    "open standards for AI safety",
    "EU AI Act compliance",
    "global semiconductor export controls",
    "rare-earth mineral supply",
    "geothermal heat pumps",
    "small modular reactors economics",
    "tokamak vs stellarator designs",
]

ANGLES = [
    "recent advances",
    "open research questions",
    "industry adoption patterns",
    "regulatory landscape",
    "key benchmarks",
    "leading research groups",
    "open-source ecosystem",
    "limitations and criticism",
    "ethical considerations",
    "five-year outlook",
    "scaling laws",
    "cost trajectory",
    "geographic concentration",
    "safety standards",
    "interoperability gaps",
    "talent pipeline",
    "investment landscape",
    "competitive dynamics",
    "academic vs industrial output",
    "open vs closed models",
    "production failure modes",
    "energy footprint",
    "lifecycle emissions",
    "supply-chain bottlenecks",
    "patent landscape",
    "standardisation efforts",
    "real-world deployment lessons",
    "benchmark saturation",
    "comparison with prior generation",
    "interpretability methods",
]

MODIFIERS = [
    "in healthcare",
    "in financial services",
    "in defence applications",
    "in education",
    "in agriculture",
    "in manufacturing",
    "for low-resource settings",
    "for European markets",
    "for the Asia-Pacific region",
    "in academic literature",
]


def topic_for(idx: int) -> str:
    """Deterministic topic from a single index, using SHA1 to spread evenly."""
    h = hashlib.sha1(f"husk-benchmark|{idx}".encode()).hexdigest()
    a = int(h[0:8], 16) % len(DOMAINS)
    b = int(h[8:16], 16) % len(ANGLES)
    c = int(h[16:24], 16) % len(MODIFIERS)
    return f"{ANGLES[b]} in {DOMAINS[a]} {MODIFIERS[c]}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-n", "--count", type=int, default=10_000)
    p.add_argument("--out", type=Path, default=Path("benchmark/topics.jsonl"))
    args = p.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        for i in range(args.count):
            fh.write(json.dumps({"index": i, "topic": topic_for(i)}) + "\n")
    print(
        f"Wrote {args.out} ({args.count} topics; "
        f"capacity ~{len(DOMAINS) * len(ANGLES) * len(MODIFIERS)} unique combos)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
