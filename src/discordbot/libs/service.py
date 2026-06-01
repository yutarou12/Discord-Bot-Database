from dataclasses import dataclass
from urllib.parse import urlparse

from libs.models import BotEntry, BotEntryPayload, BotEntryUpdatePayload, BotSearchFilters
from libs.storage import BotRepository


class ValidationError(ValueError):
    pass


@dataclass(slots=True)
class BotPage:
    entries: list[BotEntry]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.total == 0:
            return 1
        return ((self.total - 1) // self.page_size) + 1


class BotRegistrationService:
    def __init__(self, repository: BotRepository) -> None:
        self._repository = repository

    @staticmethod
    def _require_text(value: str, field_name: str, *, min_length: int = 1, max_length: int | None = None) -> str:
        cleaned = value.strip()
        if len(cleaned) < min_length:
            raise ValidationError(f"{field_name} は空にできません。")
        if max_length is not None and len(cleaned) > max_length:
            raise ValidationError(f"{field_name} は {max_length} 文字以内で入力してください。")
        return cleaned

    @staticmethod
    def _normalize_optional_url(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValidationError("招待 URL は http または https の URL を指定してください。")
        return cleaned

    @staticmethod
    def _require_bot_id(value: int) -> int:
        if value <= 0:
            raise ValidationError("Bot ID は 1 以上の整数で入力してください。")
        return value

    def register_bot(
        self,
        *,
        owner_id: int,
        bot_id: int,
        name: str,
        prefix: str,
        genre: str,
        description: str,
        invite_url: str | None,
    ) -> BotEntry:
        payload = BotEntryPayload(
            bot_id=self._require_bot_id(bot_id),
            name=self._require_text(name, "Bot名", max_length=200),
            prefix=self._require_text(prefix, "プレフィックス", max_length=32),
            genre=self._require_text(genre, "ジャンル", max_length=80),
            description=self._require_text(description, "説明", max_length=2000),
            invite_url=self._normalize_optional_url(invite_url),
        )
        return self._repository.create_entry(owner_id, payload)

    def update_bot(
        self,
        *,
        entry_id: int,
        owner_id: int,
        name: str,
        prefix: str,
        genre: str,
        description: str,
        invite_url: str | None,
    ) -> BotEntry:
        payload = BotEntryUpdatePayload(
            name=self._require_text(name, "Bot名", max_length=200),
            prefix=self._require_text(prefix, "プレフィックス", max_length=32),
            genre=self._require_text(genre, "ジャンル", max_length=80),
            description=self._require_text(description, "説明", max_length=2000),
            invite_url=self._normalize_optional_url(invite_url),
        )
        return self._repository.update_entry(entry_id, owner_id, payload)

    def delete_bot(self, *, entry_id: int, owner_id: int) -> None:
        self._repository.delete_entry(entry_id, owner_id)

    def get_owned_bots(self, owner_id: int) -> list[BotEntry]:
        return self._repository.list_owner_entries(owner_id)

    def list_page(self, *, page: int, page_size: int = 5) -> BotPage:
        if page < 1:
            raise ValidationError("ページ番号は 1 以上で指定してください。")
        total = self._repository.count_entries()
        offset = (page - 1) * page_size
        entries = self._repository.list_entries(limit=page_size, offset=offset)
        return BotPage(entries=entries, total=total, page=page, page_size=page_size)

    def search_page(
        self,
        *,
        filters: BotSearchFilters,
        page: int,
        page_size: int = 5,
    ) -> BotPage:
        if page < 1:
            raise ValidationError("ページ番号は 1 以上で指定してください。")
        total = self._repository.count_search_entries(filters)
        offset = (page - 1) * page_size
        entries = self._repository.search_entries(filters, limit=page_size, offset=offset)
        return BotPage(entries=entries, total=total, page=page, page_size=page_size)

    def get_bot(self, entry_id: int) -> BotEntry | None:
        return self._repository.get_entry(entry_id)
