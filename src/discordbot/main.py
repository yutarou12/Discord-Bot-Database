import os
import logging

import discord
from discord.ext import commands

import libs.config as config
from libs.origin_handler import DatetimeFormatter
from libs.service import BotRegistrationService
from libs.storage import BotRepository

os.chdir(os.path.dirname(os.path.abspath(__file__)))

extensions_list = [f[:-3] for f in os.listdir("./cogs") if f.endswith(".py")]

allowed_mentions = discord.AllowedMentions(
    everyone=False,
    users=False,
    roles=False
)


def configure_logging(level_name: str) -> logging.Logger:
    _logger = logging.getLogger("discord")
    _logger.setLevel(getattr(logging, level_name, logging.INFO))
    logging.getLogger('discord.http').setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    dt_fmt = '%Y-%m-%d %H:%M:%S'
    formatter = DatetimeFormatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')

    handler.setFormatter(formatter)
    _logger.addHandler(handler)

    return _logger

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


if __name__ == "__main__":
    logger = configure_logging(config.LOG_LEVEL)

    if not config.DISCORD_BOT_TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN を .env に設定してください。")

    repository = BotRepository(config.DATABASE_URL)
    repository.initialize()
    service = BotRegistrationService(repository)
    bot = DiscordBot(service)
    bot.logger = logger

    bot.run(config.DISCORD_BOT_TOKEN, log_handler=None)
