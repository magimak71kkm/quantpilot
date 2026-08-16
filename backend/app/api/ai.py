"""/ai/* — Gemini proxies with JSON schema validation."""
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import require_rate
from app.models.schemas import ScreenerReq, StrategyReq
from app.services.gemini_client import call_screener, call_strategy
from app.core.limits import QuotaExceeded

router = APIRouter()


@router.post("/screener/nl-to-filter")
async def screener_nl_to_filter(body: ScreenerReq, uid: str = Depends(require_rate)):
    try:
        return await call_screener(uid, body.text)
    except QuotaExceeded as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


@router.post("/strategy/from-desc")
async def strategy_from_desc(body: StrategyReq, uid: str = Depends(require_rate)):
    try:
        return await call_strategy(uid, body.text)
    except QuotaExceeded as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
