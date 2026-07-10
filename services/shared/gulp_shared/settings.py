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
    rsshub_base_url: str = "http://localhost:1200"
    rsshub_routes_url: str = "https://docs.rsshub.app/routes.json"
    feed_poll_interval_minutes: int = 30
    feed_entry_retention_days: int = 90
    log_level: str = "INFO"

    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins. Include the localhost <-> 127.0.0.1 twin:
        browsers treat them as distinct origins and CORS is exact-match, so a
        capture POST from the "wrong" host would otherwise be silently blocked.
        """
        origins = {self.web_origin}
        if "localhost" in self.web_origin:
            origins.add(self.web_origin.replace("localhost", "127.0.0.1"))
        elif "127.0.0.1" in self.web_origin:
            origins.add(self.web_origin.replace("127.0.0.1", "localhost"))
        return sorted(origins)


settings = Settings()
