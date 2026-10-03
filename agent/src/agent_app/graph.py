"""LangGraph loop. A tool batch finishes before the next model turn."""

import asyncio
import json
import time
from typing import TypedDict

from langgraph.graph import END, StateGraph

from agent_app.config import Settings
from agent_app.evidence import absorb, claims_from_model, known_files
from agent_app.trace import argument_summary, remember


class LoopState(TypedDict, total=False):
    question: str
    repository_id: str
    commit_sha: str
    observations: list[dict]
    steps: int
    tool_calls_made: int
    evidence: list[dict]
    trace: list[dict]
    pending: list[dict]
    answer: str
    stopped_reason: str
    started: float


def build_graph(hub, model, settings: Settings):
    """Compile the model node and the tool node. Callers invoke it once per question."""

    async def model_node(state: LoopState) -> dict:
        if _timed_out(state, settings):
            return _stop(state, "timeout", "The loop stopped because it reached the time limit.")
        if state.get("steps", 0) >= settings.max_steps:
            return _stop(state, "max_steps", "The loop stopped because it reached the step limit.")
        decision = await model.decide(
            state["question"],
            state["repository_id"],
            state.get("observations") or [],
            [item["name"] for item in await hub.list_tools()],
        )
        calls = decision.get("tool_calls") or []
        if calls:
            if state.get("tool_calls_made", 0) + len(calls) > settings.max_tool_calls:
                return _stop(state, "max_tool_calls", "The loop stopped because it reached the tool-call limit.")
            return {"steps": state.get("steps", 0) + 1, "pending": calls}
        claims = claims_from_model(
            decision.get("claims") or [],
            known_files(state.get("evidence") or []),
            "model",
            "agent",
            state.get("commit_sha") or "",
        )
        evidence = list(state.get("evidence") or [])
        evidence.extend(claims)
        return {
            "steps": state.get("steps", 0) + 1,
            "pending": [],
            "answer": decision.get("answer") or "The tools did not produce a further answer.",
            "stopped_reason": "answered",
            "evidence": evidence[:50],
        }

    async def tools_node(state: LoopState) -> dict:
        if _timed_out(state, settings):
            return _stop(state, "timeout", "The loop stopped because it reached the time limit.")
        pending = state.get("pending") or []
        results = await asyncio.gather(*[_one(hub, call, settings) for call in pending])
        observations = list(state.get("observations") or [])
        evidence = list(state.get("evidence") or [])
        trace = list(state.get("trace") or [])
        commit_sha = state.get("commit_sha") or ""
        for call, result, duration_ms in results:
            name = call.get("name") or ""
            server = hub.server_for(name)
            rows, commit_sha = absorb(result, name, server, commit_sha)
            evidence.extend(rows)
            observations.append({"tool": name, "text": _clip(result, settings.max_tool_output_chars)})
            trace.append(
                {
                    "server": server,
                    "tool": name,
                    "status": _status(result),
                    "duration_ms": duration_ms,
                    "arguments": argument_summary(call.get("arguments") or {}),
                }
            )
        remember(trace[-len(pending) :], settings.max_steps)
        return {
            "observations": observations,
            "evidence": evidence[:50],
            "trace": trace[: settings.max_steps],
            "commit_sha": commit_sha,
            "tool_calls_made": state.get("tool_calls_made", 0) + len(pending),
            "pending": [],
        }

    graph = StateGraph(LoopState)
    graph.add_node("model", model_node)
    graph.add_node("tools", tools_node)
    graph.set_entry_point("model")
    graph.add_conditional_edges("model", _route, {"tools": "tools", "end": END})
    graph.add_edge("tools", "model")
    return graph.compile()


async def run_investigation(question: str, repository_id: str, commit_sha: str, hub, model, settings: Settings) -> dict:
    """Run one bounded loop and return the public response fields."""
    app = build_graph(hub, model, settings)
    final = await app.ainvoke(
        {
            "question": question,
            "repository_id": repository_id,
            "commit_sha": commit_sha,
            "observations": [],
            "steps": 0,
            "tool_calls_made": 0,
            "evidence": [],
            "trace": [],
            "pending": [],
            "answer": "",
            "stopped_reason": "",
            "started": time.monotonic(),
        }
    )
    return {
        "answer": final.get("answer") or "",
        "evidence": final.get("evidence") or [],
        "trace": final.get("trace") or [],
        "stopped_reason": final.get("stopped_reason") or "answered",
    }


async def _one(hub, call: dict, settings: Settings) -> tuple[dict, dict, int]:
    name = call.get("name") or ""
    arguments = call.get("arguments") or {}
    started = time.perf_counter()
    result = await _call_with_retry(hub, name, arguments, settings.max_retries)
    duration_ms = int((time.perf_counter() - started) * 1000)
    return call, result, duration_ms


async def _call_with_retry(hub, name: str, arguments: dict, retries: int) -> dict:
    attempt = 0
    while True:
        try:
            result = await hub.call_tool(name, arguments)
        except Exception as exc:
            result = {"error": {"code": "INTERNAL_ERROR", "message": str(exc), "retryable": False}}
        error = result.get("error") if isinstance(result, dict) else None
        if not error or not error.get("retryable") or attempt >= retries:
            return result if isinstance(result, dict) else {"error": {"code": "INTERNAL_ERROR", "message": "Bad tool result.", "retryable": False}}
        attempt += 1


def _route(state: LoopState) -> str:
    if state.get("stopped_reason"):
        return "end"
    if state.get("pending"):
        return "tools"
    return "end"


def _timed_out(state: LoopState, settings: Settings) -> bool:
    started = state.get("started") or time.monotonic()
    return time.monotonic() - started >= settings.timeout_seconds


def _stop(state: LoopState, reason: str, answer: str) -> dict:
    return {"stopped_reason": reason, "answer": answer, "pending": [], "steps": state.get("steps", 0)}


def _status(result: dict) -> str:
    if isinstance(result, dict) and result.get("error"):
        return result["error"].get("code") or "error"
    return "ok"


def _clip(result: dict, limit: int) -> str:
    text = json.dumps(result)
    if len(text) <= limit:
        return text
    return text[:limit]
