import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.projects_router import router as projects_router
from app.bot.handlers.router import router
from app.bot.middleware.auth import build_auth_middleware
from app.config import settings
from app.logging_setup import setup_logging


async def main():
    setup_logging()

    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # middleware для сообщений и колбэков
    auth = build_auth_middleware()
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    dp.include_router(projects_router)
    dp.include_router(router)

    print("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
