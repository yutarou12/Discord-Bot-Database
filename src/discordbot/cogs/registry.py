import discord
from discord import app_commands
from discord.ext import commands

from libs.models import BotSearchFilters
from libs.views import BotPageView, BotRegistrationPanelView, EntrySelectionView


class RegistryCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def service(self):
        return self.bot.service

    @app_commands.command(
        name="register",
        description="Botを登録します"
    )
    async def register(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            view=BotRegistrationPanelView(self.service, interaction.user.id),
            ephemeral=True,
        )

    @app_commands.command(
        name="update",
        description="自分が登録したBotを更新します",
    )
    async def update(self, interaction: discord.Interaction) -> None:
        entries = self.service.get_owned_bots(interaction.user.id)
        if not entries:
            await interaction.response.send_message("更新できる Bot がありません。先に登録してください。", ephemeral=True)
            return

        await interaction.response.send_message(
            view=EntrySelectionView(self.service, entries, "update", interaction.user.id),
            ephemeral=True,
        )

    @app_commands.command(
        name="list",
        description="Bot一覧をページ表示します"
    )
    @app_commands.describe(page="表示するページ番号")
    async def list_bots(self, interaction: discord.Interaction, page: int = 1) -> None:
        page_data = self.service.list_page(page=page, page_size=5)
        await interaction.response.send_message(
            view=BotPageView(lambda next_page: self.service.list_page(page=next_page, page_size=5), page_data, title="登録済みBot一覧")
        )

    @app_commands.command(
        name="search",
        description="Botを検索します"
    )
    @app_commands.describe(
        prefix="prefix の部分一致検索",
        name="Bot名の部分一致検索",
        genre="ジャンルの部分一致検索",
        bot_id="Bot ID の完全一致検索",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        prefix: str | None = None,
        name: str | None = None,
        genre: str | None = None,
        bot_id: int | None = None,
    ) -> None:
        if prefix is None and name is None and genre is None and bot_id is None:
            await interaction.response.send_message("少なくとも 1 つの検索条件を指定してください。", ephemeral=True)
            return

        filters = BotSearchFilters(
            bot_id=bot_id,
            prefix=prefix,
            name=name,
            genre=genre,
        )
        page_data = self.service.search_page(
            filters=filters,
            page=1,
            page_size=5,
        )
        await interaction.response.send_message(
            view=BotPageView(
                lambda next_page: self.service.search_page(filters=filters, page=next_page, page_size=5),
                page_data,
                title="検索結果",
            )
        )

    @app_commands.command(
        name="delete",
        description="自分が登録したBotを削除します"
    )
    async def delete(self, interaction: discord.Interaction) -> None:
        entries = self.service.get_owned_bots(interaction.user.id)
        if not entries:
            await interaction.response.send_message("削除できる Bot がありません。", ephemeral=True)
            return

        await interaction.response.send_message(
            view=EntrySelectionView(self.service, entries, "delete", interaction.user.id),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RegistryCog(bot))
