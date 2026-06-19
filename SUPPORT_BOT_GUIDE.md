# 📚 Методичка: Система двух ботов — Техподдержка

> Проект: `bot_mini_map_ml_moscow`
> Стек: Python · aiogram 3 · SQLAlchemy async · SQLite

---

## 🤔 Почему вообще ДВА бота, а не один?

Хороший вопрос. Ведь можно было бы просто добавить команды в один бот.

**Проблема:** если пользователь и оператор сидят в одном боте, то:
- Пользователь видит команды оператора (`/answer`, `/list`)
- Нужно везде проверять `if user_id == ADMIN_ID` — код засоряется
- Неудобно: оператор работает в том же интерфейсе, что и обычный пользователь

**Решение — два бота:**
```
MAIN_BOT        — публичный, для всех пользователей
SUPPORT_BOT     — приватный, только для оператора/поддержки
```

Это стандартная практика в продакшн-проектах. Например, у Авито, Озона, банков — отдельный бот для саппорта, отдельный для клиентов.

---

## 🏗️ Архитектура: как это работает

```
Пользователь                       Оператор (ты)
     │                                   │
     ▼                                   ▼
[ MAIN_BOT ]                   [ SUPPORT_BOT ]
  /ticket → собирает            /answer → отвечает
  тему + описание               /list   → смотрит тикеты
     │                                   │
     └──────────────┬────────────────────┘
                    │
             [ SQLite БД ]
              таблица: tickets
                    │
         ticket_id, user_id, subject,
         description, status, created_at
```

**Ключевая идея:** оба бота работают с ОДНОЙ базой данных.
- MAIN_BOT пишет тикет в БД
- SUPPORT_BOT читает тикет из той же БД и отправляет ответ

Это называется **shared storage** — общее хранилище между сервисами.

---

## ❓ Почему при заливке на GitHub почти ничего не залилось?

Это **не баг** — это правильная работа `.gitignore`. Вот что там прописано:

```
__pycache__/          ← кэш Python (генерируется автоматически)
.venv/                ← виртуальное окружение (сотни МБ библиотек)
*.pyc                 ← скомпилированные файлы Python
.env                  ← СЕКРЕТЫ: токены, пароли — никогда не заливать!
Bot_mini_map_ai/data/csv/     ← CSV с данными (большие файлы)
Bot_mini_map_ai/data/models/  ← обученные ML-модели
data/*.db             ← база данных SQLite
*.log                 ← логи
.cache/               ← кэш
```

### Почему это правильно?

| Что не залилось | Почему не нужно заливать |
|----------------|--------------------------|
| `.venv/` | Это 200–500 МБ чужих библиотек. Их ставят через `pip install -r requirements.txt` |
| `.env` | Там токены Telegram, пароли — если залить, боты угонят за минуты |
| `*.db` | База данных — у каждого своя, локальная |
| `__pycache__/` | Генерируется при первом запуске автоматически |
| `data/csv/` | Большие датасеты — хранят отдельно (S3, Google Drive) |

### Что ДОЛЖНО залиться:
```
✅ Весь Python-код (.py файлы)
✅ requirements.txt
✅ README.md
✅ .gitignore
✅ .env.example   ← шаблон без реальных значений
```

### Как другой человек запустит твой проект:
```bash
git clone https://github.com/MiKleTheGoat/moscow-housing-ml
cd moscow-housing-ml
python -m venv .venv
source .venv/bin/activate        # на mac/linux
pip install -r requirements.txt
cp .env.example .env             # заполнить своими токенами
python -m Bot_mini_map_ai.main_bot.main
```

> **Совет:** создай `.env.example` — файл с пустыми переменными как шаблон, без реальных значений.

---

## 🗄️ Шаг 1 — Добавить модель Ticket в БД

**Файл:** `Bot_mini_map_ai/storage/models.py`

### Почему нужна отдельная таблица Ticket?

Сейчас тикет создаётся в памяти (`uuid.uuid4()`) и сразу умирает — если бот перезапустится, все тикеты теряются. База данных решает это: тикет записывается на диск и живёт вечно.

### Почему такая структура полей?

