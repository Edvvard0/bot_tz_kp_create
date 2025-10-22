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

from app.bot.keyboards.kbs import draft_actions_kb, review_actions_kb, persistent_projects_keyboard
from app.db.database import async_session_maker
from app.db.models.tasks import ProjectStatus, TaskDAO
from app.config import settings

# GPT: вынесенный модуль
from app.chat_gpt.service import generate_tg_post
from app.db.models.users import UserDAO  # User(id, username, full_name, is_active)
from app.scheduler.reminders import schedule_new_task_reminder

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


TELEGRAM_MAX = 4096
SAFE_CHUNK = 3500  # запас под экранирование/служебные символы

def _split_text(text: str, max_len: int = SAFE_CHUNK) -> list[str]:
    if not text:
        return [""]
    parts, cur = [], ""
    for line in text.split("\n"):
        # если строка длиннее max_len — рубим её кусками
        while len(line) > max_len:
            parts.append(line[:max_len])
            line = line[max_len:]
        if not cur:
            cur = line
        elif len(cur) + 1 + len(line) <= max_len:
            cur = f"{cur}\n{line}"
        else:
            parts.append(cur)
            cur = line
    if cur:
        parts.append(cur)
    return [p for p in parts if p]

async def send_md_v2_chunked(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    header: str | None = None,
    reply_markup=None
):
    """
    Безопасно шлёт длинные сообщения:
    - экранирует MarkdownV2 полностью (и header, и text);
    - режет на части;
    - reply_markup добавляет только к первой части (если задан).
    ВАЖНО: сюда не передавать "сырые" Markdown-лексемы (*, _, () и т.д.) — всё будет экранировано.
    """
    safe_body = escape_md_v2(text or "")
    chunks = _split_text(safe_body, SAFE_CHUNK)

    first = True
    if header:
        safe_header = escape_md_v2(header)
        # Добавим заголовок отдельным сообщением — без смешивания с телом
        await bot.send_message(
            chat_id=chat_id,
            text=safe_header,
            parse_mode=ParseMode.MARKDOWN_V2
        )

    for ch in chunks:
        await bot.send_message(
            chat_id=chat_id,
            text=ch,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup if first and reply_markup is not None else None
        )
        first = False

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

    # Подготовим сбор черновика; выдаём постоянную клавиатуру «Проекты»
    await state.clear()
    await state.set_state(Draft.collecting)
    await state.update_data(texts=[], files=[])
    await m.answer(WELCOME, reply_markup=persistent_projects_keyboard())


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
    Всегда собираем. Если state пуст — автоматически стартуем новый черновик.
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
    user_id = cb.from_user.id
    data = await state.get_data()
    brief = _compose_brief_text(data)
    logger.info("Generation requested by {} brief_len={}", user_id, len(brief))

    # 1) Черновик — сразу в БД
    draft_title = "Черновик"
    async with async_session_maker() as session:
        task = await TaskDAO.add(
            session,
            title=draft_title,
            status=ProjectStatus.new.value,
            created_by=user_id,
            brief_text=brief,
        )
        task_id = task.id
    logger.info("Draft project saved id={} by={} status='{}'", task_id, user_id, ProjectStatus.new.value)

    # 1.1) Ставим напоминание для 'новый' (сейчас 30 сек из .env)
    schedule_new_task_reminder(task_id)

    # 2) Мгновенные уведомления (без ожидания GPT)
    try:
        if user_id == settings.TEAM_PARTNER_ID:
            await cb.message.edit_text("✅ Заказ принят в работу. Бизнес-партнёр обработает проект.")
            await send_md_v2_chunked(
                bot, settings.BUSINESS_PARTNER_ID,
                text=f"ID: {task_id}\nЗадача принята в работу. Готовим пост.",
                header="🆕 Новый проект",
            )
        else:
            await cb.message.edit_text("Принял. Готовлю предпросмотр…")
            await send_md_v2_chunked(
                bot, settings.TEAM_PARTNER_ID,
                text=f"ID: {task_id}\nЗадача принята в работу.",
                header="🆕 Новый проект",
            )
    except Exception as e:
        logger.exception("Immediate notify failed: {}", e)

    # 3) GPT
    try:
        gpt_resp = await generate_tg_post(brief)
        title = (gpt_resp.get("title") or "").strip()[:255] or "Без названия"
        tg_post = (gpt_resp.get("tg_post") or "").strip()
        logger.info("GPT ok for task {}: title='{}' post_len={}", task_id, title, len(tg_post))
    except Exception as e:
        logger.exception("GPT generation failed: {}", e)
        await cb.message.edit_text("❌ Не удалось сгенерировать пост. Попробуйте ещё раз /new.")
        return

    # 4) Обновим title у задачи
    async with async_session_maker() as session:
        await TaskDAO.update(session, {"id": task_id}, title=title)

    # 5) Рассылка: СНАЧАЛА бриф → ПОТОМ пост (с кнопками, где task_id в callback_data)
    try:
        if user_id == settings.TEAM_PARTNER_ID:
            await send_md_v2_chunked(
                bot, settings.BUSINESS_PARTNER_ID,
                text=f"{title}\n\n{brief}",
                header=f"📎 Сырые материалы клиента (ID: {task_id})",
            )
            await send_md_v2_chunked(
                bot, settings.BUSINESS_PARTNER_ID,
                text=tg_post,
                header="📝 Сгенерированный пост",
                reply_markup=review_actions_kb(task_id),
            )
            await state.set_state(Draft.collecting)
            await state.update_data(texts=[], files=[])
        else:
            await send_md_v2_chunked(
                bot, cb.from_user.id,
                text=f"{title}\n\n{brief}",
                header=f"📎 Сырые материалы клиента (ID: {task_id})",
            )
            await send_md_v2_chunked(
                bot, cb.from_user.id,
                text=tg_post,
                header="📝 Сгенерированный пост",
                reply_markup=review_actions_kb(task_id),
            )
            await send_md_v2_chunked(
                bot, settings.TEAM_PARTNER_ID,
                text=f"ID: {task_id}\nЗадача взята в работу.",
                header=f"🆕 Новый проект: {title}",
            )
    except Exception as e:
        logger.exception("Dispatch (brief+post) failed: {}", e)


