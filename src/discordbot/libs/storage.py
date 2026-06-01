from datetime import datetime, timezone

from sqlalchemy import BigInteger, Column, DateTime, Integer, MetaData, String, Table, Text, and_, create_engine, delete, func, insert, select, update
from sqlalchemy.engine import Engine

from libs.models import BotEntry, BotEntryPayload, BotEntryUpdatePayload, BotSearchFilters


metadata = MetaData()

bot_entries = Table(
    "bot_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bot_id", BigInteger, nullable=False, unique=True, index=True),
    Column("owner_id", BigInteger, nullable=False, index=True),
    Column("name", String(200), nullable=False),
    Column("prefix", String(32), nullable=False),
    Column("genre", String(80), nullable=False),
    Column("description", Text, nullable=False),
    Column("invite_url", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class StorageError(RuntimeError):
    pass


class DuplicateBotError(StorageError):
    pass


class EntryNotFoundError(StorageError):
    pass


class PermissionError(StorageError):
    pass


class BotRepository:
    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url, future=True)

    def initialize(self) -> None:
        metadata.create_all(self._engine)

    @staticmethod
    def _row_to_entry(row) -> BotEntry:
        return BotEntry(
            id=row.id,
            bot_id=row.bot_id,
            owner_id=row.owner_id,
            name=row.name,
            prefix=row.prefix,
            genre=row.genre,
            description=row.description,
            invite_url=row.invite_url,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def create_entry(self, owner_id: int, payload: BotEntryPayload) -> BotEntry:
        now = self._now()
        statement = insert(bot_entries).values(
            bot_id=payload.bot_id,
            owner_id=owner_id,
            name=payload.name,
            prefix=payload.prefix,
            genre=payload.genre,
            description=payload.description,
            invite_url=payload.invite_url,
            created_at=now,
            updated_at=now,
        )

        try:
            with self._engine.begin() as connection:
                result = connection.execute(statement)
                inserted_id = result.inserted_primary_key[0]
                row = connection.execute(select(bot_entries).where(bot_entries.c.id == inserted_id)).one()
        except Exception as error:  # pragma: no cover - driver differences
            message = str(error).lower()
            if "unique" in message or "duplicate" in message:
                raise DuplicateBotError("同じ Bot ID はすでに登録されています。") from error
            raise StorageError("Bot の登録に失敗しました。") from error

        return self._row_to_entry(row)

    def update_entry(self, entry_id: int, owner_id: int, payload: BotEntryUpdatePayload) -> BotEntry:
        now = self._now()
        with self._engine.begin() as connection:
            existing = connection.execute(select(bot_entries).where(bot_entries.c.id == entry_id)).one_or_none()
            if existing is None:
                raise EntryNotFoundError("対象の Bot が見つかりません。")
            if existing.owner_id != owner_id:
                raise PermissionError("この Bot を更新する権限がありません。")

            connection.execute(
                update(bot_entries)
                .where(bot_entries.c.id == entry_id)
                .values(
                    name=payload.name,
                    prefix=payload.prefix,
                    genre=payload.genre,
                    description=payload.description,
                    invite_url=payload.invite_url,
                    updated_at=now,
                )
            )
            row = connection.execute(select(bot_entries).where(bot_entries.c.id == entry_id)).one()

        return self._row_to_entry(row)

    def delete_entry(self, entry_id: int, owner_id: int) -> None:
        with self._engine.begin() as connection:
            existing = connection.execute(select(bot_entries).where(bot_entries.c.id == entry_id)).one_or_none()
            if existing is None:
                raise EntryNotFoundError("対象の Bot が見つかりません。")
            if existing.owner_id != owner_id:
                raise PermissionError("この Bot を削除する権限がありません。")

            connection.execute(delete(bot_entries).where(bot_entries.c.id == entry_id))

    def get_entry(self, entry_id: int) -> BotEntry | None:
        with self._engine.begin() as connection:
            row = connection.execute(select(bot_entries).where(bot_entries.c.id == entry_id)).one_or_none()
        return None if row is None else self._row_to_entry(row)

    def list_entries(self, *, limit: int, offset: int = 0) -> list[BotEntry]:
        statement = (
            select(bot_entries)
            .order_by(bot_entries.c.created_at.desc(), bot_entries.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        with self._engine.begin() as connection:
            rows = connection.execute(statement).all()
        return [self._row_to_entry(row) for row in rows]

    def list_owner_entries(self, owner_id: int) -> list[BotEntry]:
        statement = (
            select(bot_entries)
            .where(bot_entries.c.owner_id == owner_id)
            .order_by(bot_entries.c.updated_at.desc(), bot_entries.c.id.desc())
        )
        with self._engine.begin() as connection:
            rows = connection.execute(statement).all()
        return [self._row_to_entry(row) for row in rows]

    def search_entries(self, filters: BotSearchFilters, *, limit: int, offset: int = 0) -> list[BotEntry]:
        conditions = []
        if filters.bot_id is not None:
            conditions.append(bot_entries.c.bot_id == filters.bot_id)
        if filters.prefix:
            conditions.append(func.lower(bot_entries.c.prefix).like(f"%{filters.prefix.lower()}%"))
        if filters.name:
            conditions.append(func.lower(bot_entries.c.name).like(f"%{filters.name.lower()}%"))
        if filters.genre:
            conditions.append(func.lower(bot_entries.c.genre).like(f"%{filters.genre.lower()}%"))

        statement = select(bot_entries)
        if conditions:
            statement = statement.where(and_(*conditions))

        statement = statement.order_by(bot_entries.c.created_at.desc(), bot_entries.c.id.desc()).limit(limit).offset(offset)
        with self._engine.begin() as connection:
            rows = connection.execute(statement).all()
        return [self._row_to_entry(row) for row in rows]

    def count_entries(self) -> int:
        statement = select(func.count()).select_from(bot_entries)
        with self._engine.begin() as connection:
            return int(connection.execute(statement).scalar_one())

    def count_search_entries(self, filters: BotSearchFilters) -> int:
        conditions = []
        if filters.bot_id is not None:
            conditions.append(bot_entries.c.bot_id == filters.bot_id)
        if filters.prefix:
            conditions.append(func.lower(bot_entries.c.prefix).like(f"%{filters.prefix.lower()}%"))
        if filters.name:
            conditions.append(func.lower(bot_entries.c.name).like(f"%{filters.name.lower()}%"))
        if filters.genre:
            conditions.append(func.lower(bot_entries.c.genre).like(f"%{filters.genre.lower()}%"))

        statement = select(func.count()).select_from(bot_entries)
        if conditions:
            statement = statement.where(and_(*conditions))
        with self._engine.begin() as connection:
            return int(connection.execute(statement).scalar_one())
