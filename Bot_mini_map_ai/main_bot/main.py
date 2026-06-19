import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.main_bot.handlers import start, location, parse
from Bot_mini_map_ai.main_bot.handlers import ticket, train, predict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


from Bot_mini_map_ai.storage.db import init_db


async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start",   description="Начало работы"),
        BotCommand(command="ticket",  description="Создать тикет в поддержку"),
        BotCommand(command="parse",   description="Запуск парсера ЦИАН"),
        BotCommand(command="train",   description="Обучить ML-модель"),
        BotCommand(command="predict", description="Предсказать цену квартиры"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())


async def main() -> None:
    await init_db()
    bot = Bot(
        token=settings.MAIN_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_routers(
        location.router,
        ticket.router,
        parse.router,
        train.router,
        predict.router,
        start.router,
    )

    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
