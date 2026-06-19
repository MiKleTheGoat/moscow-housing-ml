from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📩 Создать тикет")
    builder.button(text="📍 Отправить геолокацию", request_location=True)
    builder.button(text="💬 Чат с поддержкой")
    builder.adjust(1)

    await message.answer(
        f"Привет, {message.from_user.full_name}!\n\n"
        "📍 Отправь геолокацию — я привяжу координаты к твоему запросу.\n"
        "📩 Создай тикет — опиши проблему или вопрос.\n"
        "💬 Напиши в чат — я отвечу (или переключу на админа).",
        reply_markup=builder.as_markup(resize_keyboard=True),
    )


@router.message(F.text == "💬 Чат с поддержкой")
async def support_chat(message: Message) -> None:
    await message.answer(
        "Напиши свой вопрос сюда. Если я не смогу ответить — "
        "переключу на администратора.",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(~F.location, ~F.contact, ~F.photo, ~F.document, ~F.voice, ~F.video)
async def default_handler(message: Message) -> None:
    await message.answer(
        "🤖 Я не понял это сообщение.\n\n"
        "Пожалуйста, используйте кнопки меню ниже:\n"
        "📩 Создать тикет — написать поддержку\n"
        "📍 Отправить геолокацию — найти квартиры рядом"
    )
