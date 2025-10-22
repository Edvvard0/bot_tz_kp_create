# app/scheduler/reminders.py
from __future__ import annotations

from typing import Dict, Optional
from datetime import datetime, timedelta, timezone
import re

from aiogram import Bot
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from app.config import settings
from app.db.database import async_session_maker
from app.db.models.tasks import TaskDAO, ProjectStatus

# --- singletons ---
_scheduler: Optional[AsyncIOScheduler] = None
_bot: Optional[Bot] = None
_jobs_by_task: Dict[int, str] = {}  # task_id -> job_id


def set_bot(bot: Bot) -> None:
    """Вызывай из main.py сразу после создания Bot."""
    global _bot
    _bot = bot
    logger.info("Reminder module: bot instance injected")


def start_scheduler() -> None:
    """Запуск планировщика (идемпотентно)."""
    global _scheduler
    if _scheduler is None:
        # Московский часовой пояс
        _scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
        _scheduler.start()
        logger.info("Reminder scheduler started (Moscow timezone)")


def _escape_md_v2(text: str) -> str:
    specials = r'[_*[\]()~`>#+\-=|{}.!]'
    return re.sub(rf'({specials})', r'\\\1', text or "")


async def _notify_new_task(task_id: int) -> None:
    """
    Если задача всё ещё 'новый' — отправляем пинг ОБОИМ партнёрам
    И СРАЗУ ставим следующее напоминание через тот же интервал.
    Если статус не 'новый' — цепочку не продолжаем.
    """
    rescheduled = False
    try:
        if _bot is None:
            logger.error("Reminder job: bot is None")
            return

        async with async_session_maker() as session:
            task = await TaskDAO.find_one_or_none_by_id(session, task_id)
            if not task:
                logger.warning("Reminder: task %s not found", task_id)
                return

            if (task.status or "").strip() != ProjectStatus.new.value:
                logger.info("Reminder: task %s status changed to %s, stop chain", task_id, task.status)
                return

            title = getattr(task, "title", "") or "Без названия"
            created_at = getattr(task, "created_at", None)
            moscow_tz = timezone(timedelta(hours=3))
            if created_at:
                created_at_moscow = created_at.astimezone(moscow_tz)
                created_str = created_at_moscow.strftime("%d.%m.%Y %H:%M")
            else:
                created_str = "-"

            header = _escape_md_v2("⏰ Напоминание по проекту")
            body = (
                f"{header}\n\n"
                f"*{_escape_md_v2(title)}*\n"
                f"Статус: {_escape_md_v2(ProjectStatus.new.value)}\n"
                f"Создан: {_escape_md_v2(created_str)}\n\n"
                f"{_escape_md_v2('Нужно обработать проект и продвинуть статус.')}"
            )

            # Отправляем ОБОИМ партнерам из settings
            partners = [settings.BUSINESS_PARTNER_ID, settings.TEAM_PARTNER_ID]

            for partner_id in partners:
                try:
                    await _bot.send_message(
                        chat_id=partner_id,
                        text=body,
                        parse_mode=ParseMode.MARKDOWN_V2
                    )
                    logger.info("Reminder sent to partner %s for task %s", partner_id, task_id)
                except Exception as e:
                    logger.exception("Failed to send reminder to partner %s: {}", partner_id, e)

            # 🔁 задача всё ещё «новая» — ставим следующее напоминание
            schedule_new_task_reminder(task_id)
            rescheduled = True

    except Exception as e:
        logger.exception("Reminder job failed for task %s: {}", task_id, e)
    finally:
        if not rescheduled:
            _jobs_by_task.pop(task_id, None)


def schedule_new_task_reminder(task_id: int, *, delay_seconds: Optional[int] = None) -> None:
    """
    Поставить (или перепоставить) одноразовое напоминание для 'новый'.
    """
    if _scheduler is None:
        logger.error("schedule_new_task_reminder: scheduler not started")
        return
    delay = int(delay_seconds if delay_seconds is not None else settings.REMINDER_DELAY_SECONDS_NEW)
    moscow_tz = timezone(timedelta(hours=3))
    run_at = datetime.now(moscow_tz) + timedelta(seconds=delay)

    job = _scheduler.add_job(
        _notify_new_task,
        trigger=DateTrigger(run_date=run_at),
        args=[task_id],
        id=f"remind:new:{task_id}",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _jobs_by_task[task_id] = job.id
    logger.info("Reminder scheduled for task %s at %s (+%ss)", task_id, run_at.isoformat(), delay)


def cancel_task_reminder(task_id: int) -> None:
    """Отменить текущую напоминалку (цепочку прервётся)."""
    if _scheduler is None:
        return
    job_id = _jobs_by_task.pop(task_id, None)
    if job_id:
        try:
            _scheduler.remove_job(job_id)
            logger.info("Reminder cancelled for task %s", task_id)
        except Exception:
            pass