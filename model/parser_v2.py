import asyncio
import json
import logging
import os
import re

import math as m
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import stealth

# Маппинги
house_type_map = {"Монолитный": 3, "Панельный": 2, "Кирпичный": 3,
                  "Блочный": 1, "Деревянный": 0, "Монолитно-кирпичный": 3}

renov_map = {"Дизайнерский": 3, "Евроремонт": 2,
             "Косметический": 1, "Без ремонта": 0}

parking_map = {"Подземная": 2, "Наземная": 1, "Многоуровневая": 1,
               "Нет": 0, "Открытая": 1}

finish_map = {"Без отделки": 0, "Черновая": 0, "Предчистовая": 1,
              "White box": 1, "Чистовая": 2, "С отделкой": 2,
              "Под ключ": 2}

MOSCOW_CENTER_LAT = 55.7539
MOSCOW_CENTER_LNG = 37.6208

def calculate_distance(lat1, lat2, lon1, lon2):
    """Вычисляет расстояние в км между двумя точками на сфере"""
    R = 6371
    d_lat = m.radians(lat2 - lat1)
    d_lon = m.radians(lon2 - lon1)

    a = m.sin(d_lat / 2) ** 2 + \
        m.cos(m.radians(lat1)) * m.cos(m.radians(lat2)) * \
        m.sin(d_lon / 2) ** 2

    c = 2 * m.atan2(m.sqrt(a), m.sqrt(1 - a))
    return round(R * c, 2)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("parser.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CianParserV2():
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.cian.ru/",
        "Connection": "keep-alive",
    }

    def __init__(self, base_url: str, out_csv: str = 'house_cian.csv', max_concurrent: int = 5, cookie_file: str = "cian_cookies.json", headless: bool = True):
        self.base_url = base_url
        self.out_csv = out_csv
        self.max_concurrent = max_concurrent
        self.cookie_file = cookie_file
        self.headless = headless
        self.results: list[dict] = []
        logger.info(f"Initializing parser. File: {out_csv}, Max concurrent: {max_concurrent}, Headless: {headless}")

    async def _load_cookies(self, context) -> bool:
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                logger.info(f"Loaded {len(cookies)} cookies from {self.cookie_file}")
                return True
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")
        return False

    async def _save_cookies(self, context):
        cookies = await context.cookies()
        with open(self.cookie_file, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(cookies)} cookies to {self.cookie_file}")

    async def _page_fetch(self, page, url: str) -> str | None:
        """Full page load (captcha bypass for listing pages)."""
        try:
            resp = await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            if "captcha" in content.lower() or "robot" in content.lower():
                logger.warning("Captcha detected, waiting for manual solve in browser window...")
                await page.screenshot(path="captcha.png", full_page=True)
                input("Solve the captcha in the browser window and press Enter to continue...")
                await page.wait_for_timeout(2000)
                content = await page.content()
            return content
        except Exception as e:
            logger.error(f"Playwright page error {url}: {e}")
            return None

    async def _api_fetch(self, request_ctx, url: str) -> str | None:
        """Lightweight HTTP fetch via browser's APIRequestContext (no rendering)."""
        try:
            resp = await request_ctx.get(url, timeout=30000)
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"API fetch {url}: status {resp.status}")
        except Exception as e:
            logger.error(f"API fetch error {url}: {e}")
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
            data = {'url': url}

            # Прайс
            price = offer.get("price_rur") or offer.get("bargainTerms", {}).get("price")
            data['price'] = int(price) if price else -1

            # Площадь
            area = offer.get("totalArea") or offer.get("TotalArea")
            data['area'] = float(area) if area else -1

            # Координаты
            coord = geo.get("coordinates", {})
            data['lat'] = coord.get("lat")
            data['lng'] = coord.get("lng")

            # Этаж
            data['floor'] = offer.get("floorNumber", -1)
            data['floor_total'] = building.get("floorsCount", -1)

            # Метро
            undergrounds = geo.get("undergrounds", [])
            if undergrounds:
                data['metro'] = undergrounds[0].get("name", "")
                data['time_to_metro'] = undergrounds[0].get("time")
            else:
                data['metro'], data['time_to_metro'] = "N/A", -1

            # Тип дома
            material = building.get("houseMaterialType")
            data['house_type'] = house_type_map.get(material, 0) if material else -1

            # Ремонт
            repair = offer.get("repairType")
            data['renovation'] = renov_map.get(repair, -1) if repair else -1

            self.results.append(data)
        except Exception as e:
            logger.error(f"Error parsing offer {url}: {e}")

    def save_to_csv(self):
        if not self.results:
            logger.warning("No results to save.")
            return
        try:
            df = pd.DataFrame(self.results)
            file_exists = os.path.isfile(self.out_csv)
            df.to_csv(self.out_csv, index=False, mode='a',
                      header=not file_exists, encoding='utf-8-sig')
            logger.info(f"Successfully saved {len(self.results)} objects to {self.out_csv}")
            self.results = []
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")

    async def _playwright_run(self, max_pages: int):
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
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
            for p in range(1, max_pages + 1):
                page_url = f"{self.base_url}&p={p}"
                html = await self._page_fetch(page, page_url)
                if html:
                    listing_json = self._extract_from_listing(html)
                    page_links = [o.get('fullUrl') for o in listing_json if o.get('fullUrl')]
                    all_links.extend(page_links)
                    logger.info(f"Page {p}: {len(page_links)} links extracted")
                else:
                    logger.warning(f"Page {p}: no content")

            unique_links = list(set(all_links))
            logger.info(f"Total unique links to parse: {len(unique_links)}")

            if not unique_links:
                logger.warning("No links found, check captcha or base_url")
                await self._save_cookies(context)
                await browser.close()
                return

            sem = asyncio.Semaphore(self.max_concurrent)

            async def fetch_and_parse(url):
                async with sem:
                    html = await self._api_fetch(request_ctx, url)
                    if html:
                        json_data = self._extract_from_offer_page(html)
                        if json_data:
                            offer_dict = json_data.get('offerData', {}).get('offer') or json_data.get('offer')
                            if offer_dict:
                                self._parse_offer(offer_dict, url)

            tasks = [fetch_and_parse(url) for url in unique_links]
            await asyncio.gather(*tasks)
            logger.info(f"Parsed {len(self.results)} offers total")

            await self._save_cookies(context)
            await browser.close()

    async def run_pages(self, max_pages: int):
        await self._playwright_run(max_pages)
        self.save_to_csv()

if __name__ == "__main__":
    BASE_URL = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"
    try:
        pages = int(input("How many pages to scan? "))
    except ValueError:
        pages = 1

    parser = CianParserV2(base_url=BASE_URL, out_csv='cian_results.csv', max_concurrent=5, headless=False)
    asyncio.run(parser.run_pages(max_pages=pages))
    logger.info("Parser task completed!")