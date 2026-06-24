"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

from fastapi import FastAPI

from app.routers import capture, inbox

app = FastAPI(title="Gulp API")
app.include_router(capture.router, tags=["capture"])
app.include_router(inbox.router, tags=["inbox"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
