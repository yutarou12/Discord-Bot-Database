import logging
import os
import sys
from typing import Sequence

import discord
from discord import ui
from discord.enums import TextStyle
from discord.components import SelectOption

from libs.database import Database
from libs.config import REQUEST_CHANNEL_ID
from libs.origin_handler import BotInputDataModel, BotAddDataModel
from libs.models import BotEntry, BotSearchFilters
from libs.service import BotPage, BotRegistrationService, ValidationError
from libs.storage import DuplicateBotError, EntryNotFoundError, PermissionError


def _chunk_text(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        parts.append(text[start:start + limit])
        start += limit
    return parts


def _entry_summary(entry: BotEntry) -> str:
    invite_text = entry.invite_url or "未設定"
    return (
        f"**Bot名**: {entry.name}\n"
        f"**Bot ID**: {entry.bot_id}\n"
        f"**プレフィックス**: {entry.prefix}\n"
        f"**ジャンル**: {entry.genre}\n"
        f"**説明**: {entry.description}\n"
        f"**招待URL**: {invite_text}\n"
        f"**登録者**: <@{entry.owner_id}>"
    )


async def send_request_channel(client, user_id: int, data: BotAddDataModel) -> None:
    request_data = BotAddDataModel.model_validate(data)

    channel = client.get_channel(REQUEST_CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(REQUEST_CHANNEL_ID)
        except Exception:
            logging.getLogger(__name__).exception("REQUEST_CHANNEL_ID のチャンネルを取得できませんでした。")
            return

    def _value(text: str | None) -> str:
        return text if text else "未設定"

    tags_text = ", ".join(request_data.tags) if request_data.tags else "未設定"

    view = discord.ui.LayoutView(timeout=None)
    container = ui.Container(
        ui.TextDisplay("# Discord Bot 登録申請"),
        ui.Separator(),
        ui.TextDisplay(f"**BotID**: {_value(str(request_data.bot_id))}"),
        ui.TextDisplay(f"**Bot名**: {_value(request_data.bot_name)}"),
        ui.TextDisplay(f"**プレフィックス**: {_value(request_data.prefix)}"),
        ui.TextDisplay(f"**説明**: {_value(request_data.description)}"),
        ui.TextDisplay(f"**タグ**: {tags_text}"),
        ui.TextDisplay(f"**招待URL**: {_value(request_data.invite_url)}"),
        ui.TextDisplay(f"**ウェブサイトURL**: {_value(request_data.website_url)}"),
        ui.TextDisplay(f"**サポートサーバーURL**: {_value(request_data.support_server_url)}"),
        ui.TextDisplay(f"**バナーURL**: {_value(request_data.banner_url)}"),
        ui.TextDisplay(f"**アイコンURL**: {_value(request_data.avatar_url)}"),
        accent_colour=discord.Color.orange()
    )

    view.add_item(container)

    action_row = ui.ActionRow()
    action_row.add_item(ui.Button(label="承認する", style=discord.ButtonStyle.green, disabled=True))
    action_row.add_item(ui.Button(label="キャンセルする", style=discord.ButtonStyle.gray, disabled=True))
    view.add_item(action_row)

    await client.db.add_request_bot_data(user_id, request_data.bot_id, request_data)
    await channel.send(view=view)


def generate_registration_view(db: Database, owner_id: int, cache: BotInputDataModel) -> discord.ui.LayoutView:
    """登録ViewのUILayoutViewの生成"""
    container = generate_registration_container(db=db, owner_id=owner_id, cache=cache)
    view = discord.ui.LayoutView()
    view.add_item(container)

    return view


def generate_registration_container(db: Database, owner_id: int, cache: BotInputDataModel) -> discord.ui.Container:
    """登録ViewのUIコンテナの生成"""
    container = ui.Container(
        ui.TextDisplay(f"# Discord Bot 登録パネル"),
        ui.TextDisplay(f"- **BotID** - {cache.bot_id}\n`登録後は一覧・検索・更新・削除の各コマンドで管理できます`"),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**名前** - {cache.bot_name or ''}"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="name")
        ),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**プレフィックス** - {cache.prefix or ''}"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="prefix")
        ),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**概要**{"\n```\n" if cache.description else "" }{cache.description or ''}{ "\n```" if cache.description else "" }"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="description")
        ),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**招待リンク** - {cache.invite_url or ''}"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="invite_url")
        ),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**公式サイト** - {cache.support_server_url or ''}"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="support_server_url")
        ),
        ui.Separator(),
        ui.Section(
            ui.TextDisplay(
                f"**WEBサイト** - {cache.support_server_url or ''}"
            ),
            accessory=BotRegistrationButton(db, owner_id, cache, input_type="web_url")
        ),
        ui.Separator(),
        ui.TextDisplay("**ジャンル**"),
        BotRegistrationPanelViewActionRow(BotRegistrationTagsSelect(db, owner_id, cache)),
        ui.Separator(),
        BotRegistrationPanelViewActionRow(BotRegistrationSubmitButton(db, owner_id, cache)),
        accent_colour=discord.Color.blurple())

    return container


