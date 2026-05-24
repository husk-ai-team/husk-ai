# Examples

Runnable agent scripts used for development, manual testing, and CI smoke tests.
Start Husk first (`uv run husk-ai start`), then run an example — each one emits
traces into your local Studio at `http://localhost:7654`.

| File | Framework | Needs API key |
|---|---|---|
| `langchain_agent.py` | LangChain (ReAct agent + tool, `FakeListLLM`) | No |
| `langgraph_thread.py` | LangGraph (planner → answerer, SQLite checkpointer) | No |
| `otel-autogen.py` | Raw OpenTelemetry GenAI emitter (no framework) | No |

## Running

The example dependencies live in the `examples` dependency group:

```bash
uv run --group examples python examples/langchain_agent.py
uv run --group examples python examples/langgraph_thread.py
uv run --group examples python examples/otel-autogen.py
```

`langgraph_thread.py` is the one to try for time-travel: after it runs, open the
run in the Studio and use **Modify and replay** to branch from any checkpoint.
