"""The MCP endpoint (spec 2026-07-16 §3): four self-describing job tools,
thin over app.services.agent_jobs. Tools are sync on purpose — FastMCP runs
them in a worker thread, which keeps the asyncio.run inside enqueue legal
(same reason the REST import endpoint is sync)."""

import uuid
from typing import TYPE_CHECKING, Any

from gulp_shared.models.user import User
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.orm import Session

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


def _user(db: Session, ctx: Ctx) -> User:
    user_id: uuid.UUID = ctx.request_context.request.state.gulp_user_id  # type: ignore[union-attr]
    user = db.get(User, user_id)
    assert user is not None  # the PAT middleware just resolved it
    return user


def _error(exc: AgentJobUnavailable) -> dict[str, Any]:
    err: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.retry_after_s is not None:
        err["retry_after_s"] = exc.retry_after_s
    return {"error": err}


@mcp.tool()
def list_jobs(
    ctx: Ctx, kind: str | None = None
) -> list[dict[str, Any]] | dict[str, Any]:
    """List your pending Gulp jobs. Optional kind filter: "digest" | "cards".
    Jobs in state "building" are not claimable yet — retry them later."""
    db = deps.session_factory()
    try:
        return agent_jobs.list_jobs(db, _user(db, ctx), kind)
    except AgentJobUnavailable as exc:
        return _error(exc)
    finally:
        db.close()


@mcp.tool()
def claim_job(ctx: Ctx, job_id: str) -> dict[str, Any]:
    """Atomically claim a pending job. Returns the full self-describing task:
    instruction (follow it exactly), input (the data), output_schema (your
    result MUST validate against it), lease_expires_at."""
    db = deps.session_factory()
    try:
        return agent_jobs.claim_job(db, _user(db, ctx), job_id, deps.enqueue)
    except AgentJobUnavailable as exc:
        return _error(exc)
    finally:
        db.close()


@mcp.tool()
def submit_result(ctx: Ctx, job_id: str, result: dict[str, Any]) -> dict[str, Any]:
    """Submit a finished job's result JSON. Returns {accepted: true} or
    {accepted: false, errors: [...]} — fix the errors and submit again."""
    db = deps.session_factory()
    try:
        return agent_jobs.submit_result(db, _user(db, ctx), job_id, result, deps.enqueue)
    except AgentJobUnavailable as exc:
        return _error(exc)
    finally:
        db.close()


@mcp.tool()
def report_failure(ctx: Ctx, job_id: str, reason: str) -> dict[str, Any]:
    """Give up on a job you cannot complete; the reason is shown to the user."""
    db = deps.session_factory()
    try:
        return agent_jobs.report_failure(db, _user(db, ctx), job_id, reason)
    except AgentJobUnavailable as exc:
        return _error(exc)
    finally:
        db.close()
