from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.chat_gpt.prompts import ProjectType
from app.db.models.tasks import ProjectStatus


def draft_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Отправить проект", callback_data="send_project")],
        [InlineKeyboardButton(text="🧹 Очистить", callback_data="clear_draft")],
    ])


def review_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить пост", callback_data=f"post:approve:{task_id}")
    kb.button(text="🔁 Перегенерировать пост", callback_data=f"post:regen:{task_id}")
    kb.button(text="❌ Отмена", callback_data=f"post:cancel:{task_id}")
    kb.adjust(1)
    return kb.as_markup()

def kp_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для действий с КП"""
    kb = InlineKeyboardBuilder()
    kb.button(text="📄 Перегенерировать КП", callback_data=f"kp:regen:{task_id}")
    kb.button(text="✅ Готово", callback_data=f"kp:approve:{task_id}")
    return kb.as_markup()


def persistent_projects_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📁 Проекты")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )

# === Навигация по проектам ===
def projects_nav_kb(task_id: int, index: int, total: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    # prev / next
    b.button(text="◀️ Предыдущий", callback_data=f"proj_nav:prev:{index}")
    b.button(text="Следующий ▶️", callback_data=f"proj_nav:next:{index}")
    b.button(text="✏️ Изменить статус", callback_data=f"proj_nav:status:{task_id}:{index}")
    b.adjust(2, 1)
    # пометка номера
    info = InlineKeyboardButton(text=f"{index+1}/{total}", callback_data="proj_nav:nop")
    b.row(info)
    return b.as_markup()

# === Клавиатура выбора статуса ===
def status_choice_kb(task_id: int, index: int) -> InlineKeyboardMarkup:
    """
    В callback кладём безопасный ключ enum (имя атрибута), а пользователю — русскую метку (value).
    """
    b = InlineKeyboardBuilder()
    for name, member in ProjectStatus.__members__.items():
        b.button(text=member.value, callback_data=f"proj_set_status:{task_id}:{index}:{name}")
    b.button(text="⬅️ Назад", callback_data=f"proj_nav:back:{index}")
    b.adjust(1)
    return b.as_markup()


def project_type_kb() -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа проекта"""
    kb = InlineKeyboardBuilder()

    kb.button(text="📱 Mini App/Платформа", callback_data=f"project_type:{ProjectType.MINI_APP.value}")
    kb.button(text="🤖 Бот", callback_data=f"project_type:{ProjectType.BOT.value}")
    kb.button(text="🎨 Дизайн/Брендбук", callback_data=f"project_type:{ProjectType.DESIGN.value}")
    kb.button(text="🌐 Сайт на Tilda", callback_data=f"project_type:{ProjectType.TILDA_SITE.value}")
    kb.button(text="⚙️ Скрипт", callback_data=f"project_type:{ProjectType.SCRIPT.value}")
    kb.button(text="🔧 Другое", callback_data=f"project_type:{ProjectType.OTHER.value}")

    kb.adjust(1)
    return kb.as_markup()
