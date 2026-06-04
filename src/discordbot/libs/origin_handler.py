import logging
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta


class DatetimeFormatter(logging.Formatter):
    def formatTime(self, record: logging.LogRecord, datefmt=None):
        if datefmt is None:
            datefmt = "%Y-%m-%d %H:%M:%S,%03d"

        TZ_JST = timezone(timedelta(hours=+9), 'JST')
        created_time = datetime.fromtimestamp(record.created, tz=TZ_JST)
        s = created_time.strftime(datefmt)

        return s


class BotAddDataModel(BaseModel):
    bot_id: int
    bot_name: str
    prefix: str
    description: str
    tags: list[str]
    invite_url: str | None
    website_url: str | None
    support_server_url: str | None
    banner_url: str | None
    avatar_url: str | None
    approved: bool = False


class BotInputDataModel(BotAddDataModel):
    bot_id: int | None = None
    bot_name: str | None = None
    prefix: str | None = None
    description: str | None = None
    tags: list[str] = []
    invite_url: str | None = None
    website_url: str | None = None
    support_server_url: str | None = None
    banner_url: str | None = None
    avatar_url: str | None = None


class BotDataModel(BaseModel):
    bot_name: str
    prefix: str
    description: str
    tags: list[str]
    invite_url: str | None
    website_url: str | None
    support_server_url: str | None
    banner_url: str | None
    avatar_url: str | None
    approved: bool
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
