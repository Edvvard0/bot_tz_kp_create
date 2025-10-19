from __future__ import annotations

import re
from typing import Any

from aiogram import Router, F, Bot
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from loguru import logger

from app.bot.keyboards.kbs import draft_actions_kb, review_actions_kb
from app.db.database import async_session_maker
from app.db.models.tasks import TaskDAO, ProjectStatus
from app.config import settings

# GPT: используем вынесенный модуль
from app.chat_gpt.service import generate_tg_post
from app.db.models.users import UserDAO  # DAO поверх твоего User(id, username, full_name, is_active)

router = Router(name="gpt_flow")

WELCOME = (
    "Привет! Я помогу быстро создавать:\n"
    "• пост для TG-канала по брифу клиента,\n"
    "• (скоро) объявление для биржи,\n"
    "• (скоро) черновики ТЗ/КП в Google Docs.\n\n"
    "Скинь подряд все сообщения/файлы от клиента, затем нажми «Отправить проект»."
)

# ---- MarkdownV2 экранирование ----
MDV2_SPECIALS = r'[_*[\]()~`>#+\-=|{}.!]'

def escape_md_v2(text: str) -> str:
    if not text:
        return ""
    return re.sub(rf'({MDV2_SPECIALS})', r'\\\1', text)


# ---------------- FSM ----------------
class Draft(StatesGroup):
    collecting = State()
    reviewing = State()


def _append_to_draft(data: dict[str, Any], msg: Message):
    texts: list[str] = data.get("texts", [])
    files: list[str] = data.get("files", [])

    if msg.text:
        texts.append(msg.text)
    if msg.caption:
        texts.append(msg.caption)

    if msg.photo:
        files.append("Фото")
    if msg.document:
        files.append(f"Документ: {msg.document.file_name or 'без имени'}")
    if msg.audio:
        files.append(f"Аудио: {msg.audio.file_name or 'audio'}")
    if msg.voice:
        files.append("Голосовое")
    if msg.video:
        files.append("Видео")
    if msg.video_note:
        files.append("Видео-кружок")

    data["texts"] = texts
    data["files"] = files


def _compose_brief_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    texts = data.get("texts") or []
    files = data.get("files") or []
    if texts:
        parts.append("Текстовые сообщения:\n" + "\n\n".join(texts))
    if files:
        parts.append("Вложения:\n- " + "\n- ".join(files))
    return "\n\n".join(parts).strip() or "(пусто)"


# ---------- /start ----------
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    user_id = m.from_user.id
    logger.info("Command /start by user_id={} username='{}'", user_id, m.from_user.username)

    if user_id not in (settings.ADMIN_IDS or []):
        logger.warning("Access denied for user_id={}", user_id)
        await m.answer("⛔ Ошибка доступа. Обратитесь к администратору.")
        return

    async with async_session_maker() as session:
        db_user = await UserDAO.find_one_or_none(session, id=user_id)
        if not db_user:
            await UserDAO.add(
                session,
                id=user_id,
                username=m.from_user.username,
                full_name=m.from_user.full_name,
                is_active=True,
            )
            logger.info("User registered id/tg_id={}", user_id)
        else:
            logger.debug("User already exists tg_id={}", user_id)

    # Подготовим сбор черновика; клавиатуру не меняем
    await state.clear()
    await state.set_state(Draft.collecting)
    await state.update_data(texts=[], files=[])
    await m.answer(WELCOME)


@router.message(Command("new"))
async def cmd_new(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Draft.collecting)
    await state.update_data(texts=[], files=[])
    await m.answer(
        "Ок, начнём новый черновик. Скинь материалы, затем нажми «Отправить проект».",
        reply_markup=draft_actions_kb()
    )


# ---------- Сбор входящих сообщений ----------
@router.message(F.content_type.in_({"text", "photo", "document", "audio", "voice", "video", "video_note"}))
async def on_any_content(m: Message, state: FSMContext):
    """
    ВАЖНО: собираем сообщения всегда.
    Если состояние пустое (после approve/cancel, ребут и т.п.) — автоматически стартуем новый черновик.
    """
    current = await state.get_state()
    if current != Draft.collecting.state:
        logger.debug("No collecting state for user {}, auto-start new draft", m.from_user.id)
        await state.set_state(Draft.collecting)
        await state.update_data(texts=[], files=[])

    data = await state.get_data()
    _append_to_draft(data, m)
    await state.update_data(**data)
    logger.debug(
        "Draft updated by {}: texts={}, files={}",
        m.from_user.id,
        len(data.get("texts", [])),
        len(data.get("files", [])),
    )
    await m.answer(
        "Добавил в черновик. Жми «Отправить проект», когда готово.",
        reply_markup=draft_actions_kb()
    )


