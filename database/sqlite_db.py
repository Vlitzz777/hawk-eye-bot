import logging
import os
from typing import Any, Dict, Optional

import aiosqlite

from config import config

logger = logging.getLogger(__name__)


class UserDB:
    def __init__(self):
        self.db_path = config.DATABASE_PATH
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self):
        # Ensure the parent directory exists (default path is data/bot_users.db)
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY,
                preferred_pair TEXT    DEFAULT 'BTCUSDT',
                risk_percent   REAL    DEFAULT 1.0,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self._db.commit()
        logger.info("SQLite DB ready at %s", self.db_path)

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def is_connected(self) -> bool:
        return self._db is not None

    async def get_or_create_user(self, user_id: int) -> Dict[str, Any]:
        if not self.is_connected:
            await self.connect()

        async with self._db.execute(
            "SELECT preferred_pair, risk_percent FROM users WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            # INSERT OR IGNORE so concurrent calls don't raise UNIQUE violations
            await self._db.execute(
                "INSERT OR IGNORE INTO users (user_id, preferred_pair, risk_percent) "
                "VALUES (?, ?, ?)",
                (user_id, config.PREFERRED_PAIR, config.RISK_DEFAULT_PERCENT),
            )
            await self._db.commit()
            return {
                "preferred_pair": config.PREFERRED_PAIR,
                "risk_percent": config.RISK_DEFAULT_PERCENT,
            }

        return {"preferred_pair": row[0], "risk_percent": float(row[1])}

    async def update_pair(self, user_id: int, pair: str):
        # Ensure the row exists before UPDATE — otherwise UPDATE matches 0 rows.
        await self.get_or_create_user(user_id)
        await self._db.execute(
            "UPDATE users SET preferred_pair = ? WHERE user_id = ?",
            (pair.upper(), user_id),
        )
        await self._db.commit()

    async def update_risk(self, user_id: int, risk_pct: float):
        if not 0.1 <= risk_pct <= 5.0:
            raise ValueError("Risk percentage must be between 0.1% and 5.0%")
        await self.get_or_create_user(user_id)
        await self._db.execute(
            "UPDATE users SET risk_percent = ? WHERE user_id = ?",
            (risk_pct, user_id),
        )
        await self._db.commit()