# ---------- Одобрение / Перегенерация / Отмена ----------
def _parse_task_id(data: str) -> int | None:
    try:
        return int(data.split(":")[2])
    except Exception:
        return None

@router.callback_query(F.data.startswith("post:approve:"))
async def cb_post_approve(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != settings.BUSINESS_PARTNER_ID:
        await cb.answer("Нет прав на действие", show_alert=True)
        return

    task_id = _parse_task_id(cb.data)
    if not task_id:
        await cb.answer("task_id не найден", show_alert=True)
        return

    # При одобрении считаем, что статус меняется с 'новый' → что-то другое (например, 'составляется тз/кп')
    async with async_session_maker() as session:
        await TaskDAO.update(session, {"id": task_id}, status=ProjectStatus.drafting_tz_kp.value)

    await cb.answer("Одобрено")
    try:
        await cb.message.edit_text("✅ Одобрено и сохранено. Готов к следующему проекту.")
    except Exception:
        pass
    logger.info("Post approved by {} for task {}", cb.from_user.id, task_id)


@router.callback_query(F.data.startswith("post:cancel:"))
async def cb_post_cancel(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != settings.BUSINESS_PARTNER_ID:
        await cb.answer("Нет прав на действие", show_alert=True)
        return

    task_id = _parse_task_id(cb.data)
    if not task_id:
        await cb.answer("task_id не найден", show_alert=True)
        return

    await cb.answer("Отменено")
    try:
        await cb.message.edit_text("❌ Отменено. Чтобы начать заново — пришли материалы или /new.")
    except Exception:
        pass
    logger.info("Post cancel by {} for task {}", cb.from_user.id, task_id)


@router.callback_query(F.data.startswith("post:regen:"))
async def cb_post_regen(cb: CallbackQuery, state: FSMContext, bot: Bot):
    if cb.from_user.id != settings.BUSINESS_PARTNER_ID:
        await cb.answer("Нет прав на действие", show_alert=True)
        return

    task_id = _parse_task_id(cb.data)
    if not task_id:
        await cb.answer("task_id не найден", show_alert=True)
        return

    await cb.answer("Перегенерирую…")

    # берём бриф из БД
    async with async_session_maker() as session:
        task = await TaskDAO.find_one_or_none_by_id(session, task_id)
        if not task or not getattr(task, "brief_text", None):
            await cb.answer("Бриф не найден", show_alert=True)
            return
        brief = task.brief_text

    try:
        gpt_resp = await generate_tg_post(brief)
        new_title = (gpt_resp.get("title") or "").strip()[:255] or "Без названия"
        new_post = (gpt_resp.get("tg_post") or "").strip()

        async with async_session_maker() as session:
            await TaskDAO.update(session, {"id": task_id}, title=new_title)
    except Exception as e:
        logger.exception("Regen failed for task {}: {}", task_id, e)
        await cb.message.answer("❌ Ошибка генерации. Попробуйте ещё раз позже.")
        return

    try:
        await send_md_v2_chunked(
            bot, cb.from_user.id,
            text=new_post,
            header=f"🔁 Новая версия поста (ID: {task_id}) — {new_title}",
            reply_markup=review_actions_kb(task_id),
        )
    except Exception as e:
        logger.exception("Send new version failed: {}", e)