"""FastAPI entry. Routers stay thin; business logic lives in app/services,
persistence in gulp_shared. See services/api/CLAUDE.md."""

from fastapi import FastAPI

app = FastAPI(title="Gulp API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
