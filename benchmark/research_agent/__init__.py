"""Research Synthesizer — the LangGraph agent the Husk benchmark drives.

Four nodes (query_expansion → retrieve → synthesize → cite_check) chained as a
deterministic state machine. Real LLM calls are replaced by canned, seedable
responses so the benchmark stays reproducible and offline-friendly.
"""
