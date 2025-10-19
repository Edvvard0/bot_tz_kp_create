from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def draft_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Отправить проект", callback_data="send_project")],
        [InlineKeyboardButton(text="🧹 Очистить", callback_data="clear_draft")],
    ])


def review_actions_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data="approve_post")],
        [InlineKeyboardButton(text="🔁 Перегенерировать", callback_data="regen_post")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_review")],
    ])
