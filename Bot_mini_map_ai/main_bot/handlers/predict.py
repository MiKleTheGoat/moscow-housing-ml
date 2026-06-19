import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from Bot_mini_map_ai.config.settings import settings


logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("predict"))
async def cmd_predict(message: Message) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Команда только для администратора.")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 Mini App",
                    web_app=WebAppInfo(url=f"{settings.MINI_APP_URL}/predict"),
                )
            ]
        ]
    )
    await message.answer("Mini App для прогнозов:", reply_markup=keyboard)