```python
class Ticket(Base):
    __tablename__ = "tickets"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    # ↑ Внутренний ID в БД. autoincrement — SQLite сам считает 1, 2, 3...

    ticket_id   = Column(String, unique=True, nullable=False)
    # ↑ Человекочитаемый ID типа "A1B2C3D4". unique=True — не может быть двух одинаковых.
    #   nullable=False — поле обязательное, без него запись не создастся.

    user_id     = Column(Integer, nullable=False)
    # ↑ Telegram ID пользователя. Нужен чтобы потом отправить ему ответ через bot.send_message().

    username    = Column(String, nullable=True)
    # ↑ @username — nullable=True потому что у некоторых пользователей нет username в Telegram.

    subject     = Column(String, nullable=False)
    description = Column(String, nullable=False)
    # ↑ Тема и описание — то что пользователь ввёл через FSM.

    status      = Column(String, default="open")
    # ↑ Статус тикета. default="open" — новый тикет всегда открытый.
    #   Когда оператор ответит — меняем на "closed".

    created_at  = Column(DateTime, default=datetime.utcnow)
    # ↑ Когда создан. utcnow — UTC время, стандарт для серверов.

    answered_at = Column(DateTime, nullable=True)
    # ↑ Когда ответили. nullable=True — при создании тикета ещё нет ответа.
```

---

## 🔌 Шаг 2 — Обновить db.py

**Файл:** `Bot_mini_map_ai/storage/db.py`

### Почему нужен AsyncSessionLocal?

В текущем коде есть только `AsyncSession = async_sessionmaker(...)` — это для FastAPI через `Depends(get_session)`. Но в хэндлерах aiogram нет FastAPI, поэтому нужен способ открывать сессию вручную через `async with`.

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
# ↑ echo=False — не выводить SQL-запросы в консоль (в режиме разработки можно True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
# ↑ expire_on_commit=False — после commit() объекты не "протухают".
#   Без этого после сохранения нельзя читать поля объекта — SQLAlchemy сбрасывает их.

async def get_session():
    # Для FastAPI через Depends — yield передаёт сессию в функцию и закрывает после
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    # Создаёт все таблицы в БД если их нет. Вызывается при старте бота.
    # create_all — безопасен: если таблица уже есть, не пересоздаёт её.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

## 💾 Шаг 3 — Исправить ticket.py (сохранять в БД)

**Файл:** `Bot_mini_map_ai/main_bot/handlers/ticket.py`

### Почему сейчас тикеты теряются?

В текущем коде:
```python
ticket_id = uuid.uuid4().hex[:8].upper()  # создали в памяти
# ... отправили в Telegram ...
# КОНЕЦ — тикет нигде не записан!
```

Как только бот перезапустится — этого ticket_id уже нет нигде. Оператор получил уведомление, но найти тикет в БД невозможно.

### Исправленный `ticket_confirm`:

```python
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket

@router.callback_query(F.data == "ticket_confirm", StateFilter(TicketForm.confirm))
async def ticket_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    data      = await state.get_data()
    ticket_id = uuid.uuid4().hex[:8].upper()

    # ✅ Сохраняем в БД ДО отправки сообщений
    # Почему до? Чтобы если Telegram упадёт — тикет всё равно был сохранён.
    async with AsyncSessionLocal() as session:
        ticket = Ticket(
            ticket_id   = ticket_id,
            user_id     = callback.from_user.id,
            username    = callback.from_user.username,
            subject     = data["subject"],
            description = data["description"],
            # status = "open" — не пишем, он default в модели
        )
        session.add(ticket)       # добавляем объект в сессию (ещё не в БД)
        await session.commit()    # ← вот здесь реально пишется на диск

    await state.clear()   # очищаем FSM-состояние пользователя

    await callback.message.edit_text(
        f"Тикет <b>{ticket_id}</b> создан.\n"
        f"Скоро с вами свяжется оператор."
    )

    await callback.bot.send_message(
        settings.ADMIN_ID,
        f"📩 Новый тикет <b>{ticket_id}</b>\n"
        f"От: @{callback.from_user.username or callback.from_user.id}\n"
        f"Тема: {data['subject']}\n"
        f"Описание: {data['description']}\n\n"
        f"Ответить: /answer"
    )
    await callback.answer()
```

---

## 🤖 Шаг 4 — Написать support_bot/main.py

**Файл:** `Bot_mini_map_ai/support_bot/main.py`

### Почему структура такая же как у main_bot?

Потому что это тоже aiogram-бот. Разница только в:
- `SUPPORT_BOT_TOKEN` вместо `MAIN_BOT_TOKEN`
- Подключены другие роутеры (хэндлеры оператора)

