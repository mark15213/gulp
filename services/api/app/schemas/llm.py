"""BYOK LLM settings contract — becomes the OpenAPI types the web client reads."""

from pydantic import BaseModel


class ModelInfoOut(BaseModel):
    id: str
    label: str


class ProviderCatalogOut(BaseModel):
    provider: str
    capabilities: list[str]
    models: list[ModelInfoOut]


class CredentialOut(BaseModel):
    provider: str
    masked_key: str


class LLMSettingsOut(BaseModel):
    default_provider: str | None
    default_model: str | None
    credentials: list[CredentialOut]
    catalog: list[ProviderCatalogOut]


class CredentialIn(BaseModel):
    api_key: str


class DefaultIn(BaseModel):
    provider: str
    model: str
