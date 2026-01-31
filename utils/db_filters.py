from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from database import get_user


class DBStateFilter(BaseFilter):
    """Filter messages by user's state stored in the database.

    This prevents catch-all @router.message() handlers in other modules
    from intercepting messages that belong to a different flow.
    """

    def __init__(self, *states: str):
        self.states = set(states)

    async def __call__(self, message: Message) -> bool:
        user = await get_user(message.from_user.id)
        if not user:
            return False
        return (user.get("state") or "") in self.states
