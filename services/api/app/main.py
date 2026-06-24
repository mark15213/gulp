"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import capture, inbox
from gulp_shared.settings import settings

app = FastAPI(title="Gulp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(capture.router, tags=["capture"])
app.include_router(inbox.router, tags=["inbox"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
