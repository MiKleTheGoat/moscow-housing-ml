import logging
from datetime import datetime
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket

logger = logging.getLogger(__name__)
router = Router()

class AnswerForm(StatesGroup):
    ticket_id = State()
    answer = State()

@router.callback_query(F.data.startswith("answer_ticket:"))
async def answer_ticket_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    ticket_id = callback.data.split(":")[1]
    await state.update_data(ticket_id=ticket_id)
    await state.set_state(AnswerForm.answer)
    await callback.message.answer(f"✍️ Вы отвечаете на тикет <b>{ticket_id}</b>.\nНапишите текст ответа:")
    await callback.answer()

@router.message(Command("answer"))
async def answer_ticket(message: Message, state: FSMContext) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Нет доступа!")
        return
    await state.set_state(AnswerForm.ticket_id)
    await message.answer("Введи ID тикета (например, A123B4C): ")

@router.message(AnswerForm.ticket_id)
async def get_ticket_id(message: Message, state: FSMContext) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        return
    await state.update_data(ticket_id=message.text.strip().upper())

    await state.set_state(AnswerForm.answer)
    await message.answer("Ответ пользователю: ")

@router.message(AnswerForm.answer)
async def send_answer(message: Message, state: FSMContext) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        return
    data = await state.get_data()
    ticket_id = data["ticket_id"]
    answer_text = message.text

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        )
        ticket = result.scalar_one_or_none()

    if not ticket:
        await message.answer(f"❌ Тикет с ID {ticket_id} не найден!")
        await state.clear()
        return

    main_bot = Bot(token=settings.MAIN_BOT_TOKEN)
    try:
        await main_bot.send_message(
            ticket.user_id,
            f"📬 Ответ на тикет {ticket_id}: \n{answer_text}"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить ответ пользователю {ticket.user_id}: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")
        await main_bot.session.close()
        await state.clear()
        return
    finally:
        await main_bot.session.close()

    async with AsyncSessionLocal() as session:
        t = await session.get(Ticket, ticket.id)
        if t:
            t.status = "closed"
            t.answered_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            await session.commit()

    await message.answer(f"✅ Ответ отправлен пользователю, тикет {ticket_id} закрыт.")
    await state.clear()

@router.message(Command("list"))
async def list_tickets(message: Message) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.status == "open")
        )
        tickets = result.scalars().all()

    if not tickets:
        await message.answer("✅ Открытых тикетов нет, победа!")
    else:
        lines = [f"<b>📋 Открытые тикеты ({len(tickets)}):</b>\n"]
        for ticket in tickets:
            lines.append(f"• <b>{ticket.ticket_id}</b> — @{ticket.username or ticket.user_id}\n  Тема: {ticket.subject}")
        await message.answer("\n".join(lines))