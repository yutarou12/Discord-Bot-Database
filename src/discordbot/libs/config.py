from dotenv import load_dotenv
import os

load_dotenv()


def _split_csv(value: str) -> tuple[str, ...]:
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


DISCORD_BOT_TOKEN: str | None = os.environ.get("DISCORD_BOT_TOKEN", "").strip() or None
DATABASE_URL: str = os.environ.get("DATABASE_URL", "").strip()
POSTGRESQL_USER: str = os.environ.get("POSTGRESQL_USER", "").strip()
POSTGRESQL_PASSWORD: str = os.environ.get("POSTGRESQL_PASSWORD", "").strip()
POSTGRESQL_HOST_NAME: str = os.environ.get("POSTGRESQL_HOST_NAME", "").strip()
POSTGRESQL_PORT: str = os.environ.get("POSTGRESQL_PORT", "")
POSTGRESQL_DATABASE_NAME: str = os.environ.get("POSTGRESQL_DATABASE_NAME", "").strip()
ALLOWED_ORIGINS: tuple[str, ...] = _split_csv(os.getenv("CORS_ORIGINS", "http://localhost:3000"))

TRACEBACK_CHANNEL_ID: int = int(os.environ.get("TRACEBACK_CHANNEL_ID", 0))
ERROR_CHANNEL_ID: int = int(os.environ.get("ERROR_CHANNEL_ID", 0))

API_KEY: str | None = os.getenv("API_KEY", "").strip() or None
API_HOST: str = os.getenv("API_HOST", "0.0.0.0").strip() or "0.0.0.0"
API_PORT: int = int(os.getenv("API_PORT", "8000"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"
DEBUG: bool = bool(os.environ.get("DEBUG", ""))