```python
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.support_bot.handlers import answer_ticket
from Bot_mini_map_ai.storage.db import init_db

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await init_db()
    # ↑ Создаём таблицы в БД если их нет. Безопасно вызывать каждый раз при старте.

    bot = Bot(
        token=settings.SUPPORT_BOT_TOKEN,
        # ↑ Другой токен! Это отдельный бот в Telegram.
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        # ↑ HTML по умолчанию — чтобы везде работали теги <b>, <i> без явного указания
    )

    dp = Dispatcher(storage=MemoryStorage())
    # ↑ MemoryStorage — FSM-состояния хранятся в оперативной памяти.
    #   Минус: при перезапуске бота оператор потеряет текущее состояние /answer.
    #   Для продакшна лучше RedisStorage, но для начала MemoryStorage достаточно.

    dp.include_router(answer_ticket.router)
    # ↑ Подключаем роутер с командами /answer и /list

    await bot.delete_webhook(drop_pending_updates=True)
    # ↑ Удаляем старые сообщения которые накопились пока бот был выключен.
    #   drop_pending_updates=True — игнорируем всё что пришло пока нас не было.

    await dp.start_polling(bot)
    # ↑ Запускаем бота в режиме polling — постоянно спрашивает Telegram "есть новые сообщения?"


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 💬 Шаг 5 — Написать answer_ticket.py

**Файл:** `Bot_mini_map_ai/support_bot/handlers/answer_ticket.py`

### Почему здесь тоже FSM?

Потому что `/answer` — это диалог из двух шагов:
1. Введи ID тикета
2. Введи текст ответа

Без FSM бот не знает на каком шаге находится оператор. FSM "запоминает" что оператор уже ввёл ID и теперь ждёт текст.

### Почему создаём новый `Bot(token=MAIN_BOT_TOKEN)`?

Потому что support_bot работает со своим токеном, а ответить пользователю нужно через MAIN_BOT (пользователь написал туда). Поэтому мы создаём временный экземпляр main_bot прямо в хэндлере.

```python
import logging
from datetime import datetime
from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket

logger = logging.getLogger(__name__)
router = Router()
# ↑ Router — это как "мини-диспетчер" для группы хэндлеров.
#   Позволяет разбить хэндлеры по файлам и подключать через dp.include_router().


class AnswerForm(StatesGroup):
    ticket_id = State()   # Шаг 1: ждём ID тикета
    text      = State()   # Шаг 2: ждём текст ответа


@router.message(Command("answer"))
async def cmd_answer(message: Message, state: FSMContext) -> None:
    # Проверяем что команду написал именно оператор, а не кто-то другой
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return

    await state.set_state(AnswerForm.ticket_id)
    # ↑ Переводим пользователя в состояние "ждём ticket_id"
    await message.answer("Введи ID тикета (например: A1B2C3D4):")


@router.message(AnswerForm.ticket_id)
async def get_ticket_id(message: Message, state: FSMContext) -> None:
    # Этот хэндлер сработает ТОЛЬКО если state == AnswerForm.ticket_id
    # Именно так FSM фильтрует сообщения
    await state.update_data(ticket_id=message.text.strip().upper())
    # ↑ strip() — убираем пробелы, upper() — делаем заглавными (A1B2C3D4, не a1b2c3d4)
    # update_data — сохраняем в FSM-хранилище (временная память для этого диалога)

    await state.set_state(AnswerForm.text)
    await message.answer("Напиши ответ пользователю:")


@router.message(AnswerForm.text)
async def send_answer(message: Message, state: FSMContext) -> None:
    data        = await state.get_data()   # достаём ticket_id из FSM
    ticket_id   = data["ticket_id"]
    answer_text = message.text

    # Ищем тикет в БД по ticket_id
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id)
        )
        ticket = result.scalar_one_or_none()
        # ↑ scalar_one_or_none() — вернёт объект Ticket или None если не нашли

    if not ticket:
        await message.answer(f"❌ Тикет {ticket_id} не найден.")
        await state.clear()   # сбрасываем FSM
        return

    # Создаём временный экземпляр MAIN_BOT чтобы отправить ответ пользователю
    # Почему не можем отправить через текущий support_bot?
    # Потому что пользователь написал в main_bot — ответ должен прийти оттуда же.
    main_bot = Bot(token=settings.MAIN_BOT_TOKEN)
    try:
        await main_bot.send_message(
            ticket.user_id,   # ← user_id мы взяли из БД (сохранили при создании тикета)
            f"📬 Ответ на тикет <b>{ticket_id}</b>:\n\n{answer_text}"
        )
    finally:
        await main_bot.session.close()
        # ↑ ВАЖНО: всегда закрывать сессию Bot() чтобы не было утечки соединений

    # Обновляем статус в БД
    async with AsyncSessionLocal() as session:
        t = await session.get(Ticket, ticket.id)
        t.status      = "closed"
        t.answered_at = datetime.utcnow()
        await session.commit()

    await message.answer(f"✅ Ответ отправлен. Тикет {ticket_id} закрыт.")
    await state.clear()   # сбрасываем FSM — диалог завершён


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    # Показываем все открытые (неотвеченные) тикеты
    if message.from_user.id != settings.ADMIN_ID:
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.status == "open")
            # ↑ Фильтруем: только открытые тикеты
        )
        tickets = result.scalars().all()
        # ↑ scalars() — достаём объекты Ticket, all() — все результаты списком

    if not tickets:
        await message.answer("✅ Открытых тикетов нет.")
        return

    lines = ["<b>📋 Открытые тикеты:</b>\n"]
    for t in tickets:
        lines.append(f"• <b>{t.ticket_id}</b> — @{t.username or t.user_id}\n  Тема: {t.subject}")
    await message.answer("\n".join(lines))
