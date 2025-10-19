# app/gpt/service.py
from __future__ import annotations
import json
import re
from typing import Any, List, Dict

from loguru import logger
from openai import AsyncOpenAI

from app.config import settings

# SYSTEM PROMPT можно держать тут для наглядности
SYSTEM_PROMPT = """
Ты помощник, который превращает сырой бриф клиента (несколько сообщений, краткие описания вложений)
в аккуратный пост для TG-канала по заданному шаблону.

Строго верни один JSON-объект БЕЗ Markdown и комментариев такой формы:
{
  "title": "краткое название проекта",
  "tg_post": "текст поста в Markdown по шаблону"
}

Шаблон поста:
❗️ {Название проекта/задачи}
✅ СТАТУС: открыт ✅

✍️ Что за проект:
{одно-два абзаца — самое основное, без воды}

📎 Полное тз по ссылке
{ссылка на гугл документ, если нет — напиши 'добавим после согласования'}

💸 Оплата и сроки: ставит исполнитель

👨‍💻 Кто нужен в проект:
{роль и стек/требования}

📩 Отклики:
Пишите сюда👉 @Edward0076
В отклике указывайте:
Стек и портфолио

Правила:
- Никаких контактов заказчика.
- Если данных не хватает — используй разумные заглушки, ничего не выдумывай.
- Ограничение длины tg_post: 900–1100 символов.
"""

_client = AsyncOpenAI(api_key=settings.CHAT_GPT_API_KEY)


def _extract_json_object(text: str) -> Dict[str, Any]:
    if not text:
        raise ValueError("Пустой ответ от модели.")
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("Ответ модели не содержит JSON-объект.")
    raw = m.group(0)
    try:
        return json.loads(raw)
    except Exception as e:
        raise ValueError(f"Невалидный JSON: {e}") from e


def build_messages_from_brief(brief_text: str) -> List[Dict[str, Any]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Сырые материалы клиента (допускается шум):\n\n{brief_text.strip()}"},
    ]


async def generate_tg_post(brief_text: str) -> dict:
    """
    Возвращает словарь: {"title": str, "tg_post": str}
    """
    messages = build_messages_from_brief(brief_text)
    logger.debug("GPT request built. model='{}' brief_len={}", settings.CHAT_GPT_MODEL, len(brief_text or ""))

    resp = await _client.responses.create(
        model=settings.CHAT_GPT_MODEL,
        input=messages,
        instructions="Отвечай строго одним JSON-объектом по описанной схеме."
    )

    raw = resp.output_text or ""
    # ЛОГИРУЕМ сырой ответ модели (обрежем до 6000 символов на всякий случай)
    logger.debug("GPT raw output (truncated): {}", raw[:6000])

    data = _extract_json_object(raw)
    title = (data.get("title") or "").strip()
    tg_post = (data.get("tg_post") or "").strip()

    # ЛОГ КЛЮЧЕВОГО РЕЗУЛЬТАТА
    logger.info("GPT generation ok: title='{}' post_len={}", title, len(tg_post))
    return {"title": title, "tg_post": tg_post}
