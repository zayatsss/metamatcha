import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BrokerType(str, enum.Enum):
    MT5 = "mt5"
    MATCHTRADER = "matchtrader"
    DEMO = "demo"  # симулятор для теста без реального терминала/API


class OrderType(str, enum.Enum):
    MARKET = "market"
    LIMIT = "limit"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class TriggerAction(str, enum.Enum):
    BREAK_EVEN = "break_even"          # перевод SL в безубыток (на цену входа)
    PARTIAL_TP = "partial_tp"          # частичная фиксация % объёма
    CUSTOM_SL_MOVE = "custom_sl_move"  # перенос SL на заданную цену


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    broker: Mapped[BrokerType] = mapped_column(Enum(BrokerType))

    login: Mapped[str] = mapped_column(String(120))
    # Хранится зашифрованным (см. app/security.py). Никогда не отдаётся наружу.
    password_enc: Mapped[str] = mapped_column(String(512))
    server: Mapped[str] = mapped_column(String(200))

    # Базовый URL для MatchTrader REST/WS API (для MT5 не используется).
    api_base_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    balance: Mapped[float] = mapped_column(Float, default=0.0)
    risk_percent: Mapped[float] = mapped_column(Float, default=1.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    triggers: Mapped[list["Trigger"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class TradeGroup(Base):
    """Логическая сделка: один клик 'Вход' -> ордера на нескольких аккаунтах."""

    __tablename__ = "trade_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(40))
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide))
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType))
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sl_price: Mapped[float] = mapped_column(Float)
    tp_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    triggers: Mapped[list["Trigger"]] = relationship(back_populates="trade_group", cascade="all, delete-orphan")


class Trigger(Base):
    """Правило сопровождения: при пересечении target_price -> выполнить action."""

    __tablename__ = "triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_group_id: Mapped[int] = mapped_column(ForeignKey("trade_groups.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    symbol: Mapped[str] = mapped_column(String(40))
    target_price: Mapped[float] = mapped_column(Float)
    action: Mapped[TriggerAction] = mapped_column(Enum(TriggerAction))

    # Параметры действия:
    partial_percent: Mapped[float | None] = mapped_column(Float, nullable=True)  # для PARTIAL_TP
    new_sl_price: Mapped[float | None] = mapped_column(Float, nullable=True)      # для CUSTOM_SL_MOVE

    is_armed: Mapped[bool] = mapped_column(Boolean, default=True)
    is_fired: Mapped[bool] = mapped_column(Boolean, default=False)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    account: Mapped["Account | None"] = relationship(back_populates="triggers")
    trade_group: Mapped["TradeGroup"] = relationship(back_populates="triggers")
