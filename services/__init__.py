"""
Services: бизнес-логика без привязки к aiogram.
quest, payment, followup, media, broadcast, notification.
Реализация на этапах 3-7.
"""

from .media_service import MediaService

__all__ = ["MediaService"]
