import asyncio
import json
import logging
import os
import re
import math
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import stealth
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.parser.resumer import ParseResumer
from Bot_mini_map_ai.storage.db import AsyncSession
from Bot_mini_map_ai.storage.models import Offer
from Bot_mini_map_ai.ml.predict import predict_price

logger = logging.getLogger(__name__)

house_type_map = {
    "Монолитный": 3,
    "Панельный": 2,
    "Кирпичный": 3,
    "Блочный": 1,
    "Деревянный": 0,
    "Монолитно-кирпичный": 3
}

renov_map = {
    "Дизайнерский": 3,
    "Евроремонт": 2,
    "Косметический": 1,
    "Без ремонта": 0
}


class PlaywrightParser:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.cian.ru/",
        "Connection": "keep-alive",
    }

    def __init__(self, headless: bool = True, max_concurrent: int = 5):
        self.headless = headless
        self.max_concurrent = max_concurrent
        self.resumer = ParseResumer()
        self.results: list[dict] = []

    async def _load_cookies(self, context) -> bool:
        cookie_file = settings.PARSER_COOKIE_FILE
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                logger.info(f"Загружено {len(cookies)} куки-файлов из {cookie_file}")
                return True
            except Exception as e:
                logger.warning(f"Ошибка загрузки кук: {e}")
        return False

    async def _save_cookies(self, context):
        cookie_file = settings.PARSER_COOKIE_FILE
        try:
            os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
            cookies = await context.cookies()
            with open(cookie_file, "w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Сохранено {len(cookies)} куки-файлов в {cookie_file}")
        except Exception as e:
            logger.error(f"Ошибка сохранения кук: {e}")

    async def _page_fetch(self, page, url: str) -> str | None:
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            if "captcha" in content.lower() or "robot" in content.lower():
                logger.warning("Капча обнаружена! Требуется ручное решение в окне браузера...")
                await page.screenshot(path="captcha.png", full_page=True)
                for _ in range(30):
                    await asyncio.sleep(2)
                    content = await page.content()
                    if "captcha" not in content.lower() and "robot" not in content.lower():
                        logger.info("Капча решена успешно!")
                        break
            return content
        except Exception as e:
            logger.error(f"Ошибка Playwright при загрузке страницы {url}: {e}")
            return None

    async def _api_fetch(self, request_ctx, url: str) -> str | None:
        try:
            resp = await request_ctx.get(url, timeout=30000)
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"API fetch {url}: статус {resp.status}")
        except Exception as e:
            logger.error(f"Ошибка API fetch {url}: {e}")
        return None

    @staticmethod
    def _extract_from_listing(html: str) -> list[dict]:
        for pattern in [
            r'"offersSerialized"\s*:\s*(\[.*?\])\s*,',
            r'"offers"\s*:\s*(\[.*?\])\s*,\s*"pagination"',
        ]:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return []

    @staticmethod
    def _extract_from_offer_page(html: str) -> dict | None:
        for pattern in [
            r"window\._cianConfig\['frontend-offer-card'\]\s*=\s*({.*?});",
            r'"defaultState"\s*:\s*({.*?})\s*,\s*"legacyUrl"',
        ]:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None

    def _parse_offer(self, offer: dict, url: str = "") -> None:
        try:
            geo = offer.get("geo", {})
            building = offer.get("building", {})

            price = offer.get("price_rur") or offer.get("bargainTerms", {}).get("price")
            if not price:
                return
            price = int(price)

            # Площадь
            area = offer.get("totalArea") or offer.get("TotalArea")
            if not area:
                return
            area = float(area)

            # Координаты
            coord = geo.get("coordinates", {})
            lat = coord.get("lat")
            lng = coord.get("lng")

            # Метро
            undergrounds = geo.get("undergrounds", [])
            metro = undergrounds[0].get("name", "N/A") if undergrounds else "N/A"
            time_to_metro = undergrounds[0].get("time", -1) if undergrounds else -1

            # Этаж
            floor = offer.get("floorNumber", -1)
            floor_total = building.get("floorsCount", -1)

            # Материал и ремонт
            material = building.get("houseMaterialType")
            house_type = house_type_map.get(material, 0) if material else -1

            repair = offer.get("repairType")
            renovation = renov_map.get(repair, -1) if repair else -1

            # Оценка ML-моделью
            pred_features = {
                'area': area,
                'floor': floor,
                'time_to_metro': time_to_metro,
                'renovation': max(0, renovation),
                'house_type': max(0, house_type),
            }
            predicted_price = predict_price(pred_features)
            profit = predicted_price - price

            data = {
                'url': url,
                'price': price,
                'predicted_price': predicted_price,
                'area': area,
                'lat': lat,
                'lng': lng,
                'floor': floor,
                'floor_total': floor_total,
                'metro': metro,
                'time_to_metro': time_to_metro,
                'house_type': house_type,
                'renovation': renovation,
                'profit': profit,
                'date': pd.Timestamp.now().strftime('%Y-%m-%d')
            }

            self.results.append(data)
        except Exception as e:
            logger.error(f"Ошибка парсинга отдельного объявления {url}: {e}")

    def save_to_csv(self):
        if not self.results:
            return
        try:
            os.makedirs(os.path.dirname(settings.CSV_PATH), exist_ok=True)
            df = pd.DataFrame(self.results)
            file_exists = os.path.isfile(settings.CSV_PATH)
            df.to_csv(settings.CSV_PATH, index=False, mode='a',
                      header=not file_exists, encoding='utf-8-sig')
            logger.info(f"Успешно сохранено {len(self.results)} объявлений в CSV: {settings.CSV_PATH}")
        except Exception as e:
            logger.error(f"Ошибка сохранения в CSV: {e}")

    async def save_to_db(self):
        if not self.results:
            return
        try:
            async with AsyncSession() as session:
                for data in self.results:
                    stmt = sqlite_insert(Offer).values(**data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[Offer.url],
                        set_={k: v for k, v in data.items() if k != 'url'}
                    )
                    await session.execute(stmt)
                await session.commit()
            logger.info(f"Успешно синхронизировано {len(self.results)} объявлений с базой данных SQLite")
        except Exception as e:
            logger.error(f"Ошибка синхронизации с базой данных: {e}")

    async def run(self, max_pages: int = 50, start_page: int = 1) -> None:
        self.resumer.start_session()
        base_url = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security",
                ]
            )
            context = await browser.new_context(
                user_agent=self.HEADERS["User-Agent"],
                locale="ru-RU",
                viewport={"width": 1920, "height": 1080},
            )
            await self._load_cookies(context)

            page = await context.new_page()
            await stealth(page)
            request_ctx = context.request

            all_links = []
            for p in range(start_page, max_pages + start_page):
                page_url = f"{base_url}&p={p}"
                logger.info(f"Загрузка страницы листинга {p}...")
                html = await self._page_fetch(page, page_url)
                
                if html:
                    listing_json = self._extract_from_listing(html)
                    page_links = [o.get('fullUrl') for o in listing_json if o.get('fullUrl')]
                    all_links.extend(page_links)
                    logger.info(f"Страница {p}: извлечено {len(page_links)} ссылок")
                    
                    self.resumer.update(page=p, offers=self.resumer.offers_collected + len(page_links))
                    await asyncio.sleep(2)
                else:
                    logger.warning(f"Страница {p} не вернула контент. Возможно, блок.")
                    break

            unique_links = list(set(all_links))
            logger.info(f"Всего уникальных ссылок для детального сбора: {len(unique_links)}")

            if not unique_links:
                await self._save_cookies(context)
                await browser.close()
                return

            sem = asyncio.Semaphore(self.max_concurrent)

            async def fetch_and_parse(url):
                async with sem:
                    # Случайная пауза перед запросом
                    await asyncio.sleep(math.sin(hash(url)) * 2 + 3)
                    html = await self._api_fetch(request_ctx, url)
                    if html:
                        json_data = self._extract_from_offer_page(html)
                        if json_data:
                            offer_dict = json_data.get('offerData', {}).get('offer') or json_data.get('offer')
                            if offer_dict:
                                self._parse_offer(offer_dict, url)

            tasks = [fetch_and_parse(url) for url in unique_links]
            await asyncio.gather(*tasks)

            logger.info(f"Парсинг завершен. Собрано предложений: {len(self.results)}")
            
            # Сохранение результатов
            self.save_to_csv()
            await self.save_to_db()

            await self._save_cookies(context)
            await browser.close()
            
        self.resumer.clear()
        logger.info("Сессия парсинга завершена успешно!")
