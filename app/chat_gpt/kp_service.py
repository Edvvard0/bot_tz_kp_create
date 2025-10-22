# app/kp/kp_service.py
import asyncio
from openai import AsyncOpenAI
from docx import Document
from datetime import datetime
import os
from pathlib import Path
from app.config import settings
from app.chat_gpt.konvert_md_docx import convert_markdown_to_word


class KPService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.CHAT_GPT_API_KEY)

    async def generate_kp_content(self, project_description: str) -> str:
        """Генерирует содержание КП через ChatGPT"""
        prompt = f"""
        На основе описания проекта создай коммерческое предложение (КП) в формате Markdown. 
        Используй структуру из примера ниже, но адаптируй под конкретный проект.

        ОПИСАНИЕ ПРОЕКТА:
        {project_description}

        СТРУКТУРА КОММЕРЧЕСКОГО ПРЕДЛОЖЕНИЯ В MARKDOWN:

        # Проект: [Название проекта]

        ## План работы

        ### Краткое описание проекта:
        [Краткое описание 2-3 предложения о сути проекта]

        ### Этап 1: Frontend (React/vite)

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Компонент 1] | [Описание функционала] |
        | [Компонент 2] | [Описание функционала] |

        ### Этап 2: Backend (FastAPI)

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Модуль 1] | [Описание функционала] |
        | [Модуль 2] | [Описание функционала] |

        ### Этап 3: Дизайн

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Элемент дизайна 1] | [Описание] |
        | [Элемент дизайна 2] | [Описание] |

        ### Этап 4: Деплой и тестирование

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Задача деплоя] | [Описание] |

        ### Цена/Сроки/Этапы

        | **Этапы** | **Сроки** | **Цена** |
        |-----------|-----------|----------|
        | [Этап 1] | [время] | [стоимость] |
        | [Этап 2] | [время] | [стоимость] |
        | **Итог:** | **[общее время]** | **[общая стоимость]** |

        ТРЕБОВАНИЯ:
        1. Название проекта должно быть привлекательным
        2. Детализация должна быть конкретной и полезной для разработки
        3. Сроки и цены должны быть реалистичными для описанного проекта
        4. Сохраняй табличную структуру как в примере
        5. Используй чистый Markdown без HTML
        6. Не добавляй лишних комментариев
        """

        response = await self.client.responses.create(
            model=settings.CHAT_GPT_MODEL,
            input=[{"role": "user", "content": prompt}]
        )

        return response.output_text

    def create_kp_markdown(self, kp_content: str, project_name: str) -> str:
        """Создает .md файл с коммерческим предложением"""
        # Создаем полное содержание Markdown
        full_content = f"""# Коммерческое предложение: {project_name}

**Дата создания:** {datetime.now().strftime("%d.%m.%Y")}

{kp_content}

---
*Данное коммерческое предложение подготовлено автоматически на основе требований заказчика.*
"""

        # Сохраняем .md файл в текущей директории
        filename = f"КП_{project_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        filepath = filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return filepath

    def convert_markdown_to_docx(self, md_filepath: str) -> str:
        """Конвертирует .md файл в .docx"""
        # Создаем путь для .docx файла
        docx_filepath = md_filepath.replace('.md', '.docx')

        # Конвертируем
        success, message = convert_markdown_to_word(md_filepath, docx_filepath)

        if success:
            return docx_filepath
        else:
            raise Exception(f"Ошибка конвертации: {message}")

    async def create_kp_document(self, project_description: str, project_name: str) -> str:
        """Основная функция: создает КП и возвращает путь к .docx файлу"""

        kp_content = await self.generate_kp_content(project_description)
        md_filepath = self.create_kp_markdown(kp_content, project_name)
        docx_filepath = self.convert_markdown_to_docx(md_filepath)

        # Удаляем временный .md файл
        if os.path.exists(md_filepath):
            os.remove(md_filepath)

        return docx_filepath


# Функция для использования в боте
async def generate_kp_for_project(project_description: str, project_name: str) -> str:
    """
    Генерирует КП для проекта и возвращает путь к .docx файлу
    """
    kp_service = KPService()
    return await kp_service.create_kp_document(project_description, project_name)