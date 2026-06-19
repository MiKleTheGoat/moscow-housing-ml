import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from Bot_mini_map_ai.config.settings import settings


logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("train"))
async def cmd_train(message: Message) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Команда только для администратора.")
        return

    await message.answer("Запускаю обучение XGBoost на NVIDIA-сервере...")

    import httpx
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.ML_API_URL}/api/train")
            if resp.status_code == 200:
                data = resp.json()
                await message.answer(
                    f"✅ Обучение успешно запущено!\n"
                    f"• Статус: {data.get('status')}\n"
                    f"• Сообщение: {data.get('message')}"
                )
            else:
                await message.answer(f"❌ Ошибка запуска обучения (код ответа API: {resp.status_code})")
    except Exception as e:
        logger.error("Ошибка при запросе к API обучения: %s", e)
        await message.answer(f"❌ Не удалось связаться с API-сервером: {e}")
