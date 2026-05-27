from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderType
from app.schemas import OrderRequest
from app.services.execution import execute_trade

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/execute")
async def execute(payload: OrderRequest, db: Session = Depends(get_db)) -> dict:
    if payload.order_type == OrderType.LIMIT and payload.entry_price is None:
        raise HTTPException(422, "entry_price is required for LIMIT orders")

    group, results = await execute_trade(
        db,
        account_ids=payload.account_ids,
        symbol=payload.symbol,
        side=payload.side,
        order_type=payload.order_type,
        entry_price=payload.entry_price,
        sl_price=payload.sl_price,
        tp_price=payload.tp_price,
    )
    return {"trade_group_id": group.id, "results": results}
