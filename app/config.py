"""Application configuration."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = "steam_market.db"
    currency: int = 5  # RUB
    cache_ttl_minutes: int = 60
    rate_limit_min: float = 3.0
    rate_limit_max: float = 5.0
    backoff_base: float = 10.0
    request_timeout: float = 30.0
    scheduler_interval_minutes: int = 5
    proxy: str | None = None
    user_agents: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]

    @property
    def db_url(self) -> str:
        return str(Path(self.db_path).resolve())


settings = Settings()
