from __future__ import annotations

from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, Message
from redis.asyncio import Redis


class MediaService:
    """
    Caches Telegram file_id in Redis to avoid re-uploading media on broadcasts.
    """

    def __init__(self, redis_conn: Redis, key_prefix: str = "media:file_id:"):
        self.redis = redis_conn
        self.key_prefix = key_prefix

    def _redis_key(self, media_key: str) -> str:
        return f"{self.key_prefix}{media_key}"

    async def get_file_id(
        self,
        *,
        bot: Bot,
        media_key: str,
        file_path: str,
        admin_chat_id: int,
    ) -> str:
        cached = await self.redis.get(self._redis_key(media_key))
        if cached:
            return cached

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {file_path}")

        sent: Message = await bot.send_photo(
            chat_id=admin_chat_id,
            photo=FSInputFile(path=str(path)),
            caption=f"[cache-warmup] {media_key}",
        )
        file_id = sent.photo[-1].file_id
        await self.redis.set(self._redis_key(media_key), file_id)

        try:
            await bot.delete_message(chat_id=admin_chat_id, message_id=sent.message_id)
        except Exception:
            pass

        return file_id
