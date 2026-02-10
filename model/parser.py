import os
import time
from random import uniform

from re import search, sub
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


house_type_map = {"Монолитный": 3, "Панельный": 2, "Кирпичный": 3,
                  "Блочный": 1, "Деревянный": 0, "Монолитно-кирпичный": 3}

renov_map = {"Дизайнерский": 3, "Евроремонт": 2, "Косметический": 1, "Без ремонта": 0}

parking_map = {"Подземная": 2, "Наземная": 1, "Многоуровневая": 1, "Нет": 0, "Открытая": 1}

finish_map = {"Без отделки": 0, "Черновая": 0, "Предчистовая": 1,
              "White box": 1, "Чистовая": 2, "С отделкой": 2,
              "Под ключ": 2}

# CIAN_STROGINO_APARTMENTS_URL = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&p=1&region=1"
## Ссылка на циан


class CianParserWrapper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.base_name = 'house_cian.csv'
        self.driver = None

    def setup_chrome(self):
        print("Запуск Chrome...")
        options = ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # НАСТРОЙКА ДЛЯ СЕРВАКА (Комментируй если будешь с простого ноутбука запускать)

        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("window-size=1920,1080")

        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )


        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                    Object.defineProperty(navigator, 'webdriver', {
                      get: () => undefined
                    })
                """
        })
        self.driver.maximize_window()

    def get_links_from_current_page(self):
        print(f"Заходим на главную страницу: {self.base_url}")
        time.sleep(uniform(3, 5))
        # Проверка на капчу (ручная пауза если нужно)
        if "captcha" in self.driver.title.lower():
            input("!!! Обнаружена капча...")

        links = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-name="CardComponent"]')
            print(f"Найдено карточек: {len(cards)}")

            for card in cards:
                try:
                    link_el = card.find_element(By.CSS_SELECTOR, 'a[href*="/sale/flat/"]')
                    link = link_el.get_attribute('href')
                    if link not in [l['url'] for l in links]:
                        links.append({
                            'url': link,
                            'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                        })
                except Exception:
                    continue
        except Exception as e:
            print(f"Ошибка при сборе ссылок: {e}")

        return links

    def get_feature_by_text(self, text_label):
        try:
            xpath = f"//div[contains(text(), '{text_label}')]/following-sibling::div"
            element = self.driver.find_element(By.XPATH, xpath)
            return element.text
        except:
            try:
                xpath = f"//span[contains(text(), '{text_label}')]/../following-sibling::span" 
                element = self.driver.find_element(By.XPATH, xpath)
                return element.text
            except:
                return None

    def parse_page(self, url):
        self.driver.get(url)
        time.sleep(uniform(4, 7))

        data = {'url': url}
        price_found = False

        try:
            self.driver.execute_script("window.scrollTo(0, 300);")

            # === 1. ПОИСК ЦЕНЫ ===
            # Стратегия 1: Перебор XPath (только визуальные элементы)
            price_xpaths = [
                "//span[@itemprop='price']",
                "//div[@data-name='PriceInfo']//span",
                "//h1/following-sibling::div//span[contains(text(), '₽')]",
                "//span[contains(text(), '₽') and not(contains(text(), 'за м'))]"  # Исключаем цену за метр
            ]

            for xpath in price_xpaths:
                try:
                    element = self.driver.find_element(By.XPATH, xpath)
                    raw_text = element.text.strip()
                    # Чистим от всего кроме цифр
                    digits = ''.join(filter(str.isdigit, raw_text))
                    if digits:
                        clean_price = int(digits)
                        if clean_price > 5000000:
                            data['price'] = clean_price
                            price_found = True
                            break
                except:
                    continue

                # Если визуально не нашли, ищем в JS-объектах или Мета-тегах (ЭТО ТЕПЕРЬ ВНЕ ЦИКЛА)
            if not price_found:
                try:
                    # Вариант 1: Ищем в исходном коде страницы (самый надежный метод)
                    page_source = self.driver.page_source
                    if '"offerPrice":' in page_source:
                        # Грубый парсинг JSON из текста страницы
                        part = page_source.split('"offerPrice":')[1].split(',')[0]
                        clean_price = int(''.join(filter(str.isdigit, part)))
                        data['price'] = clean_price
                        price_found = True
                except:
                    pass

            # Стратегия 3: Мета-теги (последний шанс)
            if not price_found:
                try:
                    # Ищем мета-тег с ценой (обратите внимание на разные варианты)
                    meta = self.driver.find_element(By.CSS_SELECTOR, "meta[property='product:price:amount']")
                    if meta:
                        data['price'] = int(float(meta.get_attribute("content")))
                        price_found = True
                except:
                    pass

            if not price_found:
                print(f"Price not found for {url}")
                return data

                # === 2. ОБЩАЯ ПЛОЩАДЬ ===
            try:
                area_val = -1
                raw_text_square = ""
                raw_text_floor = ""

                area_el = self.driver.find_elements(By.CSS_SELECTOR, "div[data-name='ObjectFactoidsItem']")
                for area_text in area_el:
                    if "Общая площадь" in area_text.text:
                        raw_text_square = area_text.text
                        break

                # === 3. ЭТАЖ ИЗ ВСЕХ ЭТАЖЕЙ ===
                floor_el = self.driver.find_elements(By.CSS_SELECTOR, "div[data-name='ObjectFactoidsItem']")
                for floor_text in floor_el:
                    if "Этаж" in floor_text.text:
                        floor_text = sub(r'^\D*', '', floor_text.text)
                        raw_text_floor = floor_text
                        break

                # ОЧИСТКА ТЕКСТА
                import re
                matches = re.findall(r'(\d+[.,]?\d*)', raw_text_square)

                for match in matches:
                    temp_val = float(match.replace(',', '.'))
                    if 15 <= temp_val <= 500:
                        area_val = temp_val
                        break

                data['area'] = area_val
                data['floor'] = raw_text_floor
            except Exception as e:
                print(f"Error problem with parsing square: {e}")
                data['area'] = -1
                data['floor'] = -1

            # === 4. МЕТРО И УДАЛЕННОСТЬ ===
            try:
                metro_raw = self.driver.find_element(By.CSS_SELECTOR, "a[class*='underground_link']")
                data['metro'] = metro_raw.text

                time_to_metro = self.driver.find_element(By.CSS_SELECTOR, "span[class*='underground_time']")
                raw_time_metro = time_to_metro.text
                if 'откроется' in raw_time_metro:
                    data['time_to_metro_minutes'] = -1
                else:
                    res = search(r'\d+', raw_time_metro)
                    data['time_to_metro_minutes'] = int(res.group())
            except:
                data['metro'] = -1
                data['time_to_metro_minutes'] = -1

            # === 5. ОТДЕЛКА ЖИЛЬЯ ===
            try:
                finish_text = ""
                finish_raw = self.driver.find_elements(By.CSS_SELECTOR, "div[data-name='OfferSummaryInfoItem']")

                for fin_text in finish_raw:
                    if "отделк" in fin_text.text.lower():
                        finish = fin_text.text.split('\n')
                        if len(finish) > 1:
                            finish_text = finish[1]
                        break

                if not finish_text:
                    finish_text = self.get_feature_by_text("Отделка")

                key_word_finish = finish_text.split()[0].title() if finish_text else ""
                data['finish'] = finish_map.get(key_word_finish, -1)
            except:
                data['finish'] = -1


            # === 6. РЕНОВАЦИЯ ===

            try:
                raw_ren_text = ""
                ren_el = self.driver.find_elements(By.CSS_SELECTOR, "div[data-name='OfferSummaryInfoItem']")
                for ren_text in ren_el:
                    if "ремон" in ren_text.text.lower():
                        ren_base = ren_text.text.split('\n')
                        raw_ren_text = ren_base[1]
                        break

                if not raw_ren_text:
                    raw_ren_text = self.get_feature_by_text("Ремонт")

                key_word_ren = raw_ren_text.split()[0].title() if raw_ren_text else ""
                data['renovation'] = renov_map.get(key_word_ren, -1)
            except:
                data['renovation'] = -1

            # === 7. ОСТАЛЬНЫЕ ПАРАМЕТРЫ ===

            house_raw = self.get_feature_by_text("Тип дома")
            data['house_type'] = house_type_map.get(house_raw, 0)

            parkin_raw = self.get_feature_by_text("Парковка")
            data['parking'] = parking_map.get(parkin_raw, 0)

            # === ГОД ПОСТРОЙКИ ===
            try:
                raw_year = ""
                el_year = self.driver.find_element(By.CSS_SELECTOR, "div[class*='text]")
                raw_year = el_year.text
                data['year_built'] = raw_year

            except:
                data['year_built'] = -1

        except Exception as e:
            print(f"Ошибка парсинга страницы: {e}")

        return data

    def save_to_csv(self, data_list):
        new_df = pd.DataFrame(data_list)
        new_df = new_df.dropna(subset=['price'])

        if os.path.exists(self.base_name):
            old_df = pd.read_csv(self.base_name)
            final_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['url'], keep='last')
        else:
            final_df = new_df

        final_df.to_csv(self.base_name, index=False, encoding='utf-8-sig')
        print(f"Файл {self.base_name} успешно обновлен!")


def page_updater_and_run_parser():
    base_url = "https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=1"
    parser = CianParserWrapper(base_url)
    parser.setup_chrome()

    all_links = []
    unique_links = set()
    page_num = 1

    try:
        while True:
            print(f"--- СКАНИРУЕМ СТРАНИЦУ {page_num} ---")
            curr_page = f"{base_url}&p={page_num}"

            parser.driver.get(curr_page)
            time.sleep(uniform(4, 5))

            page_link = parser.get_links_from_current_page()

            count = 0
            for link in page_link:
                if  link['url'] not in unique_links:
                    unique_links.add(link['url'])
                    all_links.append(link)
                    count += 1

            if not page_link:
                break

            print(f"--- Успешно собрано {len(page_link)} ссылок из {len(all_links)} ---")

            if page_num >= 38:
                break

            page_num += 1

        if not all_links:
            print("Ссылки не найдены. Возможно, капча или изменилась верстка.")
        else:
            res_data = []
            # Парсим все сразу и сохраняем в csv
            for i, link_data in enumerate(all_links[:1000]):
                url = link_data.get('url')
                print(f"[{i + 1}/{len(all_links[:1000])}] Парсим: {url}")

                info = parser.parse_page(url)
                time.sleep(uniform(4, 5))

                if 'price' in info:
                    info['date'] = link_data.get('date')
                    res_data.append(info)
                else:
                    print("   -> Не удалось извлечь данные.")

            if res_data:
                parser.save_to_csv(res_data)
            else:
                print("Нет данных для сохранения (res_data пуст).")
    except Exception as e:
        print(f"Глобальная ошибка: {e}")
    finally:
        if parser.driver:
            time.sleep(10)
            parser.driver.quit()

if __name__ == '__main__':
    page_updater_and_run_parser()