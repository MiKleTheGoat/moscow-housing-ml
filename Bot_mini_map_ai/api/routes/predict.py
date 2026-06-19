import logging
from typing import List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Bot_mini_map_ai.ml.predict import predict_price
from Bot_mini_map_ai.storage.db import get_session
from Bot_mini_map_ai.storage.models import Offer

logger = logging.getLogger(__name__)
router = APIRouter()


class PredictRequest(BaseModel):
    area: float
    floor: int
    time_to_metro: int
    renovation: int = 0
    house_type: int = 0
    parking: int = 0
    finish: int = 0


class PredictResponse(BaseModel):
    price: float
    currency: str = "RUB"


class DealResponse(BaseModel):
    id: int
    url: str
    price: int
    predicted_price: Optional[float]
    area: float
    lat: Optional[float]
    lng: Optional[float]
    metro: Optional[str]
    time_to_metro: Optional[int]
    profit: Optional[float]

    class Config:
        from_attributes = True


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    price = predict_price(req.model_dump())
    return PredictResponse(price=price)


@router.get("/deals", response_model=List[DealResponse])
async def get_deals(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Offer))
    offers = result.scalars().all()
    return offers
