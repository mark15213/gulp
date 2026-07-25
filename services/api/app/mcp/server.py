"""The MCP endpoint (spec 2026-07-16 §3): four self-describing job tools,
thin over app.services.agent_jobs. Every tool body runs in a worker thread —
see _offload for why that is load-bearing, not a style choice."""

import uuid
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, Any, cast

import anyio
from gulp_shared.models.user import User
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.mcp import deps
from app.services import agent_jobs
from app.services.agent_jobs import AgentJobUnavailable

if TYPE_CHECKING:
    # FastMCP injects the request context only when a tool parameter is annotated
    # with the *bare* Context class (find_context_parameter does an issubclass
    # check that a parametrized Context[...] fails). So we must annotate with the
    # unparametrized class at runtime; alias it to the parametrized form for the
    # type checker alone, to satisfy strict mypy's missing-type-args rule.
    Ctx = Context[Any, Any, Any]
else:
    Ctx = Context

# DNS-rebinding protection guards browser clients that carry ambient credentials
# (cookies) against a malicious page rebinding to a localhost MCP server. Our
# /mcp requires an explicit Bearer PAT (never a cookie), so that attack does not
# apply, and the SDK's default (empty allow-list) would 421 every request once
# the API sits behind a reverse proxy whose Host is the public domain. Disable it.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)

mcp = FastMCP(
    "gulp",
    stateless_http=True,
    json_response=True,
    transport_security=_TRANSPORT_SECURITY,
)


def _error(exc: AgentJobUnavailable) -> dict[str, Any]:
    err: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.retry_after_s is not None:
        err["retry_after_s"] = exc.retry_after_s
    return {"error": err}


def _call(fn: Callable[..., Any], user_id: uuid.UUID, *args: Any) -> Any:
    """The whole tool body, off the event loop: its own Session, the user the
    PAT resolved to, and the service call — with a protocol rejection mapped
    onto the structured error envelope."""
    db = deps.session_factory()
    try:
        user = db.get(User, user_id)
        assert user is not None  # the PAT middleware just resolved it
        return fn(db, user, *args)
    except AgentJobUnavailable as exc:
        return _error(exc)
    finally:
        db.close()


async def _offload(ctx: Ctx, fn: Callable[..., Any], *args: Any) -> Any:
    """Run the tool body in a worker thread. Load-bearing: FastMCP (SDK 1.28)
    calls a *sync* tool fn inline on the running ASGI loop
    (fastmcp/utilities/func_metadata.py: `return fn(**kwargs)`), so a body that
    reaches `enqueue` — which drives arq through asyncio.run() — dies with
    "asyncio.run() cannot be called from a running event loop". That breaks
    every digest submit and every archive rebuild. FastAPI hands sync endpoints
    a threadpool for exactly this reason (see routers/export.py's import note);
    FastMCP does not, so we do it ourselves.

    The user id is read here, on the loop, rather than inside the thread: the
    request context is a contextvar, and this keeps the thread free of any
    assumption about how it propagates."""
    user_id: uuid.UUID = ctx.request_context.request.state.gulp_user_id  # type: ignore[union-attr]
    return await anyio.to_thread.run_sync(partial(_call, fn, user_id, *args))


@mcp.tool()
async def list_jobs(
    ctx: Ctx, kind: str | None = None
) -> list[dict[str, Any]] | dict[str, Any]:
    """List your pending Gulp jobs. Optional kind filter: "digest" | "cards".
    Jobs in state "building" are not claimable yet — retry them later."""
    return cast(
        "list[dict[str, Any]] | dict[str, Any]",
        await _offload(ctx, agent_jobs.list_jobs, kind),
    )


@mcp.tool()
async def claim_job(ctx: Ctx, job_id: str) -> dict[str, Any]:
    """Atomically claim a pending job. Returns the full self-describing task:
    instruction (follow it exactly), input (the data), output_schema (your
    result MUST validate against it), lease_expires_at."""
    return cast(
        "dict[str, Any]",
        await _offload(ctx, agent_jobs.claim_job, job_id, deps.enqueue),
    )


@mcp.tool()
async def submit_result(ctx: Ctx, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Submit a finished job's result JSON. Returns {accepted: true} or
    {accepted: false, errors: [...]} — fix the errors and submit again."""
    return cast(
        "dict[str, Any]",
        await _offload(ctx, agent_jobs.submit_result, job_id, result, deps.enqueue),
    )


@mcp.tool()
async def report_failure(ctx: Ctx, job_id: str, reason: str) -> dict[str, Any]:
    """Give up on a job you cannot complete; the reason is shown to the user."""
    return cast(
        "dict[str, Any]",
        await _offload(ctx, agent_jobs.report_failure, job_id, reason),
    )
