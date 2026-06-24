"""`just worker` / `python -m app.tasks` entry. Boots the arq worker."""

from arq import run_worker

from app.tasks import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)  # type: ignore[arg-type]
