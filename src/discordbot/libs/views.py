from typing import Sequence

import discord
from discord import ui

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


class BotRegistrationModal(ui.Modal, title="Bot登録"):
    bot_id = ui.TextInput(label="Bot ID", placeholder="123456789012345678", required=True)
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
    # invite_url = ui.TextInput(
    #     label="招待URL",
    #     placeholder="https://discord.com/api/oauth2/authorize?...",
    #     required=False,
    #     max_length=500,
    # )

    def __init__(self, service: BotRegistrationService, owner_id: int) -> None:
        super().__init__(timeout=300)
        self._service = service
        self._owner_id = owner_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            entry = self._service.register_bot(
                owner_id=self._owner_id,
                bot_id=int(self.bot_id.value),
                name=str(self.name.value),
                prefix=str(self.prefix.value),
                genre=str(self.genre.value),
                description=str(self.description.value),
                invite_url=None,
            )
        except (ValidationError, DuplicateBotError) as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        except Exception:
            await interaction.response.send_message("登録に失敗しました。時間をおいて再度お試しください。", ephemeral=True)
            raise

        view = BotSavedView("登録しました。", entry)
        await interaction.response.send_message(view=view, ephemeral=True)


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


class BotRegistrationButton(ui.Button):
    def __init__(self, service, author_id):
        self._service = service
        self._author_id = author_id
        super().__init__(label="登録フォームを開く", style=discord.ButtonStyle.green)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._author_id:
            return await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
        return await interaction.response.send_modal(BotRegistrationModal(self._service, self._author_id))


class BotRegistrationPanelView(ui.LayoutView):
    row = ui.ActionRow()

    def __init__(self, service: BotRegistrationService, author_id: int) -> None:
        super().__init__(timeout=300)
        container = ui.Container(
            ui.TextDisplay("# Discord Bot 登録パネル"),
            ui.Separator(spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(
                "- `登録` を押すと登録フォームを開きます。\n"
                "- 登録後は一覧・検索・更新・削除の各コマンドで管理できます。"
            ),
            accent_colour=discord.Color.blurple())

        self.row.add_item(BotRegistrationButton(service, author_id))
        self.add_item(container)
        self.remove_item(self.row)
        self.add_item(self.row)


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
