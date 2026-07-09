# 🏠 Moscow Housing ML - Прогнозирование цен на недвижимость в Москве

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![aiogram 3.x](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://docs.aiogram.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)

**Moscow Housing ML** — это комплексная экосистема для сбора данных, обучения моделей машинного обучения и прогнозирования цен на недвижимость в Москве. Проект включает в себя парсер объявлений недвижимости (ЦИАН), FastAPI-сервер для инференса и обучения, а также интерактивного Telegram-бота с поддержкой Telegram Mini Apps.

---

## 📂 Структура проекта

```text
bot_mini_map_ml_moscow/
├── api/                  # FastAPI сервер (ML-инференс, API для парсера)
│   ├── routes/           # Эндпоинты для парсинга, обучения и предсказаний
│   ├── main.py           # Запуск FastAPI
│   └── schemas.py        # Схемы валидации Pydantic
│
├── bot/                  # Telegram-бот (aiogram 3.x)
│   ├── handlers/         # Обработчики команд, FSM-сценариев, локации и ML
│   ├── keyboards/        # Кнопки и клавиатуры
│   ├── mini_app/         # Telegram Mini App (HTML/CSS/JS фронтенд)
│   └── main.py           # Запуск Telegram-бота
│
├── parser/               # Модуль веб-скрейпинга (ЦИАН)
│   ├── playwright.py     # Парсер на Playwright (с обходом защит)
│   └── resumer.py        # Управление возобновлением парсинга
│
├── ml/                   # Модуль машинного обучения
│   ├── train.py          # Скрипты обучения/дообучения (XGBoost / Optuna)
│   └── predict.py        # Инференс модели
│
├── model/                # Референсные материалы (исходный код и ноутбуки)
│   ├── model.py          # Исходный класс прогнозирования HousingPricePredictor
│   ├── parser.py         # Первоначальный вариант парсера
│   └── reader.ipynb      # Исследовательский Jupyter Notebook
│
├── config/               # Управление конфигурацией
│   ├── settings.py       # Pydantic Settings
│
├── data/                 # Локальное хранилище (БД, CSV, веса моделей)
└── storage/              # Файловые хранилища и сессии

```

---

## 🛠️ Технологии

* **Backend**: FastAPI, Uvicorn, Pydantic v2
* **Telegram Bot**: aiogram 3.x, FSM (Finite State Machine)
* **Web App (Mini App)**: HTML5, CSS3, JavaScript (встроен в Telegram)
* **Parser**: Playwright, Playwright Stealth, Selenium, BeautifulSoup4
* **Machine Learning**:  **LLM** (для работы со словами),XGBoost(для работ с числами), Scikit-learn, Pandas, NumPy, Optuna (для автоподбора гиперпараметров)
* **Database**: SQLAlchemy (asyncio), PostgreSQl(раньше SQLite был), Alembic

---

## 🚀 Быстрый запуск

### 1. Подготовка окружения
Клонируйте проект и перейдите в его директорию:
```bash
git clone https://github.com/MiKleTheGoat/moscow-housing-ml.git
cd bot_mini_map_ml_moscow
```

Создайте файл `.env` на основе примера:
```bash
cp config/.env
```
Заполните переменные в `.env`:
* `BOT_TOKEN` — токен вашего бота от [@BotFather](https://t.me/BotFather)
* `ADMIN_ID` — ваш Telegram ID (для уведомлений о тикетах)
* `MINI_APP_URL` — ссылка на ваш Telegram Mini App (или хост)

### 2. Запуск локально (Python)
Установите зависимости в виртуальное окружение:
```bash
python -m venv .venv
source .venv/bin/activate  # Для Linux/macOS
# или .venv\Scripts\activate для Windows

pip install -r requirements.txt
playwright install  # Установка браузеров для парсера
```

* **Запуск API-сервера:**
  ```bash
  uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
  ```
* **Запуск Telegram-бота:**
  ```bash
  python -m bot.main
  ```



---

## 📈 ML-модель предсказания цен

Модель обучается на свежих собранных данных с ЦИАН.
* **Алгоритм**: XGBoost Regressor
* **Оптимизация**: Optuna осуществляет поиск гиперпараметров на кросс-валидации для снижения MAE (средней абсолютной ошибки).
* **Метрика R²**: > 0.85 в базовых тестах.

Интеграция с ботом позволяет отправлять геолокацию или характеристики квартиры и мгновенно получать прогноз рыночной стоимости.
