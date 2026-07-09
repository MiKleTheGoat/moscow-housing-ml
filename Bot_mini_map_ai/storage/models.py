from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String(2048), unique=True, nullable=False)
    price = Column(Integer, nullable=False)
    predicted_price = Column(Float, nullable=True)
    area = Column(Float, nullable=False)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    floor = Column(Integer, nullable=True)
    floor_total = Column(Integer, nullable=True)
    metro = Column(String(255), nullable=True)
    time_to_metro = Column(Integer, nullable=True)
    house_type = Column(Integer, nullable=True)
    renovation = Column(Integer, nullable=True)
    parking = Column(Integer, nullable=True, default=0)
    finish = Column(Integer, nullable=True, default=0)
    profit = Column(Float, nullable=True)

    date = Column(DateTime(timezone=True), nullable=True)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(64), unique=True, nullable=False)
    user_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    subject = Column(String(512), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=True, default="open")
    created_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
    )
    answered_at = Column(DateTime(timezone=True), nullable=True)


class UserRequest(Base):
    __tablename__ = "user_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
