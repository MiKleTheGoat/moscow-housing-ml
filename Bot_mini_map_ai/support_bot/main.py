import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
