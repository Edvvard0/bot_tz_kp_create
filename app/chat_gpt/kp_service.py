# app/kp/kp_service.py
import asyncio
from openai import AsyncOpenAI
from datetime import datetime
import os
from app.config import settings
from app.chat_gpt.utils.konvert_md_docx import convert_kp_markdown_to_word

from app.chat_gpt.prompts import get_prompt_by_type, ProjectType
from loguru import logger


class KPService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.CHAT_GPT_API_KEY)

    async def generate_kp_content(self, project_description: str, project_type: ProjectType) -> str:
        """Генерирует содержимое КП с учетом типа проекта"""
        prompt = get_prompt_by_type(project_type, project_description)

        response = await self.client.responses.create(
            model=settings.CHAT_GPT_MODEL,
            input=[{"role": "user", "content": prompt}]
        )

        return response.output_text

    def create_kp_markdown(self, kp_content: str, project_name: str) -> str:
        """Создает .md файл с коммерческим предложением"""
        # Используем контент как есть, без дополнительных заголовков
        full_content = kp_content

        filename = f"КП_{project_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        filepath = os.path.join("generated_kp", filename)

        os.makedirs("generated_kp", exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return filepath

    def convert_markdown_to_docx(self, md_filepath: str, project_name: str) -> str:
        """Конвертирует .md файл в .docx с логотипом"""
        docx_filepath = md_filepath.replace('.md', '.docx')

        # Используем новую функцию с поддержкой логотипа
        success, message = convert_kp_markdown_to_word(
            md_filepath,
            docx_filepath,
            project_name,
            None  # Дата создания не нужна
        )

        if success:
            # Удаляем временный .md файл
            if os.path.exists(md_filepath):
                os.remove(md_filepath)
            return docx_filepath
        else:
            raise Exception(f"Ошибка конвертации: {message}")

    async def create_kp_document(self, project_description: str, project_name: str, project_type: ProjectType) -> str:
        """Основная функция: создает КП и возвращает путь к файлу"""

        # Генерируем содержимое КП с учетом типа
        kp_content = await self.generate_kp_content(project_description, project_type)

        # Создаем Markdown файл
        md_filepath = self.create_kp_markdown(kp_content, project_name)

        # Конвертируем в DOCX с логотипом
        docx_filepath = self.convert_markdown_to_docx(md_filepath, project_name)

        # Пытаемся конвертировать DOCX в PDF (оставляем логику на будущее)
        # final_filepath = convert_docx_to_pdf_with_fallback(docx_filepath)

        logger.info(f"KP document created: {docx_filepath}")
        return docx_filepath  # Возвращаем DOCX


# Функция для использования в боте
async def generate_kp_for_project(project_description: str, project_name: str, project_type: ProjectType) -> str:
    """
    Генерирует КП для проекта и возвращает путь к файлу
    """
    kp_service = KPService()
    return await kp_service.create_kp_document(project_description, project_name, project_type)