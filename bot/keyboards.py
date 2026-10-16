from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .texts import PRAYER_NAMES, PRAYERS

# Кнопка -> ключ намаза (обратное соответствие названиям)
NAME_TO_KIND = {name: kind for kind, name in PRAYER_NAMES.items()}

BTN_DAY = "➕ День"
BTN_FAST = "🌙 Пост"
BTN_STATUS = "📊 Статус"


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=PRAYER_NAMES["fajr"]),
                KeyboardButton(text=PRAYER_NAMES["dhuhr"]),
                KeyboardButton(text=PRAYER_NAMES["asr"]),
            ],
            [
                KeyboardButton(text=PRAYER_NAMES["maghrib"]),
                KeyboardButton(text=PRAYER_NAMES["isha"]),
            ],
            [KeyboardButton(text=BTN_DAY), KeyboardButton(text=BTN_FAST)],
            [KeyboardButton(text=BTN_STATUS)],
        ],
        resize_keyboard=True,
    )


def reg_method_kb() -> InlineKeyboardMarkup:
    """Выбор способа задать долг — от грубого к точному."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Годами", callback_data="reg:years"),
                InlineKeyboardButton(text="По датам", callback_data="reg:dates"),
            ],
            [
                InlineKeyboardButton(text="В днях", callback_data="reg:days"),
                InlineKeyboardButton(text="По каждому намазу", callback_data="reg:each"),
            ],
        ]
    )


def edit_kb() -> InlineKeyboardMarkup:
    """Выбор, какой долг (в днях) редактировать."""
    prayer_buttons = [
        InlineKeyboardButton(text=PRAYER_NAMES[k], callback_data=f"edit:{k}")
        for k in PRAYERS
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            prayer_buttons[:3],
            prayer_buttons[3:],
            [InlineKeyboardButton(text="Все намазы", callback_data="edit:all")],
            [InlineKeyboardButton(text=BTN_FAST, callback_data="edit:fast")],
        ]
    )


def undo_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Отменить", callback_data="undo:do")]
        ]
    )


def confirm_reset_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да, сбросить", callback_data="reset:yes"),
                InlineKeyboardButton(text="Отмена", callback_data="reset:no"),
            ]
        ]
    )
