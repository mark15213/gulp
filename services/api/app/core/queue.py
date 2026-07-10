"""The enqueue seam (spec C5). API is sync; bridge to arq's async pool."""

import asyncio
import logging

from arq import create_pool
from arq.connections import RedisSettings
from gulp_shared.settings import settings

logger = logging.getLogger("gulp.api")


def enqueue(job_name: str, *args: object) -> None:
    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            job = await pool.enqueue_job(job_name, *args)
            logger.info(
                "enqueued job=%s job_id=%s args=%s",
                job_name,
                getattr(job, "job_id", "-"),
                args,
            )
        finally:
            await pool.aclose()

    try:
        asyncio.run(_go())
    except Exception:
        logger.exception("enqueue failed job=%s args=%s", job_name, args)
        raise
