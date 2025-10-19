from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from app.config import settings


class AllowAdminsOnly(BaseMiddleware):
    def __init__(self, admin_ids: list[int]):
        super().__init__()
        self.admin_ids = set(admin_ids)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None or user_id not in self.admin_ids:
            # молча игнорируем или отвечаем — выбери поведение
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещён.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещён.", show_alert=True)
            return

        return await handler(event, data)


def build_auth_middleware():
    return AllowAdminsOnly(admin_ids=list(settings.ADMIN_IDS or []))
