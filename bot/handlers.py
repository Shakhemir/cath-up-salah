from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from . import db
from .config import settings
from .keyboards import (
    BTN_DAY,
    BTN_FAST,
    BTN_STATUS,
    NAME_TO_KIND,
    confirm_reset_kb,
    edit_kb,
    main_kb,
    reg_method_kb,
)
from .states import Edit, FastSetup, Reg
from .texts import FAST, HELP, PRAYER_NAMES, PRAYERS, build_status

router = Router()

NOT_REGISTERED = "Сначала регистрация: /start"
EDIT_TARGETS = PRAYERS + ["all", FAST]


# ──────────────────────────── парсеры ────────────────────────────


def _parse_years(text: str):
    """Число лет: допускаем дробное (3.5), ограничиваем разумным диапазоном."""
    try:
        value = float((text or "").replace(",", ".").strip())
    except ValueError:
        return None
    if value <= 0 or value > 100:
        return None
    return value


def _parse_date(text: str):
    try:
        return datetime.strptime((text or "").strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def _parse_positive_int(text: str):
    try:
        value = int((text or "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _parse_nonneg_int(text: str):
    try:
        value = int((text or "").strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def _parse_count(command: CommandObject | None):
    """Разбирает аргумент команды (/fajr 10). Возвращает (n, error)."""
    if command is None or not command.args:
        return 1, None
    token = command.args.strip().split()[0]
    try:
        n = int(token)
    except ValueError:
        return None, "Нужно целое число. Пример: /fajr 10"
    if n <= 0:
        return None, "Число должно быть больше нуля."
    return n, None


# ──────────────────────────── общие помощники ────────────────────────────


async def _mark(message: Message, kind: str, n: int) -> None:
    uid = message.from_user.id
    if not await db.is_registered(uid):
        await message.answer(NOT_REGISTERED)
        return

    if kind == FAST:
        counters = await db.get_counters(uid)
        if counters.get(FAST, (0, 0))[0] <= 0:
            await message.answer("Сначала настрой долг по постам: /fasts")
            return

    added = await db.add_done(uid, kind, n)
    counters = await db.get_counters(uid)
    label = "🌙 Пост" if kind == FAST else PRAYER_NAMES[kind]

    if added == 0:
        head = f"{label}: долг уже закрыт ✅"
    elif added < n:
        head = f"✅ {label} +{added} (долг закрыт)"
    else:
        head = f"✅ {label} +{added}"

    await message.answer(head + "\n\n" + build_status(counters))


async def _show_status(message: Message) -> None:
    uid = message.from_user.id
    if not await db.is_registered(uid):
        await message.answer(NOT_REGISTERED)
        return
    counters = await db.get_counters(uid)
    await message.answer(build_status(counters), reply_markup=main_kb())


async def _after_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    counters = await db.get_counters(message.from_user.id)
    await message.answer(
        "✅ Готово!\n"
        "Отмечай наверстанное кнопками ниже или командами (/help).\n"
        "Уточнить долг по дням можно в любой момент: /edit\n\n"
        + build_status(counters),
        reply_markup=main_kb(),
    )


# ──────────────────────────── регистрация ────────────────────────────


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if await db.is_registered(message.from_user.id):
        counters = await db.get_counters(message.from_user.id)
        await message.answer(
            "Ты уже зарегистрирован.\n\n" + build_status(counters),
            reply_markup=main_kb(),
        )
        return
    await message.answer(
        "Ассаламу алейкум! 🤲\n"
        "Бот помогает наверстать долговые намазы (и посты).\n\n"
        "Как задать долг? (от грубого к точному — потом можно уточнить /edit)",
        reply_markup=reg_method_kb(),
    )


@router.callback_query(F.data == "reg:years")
async def reg_years(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.years)
    await callback.message.answer("Сколько лет долга? (например 5):")
    await callback.answer()


@router.callback_query(F.data == "reg:days")
async def reg_days(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.days)
    await callback.message.answer("Сколько дней долга? (одинаково на каждый намаз):")
    await callback.answer()


@router.callback_query(F.data == "reg:dates")
async def reg_dates(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.date_start)
    await callback.message.answer("С какой даты начался долг? Формат ДД.ММ.ГГГГ (например 01.03.2015):")
    await callback.answer()


@router.callback_query(F.data == "reg:each")
async def reg_each(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.each)
    await state.update_data(idx=0, totals={})
    await callback.message.answer(
        "Долг по дням для каждого намаза по очереди.\n"
        f"{PRAYER_NAMES[PRAYERS[0]]}: сколько дней?"
    )
    await callback.answer()


@router.message(Reg.years)
async def reg_years_input(message: Message, state: FSMContext) -> None:
    years = _parse_years(message.text)
    if years is None:
        await message.answer("Введи положительное число лет, например 5.")
        return
    days = max(0, round(years * settings.days_per_year))
    await db.register_all(message.from_user.id, days, years=years)
    await _after_registration(message, state)


@router.message(Reg.days)
async def reg_days_input(message: Message, state: FSMContext) -> None:
    days = _parse_positive_int(message.text)
    if days is None:
        await message.answer("Введи целое число дней, например 1825.")
        return
    await db.register_all(message.from_user.id, days)
    await _after_registration(message, state)


@router.message(Reg.date_start)
async def reg_date_start(message: Message, state: FSMContext) -> None:
    start = _parse_date(message.text)
    if start is None:
        await message.answer("Введи дату в формате ДД.ММ.ГГГГ, например 01.03.2015.")
        return
    await state.update_data(start=start.isoformat())
    await state.set_state(Reg.date_end)
    await message.answer("По какую дату? Формат ДД.ММ.ГГГГ (например 15.06.2020):")


@router.message(Reg.date_end)
async def reg_date_end(message: Message, state: FSMContext) -> None:
    end = _parse_date(message.text)
    if end is None:
        await message.answer("Введи дату в формате ДД.ММ.ГГГГ, например 15.06.2020.")
        return
    data = await state.get_data()
    start = date.fromisoformat(data["start"])
    days = (end - start).days + 1  # обе даты включительно
    if days <= 0:
        await message.answer("Конечная дата должна быть не раньше начальной. Введи ещё раз:")
        return
    await db.register_all(message.from_user.id, days)
    await _after_registration(message, state)


@router.message(Reg.each)
async def reg_each_input(message: Message, state: FSMContext) -> None:
    value = _parse_nonneg_int(message.text)
    if value is None:
        await message.answer("Введи целое число дней (0 — если долга нет):")
        return
    data = await state.get_data()
    idx = data["idx"]
    totals = data["totals"]
    totals[PRAYERS[idx]] = value
    idx += 1
    if idx < len(PRAYERS):
        await state.update_data(idx=idx, totals=totals)
        await message.answer(f"{PRAYER_NAMES[PRAYERS[idx]]}: сколько дней?")
        return
    await db.register_each(message.from_user.id, totals)
    await _after_registration(message, state)


# ──────────────────────────── отметки намазов ────────────────────────────


@router.message(Command(commands=PRAYERS))
async def cmd_prayer(message: Message, command: CommandObject) -> None:
    n, error = _parse_count(command)
    if error:
        await message.answer(error)
        return
    await _mark(message, command.command, n)


@router.message(Command("day"))
async def cmd_day(message: Message, command: CommandObject) -> None:
    uid = message.from_user.id
    if not await db.is_registered(uid):
        await message.answer(NOT_REGISTERED)
        return
    n, error = _parse_count(command)
    if error:
        await message.answer(error)
        return
    for kind in PRAYERS:
        await db.add_done(uid, kind, n)
    counters = await db.get_counters(uid)
    head = "✅ Отмечен день" if n == 1 else f"✅ Отмечено дней: {n}"
    await message.answer(head + "\n\n" + build_status(counters))


@router.message(Command("fast"))
async def cmd_fast(message: Message, command: CommandObject) -> None:
    n, error = _parse_count(command)
    if error:
        await message.answer(error)
        return
    await _mark(message, FAST, n)


# ──────────────────────────── посты (настройка) ────────────────────────────


@router.message(Command("fasts"))
async def cmd_fasts(message: Message, state: FSMContext) -> None:
    if not await db.is_registered(message.from_user.id):
        await message.answer(NOT_REGISTERED)
        return
    await state.set_state(FastSetup.amount)
    await message.answer("Сколько дней постов нужно наверстать? Введи число (например 30):")


@router.message(FastSetup.amount)
async def fasts_amount(message: Message, state: FSMContext) -> None:
    days = _parse_positive_int(message.text)
    if days is None:
        await message.answer("Введи целое число дней, например 30.")
        return
    await db.set_total(message.from_user.id, FAST, days)
    await state.clear()
    counters = await db.get_counters(message.from_user.id)
    await message.answer(
        f"🌙 Долг по постам: {days} дней.\n\n" + build_status(counters),
        reply_markup=main_kb(),
    )


# ──────────────────────────── редактирование долга ────────────────────────────


async def _apply_edit(message: Message, target: str, value: int) -> None:
    uid = message.from_user.id
    if target == "all":
        for kind in PRAYERS:
            await db.set_total(uid, kind, value)
    else:
        await db.set_total(uid, target, value)
    counters = await db.get_counters(uid)
    await message.answer("✅ Долг обновлён.\n\n" + build_status(counters))


@router.message(Command("edit"))
async def cmd_edit(message: Message, command: CommandObject, state: FSMContext) -> None:
    if not await db.is_registered(message.from_user.id):
        await message.answer(NOT_REGISTERED)
        return

    # Быстрый формат: /edit <намаз|all|fast> <дней>
    if command.args:
        parts = command.args.split()
        if len(parts) != 2:
            await message.answer(
                "Формат: /edit &lt;намаз|all|fast&gt; &lt;дней&gt;\nНапример: /edit fajr 1700"
            )
            return
        target = parts[0].lower()
        if target not in EDIT_TARGETS:
            await message.answer("Доступно: fajr, dhuhr, asr, maghrib, isha, all, fast")
            return
        value = _parse_nonneg_int(parts[1])
        if value is None:
            await message.answer("Число дней — целое ≥ 0.")
            return
        await _apply_edit(message, target, value)
        return

    await message.answer("Что отредактировать? (долг в днях)", reply_markup=edit_kb())


@router.callback_query(F.data.startswith("edit:"))
async def edit_choose(callback: CallbackQuery, state: FSMContext) -> None:
    target = callback.data.split(":", 1)[1]
    await state.set_state(Edit.value)
    await state.update_data(target=target)

    if target == "all":
        prompt = "Новый долг (дней) для ВСЕХ намазов:"
    else:
        counters = await db.get_counters(callback.from_user.id)
        total, done = counters.get(target, (0, 0))
        label = "🌙 Пост" if target == FAST else PRAYER_NAMES[target]
        prompt = f"{label}: сейчас долг {total}, сделано {done}.\nНовый долг (дней):"

    await callback.message.answer(prompt)
    await callback.answer()


@router.message(Edit.value)
async def edit_value(message: Message, state: FSMContext) -> None:
    value = _parse_nonneg_int(message.text)
    if value is None:
        await message.answer("Введи целое число дней ≥ 0.")
        return
    data = await state.get_data()
    target = data["target"]
    await state.clear()
    await _apply_edit(message, target, value)


# ──────────────────────────── статус / сброс / помощь ────────────────────────────


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    await _show_status(message)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("reset"))
async def cmd_reset(message: Message) -> None:
    if not await db.is_registered(message.from_user.id):
        await message.answer(NOT_REGISTERED)
        return
    await message.answer("Сбросить все данные и начать заново?", reply_markup=confirm_reset_kb())


@router.callback_query(F.data == "reset:yes")
async def reset_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await db.reset_user(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text("Данные сброшены. Нажми /start для новой регистрации.")
    await callback.answer()


@router.callback_query(F.data == "reset:no")
async def reset_no(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Отменено.")
    await callback.answer()


# ──────────────────────────── кнопки обычной клавиатуры ────────────────────────────


@router.message(StateFilter(None), F.text == BTN_STATUS)
async def kb_status(message: Message) -> None:
    await _show_status(message)


@router.message(StateFilter(None), F.text == BTN_DAY)
async def kb_day(message: Message) -> None:
    uid = message.from_user.id
    if not await db.is_registered(uid):
        await message.answer(NOT_REGISTERED)
        return
    for kind in PRAYERS:
        await db.add_done(uid, kind, 1)
    counters = await db.get_counters(uid)
    await message.answer("✅ Отмечен день\n\n" + build_status(counters))


@router.message(StateFilter(None), F.text == BTN_FAST)
async def kb_fast(message: Message) -> None:
    await _mark(message, FAST, 1)


@router.message(StateFilter(None), F.text.in_(set(NAME_TO_KIND)))
async def kb_prayer(message: Message) -> None:
    await _mark(message, NAME_TO_KIND[message.text], 1)


# ──────────────────────────── всё остальное ────────────────────────────


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Не понял. /help — список команд.")
