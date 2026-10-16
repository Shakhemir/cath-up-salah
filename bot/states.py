from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    """Регистрация: ввод числа лет или периода (с — по)."""

    years = State()
    period_start = State()
    period_end = State()


class FastSetup(StatesGroup):
    """Настройка долга по постам."""

    amount = State()
