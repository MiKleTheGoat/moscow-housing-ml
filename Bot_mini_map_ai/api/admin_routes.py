
import io
import logging
from typing import Optional

import qrcode
from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select, desc

from Bot_mini_map_ai.api.admin_auth import (
    create_access_token,
    get_or_create_totp_secret,
    get_totp_uri,
    is_ip_allowed,
    is_token_valid,
    verify_password,
    verify_totp,
)
from Bot_mini_map_ai.storage.db import AsyncSession
from Bot_mini_map_ai.storage.models import Offer, UserRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_token(request: Request) -> Optional[str]:
    token = request.cookies.get("admin_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    return token


def _require_auth(request: Request) -> None:
    token = _get_token(request)
    if not token or not is_token_valid(token):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _require_ip(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    if not is_ip_allowed(client_ip):
        logger.warning("Blocked admin access from IP: %s", client_ip)
        raise HTTPException(status_code=403, detail="IP not in whitelist")


# ─── Auth schemas ─────────────────────────────────────────────────────────────

class LoginStep1(BaseModel):
    password: str


class LoginStep2(BaseModel):
    totp_code: str


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@router.post("/login/password")
async def login_password(body: LoginStep1, request: Request):
    _require_ip(request)
    if not verify_password(body.password):
        raise HTTPException(status_code=401, detail="Неверный пароль")
    return {"step": "totp_required"}


@router.post("/login/totp")
async def login_totp(body: LoginStep2, request: Request, response: Response):
    _require_ip(request)
    if not verify_totp(body.totp_code):
        raise HTTPException(status_code=401, detail="Неверный код 2FA")

    token = create_access_token()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,   # Поставь True когда с https в продакшн
        max_age=3600,
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("admin_token")
    return {"status": "logged_out"}


# ─── Setup QR ─────────────────────────────────

@router.get("/setup-qr")
async def setup_qr(request: Request):

    _require_ip(request)
    secret = get_or_create_totp_secret()
    uri = get_totp_uri(secret)

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@router.get("/setup-secret")
async def setup_secret(request: Request):
    _require_ip(request)
    return {"secret": get_or_create_totp_secret()}


# ─── Data endpoints (require auth) ────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(request: Request):
    _require_auth(request)
    async with AsyncSession() as session:
        total_offers = (await session.execute(select(func.count(Offer.id)))).scalar()
        total_requests = (await session.execute(select(func.count(UserRequest.id)))).scalar()
        avg_price_row = (await session.execute(select(func.avg(Offer.price)))).scalar()
        good_deals = (await session.execute(
            select(func.count(Offer.id)).where(Offer.profit > 0)
        )).scalar()

    return {
        "total_offers":   total_offers,
        "total_requests": total_requests,
        "avg_price":      round(avg_price_row or 0),
        "good_deals":     good_deals,
    }


@router.get("/offers")
async def list_offers(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    sort: str = "profit",
):
    _require_auth(request)
    sort_col = {
        "profit": desc(Offer.profit),
        "price":  desc(Offer.price),
        "area":   desc(Offer.area),
        "id":     desc(Offer.id),
    }.get(sort, desc(Offer.profit))

    async with AsyncSession() as session:
        rows = (await session.execute(
            select(Offer).order_by(sort_col).limit(limit).offset(offset)
        )).scalars().all()

        total = (await session.execute(select(func.count(Offer.id)))).scalar()

    return {
        "total": total,
        "items": [
            {
                "id":              r.id,
                "url":             r.url,
                "price":           r.price,
                "predicted_price": r.predicted_price,
                "profit":          r.profit,
                "area":            r.area,
                "metro":           r.metro,
                "floor":           r.floor,
                "floor_total":     r.floor_total,
                "time_to_metro":   r.time_to_metro,
                "renovation":      r.renovation,
                "house_type":      r.house_type,
                "lat":             r.lat,
                "lng":             r.lng,
                "date":            r.date,
            }
            for r in rows
        ],
    }


@router.delete("/offers/{offer_id}")
async def delete_offer(offer_id: int, request: Request):
    _require_auth(request)
    async with AsyncSession() as session:
        row = await session.get(Offer, offer_id)
        if not row:
            raise HTTPException(status_code=404, detail="Offer not found")
        await session.delete(row)
        await session.commit()
    return {"deleted": offer_id}


@router.get("/requests")
async def list_requests(
    request: Request,
    limit: int = 50,
    offset: int = 0,
):
    _require_auth(request)
    async with AsyncSession() as session:
        rows = (await session.execute(
            select(UserRequest).order_by(desc(UserRequest.created_at)).limit(limit).offset(offset)
        )).scalars().all()
        total = (await session.execute(select(func.count(UserRequest.id)))).scalar()

    return {
        "total": total,
        "items": [
            {
                "id":         r.id,
                "user_id":    r.user_id,
                "username":   r.username,
                "latitude":   r.latitude,
                "longitude":  r.longitude,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.delete("/requests/{req_id}")
async def delete_request(req_id: int, request: Request):
    _require_auth(request)
    async with AsyncSession() as session:
        row = await session.get(UserRequest, req_id)
        if not row:
            raise HTTPException(status_code=404, detail="Request not found")
        await session.delete(row)
        await session.commit()
    return {"deleted": req_id}


# ─── Admin SPA (HTML shell) ───────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def admin_ui(request: Request):
    _require_ip(request)
    import pathlib
    html_path = pathlib.Path(__file__).parent / "admin_ui.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<p>admin_ui.html not found</p>", status_code=500)
