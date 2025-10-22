from __future__ import annotations
import json
import re
import io
from typing import Any, List, Dict
from datetime import datetime

from loguru import logger
from openai import AsyncOpenAI
from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.config import settings

# SYSTEM PROMPT для генерации структуры КП
KP_SYSTEM_PROMPT = """
Ты — профессиональный менеджер проектов, который создает структурированные коммерческие предложения для IT-проектов.

Твоя задача: на основе предоставленного описания проекта сгенерировать JSON с данными для заполнения КП.

Верни строго в формате JSON:

{
  "project_name": "название проекта",
  "project_description": "краткое описание проекта 2-3 абзаца",
  "stages": {
    "design": {
      "duration": "2 недели",
      "price": "30000"
    },
    "backend": {
      "duration": "3 недели", 
      "price": "70000"
    },
    "frontend": {
      "duration": "3 недели",
      "price": "50000"
    },
    "deployment": {
      "duration": "1 неделя",
      "price": "15000"
    }
  },
  "frontend_tasks": [
    {"task": "Онбординг", "details": "Регистрация, ввод телефона, подтверждение SMS"},
    {"task": "Личный кабинет", "details": "Дашборд с прогрессом, графики веса и дохода"}
  ],
  "backend_tasks": [
    {"task": "Система аутентификации", "details": "Регистрация по номеру телефона, SMS-верификация"},
    {"task": "Профиль пользователя", "details": "Хранение данных: личная информация, вес, прогресс"}
  ],
  "design_tasks": [
    {"task": "Брендбук", "details": "Цветовая палитра, типографика, логотип, UI-кит"},
    {"task": "Компоненты", "details": "Кнопки, формы, карточки, модальные окна, навигация"}
  ],
  "deployment_tasks": [
    {"task": "Настройка домена к серверу", "details": "Подключаем домен к серверу"},
    {"task": "Настройка сервера", "details": "Ставим базовую безопасность, тестируем на утечки"}
  ]
}

ПРАВИЛА:
- Цены и сроки должны быть реалистичными для описанного проекта
- Если в описании проекта указаны конкретные цифры - используй их
- Задачи должны соответствовать типу проекта (Telegram Mini App)
- Описание проекта должно быть кратким и деловым
"""

_client = AsyncOpenAI(api_key=settings.CHAT_GPT_API_KEY)


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Извлекает JSON из ответа модели"""
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


def build_kp_messages(project_description: str) -> List[Dict[str, Any]]:
    """Строит сообщения для генерации структуры КП"""
    return [
        {"role": "system", "content": KP_SYSTEM_PROMPT},
        {"role": "user",
         "content": f"ОПИСАНИЕ ПРОЕКТА ДЛЯ КОММЕРЧЕСКОГО ПРЕДЛОЖЕНИЯ:\n\n{project_description.strip()}"},
    ]


async def generate_kp_data(project_description: str) -> Dict[str, Any]:
    """
    Генерирует структурированные данные для КП на основе описания проекта
    """
    messages = build_kp_messages(project_description)
    logger.debug("GPT KP data request. model='{}'", settings.CHAT_GPT_MODEL)

    resp = await _client.responses.create(
        model=settings.CHAT_GPT_MODEL,
        input=messages,
        instructions="Верни строго JSON-объект по указанной схеме без дополнительных комментариев."
    )

    raw = resp.output_text or ""
    logger.debug("GPT KP raw output: {}", raw)

    data = _extract_json_object(raw)
    logger.info("GPT KP data generation ok: project='{}'", data.get("project_name"))

    return data