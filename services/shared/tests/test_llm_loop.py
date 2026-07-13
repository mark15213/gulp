"""Tool loop: execute calls, feed results back, stop on plain answer / max_iters."""

from typing import Any

from gulp_shared.llm.base import (
    ChatMessage,
    DoneEvent,
    ModelConfig,
    TextDelta,
    ToolCall,
    ToolCallEvent,
    ToolSpec,
)
from gulp_shared.llm.loop import run_tool_loop

CFG = ModelConfig(provider="anthropic", api_key="sk-test")
TOOLS = [ToolSpec(name="search", description="d", input_schema={"type": "object"})]


class ScriptedProvider:
    """Each round yields the next scripted event list; records the convo."""

    def __init__(self, rounds: list[list[Any]]) -> None:
        self.rounds = rounds
        self.seen: list[list[ChatMessage]] = []

    async def complete_json(self, **kw: Any) -> dict[str, Any]:
        raise AssertionError("loop must stream")

    async def stream_chat(self, *, system, messages, tools, config):  # type: ignore[no-untyped-def]
        self.seen.append(list(messages))
        for ev in self.rounds[len(self.seen) - 1]:
            yield ev


async def test_loop_executes_tools_then_finishes() -> None:
    call = ToolCall(id="c1", name="search", arguments={"q": "x"})
    prov = ScriptedProvider(
        [
            [ToolCallEvent(tool_call=call), DoneEvent(stop_reason="tool_use")],
            [TextDelta(text="answer"), DoneEvent(stop_reason="stop")],
        ]
    )
    executed: list[ToolCall] = []

    async def executor(c: ToolCall) -> str:
        executed.append(c)
        return "result-1"

    events = [
        e
        async for e in run_tool_loop(
            system="s",
            messages=[ChatMessage(role="user", content="q")],
            tools=TOOLS,
            executor=executor,
            config=CFG,
            provider=prov,
        )
    ]
    assert executed == [call]
    assert [e.type for e in events] == ["tool_call", "text_delta", "done"]
    assert events[-1] == DoneEvent(stop_reason="stop")
    # round 2 saw: user, assistant(tool_calls), tool(result)
    round2 = prov.seen[1]
    assert round2[1].tool_calls == [call]
    assert round2[2].role == "tool" and round2[2].content == "result-1"
    assert round2[2].tool_call_id == "c1"


async def test_loop_stops_at_max_iters() -> None:
    call = ToolCall(id="c1", name="search", arguments={})
    prov = ScriptedProvider(
        [[ToolCallEvent(tool_call=call), DoneEvent(stop_reason="tool_use")]] * 3
    )

    async def executor(c: ToolCall) -> str:
        return "r"

    events = [
        e
        async for e in run_tool_loop(
            system=None,
            messages=[ChatMessage(role="user", content="q")],
            tools=TOOLS,
            executor=executor,
            config=CFG,
            provider=prov,
            max_iters=3,
        )
    ]
    assert events[-1] == DoneEvent(stop_reason="max_iters")
    assert len(prov.seen) == 3
