import uuid
import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket


logger = logging.getLogger(__name__)
router = Router()


class TicketForm(StatesGroup):
    subject = State()
    description = State()
    confirm = State()


@router.message(F.text == "📩 Создать тикет")
@router.message(Command("ticket"))
async def ticket_start(message: Message, state: FSMContext) -> None:
    await state.set_state(TicketForm.subject)
    await message.answer("Опишите коротко проблему: ")


@router.message(TicketForm.subject)
async def ticket_subject(message: Message, state: FSMContext) -> None:
    await state.update_data(subject=message.text)
    await state.set_state(TicketForm.description)
    await message.answer("Теперь подробно опиши проблему:")


@router.message(TicketForm.description)
async def ticket_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text)
    data = await state.get_data()

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data="ticket_confirm")
    builder.button(text="❌ Отмена", callback_data="ticket_cancel")

    await message.answer(
        f"Тикет:\n\n"
        f"<b>Тема:</b> {data['subject']}\n"
        f"<b>Описание:</b> {data['description']}\n\n"
        f"Отправляем?",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(TicketForm.confirm)


@router.callback_query(F.data == "ticket_confirm", StateFilter(TicketForm.confirm))
async def ticket_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    ticket_id = uuid.uuid4().hex[:8].upper()

    async with AsyncSessionLocal() as session:
        ticket = Ticket(
            ticket_id=ticket_id,
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            subject=data["subject"],
            description=data["description"],
        )
        session.add(ticket)
        await session.commit()

    await state.clear()

    from aiogram import Bot

    await callback.message.edit_text(
        f"Тикет <b>{ticket_id}</b> создан.\n"
        f"Скоро с вами свяжется админ."
    )

    support_bot = Bot(token=settings.SUPPORT_BOT_TOKEN)
    try:
        builder = InlineKeyboardBuilder()
        builder.button(text="✍️ Ответить", callback_data=f"answer_ticket:{ticket_id}")
        await support_bot.send_message(
            settings.ADMIN_ID,
            f"📩 <b>Новый тикет {ticket_id}</b>\n\n"
            f"👤 <b>От:</b> @{callback.from_user.username or callback.from_user.id}\n"
            f"📋 <b>Тема:</b> {data['subject']}\n"
            f"💬 <b>Описание:</b> {data['description']}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администратору через саппорт-бота: {e}")
    finally:
        await support_bot.session.close()

    await callback.answer()


@router.callback_query(F.data == "ticket_cancel", StateFilter(TicketForm.confirm))
async def ticket_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Тикет отменён.")
    await callback.answer()
