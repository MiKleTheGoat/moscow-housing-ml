import logging
import httpx

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.parser.resumer import ParseResumer


logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("parse"))
async def cmd_parse(message: Message) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Команда только для администратора.")
        return

    resumer = ParseResumer()

    if resumer.has_saved_state():
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Продолжить", callback_data="parse_resume")
        builder.button(text="🔄 Начать заново", callback_data="parse_restart")
        builder.button(text="❌ Отмена", callback_data="parse_cancel")

        await message.answer(
            f"Есть незавершённая сессия:\n"
            f"• Последняя страница: {resumer.last_page}\n"
            f"• Собрано офферов: {resumer.offers_collected}\n\n"
            "Продолжить или начать сначала?",
            reply_markup=builder.as_markup(),
        )
    else:
        await message.answer("Запускаю парсинг с первой страницы...")
        await _run_parse(message, start_page=1)


@router.callback_query(F.data == "parse_resume")
async def parse_resume(callback: CallbackQuery) -> None:
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    resumer = ParseResumer()
    await callback.message.edit_text(
        f"Продолжаю парсинг со страницы {resumer.last_page}..."
    )
    await _run_parse(callback.message, start_page=resumer.last_page)
    await callback.answer()


@router.callback_query(F.data == "parse_restart")
async def parse_restart(callback: CallbackQuery) -> None:
    if callback.from_user.id != settings.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    ParseResumer().clear()
    await callback.message.edit_text("Запускаю парсинг с первой страницы...")
    await _run_parse(callback.message, start_page=1)
    await callback.answer()


@router.callback_query(F.data == "parse_cancel")
async def parse_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Отменено.")
    await callback.answer()

async def _run_parse(message: Message, start_page: int) -> None:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{settings.ML_API_URL}/api/parse")
            if resp.status_code == 200:
                data = resp.json()
                await message.answer(
                    f"✅ Парсер успешно запущен через API!\n"
                    f"• Начальная страница: {data.get('last_page')}\n"
                    f"• Собрано предложений: {data.get('offers_collected')}\n\n"
                    f"Логи процесса записываются в <code>parser.log</code>."
                )
            else:
                await message.answer(f"❌ Ошибка запуска парсера (код ответа API: {resp.status_code})")
    except Exception as e:
        logger.error("Ошибка при запросе к API парсинга: %s", e)
        await message.answer(f"❌ Не удалось связаться с API-сервером: {e}")
