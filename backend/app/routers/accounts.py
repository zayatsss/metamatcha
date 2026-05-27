from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.brokers.manager import broker_manager
from app.database import get_db
from app.models import Account
from app.schemas import AccountCreate, AccountOut
from app.security import encrypt_password

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountOut)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> AccountOut:
    account = Account(
        label=payload.label,
        broker=payload.broker,
        login=payload.login,
        password_enc=encrypt_password(payload.password),
        server=payload.server,
        api_base_url=payload.api_base_url,
        balance=payload.balance,
        risk_percent=payload.risk_percent,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return AccountOut.model_validate(account)


@router.get("", response_model=list[AccountOut])
async def list_accounts(db: Session = Depends(get_db)) -> list[AccountOut]:
    accounts = db.query(Account).all()
    out = []
    for acc in accounts:
        dto = AccountOut.model_validate(acc)
        dto.connected = await broker_manager.status(acc.id)
        out.append(dto)
    return out


@router.post("/{account_id}/connect", response_model=AccountOut)
async def connect_account(account_id: int, db: Session = Depends(get_db)) -> AccountOut:
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(404, "account not found")
    ok = await broker_manager.connect(account)
    if not ok:
        raise HTTPException(502, "broker connection failed")
    # Подтянем актуальный баланс из терминала/брокера.
    adapter = await broker_manager.get_adapter(account)
    account.balance = await adapter.get_balance()
    db.commit()
    db.refresh(account)
    dto = AccountOut.model_validate(account)
    dto.connected = True
    return dto


@router.post("/{account_id}/disconnect")
async def disconnect_account(account_id: int) -> dict:
    await broker_manager.disconnect(account_id)
    return {"ok": True}
