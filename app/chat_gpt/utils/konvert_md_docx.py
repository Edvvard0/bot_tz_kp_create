# app/chat_gpt/utils/konvert_md_docx.py
"""
Конвертер Markdown в Word с логотипом в левом верхнем углу
Простое текстовое оформление без таблиц
"""

import os
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


class MarkdownToWordConverter:
    """Класс для конвертации Markdown в Word с логотипом в левом верхнем углу"""

    def __init__(self):
        self.doc = None
        self.logo_path = "hacktaika.png"  # Путь к логотипу

    def create_document(self):
        """Создает новый документ Word с логотипом в левом верхнем углу"""
        self.doc = Document()

        # Устанавливаем стандартный стиль
        style = self.doc.styles['Normal']
        font = style.font
        font.name = 'Times New Roman'
        font.size = Pt(12)
        font.color.rgb = RGBColor(0, 0, 0)

        # Добавляем шапку с логотипом слева
        self.add_header_with_logo()

    def add_header_with_logo(self):
        """Добавляет шапку с логотипом в левом верхнем углу"""
        try:
            # Создаем параграф для логотипа (выровненный по левому краю)
            logo_paragraph = self.doc.add_paragraph()
            logo_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

            # Добавляем логотип если он существует
            if os.path.exists(self.logo_path):
                run = logo_paragraph.add_run()
                run.add_picture(self.logo_path, width=Inches(1.1))  # Логотип как в примере

            # Добавляем отступ после логотипа
            logo_paragraph.paragraph_format.space_after = Pt(6)

            # Добавляем основной заголовок (выровненный по левому краю)
            title_paragraph = self.doc.add_paragraph()
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT

            title_run = title_paragraph.add_run("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ")
            title_run.bold = True
            title_run.font.size = Pt(16)
            title_run.font.name = 'Times New Roman'

            # Добавляем отступ после заголовка
            title_paragraph.paragraph_format.space_after = Pt(12)

        except Exception as e:
            print(f"⚠️ Не удалось добавить логотип: {e}")
            # Резервный вариант: заголовок без логотипа
            title_paragraph = self.doc.add_paragraph()
            title_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            title_run = title_paragraph.add_run("КОММЕРЧЕСКОЕ ПРЕДЛОЖЕНИЕ")
            title_run.bold = True
            title_run.font.size = Pt(16)
            title_run.font.name = 'Times New Roman'
            self.doc.add_paragraph()

    def add_project_info(self, project_name, creation_date):
        """Добавляет информацию о проекте под шапкой"""
        # Добавляем название проекта (выровнено по левому краю)
        if project_name:
            project_paragraph = self.doc.add_paragraph()
            project_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            project_run = project_paragraph.add_run(project_name)
            project_run.bold = True
            project_run.font.size = Pt(14)
            project_run.font.name = 'Times New Roman'
            project_paragraph.paragraph_format.space_after = Pt(6)

        # Добавляем дату создания (выровнено по левому краю)
        if creation_date:
            date_paragraph = self.doc.add_paragraph()
            date_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            date_run = date_paragraph.add_run(f"Дата создания: {creation_date}")
            date_run.italic = True
            date_run.font.size = Pt(10)
            date_run.font.name = 'Times New Roman'
            date_paragraph.paragraph_format.space_after = Pt(12)

        # Добавляем разделительную линию
        line_paragraph = self.doc.add_paragraph()
        line_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        line_run = line_paragraph.add_run("_" * 60)
        line_run.font.size = Pt(10)
        self.doc.add_paragraph()

    def add_table_borders(self, table):
        """Добавляет границы к таблице"""
        tbl = table._element
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement('w:tblPr')
            tbl.insert(0, tblPr)

        # Создаем элемент границ
        tblBorders = OxmlElement('w:tblBorders')
        for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
            border = OxmlElement(f'w:{border_name}')
            border.set(qn('w:val'), 'single')
            border.set(qn('w:sz'), '4')
            border.set(qn('w:space'), '0')
            border.set(qn('w:color'), '000000')
            tblBorders.append(border)

        tblPr.append(tblBorders)

    def parse_inline_formatting(self, text):
        """Парсит встроенное форматирование (жирный, курсив, код)"""
        parts = []

        # Регулярное выражение для поиска форматирования
        pattern = r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*|`.*?`|___.*?___|__.*?__|_.*?_)'

        last_end = 0
        for match in re.finditer(pattern, text):
            # Добавляем текст до совпадения
            if match.start() > last_end:
                parts.append((text[last_end:match.start()], {}))

            matched_text = match.group()
            formatting = {}
            clean_text = matched_text

            # Проверяем тип форматирования
            if matched_text.startswith('***') or matched_text.startswith('___'):
                formatting = {'bold': True, 'italic': True}
                clean_text = matched_text[3:-3]
            elif matched_text.startswith('**') or matched_text.startswith('__'):
                formatting = {'bold': True}
                clean_text = matched_text[2:-2]
            elif matched_text.startswith('*') or matched_text.startswith('_'):
                formatting = {'italic': True}
                clean_text = matched_text[1:-1]
            elif matched_text.startswith('`'):
                formatting = {'code': True}
                clean_text = matched_text[1:-1]

            parts.append((clean_text, formatting))
            last_end = match.end()

        # Добавляем оставшийся текст
        if last_end < len(text):
            parts.append((text[last_end:], {}))

        return parts if parts else [(text, {})]

    def add_formatted_text(self, paragraph, text):
        """Добавляет текст с форматированием в параграф"""
        parts = self.parse_inline_formatting(text)

        for part_text, formatting in parts:
            run = paragraph.add_run(part_text)
            run.font.name = 'Times New Roman'
            run.font.size = Pt(12)
            run.font.color.rgb = RGBColor(0, 0, 0)

            if formatting.get('bold'):
                run.bold = True
            if formatting.get('italic'):
                run.italic = True
            if formatting.get('code'):
                run.font.name = 'Courier New'
                run.font.size = Pt(10)

    def process_table(self, lines, start_idx):
        """Обрабатывает таблицу из markdown"""
        table_lines = []
        idx = start_idx

        # Собираем все строки таблицы
        while idx < len(lines) and '|' in lines[idx]:
            table_lines.append(lines[idx])
            idx += 1

        if len(table_lines) < 2:
            return idx

        # Парсим таблицу
        rows = []
        for line in table_lines:
            # Пропускаем разделительную строку (---|---|---)
            if re.match(r'^\|[\s\-:|]+\|$', line.strip()):
                continue

            # Разбиваем строку на ячейки
            cells = [cell.strip() for cell in line.split('|')]
            # Удаляем пустые ячейки в начале и конце
            cells = [c for c in cells if c or cells.index(c) not in [0, len(cells) - 1]]
            if cells:
                rows.append(cells)

        if not rows:
            return idx

        # Создаем таблицу в документе
        table = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = 'Table Grid'
        self.add_table_borders(table)

        # Заполняем таблицу
        for i, row_data in enumerate(rows):
            for j, cell_text in enumerate(row_data):
                if j < len(table.rows[i].cells):
                    cell = table.rows[i].cells[j]
                    # Очищаем ячейку и добавляем форматированный текст
                    cell.text = ''
                    paragraph = cell.paragraphs[0]
                    self.add_formatted_text(paragraph, cell_text)
                    # Устанавливаем выравнивание по ширине для текста в ячейках
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

                    # Форматирование для заголовка таблицы (первая строка)
                    if i == 0:
                        for run in paragraph.runs:
                            run.bold = True

        return idx

    def process_list(self, lines, start_idx):
        """Обрабатывает списки (маркированные и нумерованные)"""
        idx = start_idx
        list_items = []

        # Определяем тип списка
        first_line = lines[start_idx].strip()
        is_ordered = bool(re.match(r'^\d+\.', first_line))

        # Собираем элементы списка
        while idx < len(lines):
            line = lines[idx].strip()
            if not line:
                break

            # Проверяем маркированный список
            if re.match(r'^[-*+]\s', line):
                list_items.append(('unordered', line[2:]))
                idx += 1
            # Проверяем нумерованный список
            elif re.match(r'^\d+\.\s', line):
                match = re.match(r'^\d+\.\s(.*)', line)
                list_items.append(('ordered', match.group(1)))
                idx += 1
            else:
                break

        # Добавляем элементы списка в документ
        for list_type, item_text in list_items:
            paragraph = self.doc.add_paragraph(style='List Bullet' if list_type == 'unordered' else 'List Number')
            self.add_formatted_text(paragraph, item_text)

        return idx

    def add_footer(self):
        """Добавляет футер с информацией о компании"""
        self.doc.add_page_break()

        footer_paragraph = self.doc.add_paragraph()
        footer_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_run = footer_paragraph.add_run(
            "Данное коммерческое предложение подготовлено автоматически\nна основе требований заказчика.")
        footer_run.italic = True
        footer_run.font.size = Pt(10)
        footer_run.font.name = 'Times New Roman'

    def convert_file(self, input_path, output_path, project_name=None, creation_date=None):
        """Конвертирует markdown файл в Word с логотипом в левом верхнем углу"""
        try:
            # Читаем файл
            with open(input_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Создаем документ с логотипом
            self.create_document()

            # Добавляем информацию о проекте
            self.add_project_info(project_name, creation_date)

            # Разбиваем на строки
            lines = content.split('\n')

            i = 0
            while i < len(lines):
                line = lines[i]
                stripped = line.strip()

                # Пропускаем пустые строки
                if not stripped:
                    i += 1
                    continue

                # Заголовки
                if stripped.startswith('#'):
                    level = 0
                    while level < len(stripped) and stripped[level] == '#':
                        level += 1

                    title_text = stripped[level:].strip()

                    # Для заголовков используем стили Word
                    if level == 1:
                        paragraph = self.doc.add_paragraph(style='Heading 1')
                    elif level == 2:
                        paragraph = self.doc.add_paragraph(style='Heading 2')
                    else:
                        paragraph = self.doc.add_paragraph(style=f'Heading {min(level, 9)}')

                    self.add_formatted_text(paragraph, title_text)
                    paragraph.paragraph_format.space_after = Pt(6)
                    i += 1

                # Горизонтальная линия
                elif stripped == '---' or stripped == '***' or stripped == '___':
                    line_paragraph = self.doc.add_paragraph()
                    line_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    line_run = line_paragraph.add_run("_" * 60)
                    line_run.font.size = Pt(10)
                    i += 1

                # Таблицы
                elif '|' in line:
                    i = self.process_table(lines, i)

                # Списки
                elif re.match(r'^[-*+]\s', stripped) or re.match(r'^\d+\.\s', stripped):
                    i = self.process_list(lines, i)

                # Блок кода (```)
                elif stripped.startswith('```'):
                    i += 1
                    code_lines = []
                    while i < len(lines) and not lines[i].strip().startswith('```'):
                        code_lines.append(lines[i])
                        i += 1

                    if code_lines:
                        paragraph = self.doc.add_paragraph()
                        run = paragraph.add_run('\n'.join(code_lines))
                        run.font.name = 'Courier New'
                        run.font.size = Pt(10)
                        run.font.color.rgb = RGBColor(0, 0, 0)

                    i += 1

                # Обычный текст
                else:
                    paragraph = self.doc.add_paragraph()
                    self.add_formatted_text(paragraph, line)
                    # Устанавливаем выравнивание по левому краю для обычного текста
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    i += 1

            # Добавляем футер
            self.add_footer()

            # Сохраняем документ
            self.doc.save(output_path)
            return True, "Успешно конвертировано"

        except Exception as e:
            return False, f"Ошибка при конвертации: {str(e)}"


def convert_markdown_to_word(input_path, output_path=None, project_name=None, creation_date=None):
    """
    Основная функция для конвертации Markdown в Word с логотипом в левом верхнем углу
    """
    # Если выходной путь не указан, создаем его на основе входного
    if output_path is None:
        input_path_obj = Path(input_path)
        output_path = input_path_obj.with_suffix('.docx')

    # Создаем конвертер и выполняем конвертацию
    converter = MarkdownToWordConverter()
    return converter.convert_file(input_path, output_path, project_name, creation_date)


def convert_kp_markdown_to_word(input_path, output_path, project_name, creation_date):
    """
    Специальная функция для конвертации КП Markdown в Word с логотипом в левом верхнем углу
    """
    return convert_markdown_to_word(input_path, output_path, project_name, creation_date)