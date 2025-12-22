import os
import time
from random import uniform

import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.safari.options import Options as SafariOptions

house_type_map = {"Монолитный": 3, "Панельный": 2, "Кирпичный": 3, "Блочный": 1, "Деревянный": 0,
                  "Кирпично-монолитный": 3}
renov_map = {"Дизайнерский": 3, "Евроремонт": 2, "Косметический": 1, "Без ремонта": 0}
class_map = {"Премиум": 4, "Бизнес": 3, "Комфорт": 2, "Типовой": 1}
parking_map = {"Подземная": 2, "Наземная": 1, "Многоуровневая": 1, "Нет": 0}
finish_map = {"Без отделки": 0, "Черновая": 0, "Предчистовая": 1, "White box": 1, "Чистовая": 2, "С отделкой": 2,
              "Под ключ": 2}

CIAN_STROGINO_APARTMENTS_URL = 'https://www.cian.ru/cat.php?deal_type=sale&engine_version=2&foot_min=45&metro%5B0%5D=228&offer_type=flat&only_foot=2'


class CianParserWrapper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.base_name = 'house_cian.csv'
        self.driver = None

    def scrape_safari(self):
        print("Запуск Safari...")
        options = SafariOptions()
        self.driver = webdriver.Safari(options=options)
        self.driver.maximize_window()

    def get_links(self):
        print(f"Заходим на главную страницу: {self.base_url}")
        self.driver.get(self.base_url)
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
                xpath = f"//span[contains(text(), '{text_label}')]/../following-sibling::span"  # или li
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

            # Стратегия 2: Если визуально не нашли, ищем в JS-объектах или Мета-тегах (ЭТО ТЕПЕРЬ ВНЕ ЦИКЛА)
            if not price_found:
                try:
                    # Вариант А: Ищем в исходном коде страницы (самый надежный метод)
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
                raw_text = ""

                area_el = self.driver.find_elements(By.CSS_SELECTOR, "div[data-name='ObjectFactoidsItem']")
                for area_text in area_el:
                    if "Общая площадь" in area_text.text:
                        raw_text = area_text.text
                        break

                if not raw_text:
                    raw_text = self.driver.find_element(By.TAG_NAME, "h1")
                    raw_text = raw_text.text

                # ОЧИСТКА ТЕКСТА
                import re
                matches = re.findall(r'(\d+[.,]?\d*)', raw_text)

                for match in matches:
                    temp_val = float(match.replace(',', '.'))
                    if 15 <= temp_val <= 500:
                        area_val = temp_val
                        break

                data['area'] = area_val
            except Exception as e:
                print(f"Error problem with parsing square: {e}")
                data['area'] = -1

            # === 3. МЕТРО И УДАЛЕННОСТЬ ===
            try:
                metro_raw = self.driver.find_element(By.XPATH, "//a[contains(@href, 'metro')]")
                data['metro'] = metro_raw.text

                time_to_metro = self.driver.find_element(By.XPATH, "//a[contains(@href, 'metro')]/following-sibling::span")
                data['time_to_metro'] = time_to_metro.text
            except:
                data['metro'] = "Not found"
                data['time_to_metro'] = "Not found"

            # === 4. ОСТАЛЬНЫЕ ПАРАМЕТРЫ ===
            renov_raw = self.get_feature_by_text("Ремонт")
            data['renovation'] = renov_map.get(renov_raw, -1)

            house_raw = self.get_feature_by_text("Тип дома")
            data['house_type'] = house_type_map.get(house_raw, 0)

            parkin_raw = self.get_feature_by_text("Парковка")
            data['parking'] = parking_map.get(parkin_raw, 0)

            finish_raw = self.get_feature_by_text("Отделка")
            data['finish'] = finish_map.get(finish_raw, -1)

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


if __name__ == '__main__':
    parser = CianParserWrapper(CIAN_STROGINO_APARTMENTS_URL)
    parser.scrape_safari()

    try:
        links = parser.get_links()

        if not links:
            print("Ссылки не найдены. Возможно, капча или изменилась верстка.")
        else:
            res_data = []
            # Парсим все сразу и сохраняем в csv
            for i, link_data in enumerate(links[:2]):
                url = link_data.get('url')
                print(f"[{i + 1}] Парсим: {url}")

                info = parser.parse_page(url)

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
        time.sleep(10)
        parser.driver.quit()
