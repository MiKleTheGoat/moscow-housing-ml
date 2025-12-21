from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import os
import pandas as pd
import time
from random import uniform

house_type_map = {
    "Монолитный": 3,
    "Панельный": 2,
    "Кирпичный": 3,
    "Блочный": 1,
    "Деревянный": 0
}
renov_map = {"Дизайнерский": 3, "Евроремонт": 2, "Косметический": 1, "Без ремонта": 0}
class_map = {"Премиум": 4, "Бизнес": 3, "Комфорт": 2, "Типовой": 1}
parking_map = {"Подземная": 2, "Наземная": 1, "Многоуровневая": 1, "Нет": 0}
finish_map = {
    "Без отделки": 0,
    "Черновая": 0,
    "Предчистовая": 1,
    "White box": 1,
    "Чистовая": 2,
    "С отделкой": 2,
    "Под ключ": 2
}

# Название на ЦИАН : Имя колонки в таблице
features_to_find = {
    "Тип дома": "house_type",
    "Парковка": "parking",
    "Отделка": "finish",
    "Класс": "jk_class"
}
url_main = 'https://www.cian.ru/kupit-kvartiru-moskva-metro-strogino/'

# Основной класс для парсинга ЦИАН
class CianParserWrapper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.base_name = 'house_cian.csv'

    # Инициализация драйвера Safari
    def ScrapSafari(self):
        options = SafariOptions()
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        options.set_capability("browserName", "safari")
        self.driver = webdriver.Safari(options=options)
        self.driver.maximize_window()
    # Получение всех ссылок на жилье с главной страницы
    def get_links(self):
        self.driver.get(self.base_url)
        time.sleep(uniform(5, 7))
        #Сначала обрабатываем враппер офферов где все карточки
        offer_wrapper = self.driver.find_element(By.CSS_SELECTOR, '[data-name*="Offers"]')
        #Затем находим все карточки внутри враппера
        cards = self.driver.find_elements(By.CSS_SELECTOR, 'article[data-name*="CardComponent"]')

        links = []
        #Проходим по всем карточкам и вытаскиваем ссылки и дату создания
        for card in cards:
            try:
                link = card.find_element(By.TAG_NAME, 'a').get_attribute('href')
                links.append({
                    'url': link,
                    'date': pd.Timestamp.now().strftime('%Y-%m-%d')
                })
            except Exception as e:
                print(f"Error extracting link: {e}")
                continue
        return links
    #Парсим страницу по ссылке
    def parse_page(self, url):
        self.driver.get(url)
        time.sleep(uniform(7, 9))
        data = {'url': url}
        wait = WebDriverWait(self.driver, 25)
        try:
            self.driver.execute_script("window.scrollTo(0, 750);")
            time.sleep(2)
            #Цена жилья
            price_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'span[data-name*="OfferPrice"]')))
            price_raw = price_element.text
            data['price'] = int(''.join(filter(str.isdigit, price_raw)))
            #Площадь жилья
            area_XPATH = "//span[contains(text(), 'Общая')]/following-sibling::span"
            try:
                area_element = self.driver.find_element(By.XPATH, area_XPATH)
                area_raw = area_element.text
                data['area'] = float(area_raw.split()[0].replace('м²', '').replace(",", ".").rstrip(''))
            except:
                data['area'] = -1

            repair_xpath = "//span[contains(text(), 'Ремонт')]/following-sibling::span"
            try:
                repair_element = self.driver.find_element(By.XPATH, repair_xpath)
                repair_raw = repair_element.text
                data['renovation'] = renov_map.get(repair_raw, -1)
            except:
                data['renovation'] = -1

            #Теперь блок кода где лежат доп параметры о жилье
            all_list = self.driver.find_elements(By.CSS_SELECTOR, 'ul[class*="--list"]')

            for features in all_list:
                items = features.find_elements(By.CSS_SELECTOR, 'li[class*="--item"]')

                for item in items:
                    content = item.text
                    for cian_key, cian_csv in features_to_find.items():
                        if cian_key in content:
                            #Разбиваем по переносу строки, берем последний элемент (значение)
                            value = content.split('\n')[-1].strip()
                            #Маппинг значений
                            if cian_key == "Отделка":
                                data[cian_csv] = finish_map.get(value, -1)
                            elif cian_key == "Класс":
                                data[cian_csv] = class_map.get(value, -1)
                            elif cian_key == "Парковка":
                                data[cian_csv] = parking_map.get(value, -1)
                            elif cian_key == "Тип дома":
                                data[cian_csv] = house_type_map.get(value, 0)
                            else:
                                data[cian_csv] = value
        except Exception as e:
            print(f"Error extracting features: {url} : {e}")
        return data
    #Сохранение данных в CSV
    def save_to_csv(self, data_list):
        new_df = pd.DataFrame(data_list)
        if os.path.exists(self.base_name):
            old_df = pd.read_csv(self.base_name)
            # Удаляем дубликаты по URL, чтобы не парсить одно и то же дважды
            final_df = pd.concat([old_df, new_df]).drop_duplicates(subset=['url'], keep='last')
        else:
            final_df = new_df
        final_df.to_csv(self.base_name, index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    parser = CianParserWrapper(url_main)
    parser.ScrapSafari()
    links = parser.get_links()

    res_data = []
    # Парсим первые 5 для теста
    for i, link_data in enumerate(links[:5]):
        url = link_data.get('url')
        if not url:
            continue

        print(f"[{i + 1}/5] Парсим: {url}")
        info = parser.parse_page(url)

        # СОХРАНЯЕМ ТОЛЬКО ЕСЛИ ЕСТЬ ЦЕНА
        if 'price' in info:
            info['date'] = link_data.get('date', pd.Timestamp.now().strftime('%Y-%m-%d'))
            res_data.append(info)
            print(f"--- Успешно: {info['price']} руб.")
        else:
            print(f"--- Пропущено: Данные не найдены для {url}")

    if res_data:
        parser.save_to_csv(res_data)
        print(f"Сохранено объектов: {len(res_data)}")

    parser.driver.quit()
    print("Работа завершена.")
