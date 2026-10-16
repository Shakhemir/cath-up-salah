from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from . import db
from .keyboards import (
    BTN_DAY,
    BTN_FAST,
    BTN_STATUS,
    NAME_TO_KIND,
    confirm_reset_kb,
    main_kb,
    reg_method_kb,
)
from .states import FastSetup, Reg
from .texts import FAST, HELP, PRAYER_NAMES, PRAYERS, build_status

router = Router()

NOT_REGISTERED = "Сначала регистрация: /start"


# ──────────────────────────── вспомогательные ────────────────────────────


def _parse_years(text: str):
    """Число лет: допускаем дробное (3.5), ограничиваем разумным диапазоном."""
    try:
        value = float((text or "").replace(",", ".").strip())
    except ValueError:
        return None
    if value <= 0 or value > 100:
        return None
    return value


def _parse_year(text: str):
    try:
        year = int((text or "").strip())
    except ValueError:
        return None
    return year if 1900 <= year <= 2100 else None


def _parse_positive_int(text: str):
    try:
        value = int((text or "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


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


async def _finish_registration(message: Message, state: FSMContext, years: float) -> None:
    days = await db.register_user(message.from_user.id, years)
    await state.clear()
    counters = await db.get_counters(message.from_user.id)
    await message.answer(
        f"✅ Готово! Долг: {years:g} лет ≈ {days} дней — по {days} каждого намаза.\n\n"
        "Отмечай наверстанное кнопками ниже или командами (/help).\n\n"
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
        "Сколько лет долга нужно наверстать?",
        reply_markup=reg_method_kb(),
    )


@router.callback_query(F.data == "reg:years")
async def reg_years(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.years)
    await callback.message.answer("Введи число лет (например 5):")
    await callback.answer()


@router.callback_query(F.data == "reg:period")
async def reg_period(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Reg.period_start)
    await callback.message.answer("С какого года начать? (например 2015):")
    await callback.answer()


@router.message(Reg.years)
async def reg_years_input(message: Message, state: FSMContext) -> None:
    years = _parse_years(message.text)
    if years is None:
        await message.answer("Введи положительное число лет, например 5.")
        return
    await _finish_registration(message, state, years)


@router.message(Reg.period_start)
async def reg_period_start(message: Message, state: FSMContext) -> None:
    year = _parse_year(message.text)
    if year is None:
        await message.answer("Введи год четырьмя цифрами, например 2015.")
        return
    await state.update_data(start=year)
    await state.set_state(Reg.period_end)
    await message.answer("По какой год? (например 2020):")


@router.message(Reg.period_end)
async def reg_period_end(message: Message, state: FSMContext) -> None:
    end = _parse_year(message.text)
    if end is None:
        await message.answer("Введи год четырьмя цифрами, например 2020.")
        return
    data = await state.get_data()
    years = end - data["start"]
    if years <= 0:
        await message.answer("Конечный год должен быть больше начального. Введи ещё раз:")
        return
    await _finish_registration(message, state, years)


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
    await db.set_fast(message.from_user.id, days)
    await state.clear()
    counters = await db.get_counters(message.from_user.id)
    await message.answer(
        f"🌙 Долг по постам: {days} дней.\n\n" + build_status(counters),
        reply_markup=main_kb(),
    )


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
