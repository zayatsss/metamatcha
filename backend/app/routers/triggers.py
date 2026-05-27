from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Trigger, TriggerAction
from app.schemas import TriggerCreate, TriggerOut

router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.post("", response_model=TriggerOut)
def create_trigger(payload: TriggerCreate, db: Session = Depends(get_db)) -> TriggerOut:
    if payload.action == TriggerAction.PARTIAL_TP and not payload.partial_percent:
        raise HTTPException(422, "partial_percent is required for PARTIAL_TP")
    if payload.action == TriggerAction.CUSTOM_SL_MOVE and payload.new_sl_price is None:
        raise HTTPException(422, "new_sl_price is required for CUSTOM_SL_MOVE")

    trigger = Trigger(
        trade_group_id=payload.trade_group_id,
        account_id=payload.account_id,
        symbol=payload.symbol,
        target_price=payload.target_price,
        action=payload.action,
        partial_percent=payload.partial_percent,
        new_sl_price=payload.new_sl_price,
    )
    db.add(trigger)
    db.commit()
    db.refresh(trigger)
    return TriggerOut.model_validate(trigger)


@router.get("", response_model=list[TriggerOut])
def list_triggers(db: Session = Depends(get_db)) -> list[TriggerOut]:
    return [TriggerOut.model_validate(t) for t in db.query(Trigger).all()]


@router.delete("/{trigger_id}")
def delete_trigger(trigger_id: int, db: Session = Depends(get_db)) -> dict:
    trigger = db.get(Trigger, trigger_id)
    if not trigger:
        raise HTTPException(404, "trigger not found")
    db.delete(trigger)
    db.commit()
    return {"ok": True}