class BotRegistrationModal(ui.Modal):
    def __init__(self, db: Database, owner_id: int, cache: BotInputDataModel,
                 title: str, text: str, description: str, component_style: TextStyle, placeholder: str, max_length: int | None, default: str | None, cache_name: str) -> None:
        super().__init__(title=title, timeout=300)
        self.input = discord.ui.Label(
            text=text,
            description=description,
            component=discord.ui.TextInput(
                style=component_style,
                placeholder=placeholder,
                max_length=max_length,
                default=default
            ),
        )
        self.add_item(self.input)
        self._db = db
        self._owner_id = owner_id
        self._cache = cache
        self._cache_name = cache_name

    async def on_submit(self, interaction: discord.Interaction) -> None:
        setattr(self._cache, self._cache_name, self.input.component.value)

        view = generate_registration_view(db=self._db, owner_id=self._owner_id, cache=self._cache)

        await interaction.response.edit_message(view=view)


class BotRegistrationPrefixModal(ui.Modal, title="入力 - Bot プレフィックス"):
    def __init__(self, db: Database, owner_id: int, cache: BotInputDataModel) -> None:
        super().__init__(timeout=300)
        self.prefix = discord.ui.Label(
            text='プレフィックス',
            description='プレフィックスを入力してください。例: !',
            component=discord.ui.TextInput(
                style=discord.TextStyle.short,
                placeholder='例: !',
                max_length=10,
                default=cache.prefix or ""
            ),
        )
        self.add_item(self.prefix)
        self._db = db
        self._owner_id = owner_id
        self._cache = cache

    async def on_submit(self, interaction: discord.Interaction) -> None:
        prefix = self.prefix.component.value
        self._cache.prefix = prefix

        view = generate_registration_view(db=self._db, owner_id=self._owner_id, cache=self._cache)

        return await interaction.response.edit_message(view=view)


