"""`just worker` / `python -m app.tasks` entry. Boots the arq worker."""

import logging

from arq import run_worker
from gulp_shared.logging import configure_logging

from app.tasks import WorkerSettings

if __name__ == "__main__":
    configure_logging("worker")
    logging.getLogger("gulp.worker").info("starting worker")
    run_worker(WorkerSettings)  # type: ignore[arg-type]
