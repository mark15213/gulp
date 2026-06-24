"""Job definitions (arq). The queue the API enqueues into.

S1 ships a no-op `process_snapshot` — the seam S2 grows into the real pipeline
(fetch → parse → chunk → pack → draft cards → link concepts).
"""

import logging

from arq.connections import RedisSettings

from gulp_shared.settings import settings

logger = logging.getLogger("gulp.worker")


async def process_snapshot(ctx: dict, snapshot_id: str) -> None:
    logger.info("TODO(S2): process snapshot %s", snapshot_id)


class WorkerSettings:
    functions = [process_snapshot]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
