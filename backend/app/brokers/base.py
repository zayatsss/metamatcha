"""Единый интерфейс брокера. MT5 и MatchTrader реализуют его по-своему,
а вся бизнес-логика (исполнение, сопровождение) работает только с этим
контрактом и ничего не знает о специфике конкретной платформы."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models import OrderSide, OrderType
from app.risk import SymbolSpec


@dataclass
class Position:
    ticket: str
    symbol: str
    side: OrderSide
    volume: float
    entry_price: float
    sl: float | None
    tp: float | None


@dataclass
class OrderResult:
    ok: bool
    ticket: str | None = None
    message: str = ""


class BrokerAdapter(ABC):
    """Один экземпляр на один подключённый аккаунт."""

    @abstractmethod
    async def connect(self) -> bool: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def is_connected(self) -> bool: ...

    @abstractmethod
    async def get_balance(self) -> float: ...

    @abstractmethod
    async def get_symbol_spec(self, symbol: str) -> SymbolSpec: ...

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """Текущая цена (используется фоновым воркером для проверки триггеров)."""

    @abstractmethod
    async def place_order(
        self,
        *,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        volume: float,
        price: float | None,
        sl: float | None,
        tp: float | None,
    ) -> OrderResult: ...

    @abstractmethod
    async def get_positions(self, symbol: str | None = None) -> list[Position]: ...

    @abstractmethod
    async def modify_sl(self, ticket: str, new_sl: float) -> OrderResult:
        """Используется для Break-Even и Custom SL Move."""

    @abstractmethod
    async def close_partial(self, ticket: str, volume: float) -> OrderResult:
        """Используется для частичной фиксации (Partial TP)."""
