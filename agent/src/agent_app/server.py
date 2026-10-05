"""HTTP entry for one question. MCP servers stay the tool hosts."""

import time

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from investigator_shared.secrets import log_event

from agent_app.config import get_settings, model_ready
from agent_app.metrics import snapshot as metrics_snapshot
from agent_app.graph import run_investigation
from agent_app.mcp_client import HttpMcpHub
from agent_app.prompts import load_prompt
from agent_app.trace import argument_hash, argument_summary, remember


async def health(_: Request) -> JSONResponse:
    """Process health for Compose. This does not check the API key."""
    return JSONResponse({"status": "ok", "service": "agent"})


async def metrics(_: Request) -> JSONResponse:
    """Counters and histograms for this process. A restart clears them."""
    return JSONResponse(metrics_snapshot())


async def investigate_route(request: Request) -> JSONResponse:
    body = await request.json()
    result = await investigate(body)
    return JSONResponse(result)


async def investigate(body: dict, hub=None, model=None, settings=None) -> dict:
    """Clone when the caller passed a URL, then run the loop."""
    settings = settings or get_settings()
    if not model_ready(settings):
        return _empty("Set OPENAI_API_KEY before requesting an investigation.", "configuration")

    question = (body.get("question") or "").strip()
    prompt_name = (body.get("prompt") or "").strip()
    hub = hub or HttpMcpHub(settings)
    model = model or _load_model(settings)
    repository_id = (body.get("repository_id") or "").strip()
    if prompt_name:
        prompt_arguments = body.get("arguments") if isinstance(body.get("arguments"), dict) else {}
        prompt_arguments = dict(prompt_arguments)
        if repository_id and "repository_id" not in prompt_arguments:
            prompt_arguments["repository_id"] = repository_id
        loaded = await load_prompt(hub, prompt_name, prompt_arguments)
        if not loaded:
            return _empty(f"Prompt {prompt_name} was not found.", "answered")
        question = loaded
    if not question:
        return _empty("A question is required.", "answered")
    commit_sha = ""
    trace: list[dict] = []
    if not repository_id:
        url = (body.get("url") or "").strip()
        if not url:
            return _empty("Provide a repository_id or a GitHub url.", "answered")
        arguments = {"repository_url": url}
        if body.get("ref"):
            arguments["ref"] = body["ref"]
        started = time.perf_counter()
        cloned = await hub.call_tool("clone_repository", arguments)
        duration_ms = int((time.perf_counter() - started) * 1000)
        trace.append(
            {
                "server": hub.server_for("clone_repository"),
                "tool": "clone_repository",
                "status": "ok" if isinstance(cloned, dict) and "error" not in cloned else "error",
                "duration_ms": duration_ms,
                "arguments": argument_summary(arguments),
                "argument_hash": argument_hash(arguments),
            }
        )
        remember(trace, settings.max_steps)
        if not isinstance(cloned, dict) or cloned.get("error") or not cloned.get("repository_id"):
            return {
                "answer": "The repository could not be cloned, so the answer is unknown.",
                "evidence": [],
                "trace": trace,
                "stopped_reason": "answered",
            }
        repository_id = cloned["repository_id"]
        commit_sha = cloned.get("resolved_commit") or ""

    started_loop = time.perf_counter()
    result = await run_investigation(
        question,
        repository_id,
        commit_sha,
        hub,
        model,
        settings,
        session_id=str(body.get("session_id") or ""),
    )
    result["trace"] = (trace + result["trace"])[: settings.max_steps]
    log_event(
        "investigation",
        duration_ms=int((time.perf_counter() - started_loop) * 1000),
        status=result.get("stopped_reason") or "answered",
        repository_id=repository_id,
    )
    return result


def _load_model(settings):
    if settings.test_model == "scripted":
        from tests.fake_model import ScriptedModel

        return ScriptedModel()
    from agent_app.model import OpenAIModel

    return OpenAIModel(settings)


def _empty(answer: str, reason: str) -> dict:
    return {"answer": answer, "evidence": [], "trace": [], "stopped_reason": reason}


app = Starlette(
    routes=[
        Route("/health", endpoint=health, methods=["GET"]),
        Route("/metrics", endpoint=metrics, methods=["GET"]),
        Route("/investigate", endpoint=investigate_route, methods=["POST"]),
    ]
)


def main() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
