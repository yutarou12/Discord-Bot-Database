from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str | None
    database_url: str
    api_key: str | None
    api_host: str
    api_port: int
    allowed_origins: tuple[str, ...]
    log_level: str


def _split_csv(value: str) -> tuple[str, ...]:
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


def load_settings() -> Settings:
    token = os.getenv("DISCORD_BOT_DB_TOKEN", "").strip() or None

    database_url = os.getenv("DATABASE_URL", "sqlite:///./discord_bots.db").strip()
    api_key = os.getenv("API_KEY", "").strip() or None
    api_host = os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0"
    api_port = int(os.getenv("API_PORT", "8000"))
    allowed_origins = _split_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

    return Settings(
        discord_token=token,
        database_url=database_url,
        api_key=api_key,
        api_host=api_host,
        api_port=api_port,
        allowed_origins=allowed_origins,
        log_level=log_level,
    )
