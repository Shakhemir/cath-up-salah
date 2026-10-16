from aiogram.fsm.state import State, StatesGroup


class Reg(StatesGroup):
    """Регистрация — от грубой настройки к точной."""

    years = State()        # число лет (× 365)
    days = State()         # число дней (одинаково на каждый намаз)
    date_start = State()   # период по датам: начало
    date_end = State()     # период по датам: конец
    each = State()         # свой долг по каждому намазу (последовательный ввод)


class FastSetup(StatesGroup):
    """Настройка долга по постам."""

    amount = State()


class Edit(StatesGroup):
    """Редактирование долга по дням в любой момент."""

    value = State()        # в data лежит target: ключ намаза, 'all' или 'fast'
