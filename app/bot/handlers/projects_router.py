from __future__ import annotations
import re
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery
from loguru import logger

from app.config import settings
from app.db.database import async_session_maker
from app.db.models.tasks import TaskDAO, ProjectStatus
from app.bot.keyboards.kbs import (
    projects_nav_kb,
    status_choice_kb,
    persistent_projects_keyboard,
)
from app.scheduler.reminders import schedule_new_task_reminder, cancel_task_reminder

router = Router(name="projects")

# --- MarkdownV2 escaping ---
MDV2_SPECIALS = r'[_*[\]()~`>#+\-=|{}.!]'
def escape_md_v2(text: str) -> str:
    if not text:
        return ""
    return re.sub(rf'({MDV2_SPECIALS})', r'\\\1', text)


# --- Рендер карточки проекта ---
def render_project_md(
    title: str,
    status_label: str,
    created_str: str,
    index: int,
    total: int
) -> str:
    safe_title = escape_md_v2(title)
    safe_status = escape_md_v2(status_label)
    safe_created = escape_md_v2(created_str)
    header = escape_md_v2("📁 Проект")
    status_cap = escape_md_v2("Статус")
    created_cap = escape_md_v2("Создан")
    pos_cap = escape_md_v2("Позиция")
    return (
        f"{header}\n\n"
        f"*{safe_title}*\n"
        f"{status_cap}: {safe_status}\n"
        f"{created_cap}: {safe_created}\n"
        f"{pos_cap}: {index+1}/{total}"
    )


# --- Хелпер: показать проект по индексу от новых к старым ---
async def _send_project_by_index(message_or_cb, index: int):
    async with async_session_maker() as session:
        total = await TaskDAO.count_all(session)
        if total == 0:
            text = escape_md_v2("Список проектов пуст.")
            if isinstance(message_or_cb, Message):
                await message_or_cb.answer(
                    text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    reply_markup=persistent_projects_keyboard(),
                )
            else:
                await message_or_cb.message.edit_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            return

        # нормализуем индекс в диапазон [0, total-1] (циклическая навигация)
        index_norm = (index % total + total) % total

        # ⚠️ TaskDAO.get_by_offset_desc должен возвращать объект с полями:
        # id:int, title:str, status:str (РУССКИЙ), created_at:str|'ДД.ММ.ГГГГ ЧЧ:ММ'
        task = await TaskDAO.get_by_offset_desc(session, index_norm)
        if not task:
            text = escape_md_v2("Не удалось загрузить проект.")
            if isinstance(message_or_cb, Message):
                await message_or_cb.answer(text, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await message_or_cb.message.edit_text(text, parse_mode=ParseMode.MARKDOWN_V2)
            return

        status_label = str(task.status)
        created_str = task.created_at or "-"
        md = render_project_md(task.title, status_label, created_str, index_norm, total)
        kb = projects_nav_kb(task_id=task.id, index=index_norm, total=total)

        if isinstance(message_or_cb, Message):
            await message_or_cb.answer(md, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)
        else:
            await message_or_cb.message.edit_text(md, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=kb)


# --- Кнопка "📁 Проекты" (reply-клавиатура) ---
@router.message(F.text == "📁 Проекты")
async def show_projects_entry(m: Message):
    logger.info("Projects list requested by user {}", m.from_user.id)
    await _send_project_by_index(m, index=0)


# --- Навигация ---
@router.callback_query(F.data.startswith("proj_nav:prev:"))
async def proj_prev(cb: CallbackQuery):
    _, _, s_index = cb.data.split(":")
    index = int(s_index) - 1
    await _send_project_by_index(cb, index)

@router.callback_query(F.data.startswith("proj_nav:next:"))
async def proj_next(cb: CallbackQuery):
    _, _, s_index = cb.data.split(":")
    index = int(s_index) + 1
    await _send_project_by_index(cb, index)

@router.callback_query(F.data == "proj_nav:nop")
async def proj_nop(cb: CallbackQuery):
    await cb.answer(" ")

@router.callback_query(F.data.startswith("proj_nav:back:"))
async def proj_back(cb: CallbackQuery):
    _, _, s_index = cb.data.split(":")
    index = int(s_index)
    await _send_project_by_index(cb, index)


# --- Изменение статуса (показ вариантов) ---
@router.callback_query(F.data.startswith("proj_nav:status:"))
async def proj_status_menu(cb: CallbackQuery):
    _, _, s_task_id, s_index = cb.data.split(":")
    task_id = int(s_task_id); index = int(s_index)
    kb = status_choice_kb(task_id=task_id, index=index)
    await cb.message.edit_reply_markup(reply_markup=kb)
    await cb.answer("Выберите новый статус")


# --- Применить новый статус + уведомление «второму партнёру» ---
@router.callback_query(F.data.startswith("proj_set_status:"))
async def proj_set_status(cb: CallbackQuery, bot: Bot):
    _, s_task_id, s_index, enum_name = cb.data.split(":")
    task_id = int(s_task_id); index = int(s_index)

    if enum_name not in ProjectStatus.__members__:
        await cb.answer("Неизвестный статус", show_alert=True)
        return
    new_status_ru = ProjectStatus[enum_name].value

    async with async_session_maker() as session:
        updated = await TaskDAO.update(session, {"id": task_id}, status=new_status_ru)
        if not updated:
            await cb.answer("Не удалось обновить статус", show_alert=True)
            return
        task = await TaskDAO.find_one_or_none_by_id(session, task_id)

    logger.info("Task {} status changed to '{}' by {}", task_id, new_status_ru, cb.from_user.id)
    await cb.answer("Статус обновлён")

    # 🔔 управление напоминаниями
    if new_status_ru == ProjectStatus.new.value:
        schedule_new_task_reminder(task_id)
    else:
        cancel_task_reminder(task_id)

    # уведомим «второго партнёра»
    actor = cb.from_user.id
    if actor == settings.BUSINESS_PARTNER_ID:
        recipients = [settings.TEAM_PARTNER_ID]
    elif actor == settings.TEAM_PARTNER_ID:
        recipients = [settings.BUSINESS_PARTNER_ID]
    else:
        recipients = [uid for uid in (settings.ADMIN_IDS or []) if uid != actor]

    title = getattr(task, "title", "") or ""
    created_at = getattr(task, "created_at", None)
    created_str = created_at.strftime("%d.%m.%Y %H:%M") if created_at else "-"

    def esc(x: str) -> str:
        import re
        return re.sub(r'([_*[\]()~`>#+\-=|{}.!])', r'\\\1', x or "")

    header = esc("🔔 Изменён статус проекта")
    msg = f"{header}\n\n*{esc(title)}*\nСтатус: {esc(new_status_ru)}\nСоздан: {esc(created_str)}"

    for uid in recipients:
        try:
            await bot.send_message(chat_id=uid, text=msg, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.exception("Notify partner {} failed: {}", uid, e)

    # перерисуем карточку
    await _send_project_by_index(cb, index=index)

