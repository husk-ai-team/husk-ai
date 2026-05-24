"""Minimal LangChain example used to validate Husk's tracer end-to-end.

Uses `FakeListLLM` so the example needs no API keys and runs deterministically in CI.
Replace with `ChatOpenAI` / `ChatAnthropic` for a real run.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def main() -> None:
    from langchain.agents import AgentExecutor, Tool, create_react_agent
    from langchain.prompts import PromptTemplate
    from langchain_community.llms import FakeListLLM

    def echo_tool(query: str) -> str:
        return f"You said: {query}"

    tools = [
        Tool(
            name="echo",
            func=echo_tool,
            description="Echoes the input back. Useful when you want to repeat something.",
        )
    ]

    # FakeListLLM walks through canned responses in order. This simulates an agent
    # that decides to call the echo tool, then finishes.
    responses = [
        "Thought: I should call the echo tool.\nAction: echo\nAction Input: hello world",
        "Thought: I now know the final answer.\nFinal Answer: hello world",
    ]
    llm = FakeListLLM(responses=responses)

    prompt = PromptTemplate.from_template(
        """Answer the user. You have access to these tools:

{tools}

Use this format:
Thought: ...
Action: <one of [{tool_names}]>
Action Input: ...
Observation: ...
... (repeat as needed)
Thought: I now know the final answer.
Final Answer: ...

Question: {input}
{agent_scratchpad}"""
    )

    agent = create_react_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=False, max_iterations=3)
    result = executor.invoke({"input": "Say hello world."})
    log.info(f"Final: {result.get('output')}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
