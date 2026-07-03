"""Figure gallery contract — becomes the OpenAPI type the web reads."""

import uuid

from pydantic import BaseModel


class FigureAssetOut(BaseModel):
    id: uuid.UUID
    label: str | None
    caption: str | None
    mime_type: str
    width: int | None
    height: int | None
