import platform

from datetime import datetime, timedelta, timezone

import discord
from discord import Game
from discord.ext import commands


class Log(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        await self.bot.wait_until_ready()
        app_info = self.bot.application
        if app_info:
            guild_count = app_info.approximate_guild_count
        else:
            guild_count = 0

        jst = datetime.now(timezone.utc) + timedelta(hours=9)
        dpy_ver = discord.__version__
        python_var = platform.python_version()
        self.bot.logger.info('--------------------------------')
        self.bot.logger.info(jst.strftime('%Y/%m/%d %H:%M:%S'))
        self.bot.logger.info(f'{self.bot.user.name} ({self.bot.user.id})')
        self.bot.logger.info(f'{guild_count} servers')
        self.bot.logger.info(f'discord.py {dpy_ver} python {python_var}')
        self.bot.logger.info('--------------------------------')

        # log_channel = await self.bot.fetch_channel(ON_READY_CHANNEL_ID)
        # if log_channel:
        #     today_stamp = math.floor(datetime.utcnow().timestamp())
        #     embed = Embed(title='on_ready')
        #     embed.add_field(name='NowTime', value=f'<t:{today_stamp}:d> <t:{today_stamp}:T>', inline=False)
        #     embed.add_field(name='Servers', value=f'{guild_count}', inline=False)
        #     await log_channel.send(embed=embed)

        await self.bot.change_presence(
            activity=Game(name='Discord Bot Database'),
        )


async def setup(bot):
    await bot.add_cog(Log(bot))
