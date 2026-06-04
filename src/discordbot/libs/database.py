import asyncpg

from functools import wraps

from libs.origin_handler import BotAddDataModel
import libs.config as config


class ProductionDatabase:

    def __init__(self):
        self.pool = None

    async def setup(self):
        self.pool = await asyncpg.create_pool(f"postgresql://{config.POSTGRESQL_USER}:{config.POSTGRESQL_PASSWORD}@{config.POSTGRESQL_HOST_NAME}:{config.POSTGRESQL_PORT}/{config.POSTGRESQL_DATABASE_NAME}")

        async with self.pool.acquire() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS bot_data (bot_id bigint NOT NULL, user_id bigint NOT NULL, bot_name varchar(50) NOT NULL, prefix varchar(10) NOT NULL, description text, tags text, invite_url text, website_url text, support_server_url text, banner_url text, avatar_url text, approved boolean NOT NULL, approved_at timestamp, created_at timestamp NOT NULL, updated_at timestamp)"
            )
        return self.pool

    def check_connection(func):
        @wraps(func)
        async def inner(self, *args, **kwargs):
            self.pool = self.pool or await self.setup()
            return await func(self, *args, **kwargs)

        return inner

    @check_connection
    async def execute(self, sql):
        async with self.pool.acquire() as con:
            await con.execute(sql)

    @check_connection
    async def fetch(self, sql):
        async with self.pool.acquire() as con:
            data = await con.fetch(sql)
        return data

    @check_connection
    async def add_request_bot_data(self, user_id: int, bot_id: int, data: BotAddDataModel):
        """Add a bot data to the database."""
        async with self.pool.acquire() as con:
            await con.execute(
                "INSERT INTO bot_data (bot_id, user_id, bot_name, prefix, description, tags, invite_url, website_url, support_server_url, banner_url, avatar_url, approved, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, false, now(), now())",
                bot_id, user_id, data.bot_name, data.prefix, data.description, ','.join(data.tags), data.invite_url, data.website_url, data.support_server_url, data.banner_url, data.avatar_url)

    @check_connection
    async def get_bot_data(self, user_id: int, bot_id: int):
        """Get a bot data from the database."""
        async with self.pool.acquire() as con:
            data = await con.fetch("SELECT * FROM bot_data WHERE bot_id = $1 AND user_id = $2", bot_id, user_id)
            if not data:
                return None
            return data[0]

    @check_connection
    async def get_duplicate_bot_data(self, user_id: int, bot_id: int) -> bool:
        """Get Bool a duplicate bot data from the database."""
        data = await self.get_duplicate_bot_data(user_id, bot_id)
        if not data:
            return False
        else:
            return True

    @check_connection
    async def update_bot_data(self, user_id: int, bot_id: int, data: BotAddDataModel):
        """Update a bot data from the database."""
        async with self.pool.acquire() as con:
            await con.execute()


if config.DEBUG:
    Database = ProductionDatabase
else:
    Database = ProductionDatabase
