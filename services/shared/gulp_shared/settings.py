"""Application settings, loaded from the environment (see .env.example)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://gulp:gulp@localhost:5432/gulp"
    redis_url: str = "redis://localhost:6379/0"
    auth_secret: str = "change-me"
    anthropic_api_key: str = ""
    web_origin: str = "http://localhost:3000"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"
    export_dir: str = "/tmp/gulp-exports"
    media_dir: str = "/tmp/gulp-media"


settings = Settings()
