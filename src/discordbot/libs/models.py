from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class BotEntry:
    id: int
    bot_id: int
    owner_id: int
    name: str
    prefix: str
    genre: str
    description: str
    invite_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class BotEntryPayload:
    bot_id: int
    name: str
    prefix: str
    genre: str
    description: str
    invite_url: str | None = None


@dataclass(slots=True)
class BotEntryUpdatePayload:
    name: str
    prefix: str
    genre: str
    description: str
    invite_url: str | None = None


@dataclass(slots=True)
class BotSearchFilters:
    bot_id: int | None = None
    prefix: str | None = None
    name: str | None = None
    genre: str | None = None
