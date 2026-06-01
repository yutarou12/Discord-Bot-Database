from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from discordbot.libs.config import load_settings
from discordbot.libs.models import BotSearchFilters
from discordbot.libs.service import BotRegistrationService, ValidationError
from discordbot.libs.storage import DuplicateBotError, EntryNotFoundError, PermissionError
from discordbot.libs.config import Settings
from discordbot.libs.storage import BotRepository


class BotCreateRequest(BaseModel):
    bot_id: int = Field(ge=1)
    name: str
    prefix: str
    genre: str
    description: str
    invite_url: str | None = None
    owner_id: int = Field(ge=1)


class BotUpdateRequest(BaseModel):
    name: str
    prefix: str
    genre: str
    description: str
    invite_url: str | None = None
    owner_id: int = Field(ge=1)


class BotSearchRequest(BaseModel):
    prefix: str | None = None
    name: str | None = None
    genre: str | None = None
    bot_id: int | None = Field(default=None, ge=1)


def _serialize_entry(entry):
    return {
        "id": entry.id,
        "bot_id": entry.bot_id,
        "owner_id": entry.owner_id,
        "name": entry.name,
        "prefix": entry.prefix,
        "genre": entry.genre,
        "description": entry.description,
        "invite_url": entry.invite_url,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


def create_app(service: BotRegistrationService, settings: Settings) -> FastAPI:
    app = FastAPI(title="Discord Bot Database API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    def require_api_key(x_api_key: str = Header(default="")) -> None:
        if not settings.api_key:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API key is not configured.")
        if x_api_key != settings.api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key.")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/bots")
    async def list_bots(
        prefix: str | None = None,
        name: str | None = None,
        genre: str | None = None,
        bot_id: int | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> dict[str, object]:
        if page < 1 or page_size < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ページ指定が不正です。")

        filters = BotSearchFilters(bot_id=bot_id, prefix=prefix, name=name, genre=genre)
        if any((prefix, name, genre, bot_id)):
            page_data = service.search_page(filters=filters, page=page, page_size=page_size)
        else:
            page_data = service.list_page(page=page, page_size=page_size)

        return {
            "items": [_serialize_entry(entry) for entry in page_data.entries],
            "total": page_data.total,
            "page": page_data.page,
            "page_size": page_data.page_size,
            "total_pages": page_data.total_pages,
        }

    @app.post("/bots", dependencies=[Depends(require_api_key)])
    async def create_bot(request: BotCreateRequest) -> dict[str, object]:
        try:
            entry = service.register_bot(
                owner_id=request.owner_id,
                bot_id=request.bot_id,
                name=request.name,
                prefix=request.prefix,
                genre=request.genre,
                description=request.description,
                invite_url=request.invite_url,
            )
        except (ValidationError, DuplicateBotError) as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        return _serialize_entry(entry)

    @app.patch("/bots/{entry_id}", dependencies=[Depends(require_api_key)])
    async def update_bot(entry_id: int, request: BotUpdateRequest) -> dict[str, object]:
        try:
            entry = service.update_bot(
                entry_id=entry_id,
                owner_id=request.owner_id,
                name=request.name,
                prefix=request.prefix,
                genre=request.genre,
                description=request.description,
                invite_url=request.invite_url,
            )
        except (ValidationError, EntryNotFoundError, PermissionError) as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        return _serialize_entry(entry)

    @app.delete("/bots/{entry_id}", dependencies=[Depends(require_api_key)])
    async def delete_bot(entry_id: int, owner_id: int) -> dict[str, str]:
        try:
            service.delete_bot(entry_id=entry_id, owner_id=owner_id)
        except (EntryNotFoundError, PermissionError) as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
        return {"status": "deleted"}

    return app


_settings = load_settings()
_repository = BotRepository(_settings.database_url)
_repository.initialize()
_service = BotRegistrationService(_repository)
app = create_app(_service, _settings)
