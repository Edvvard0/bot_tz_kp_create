import asyncio
import signal

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers.projects_router import router as projects_router
from app.bot.handlers.router import router as gpt_router
from app.bot.middleware.auth import build_auth_middleware
from app.config import settings
from app.logging_setup import setup_logging

# планировщик напоминаний
from app.scheduler.reminders import start_scheduler, set_bot as reminders_set_bot

bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

async def main():
    setup_logging()

    # middleware
    auth = build_auth_middleware()
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    # роутеры
    dp.include_router(projects_router)
    dp.include_router(gpt_router)

    # ❗️ запуск планировщика ДОЛЖЕН быть внутри работающего loop
    reminders_set_bot(bot)
    start_scheduler()

    # аккуратное завершение
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    print("Bot started")
    polling = asyncio.create_task(dp.start_polling(bot))
    await stop_event.wait()
    polling.cancel()
    try:
        await polling
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())
