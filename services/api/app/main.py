"""FastAPI entry. Routers stay thin; logic in app/services, persistence in gulp_shared."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from gulp_shared.settings import settings

from app.routers import capture, cards, export, figures, inbox, library, pack, processing, today

app = FastAPI(title="Gulp API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(capture.router, tags=["capture"])
app.include_router(cards.router, tags=["cards"])
app.include_router(export.router, tags=["export"])
app.include_router(figures.router, tags=["figures"])
app.include_router(inbox.router, tags=["inbox"])
app.include_router(library.router, tags=["library"])
app.include_router(pack.router, tags=["pack"])
app.include_router(processing.router, tags=["processing"])
app.include_router(today.router, tags=["today"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
