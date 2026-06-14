"""Prompt templates used by the four nodes of the Research Synthesizer.

Kept in a single module so the benchmark can hash them, version them, and emit
them as canned spans on the OTel trace without scattering string literals.
"""

from __future__ import annotations

QUERY_EXPANSION_SYSTEM = (
    "You are a research planner. Given a single topic, produce 3–5 focused "
    "sub-queries that together cover the topic well. Output a JSON list of "
    "strings, no commentary."
)

QUERY_EXPANSION_USER = "Topic: {topic}"

RETRIEVE_TOOL_NAME = "knowledge_api.search"

# analyze is the cost-dominant upstream reasoning step: for every retrieved
# source it extracts claims, weighs evidence and rates relevance. This mirrors
# real agents, where retrieval + deep reasoning over documents is the expensive
# phase and the final answer formatting is comparatively cheap.
ANALYZE_SYSTEM = (
    "You are a meticulous research analyst. For EACH numbered source snippet, "
    "extract its key claims, assess the strength and quality of its evidence, "
    "flag any contradictions with the other sources, and rate its relevance to "
    "the topic. Be thorough and explicit — this structured analysis is the only "
    "context the downstream writer will see, so omit nothing important."
)

ANALYZE_USER = (
    "Topic: {topic}\n\nSources:\n{sources}\n\n"
    "Produce a detailed per-source analysis (claims, evidence quality, "
    "contradictions, relevance) for every source:"
)

SYNTHESIZE_SYSTEM = (
    "You are a research synthesizer. Given a topic, the source snippets, and a "
    "prepared analysis, produce a 4–6 sentence answer. Cite sources inline as "
    "[1], [2], … matching the order of the snippets. Rely on the analysis; do "
    "not re-derive it."
)

SYNTHESIZE_USER = (
    "Topic: {topic}\n\nSources:\n{sources}\n\nAnalysis:\n{analysis}\n\n"
    "Write the synthesized answer:"
)

CITE_CHECK_SYSTEM = (
    "You are a citation auditor. Given an answer with inline [N] citations "
    "and the list of source snippets, return one of: 'valid' (every citation "
    "matches a real snippet), 'mismatch' (one or more citations don't match), "
    "or 'missing' (some sources never cited)."
)

CITE_CHECK_USER = "Answer:\n{answer}\n\nSources:\n{sources}\n\nVerdict:"
