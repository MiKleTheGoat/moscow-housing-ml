# 📚 Методичка: Система двух ботов — Техподдержка

> Проект: `bot_mini_map_ml_moscow`  
> Стек: Python · aiogram 3 · SQLAlchemy async · SQLite

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
| `.venv/` | Это 200–500 МБ чужих библиотек. Ставят через `pip install -r requirements.txt` |
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
```

### Как другой человек запустит твой проект:
```bash
git clone https://github.com/MiKleTheGoat/...
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # заполнить своими токенами
python -m Bot_mini_map_ai.main_bot.main
```

> **Совет:** создай `.env.example` — файл с пустыми переменными как шаблон.

---

## 🏗️ Архитектура

```
MAIN_BOT (пользователь)     SUPPORT_BOT (оператор/ты)
  /ticket → FSM               /answer — ответить
  /predict                    /list   — список тикетов
  /parse
       │                           │
       └──────────┬────────────────┘
                  │
           [ SQLite БД ]
            таблица: tickets
```

**Главная идея:** два токена → два бота, но ОДНА база данных.

---

## Шаг 1 — Добавить модель Ticket (storage/models.py)

```python
class Ticket(Base):
    __tablename__ = "tickets"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id   = Column(String, unique=True, nullable=False)
    user_id     = Column(Integer, nullable=False)
    username    = Column(String, nullable=True)
    subject     = Column(String, nullable=False)
    description = Column(String, nullable=False)
    status      = Column(String, default="open")       # open / closed
    created_at  = Column(DateTime, default=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)
```

---

## Шаг 2 — Обновить db.py

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

---

## Шаг 3 — Исправить ticket.py (добавить сохранение в БД)

В функцию `ticket_confirm` добавить после генерации UUID:

```python
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket

# Сохраняем тикет в БД
async with AsyncSessionLocal() as session:
    ticket = Ticket(
        ticket_id   = ticket_id,
        user_id     = callback.from_user.id,
        username    = callback.from_user.username,
        subject     = data["subject"],
        description = data["description"],
    )
    session.add(ticket)
    await session.commit()
```

---

## Шаг 4 — Написать support_bot/main.py

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
    bot = Bot(token=settings.SUPPORT_BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(answer_ticket.router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Шаг 5 — Написать answer_ticket.py

```python
import logging
from datetime import datetime
from aiogram import Bot, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from sqlalchemy import select
from Bot_mini_map_ai.config.settings import settings
from Bot_mini_map_ai.storage.db import AsyncSessionLocal
from Bot_mini_map_ai.storage.models import Ticket

logger = logging.getLogger(__name__)
router = Router()

class AnswerForm(StatesGroup):
    ticket_id = State()
    text      = State()

@router.message(Command("answer"))
async def cmd_answer(message: Message, state: FSMContext) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        await message.answer("⛔ Нет доступа.")
        return
    await state.set_state(AnswerForm.ticket_id)
    await message.answer("Введи ID тикета (например: A1B2C3D4):")

@router.message(AnswerForm.ticket_id)
async def get_ticket_id(message: Message, state: FSMContext) -> None:
    await state.update_data(ticket_id=message.text.strip().upper())
    await state.set_state(AnswerForm.text)
    await message.answer("Напиши ответ пользователю:")

@router.message(AnswerForm.text)
async def send_answer(message: Message, state: FSMContext) -> None:
    data        = await state.get_data()
    ticket_id   = data["ticket_id"]
    answer_text = message.text

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.ticket_id == ticket_id))
        ticket = result.scalar_one_or_none()

    if not ticket:
        await message.answer(f"❌ Тикет {ticket_id} не найден.")
        await state.clear()
        return

    main_bot = Bot(token=settings.MAIN_BOT_TOKEN)
    try:
        await main_bot.send_message(
            ticket.user_id,
            f"📬 Ответ на тикет <b>{ticket_id}</b>:\n\n{answer_text}")
    finally:
        await main_bot.session.close()

    async with AsyncSessionLocal() as session:
        t = await session.get(Ticket, ticket.id)
        t.status      = "closed"
        t.answered_at = datetime.utcnow()
        await session.commit()

    await message.answer(f"✅ Ответ отправлен. Тикет {ticket_id} закрыт.")
    await state.clear()

@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if message.from_user.id != settings.ADMIN_ID:
        return
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Ticket).where(Ticket.status == "open"))
        tickets = result.scalars().all()
    if not tickets:
        await message.answer("✅ Открытых тикетов нет.")
        return
    lines = ["<b>📋 Открытые тикеты:</b>\n"]
    for t in tickets:
        lines.append(f"• <b>{t.ticket_id}</b> — @{t.username or t.user_id}\n  Тема: {t.subject}")
    await message.answer("\n".join(lines))
```

---

## 🚀 Запуск

### Два терминала:
```bash
# Терминал 1
python -m Bot_mini_map_ai.main_bot.main

# Терминал 2
python -m Bot_mini_map_ai.support_bot.main
```

### Или один файл run_all.py:
```python
import asyncio
import Bot_mini_map_ai.main_bot.main as main_bot
import Bot_mini_map_ai.support_bot.main as support_bot

async def run():
    await asyncio.gather(main_bot.main(), support_bot.main())

asyncio.run(run())
```

---

## ✅ Чеклист

- [ ] 1. Добавить `Ticket` в `storage/models.py`
- [ ] 2. Добавить `AsyncSessionLocal` в `storage/db.py`
- [ ] 3. Исправить `ticket.py` — сохранение в БД
- [ ] 4. Написать `support_bot/main.py`
- [ ] 5. Написать `support_bot/handlers/answer_ticket.py`
- [ ] 6. Запустить оба бота
- [ ] 7. Создать `.env.example` для GitHub

---

## 📖 Ресурсы

| Тема | Ссылка |
|------|--------|
| aiogram 3 | https://docs.aiogram.dev/en/latest/ |
| FSM | https://docs.aiogram.dev/en/latest/dispatcher/finite_state_machine/ |
| SQLAlchemy async | https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html |
| Примеры aiogram | https://github.com/aiogram/aiogram/tree/dev-3.x/examples |
