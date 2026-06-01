import os
import asyncio
import logging
import platform
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands

from libs.config import load_settings
from libs.service import BotRegistrationService
from libs.storage import BotRepository

logger = logging.getLogger(__name__)

os.chdir(os.path.dirname(os.path.abspath(__file__)))

extensions_list = [f[:-3] for f in os.listdir("./cogs") if f.endswith(".py")]

allowed_mentions = discord.AllowedMentions(
    everyone=False,
    users=False,
    roles=False
)

def configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


class DiscordBot(commands.Bot):
    def __init__(self, service: BotRegistrationService) -> None:
        intents = discord.Intents.default()
        super().__init__(
            command_prefix=commands.when_mentioned_or("dbd:"),
            intents=intents,
            allowed_mentions=allowed_mentions
        )
        self.service = service

    async def setup_hook(self) -> None:
        try:
            await self.load_extension('jishaku')
        except discord.ext.commands.ExtensionAlreadyLoaded:
            await self.reload_extension('jishaku')
        for ext in extensions_list:
            try:
                await self.load_extension(f'cogs.{ext}')
            except discord.ext.commands.ExtensionAlreadyLoaded:
                await self.reload_extension(f'cogs.{ext}')
                
    async def on_ready(self) -> None:
        jst = datetime.now(timezone.utc) + timedelta(hours=9)
        dpy_ver = discord.__version__
        python_var = platform.python_version()
        logger.info('--------------------------------')
        logger.info(jst.strftime('%Y/%m/%d %H:%M:%S'))
        logger.info(f'{self.user.name} ({self.user.id})')
        logger.info(f'discord.py {dpy_ver} python {python_var}')
        logger.info('--------------------------------')
    

async def main() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)

    if not settings.discord_token:
        raise RuntimeError("DISCORD_BOT_DB_TOKEN を .env に設定してください。")

    repository = BotRepository(settings.database_url)
    repository.initialize()
    service = BotRegistrationService(repository)
    bot = DiscordBot(service)

    try:
        bot.run(settings.discord_token)
    finally:
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
