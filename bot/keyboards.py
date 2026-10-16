from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .texts import PRAYER_NAMES

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
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Указать годы", callback_data="reg:years")],
            [InlineKeyboardButton(text="Период (с — по)", callback_data="reg:period")],
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
