"""The enqueue seam (spec C5). API is sync; bridge to arq's async pool."""

import asyncio

from arq import create_pool
from arq.connections import RedisSettings
from gulp_shared.settings import settings


def enqueue(job_name: str, *args: object) -> None:
    async def _go() -> None:
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            await pool.enqueue_job(job_name, *args)
        finally:
            await pool.aclose()

    asyncio.run(_go())
