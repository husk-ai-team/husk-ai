"""Deterministic mock for the knowledge_api.search tool call (N2).

A real research agent would hit Bing / Google / a vector store here. For the
benchmark we want zero network, zero variance, and a stable input → output
mapping so re-runs and replays are bit-identical (modulo the failure
injector). We synthesise 4 source snippets per topic using a seeded SHA1 hash
so two different topics produce different snippets but the same topic always
produces the same snippets.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: int
    title: str
    snippet: str


def _seeded_word(topic: str, slot: int) -> str:
    """Stable pseudo-word derived from topic + slot index."""
    h = hashlib.sha1(f"{topic}|{slot}".encode()).hexdigest()
    return h[:8]


def retrieve(topic: str, query: str, *, force_empty: bool = False) -> list[Source]:
    """Return a deterministic list of source snippets for (topic, query).

    `force_empty=True` simulates a retrieval failure (N2 fail mode in the
    benchmark's failure-injection distribution).
    """
    if force_empty:
        return []

    sources: list[Source] = []
    for i in range(1, 5):  # 4 sources per query
        word = _seeded_word(f"{topic}::{query}", i)
        sources.append(
            Source(
                id=i,
                title=f"{topic.title()} — reference {i} ({word})",
                snippet=(
                    f"Reference {i} for topic '{topic}' addressing query "
                    f"'{query}'. Key fact: {word}-derived datum #{i}."
                ),
            )
        )
    return sources


def render_sources(sources: list[Source]) -> str:
    """Pretty-print sources for prompt inclusion."""
    if not sources:
        return "(no sources retrieved)"
    return "\n".join(f"[{s.id}] {s.title}: {s.snippet}" for s in sources)
