from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "SupportFusion AI"
    app_env: str = "development"
    database_url: str = (
        f"sqlite:///{(ROOT_DIR / 'data' / 'supportfusion.db').as_posix()}"
    )
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173"
    github_token: str | None = None
    github_default_repository: str = "appsmithorg/appsmith"
    collector_user_agent: str = (
        "SupportFusionAI/0.1 (+https://bilalbouizdouzene.github.io)"
    )
    search_mode: str = "STANDARD"

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env"), extra="ignore", case_sensitive=False
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
