import logging
import math

from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from sqlalchemy import select

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.db import AsyncSession
from Bot_mini_map_ai.storage.models import UserRequest, Offer


logger = logging.getLogger(__name__)
router = Router()


def calculate_distance(lat1: float, lat2: float, lon1: float, lon2: float) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + \
        math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
        math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


@router.message(F.location)
async def handle_location(message: Message) -> None:
    loc = message.location
    lat, lon = loc.latitude, loc.longitude

    async with AsyncSession() as session:
        new_request = UserRequest(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            latitude=lat,
            longitude=lon
        )
        session.add(new_request)

        result = await session.execute(select(Offer))
        offers = result.scalars().all()
        await session.commit()

    if not offers:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🗺️ Открыть МiniApp",
                        web_app=WebAppInfo(url=f"{settings.MINI_APP_URL}/?lat={lat}&lng={lon}"),
                    )
                ]
            ]
        )
        await message.answer(
            f"📍 Координаты получены:\n"
            f"Широта: {lat:.6f}\n"
            f"Долгота: {lon:.6f}\n\n"
            "⚠️ База данных объявлений пока пуста. Запустите парсер, чтобы наполнить базу предложениями с ЦИАН.",
            reply_markup=keyboard
        )
        return

    closest_offers = []
    for offer in offers:
        if offer.lat is not None and offer.lng is not None:
            dist = calculate_distance(lat, offer.lat, lon, offer.lng)
            closest_offers.append((offer, dist))

    # Сортируем по возрастанию расстояния
    closest_offers.sort(key=lambda x: x[1])
    top_5 = closest_offers[:5]

    response_text = f"📍 Ваши координаты получены: (<code>{lat:.5f}</code>, <code>{lon:.5f}</code>)\n\n"
    response_text += "🏠 <b>Ближайшие предложения рядом с вами:</b>\n\n"

    for idx, (offer, dist) in enumerate(top_5, 1):
        price_str = f"{offer.price:,.0f} ₽" if offer.price > 0 else "не указана"
        pred_str = ""
        if offer.predicted_price and offer.predicted_price > 0:
            profit = offer.predicted_price - offer.price
            pred_str = f"\n   🤖 Оценка: <code>{offer.predicted_price:,.0f} ₽</code>"
            if profit > 0:
                pred_str += f" (Выгода: <b>{profit:,.0f} ₽</b> 🔥)"
            else:
                pred_str += f" (Переплата: <b>{abs(profit):,.0f} ₽</b> ⚠️)"

        response_text += (
            f"<b>{idx}. {offer.metro or 'Н/Д'}</b> (~{dist} км)\n"
            f"   Площадь: {offer.area} м² | Этаж: {offer.floor}/{offer.floor_total or 'Н/Д'}\n"
            f"   Цена: <code>{price_str}</code>{pred_str}\n"
            f"   🔗 <a href='{offer.url}'>Открыть объявление на ЦИАН</a>\n\n"
        )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗺️ Интерактивная карта",
                    web_app=WebAppInfo(url=f"{settings.MINI_APP_URL}/?lat={lat}&lng={lon}"),
                )
            ]
        ]
    )

    await message.answer(
        response_text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
