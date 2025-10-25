# app/kp/kp_service.py
import markdown
from fpdf import FPDF
from loguru import logger
from openai import AsyncOpenAI
from datetime import datetime
import os

from app.chat_gpt.docx_to_pdf_converter import convert_docx_to_pdf_with_fallback
from app.config import settings
from app.chat_gpt.utils.konvert_md_docx import convert_markdown_to_word


class KPService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.CHAT_GPT_API_KEY)

    async def generate_kp_content(self, project_description: str) -> str:
        prompt = f"""
        На основе описания проекта создай коммерческое предложение (КП) в формате Markdown.

        ОПИСАНИЕ ПРОЕКТА:
        {project_description}

        ПРОАНИЛИЗИРУЙ ОПИСАНИЕ ПРОЕКТА И ОПРЕДЕЛИ ЕГО ТИП:

        - ЕСЛИ это Mini App, платформа или веб-приложение с бэкендом → используй структуру с 4 этапами
        - ЕСЛИ это дизайн, брендбук или айдентика → используй структуру с 3 этапами  
        - ЕСЛИ это скрипт, интеграция API или автоматизация → используй структуру с 1 этапом
        - ЕСЛИ это сайт на конструкторе или лендинг → используй структуру с 1 этапом
        - ЕСЛИ проект нестандартный → адаптируй этапы под задачу

        СТРУКТУРА КОММЕРЧЕСКОГО ПРЕДЛОЖЕНИЯ В MARKDOWN:

        # Проект: [Название проекта]

        ## План работы

        ### Краткое описание проекта:
        [2-3 предложения о сути проекта]

        [ВСТАВЬ ПОДХОДЯЩИЕ ЭТАПЫ НА ОСНОВЕ АНАЛИЗА ПРОЕКТА]

        ### Цена/Сроки/Этапы

        | **Этапы** | **Сроки** | **Цена** |
        |-----------|-----------|----------|
        [ВСТАВЬ ЭТАПЫ С РЕАЛИСТИЧНЫМИ СРОКАМИ И СТОИМОСТЬЮ]
        | **Итог:** | **[общее время]** | **[общая стоимость]** |

        ---

        **ШАБЛОНЫ ДЛЯ РАЗНЫХ ТИПОВ ПРОЕКТОВ:**

        **ДЛЯ MINI APP / ПЛАТФОРМ:**
        ```
        ### Этап 1: Frontend (React/vite)

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Компонент] | [Конкретный функционал] |
        | [Компонент] | [Конкретный функционал] |

        ### Этап 2: Backend (FastAPI)

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Модуль] | [Конкретный функционал] |
        | [Модуль] | [Конкретный функционал] |

        ### Этап 3: Дизайн

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Элемент] | [Конкретное описание] |
        | [Элемент] | [Конкретное описание] |

        ### Этап 4: Деплой и тестирование

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Задача] | [Конкретные действия] |
        ```

        **ДЛЯ ДИЗАЙНА / БРЕНДБУКА:**
        ```
        ### Этап 1: Разработка основ бренда

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | Разработка логотипа | 3-4 концепции с описанием |
        | Цветовая палитра | Основные и акцентные цвета |
        | Типографика | Шрифты для заголовков и текста |

        ### Этап 2: Адаптация и применение

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | Оформление соцсетей | Аватарки, обложки, шаблоны |
        | Деловые материалы | Презентации, бланки, визитки |

        ### Этап 3: Финальная корректировка и передача

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | Создание брендбука | PDF-руководство с правилами |
        | Подготовка файлов | Исходники и экспорт |
        ```

        **ДЛЯ СКРИПТОВ / ИНТЕГРАЦИЙ:**
        ```
        ### Этап 1: Разработка Python-скрипта

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Техническая задача] | [Конкретная реализация] |
        | [Техническая задача] | [Конкретная реализация] |
        | Документация | Инструкция по использованию |
        ```

        **ДЛЯ САЙТОВ НА КОНСТРУКТОРАХ:**
        ```
        ### Этап 1: Создание сайта на Tilda

        | **Задача** | **Детализация** |
        |------------|-----------------|
        | [Страница] | [Контент и функционал] |
        | [Страница] | [Контент и функционал] |
        | Настройка | SEO, формы, аналитика |
        ```

        ТРЕБОВАНИЯ:
        1. Проанализируй тип проекта и выбери подходящую структуру
        2. Название проекта должно быть привлекательным
        3. Детализация должна быть конкретной и полезной для разработки
        4. Сроки и цены должны быть реалистичными
        5. Сохраняй табличную структуру
        6. Используй чистый Markdown без HTML
        7. Не добавляй лишних комментариев
        """

        response = await self.client.responses.create(
            model=settings.CHAT_GPT_MODEL,
            input=[{"role": "user", "content": prompt}]
        )

        return response.output_text

    def create_kp_markdown(self, kp_content: str, project_name: str) -> str:
        """Создает .md файл с коммерческим предложением"""
        full_content = f"""# Коммерческое предложение: {project_name}

**Дата создания:** {datetime.now().strftime("%d.%m.%Y")}

{kp_content}

---
*Данное коммерческое предложение подготовлено автоматически на основе требований заказчика.*
"""

        filename = f"КП_{project_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        filepath = os.path.join("generated_kp", filename)

        os.makedirs("generated_kp", exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_content)

        return filepath

    def convert_markdown_to_docx(self, md_filepath: str) -> str:
        """Конвертирует .md файл в .docx"""
        docx_filepath = md_filepath.replace('.md', '.docx')

        success, message = convert_markdown_to_word(md_filepath, docx_filepath)

        if success:
            # Удаляем временный .md файл
            if os.path.exists(md_filepath):
                os.remove(md_filepath)
            return docx_filepath
        else:
            raise Exception(f"Ошибка конвертации: {message}")

    async def create_kp_document(self, project_description: str, project_name: str) -> str:
        """Основная функция: создает КП и возвращает путь к файлу (PDF или DOCX)"""

        # Генерируем содержимое КП
        kp_content = await self.generate_kp_content(project_description)

        # Создаем Markdown файл
        md_filepath = self.create_kp_markdown(kp_content, project_name)

        # Конвертируем в DOCX
        docx_filepath = self.convert_markdown_to_docx(md_filepath)

        # Пытаемся конвертировать DOCX в PDF
        final_filepath = convert_docx_to_pdf_with_fallback(docx_filepath)

        logger.info(f"KP document created: {final_filepath}")
        return final_filepath


# Функция для использования в боте
async def generate_kp_for_project(project_description: str, project_name: str) -> str:
    """
    Генерирует КП для проекта и возвращает путь к .docx файлу
    """
    kp_service = KPService()
    return await kp_service.create_kp_document(project_description, project_name)