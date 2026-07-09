import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeDefault, BotCommand

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.support_bot.handlers import answer_ticket
from Bot_mini_map_ai.storage.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="list",   description="Лист тикетов"),
        BotCommand(command="answer",  description="Ответить на тикет"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main() -> None:
    await init_db()

    bot = Bot(
        token=settings.SUPPORT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(answer_ticket.router)

    await bot.delete_webhook(drop_pending_updates=True)

    await dp.start_polling(bot)