```

---

## 🚀 Запуск обоих ботов

### Вариант 1 — два отдельных терминала (проще для разработки)

```bash
# Терминал 1
python -m Bot_mini_map_ai.main_bot.main

# Терминал 2
python -m Bot_mini_map_ai.support_bot.main
```

### Вариант 2 — один файл run_all.py (через asyncio.gather)

```python
import asyncio
import Bot_mini_map_ai.main_bot.main as main_bot
import Bot_mini_map_ai.support_bot.main as support_bot

async def run():
    await asyncio.gather(
        main_bot.main(),
        support_bot.main(),
    )
    # ↑ asyncio.gather запускает обе корутины ОДНОВРЕМЕННО в одном event loop.
    #   Это не многопоточность — Python всё ещё однопоточный.
    #   Но пока один бот "ждёт" ответа от Telegram, второй работает.

asyncio.run(run())
```

---

## 📊 Полный поток данных

```
1. Пользователь пишет /ticket → MAIN_BOT
         │
         ├─ FSM шаг 1: вводит тему       (state = TicketForm.subject)
         ├─ FSM шаг 2: вводит описание   (state = TicketForm.description)
         └─ жмёт "✅ Отправить"          (state = TicketForm.confirm)
                  │
                  ├─ ticket_id = "A1B2C3D4"
                  ├─ Ticket → записывается в БД (status="open")
                  ├─ Пользователю: "Тикет создан, ждите"
                  └─ Оператору через SUPPORT_BOT: "📩 Новый тикет A1B2C3D4"

2. Оператор пишет /answer → SUPPORT_BOT
         │
         ├─ FSM шаг 1: вводит "A1B2C3D4" (state = AnswerForm.ticket_id)
         └─ FSM шаг 2: вводит текст       (state = AnswerForm.text)
                  │
                  ├─ Ищет Ticket в БД по ticket_id
                  ├─ Создаёт Bot(MAIN_BOT_TOKEN)
                  ├─ Отправляет ответ пользователю через MAIN_BOT
                  ├─ Ticket в БД: status="closed", answered_at=now()
                  └─ Оператору: "✅ Ответ отправлен"
```

---

## ⚠️ Важные концепции которые нужно понять

### FSM (Finite State Machine) — машина состояний

Без FSM бот не знает контекст разговора. Каждое сообщение он обрабатывает как новое.

С FSM каждый пользователь находится в каком-то "состоянии":
```
Нет состояния → /ticket → state: subject → state: description → state: confirm → Нет состояния
```

Хэндлер `@router.message(TicketForm.subject)` сработает ТОЛЬКО если пользователь в состоянии `subject`. Для всех остальных это сообщение игнорируется.

### async/await — зачем?

Telegram-боты по природе ждут: отправил запрос к Telegram API → ждёт ответа.
Без async в это время бот был бы заморожен и не мог бы отвечать другим пользователям.

`async/await` позволяет: пока один запрос "ожидает", бот обрабатывает других пользователей.

### SQLAlchemy ORM — зачем не писать SQL руками?

Можно писать так:
```python
cursor.execute("INSERT INTO tickets VALUES (?, ?, ?)", (ticket_id, user_id, subject))
```

Но SQLAlchemy позволяет так:
```python
session.add(Ticket(ticket_id=ticket_id, user_id=user_id, subject=subject))
await session.commit()
```

Плюсы: безопаснее (нет SQL-инъекций), удобнее, легко переключиться с SQLite на PostgreSQL.

---

## ✅ Чеклист

- [ ] 1. Добавить `Ticket` в `storage/models.py`
- [ ] 2. Добавить `AsyncSessionLocal` в `storage/db.py`
- [ ] 3. Исправить `ticket.py` — добавить сохранение в БД
- [ ] 4. Написать `support_bot/main.py`
- [ ] 5. Написать `support_bot/handlers/answer_ticket.py`
- [ ] 6. Запустить оба бота
- [ ] 7. Создать `.env.example` для GitHub

---

## 📖 Ресурсы для изучения

| Тема | Ссылка |
|------|--------|
| aiogram 3 — официальная дока | https://docs.aiogram.dev/en/latest/ |
| FSM в aiogram | https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/ |
| SQLAlchemy async | https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html |
| Примеры aiogram 3 | https://github.com/aiogram/aiogram/tree/dev-3.x/examples |
| Telegram Bot API | https://core.telegram.org/bots/api |