@router.callback_query(F.data == "clear_draft")
async def clear_draft(cb: CallbackQuery, state: FSMContext):
    await state.update_data(texts=[], files=[])
    await cb.answer("Черновик очищен")
    await cb.message.edit_text(
        "Черновик очищен. Пришли материалы заново.",
        reply_markup=draft_actions_kb()
    )
    logger.debug("Draft cleared by {}", cb.from_user.id)


# ---------- Генерация поста ----------
@router.callback_query(F.data == "send_project")
async def send_project(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    brief = _compose_brief_text(data)
    logger.info("Generation requested by {} brief_len={}", cb.from_user.id, len(brief))

    await cb.message.edit_text("Генерирую пост, секунду…")
    try:
        gpt_resp = await generate_tg_post(brief)  # {"title":..., "tg_post":...}
        title = gpt_resp["title"].strip()[:255]
        tg_post = gpt_resp["tg_post"].strip()
    except Exception as e:
        logger.exception("GPT generation failed: {}", e)
        await cb.message.edit_text(f"Не получилось сгенерировать пост: {e}\nПопробуй ещё раз.")
        return

    # сохраняем проект (только title + статус)
    async with async_session_maker() as session:
        await TaskDAO.add(session, title=title, status=ProjectStatus.new)
    logger.info("Project saved title='{}' status='{}'", title, ProjectStatus.new.value)

    await state.update_data(gen_title=title, gen_post=tg_post)
    await state.set_state(Draft.reviewing)

    safe_title = escape_md_v2(title)
    safe_post = escape_md_v2(tg_post)
    await cb.message.edit_text(
        f"Предпросмотр поста \\(название задачи: *{safe_title}*\\):\n\n{safe_post}",
        reply_markup=review_actions_kb(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


# ---------- Одобрение / Перегенерация / Отмена ----------
@router.callback_query(Draft.reviewing, F.data == "approve_post")
async def approve_post(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    title = data.get("gen_title") or ""
    tg_post = data.get("gen_post") or ""

    safe_title = escape_md_v2(title)
    safe_post = escape_md_v2(tg_post)

    header = escape_md_v2("✅ Одобрено и сохранено.")
    label_title = escape_md_v2("Название")
    label_post = escape_md_v2("Пост")

    await cb.message.edit_text(
        f"{header}\n\n{label_title}: *{safe_title}*\n\n{label_post}:\n{safe_post}",
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info("Post approved by {} title='{}'", cb.from_user.id, title)

    # 🔁 СРАЗУ ГОТОВЫ К НОВОМУ ПРОЕКТУ
    await state.set_state(Draft.collecting)
    await state.update_data(texts=[], files=[])
    # отдельное уведомление не обязательно, но можно:
    # await cb.message.answer("Готов к следующему проекту. Присылай материалы и жми «Отправить проект».", reply_markup=draft_actions_kb())


@router.callback_query(Draft.reviewing, F.data == "regen_post")
async def regen_post(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brief = _compose_brief_text(data)
    await cb.message.edit_text("Перегенирую…")
    logger.info("Regeneration requested by {} brief_len={}", cb.from_user.id, len(brief))

    try:
        gpt_resp = await generate_tg_post(brief)
    except Exception as e:
        logger.exception("GPT regeneration failed: {}", e)
        await cb.message.edit_text(f"Ошибка генерации: {e}")
        return

    await state.update_data(gen_title=gpt_resp["title"], gen_post=gpt_resp["tg_post"])

    safe_post = escape_md_v2(gpt_resp["tg_post"])
    await cb.message.edit_text(
        f"Новая версия:\n\n{safe_post}",
        reply_markup=review_actions_kb(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


@router.callback_query(Draft.reviewing, F.data == "cancel_review")
async def cancel_review(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Отменил. Чтобы начать заново — пришли материалы или /new.")
    logger.info("Review cancelled by {}", cb.from_user.id)
    # 🔁 Авто-возврат в сбор нового черновика
    await state.set_state(Draft.collecting)
    await state.update_data(texts=[], files=[])