from pydantic import BaseModel, ConfigDict, Field

from app.models import BrokerType, OrderSide, OrderType, TriggerAction


class AccountCreate(BaseModel):
    label: str
    broker: BrokerType
    login: str
    password: str
    server: str
    api_base_url: str | None = None
    balance: float = Field(ge=0)
    risk_percent: float = Field(gt=0, le=100)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    broker: BrokerType
    login: str
    server: str
    balance: float
    risk_percent: float
    is_active: bool
    connected: bool = False


class OrderRequest(BaseModel):
    account_ids: list[int] = Field(min_length=1)
    symbol: str
    side: OrderSide
    order_type: OrderType
    entry_price: float | None = None  # обязателен для LIMIT
    sl_price: float
    tp_price: float | None = None


class TriggerCreate(BaseModel):
    trade_group_id: int
    account_id: int | None = None  # None => все активные аккаунты
    symbol: str
    target_price: float
    action: TriggerAction
    partial_percent: float | None = Field(default=None, gt=0, le=100)
    new_sl_price: float | None = None


class TriggerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trade_group_id: int
    account_id: int | None
    symbol: str
    target_price: float
    action: TriggerAction
    partial_percent: float | None
    new_sl_price: float | None
    is_armed: bool
    is_fired: bool
