# Husk benchmark -- cost equivalence matrix

**Tokens bypassed deterministically (DCS):** 38,999
  - input tokens: 27,299 (fraction 0.70)
  - output tokens: 11,700

These are tokens that the modify-and-replay engine bypassed at the
upstream nodes of failed runs in the benchmark. The figure below
translates that saving into per-provider USD using current list prices
(packages/husk-shared/src/husk_shared/pricing.py).

| Provider:model | $ saved (this benchmark) | vs Groq smallest |
|---|---:|---:|
| groq:llama-3.1-8b-instant | $0.0023 | 1.0x |
| groq:llama-3.3-70b-versatile | $0.0253 | 11.0x |
| openai:gpt-4o-mini | $0.0111 | 4.8x |
| openai:gpt-4o | $0.1852 | 80.5x |
| openai:gpt-4.1 | $0.1482 | 64.4x |
| openai:o1 | $1.1115 | 483.0x |
| anthropic:claude-haiku-3.5 | $0.0686 | 29.8x |
| anthropic:claude-sonnet-3.5 | $0.2574 | 111.9x |
| anthropic:claude-sonnet-4 | $0.2574 | 111.9x |
| anthropic:claude-opus-4 | $1.2870 | 559.3x |

**Reading the table.** The benchmark ran on Groq llama-3.x because
it is the cheapest production LLM provider. The Groq saving is
intentionally small in absolute dollars. The 'vs Groq smallest'
column shows the multiplier you would observe if the same workload
ran on each pricier provider. For a real customer running a debug
cycle on Claude Sonnet 4, the saving per replay is the corresponding
row, not the Groq baseline.