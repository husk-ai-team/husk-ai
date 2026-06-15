"""Research Synthesizer — the agent the Husk benchmark drives.

Five nodes (query_expansion → retrieve → analyze → synthesize → cite_check)
chained on Husk's own engine. Real LLM calls fall back to canned, seedable
responses when no provider key is set, so the benchmark stays reproducible and
offline-friendly.
"""