class BotRegistrationButton(ui.Button):
    def __init__(self, db, author_id: int, cache: BotInputDataModel, input_type: str):
        self._db = db
        self._author_id = author_id
        self._input_type = input_type
        self._cache = cache
        super().__init__(label="入力", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
        if self._input_type == "name":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - Bot名", "Bot名", "Botの名前を入力してください。", discord.TextStyle.short, '例: 案内Bot', 50, self._cache.bot_name, "bot_name"))
        elif self._input_type == "prefix":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - プレフィックス", "プレフィックス", "Botのプレフィックスを入力してください。", discord.TextStyle.short, '例: !', 10, self._cache.prefix, "prefix"))
        elif self._input_type == "description":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - 概要", "概要", "Botの概要を入力してください。", discord.TextStyle.long, '例: このBotはサーバーの案内を行います。', 150, self._cache.description, "description"))
        elif self._input_type == "invite_url":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - 招待リンク", "招待リンク", "Botの招待リンクを入力してください。", discord.TextStyle.short, '例: https://discord.com/api/oauth2/authorize?client_id=123456789012345678&permissions=0&scope=bot', None,  self._cache.invite_url, "invite_url"))
        elif self._input_type == "web_url":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - ウェブサイトURL", "ウェブサイトURL", "BotのウェブサイトURLを入力してください。", discord.TextStyle.short, '例: https://example.com', None, self._cache.website_url, "website_url"))
        elif self._input_type == "support_server_url":
            return await interaction.response.send_modal(BotRegistrationModal(self._db, self._author_id, self._cache, "入力 - サポートサーバー", "サポートサーバーURL", "BotのサポートサーバーURLを入力してください。", discord.TextStyle.short, '例: https://discord.gg/sXnAt7C8', 28, self._cache.support_server_url, "support_server_url"))
        return await interaction.response.send_message("不明な入力タイプです。", ephemeral=True)


class BotRegistrationSubmitButton(ui.Button):
    def __init__(self, db: Database, author_id: int, cache: BotInputDataModel):
        self._db = db
        self._author_id = author_id
        self._cache = cache

        super().__init__(label="登録", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)

        bot_add_data_model = BotAddDataModel.model_validate(self._cache)
        view = BotRegistrationSubmitView()
        await interaction.response.edit_message(view=view)

        await send_request_channel(interaction.client, interaction.user.id, self._cache)


class BotRegistrationSubmitView(ui.LayoutView):
    def __init__(self):
        super().__init__(timeout=300)
        container = ui.Container(
            ui.TextDisplay("# Discord Bot 登録パネル"),
            ui.TextDisplay(
                "Botの申請を行いました。承認次第掲載されます。"
            ),
            accent_colour=discord.Color.blurple()
        )

        self.add_item(container)


class BotRegistrationPanelView(ui.LayoutView):
    def __init__(self, db: Database, author_id: int, bot_id: int, bot: discord.User | None) -> None:
        super().__init__(timeout=300)

        cache = BotInputDataModel()
        cache.bot_id = bot_id
        if bot:
            cache.bot_name = bot.name
            cache.avatar_url = bot.avatar.url if bot.avatar else None
            cache.banner_url = bot.banner.url if bot.banner else None

        container = generate_registration_container(db=db, owner_id=author_id, cache=cache)

        self.add_item(container)


class BotRegistrationPanelViewActionRow(ui.ActionRow):
    def __init__(self, select):
        super().__init__()
        self.add_item(select)


class BotRegistrationTagsSelect(ui.Select):
    def __init__(self, db: Database, author_id: int, cache: BotInputDataModel) -> None:
        self._db = db
        self._owner_id = author_id
        self._cache = cache

        options = [
            SelectOption(label='Fun', value='fun', default=True if 'fun' in cache.tags else False),
            SelectOption(label='Server', value='server', default=True if 'server' in cache.tags else False),
            SelectOption(label='Voice', value='voice', default=True if 'voice' in cache.tags else False),
            SelectOption(label='Admin', value='admin', default=True if 'admin' in cache.tags else False),
        ]
        super().__init__(placeholder='Botのジャンルを選択してください。', min_values=1, max_values=4, options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_values = self.values

        self._cache.tags = selected_values
        view = generate_registration_view(db=self._db, owner_id=self._owner_id, cache=self._cache)

        return await interaction.response.edit_message(view=view)


class BotEditModal(ui.Modal, title="Bot更新"):
    name = ui.TextInput(label="Bot名", placeholder="例: 案内Bot", required=True, max_length=200)
    prefix = ui.TextInput(label="プレフィックス", placeholder="例: !", required=True, max_length=32)
    genre = ui.TextInput(label="ジャンル", placeholder="例: 情報 / 音楽 / 管理", required=True, max_length=80)
    description = ui.TextInput(
        label="説明",
        placeholder="このBotの役割を簡潔に説明してください",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=2000,
    )
    invite_url = ui.TextInput(
        label="招待URL",
        placeholder="https://discord.com/api/oauth2/authorize?...",
        required=False,
        max_length=500,
    )

    def __init__(self, service: BotRegistrationService, entry: BotEntry) -> None:
        super().__init__(timeout=300)
        self._service = service
        self._entry = entry
        self.name.default = entry.name
        self.prefix.default = entry.prefix
        self.genre.default = entry.genre
        self.description.default = entry.description
        self.invite_url.default = entry.invite_url or ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            updated = self._service.update_bot(
                entry_id=self._entry.id,
                owner_id=self._entry.owner_id,
                name=str(self.name.value),
                prefix=str(self.prefix.value),
                genre=str(self.genre.value),
                description=str(self.description.value),
                invite_url=str(self.invite_url.value) if self.invite_url.value else None,
            )
        except (ValidationError, EntryNotFoundError, PermissionError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("更新に失敗しました。時間をおいて再度お試しください。", ephemeral=True)
            raise

        await interaction.response.send_message(view=BotSavedView("更新しました。", updated), ephemeral=True)


class BotSavedView(ui.LayoutView):
    def __init__(self, headline: str, entry: BotEntry) -> None:
        super().__init__()
        container = ui.Container(
            ui.TextDisplay(f"# {headline}"),
            ui.Separator(spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(_entry_summary(entry)),
            accent_colour=discord.Color.blurple()
        )

        self.add_item(container)


class BotDeleteConfirmView(ui.LayoutView):
    row = ui.ActionRow()

    def __init__(self, service: BotRegistrationService, entry: BotEntry) -> None:
        super().__init__()
        self._service = service
        self._entry = entry
        container = ui.Container(
            ui.TextDisplay("# Bot を削除しますか？"),
            ui.Separator(spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(_entry_summary(entry)),
            accent_colour=discord.Color.red()
        )

        self.row.add_item(BotDeleteConfirmModalButton.Delete(service, entry))
        self.row.add_item(BotDeleteConfirmModalButton.Cancel())
        self.add_item(container)
        self.remove_item(self.row)
        self.add_item(self.row)


class BotDeleteConfirmModalButton:

    class Delete(ui.Button):
        def __init__(self, service, entry):
            self._service = service
            self._entry = entry
            super().__init__(label="削除する", style=discord.ButtonStyle.red)

        async def callback(self, interaction: discord.Interaction):
            try:
                self._service.delete_bot(entry_id=self._entry.id, owner_id=self._entry.owner_id)
            except (EntryNotFoundError, PermissionError) as error:
                return await interaction.response.send_message(str(error), ephemeral=True)

            except Exception:
                await interaction.response.send_message("削除に失敗しました。時間をおいて再度お試しください。", ephemeral=True)
                raise

            return await interaction.response.edit_message(view=BotSavedView("削除しました。", self._entry))

    class Cancel(ui.Button):
        def __init__(self):
            super().__init__(label="キャンセル", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            return await interaction.response.send_message("削除を取り消しました。", ephemeral=True)


class EntryChoiceSelect(ui.Select):
    def __init__(self, entries: Sequence[BotEntry], mode: str, service: BotRegistrationService) -> None:
        self._entries_by_value = {str(entry.id): entry for entry in entries[:25]}
        self._mode = mode
        self._service = service
        options = [
            discord.SelectOption(
                label=entry.name[:100],
                value=str(entry.id),
                description=f"{entry.genre} / {entry.prefix}",
            )
            for entry in entries[:25]
        ]
        placeholder = "更新する Bot を選択してください" if mode == "update" else "削除する Bot を選択してください"
        super().__init__(placeholder=placeholder, min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        entry = self._entries_by_value.get(self.values[0])
        if entry is None:
            await interaction.response.send_message("選択された Bot が見つかりませんでした。", ephemeral=True)
            return

        if self._mode == "update":
            await interaction.response.send_modal(BotEditModal(self._service, entry))
            return

        await interaction.response.edit_message(view=BotDeleteConfirmView(self._service, entry))


class EntrySelectionView(ui.LayoutView):
    def __init__(self, service: BotRegistrationService, entries: Sequence[BotEntry], mode: str, author_id: int) -> None:
        super().__init__(timeout=300)
        self._service = service
        self._entries = list(entries)
        self._mode = mode
        self._author_id = author_id

        container = ui.Container(accent_colour=discord.Color.orange())
        title = "# 更新対象の Bot を選択してください" if mode == "update" else "# 削除対象の Bot を選択してください"
        container.add_item(ui.TextDisplay(title))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        if not entries:
            container.add_item(ui.TextDisplay("-# 登録されている Bot がありません。"))
            self.add_item(container)
            return

        container.add_item(ui.TextDisplay(f"-# {len(entries)} 件の Bot が見つかりました。"))
        self.add_item(container)

        row = ui.ActionRow()
        row.add_item(EntryChoiceSelect(entries, mode, service))
        self.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._author_id:
            await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
            return False
        return True


class BotPageView(ui.LayoutView):
    row = ui.ActionRow()

    def __init__(self, page_loader, page_data: BotPage, *, title: str) -> None:
        super().__init__(timeout=300)
        self._page_loader = page_loader
        self._page_data = page_data
        self._title = title
        self._render()

    def _render(self) -> None:
        container = ui.Container(accent_colour=discord.Color.blurple())
        container.add_item(ui.TextDisplay(f"# {self._title}"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(ui.TextDisplay(f"-# {self._page_data.page} / {self._page_data.total_pages} ページ  •  全 {self._page_data.total} 件"))

        if not self._page_data.entries:
            container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.large))
            container.add_item(ui.TextDisplay("該当する Bot はありません。"))
        else:
            for entry in self._page_data.entries:
                accessory = (
                    ui.Button(label="招待URL", url=entry.invite_url)
                    if entry.invite_url
                    else ui.Button(label="招待URLなし", style=discord.ButtonStyle.gray, disabled=True)
                )
                section = ui.Section(ui.TextDisplay(_entry_summary(entry)), accessory=accessory)
                container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
                container.add_item(section)

        self.row.add_item(BotPageViewButton.Previous(self._page_data, self._page_loader, self._title))
        self.row.add_item(BotPageViewButton.Next(self._page_data, self._page_loader, self._title))
        self.add_item(container)
        self.remove_item(self.row)
        self.add_item(self.row)


class BotPageViewButton:
    class Previous(ui.Button):
        def __init__(self, page_data, page_loader, title):
            self._page_data = page_data
            self._page_loader = page_loader
            self._title = title
            super().__init__(label="前へ", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            if self._page_data.page <= 1:
                self.disabled = True
                return await interaction.response.send_message("これ以上前のページはありません。", ephemeral=True)
            else:
                self.disabled = False
            page = self._page_loader(self._page_data.page - 1)
            return await interaction.response.edit_message(view=BotPageView(self._page_loader, page, title=self._title))

    class Next(ui.Button):
        def __init__(self, page_data, page_loader, title):
            self._page_data = page_data
            self._page_loader = page_loader
            self._title = title
            super().__init__(label="次へ", style=discord.ButtonStyle.gray)

        async def callback(self, interaction: discord.Interaction):
            if self._page_data.page >= self._page_data.total_pages:
                return await interaction.response.send_message("これ以上次のページはありません。", ephemeral=True)

            page = self._page_loader(self._page_data.page + 1)
            return await interaction.response.edit_message(view=BotPageView(self._page_loader, page, title=self._title))


class SearchPanelView(ui.LayoutView):
    row = ui.ActionRow()

    def __init__(self, service: BotRegistrationService, author_id: int):
        super().__init__(timeout=300)
        self._service = service
        self._author_id = author_id
        container = ui.Container(accent_colour=discord.Color.green())
        container.add_item(ui.TextDisplay("# Bot 検索"))
        container.add_item(ui.Separator(spacing=discord.SeparatorSpacing.small))
        container.add_item(
            ui.TextDisplay(
                "- `prefix`、`名前`、`ジャンル`、`Bot ID` のいずれかを指定できます。\n"
                "- 条件はすべて部分一致で検索します。"
            )
        )
        self.add_item(container)
        self.add_item(self.row)


class SearchPanelViewSearchButton(ui.Button):
    def __init__(self, service: BotRegistrationService, author_id: int):
        self._service = service
        self._author_id = author_id
        super().__init__(label="検索フォームを開く", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:

            return await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
        return await interaction.response.send_modal(SearchModal(self._service, self._author_id))


class SearchModal(ui.Modal, title="Bot検索"):
    bot_id = ui.TextInput(label="Bot ID", required=False, placeholder="123456789012345678")
    prefix = ui.TextInput(label="プレフィックス", required=False, max_length=32)
    name = ui.TextInput(label="Bot名", required=False, max_length=200)
    genre = ui.TextInput(label="ジャンル", required=False, max_length=80)

    def __init__(self, service: BotRegistrationService, owner_id: int):
        super().__init__(timeout=300)
        self._service = service
        self._owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        filters = BotSearchFilters(
            bot_id=int(self.bot_id.value) if self.bot_id.value else None,
            prefix=str(self.prefix.value).strip() or None,
            name=str(self.name.value).strip() or None,
            genre=str(self.genre.value).strip() or None,
        )
        if not any((filters.bot_id, filters.prefix, filters.name, filters.genre)):
            return await interaction.response.send_message("少なくとも 1 つの検索条件を指定してください。", ephemeral=True)

        try:
            page = self._service.search_page(filters=filters, page=1, page_size=5)
        except ValidationError as error:
            return await interaction.response.send_message(str(error), ephemeral=True)

        return await interaction.response.send_message(view=BotPageView(self._service, page, title="検索結果"), ephemeral=True)
