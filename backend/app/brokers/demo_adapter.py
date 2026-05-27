"""Демо-брокер для тестирования дашборда без реального терминала/API.

Симулирует подключение, баланс, движение цены (случайное блуждание вокруг
базовой) и сделки в памяти — чтобы можно было прокликать весь флоу: коннект,
живой тикер, расчёт лотов, вход и автоматическое сопровождение по триггерам.

Спецификации инструментов здесь приблизительные (демо), но математика лота
полностью реальная — лот считается тем же кодом, что и для MT5/MatchTrader."""

import itertools
import random

from app.brokers.base import BrokerAdapter, OrderResult, Position, Quote
from app.models import OrderSide, OrderType
from app.risk import SymbolSpec

_BASE_PRICE = {
    "EURUSD": 1.10,
    "GBPUSD": 1.27,
    "USDJPY": 150.0,
    "XAUUSD": 2000.0,
    "XAGUSD": 25.0,
    "US30": 35000.0,
    "NAS100": 16000.0,
    "BTCUSD": 60000.0,
}


def _demo_spec(symbol: str) -> SymbolSpec:
    s = symbol.upper()
    if s.startswith("XAU") or s.startswith("XAG"):
        return SymbolSpec(symbol=s, digits=2, point=0.01, contract_size=100, tick_size=0.01, tick_value=1.0)
    if s in ("US30", "NAS100", "SPX500", "BTCUSD"):
        return SymbolSpec(symbol=s, digits=1, point=0.1, contract_size=1, tick_size=0.1, tick_value=0.1)
    if "JPY" in s:
        return SymbolSpec(symbol=s, digits=3, point=0.001, contract_size=100_000, tick_size=0.001, tick_value=0.67)
    # FX-стиль по умолчанию (как EURUSD): пункт $10 на лот.
    return SymbolSpec(symbol=s, digits=5, point=0.00001, contract_size=100_000, tick_size=0.00001, tick_value=1.0)


class DemoAdapter(BrokerAdapter):
    _ticket_seq = itertools.count(1000)

    def __init__(self, balance: float = 10_000.0):
        self._balance = balance
        self._connected = False
        self._last: dict[str, float] = {}
        self._positions: dict[str, Position] = {}

    async def connect(self) -> bool:
        self._connected = True
        return True

    async def disconnect(self) -> None:
        self._connected = False

    async def is_connected(self) -> bool:
        return self._connected

    async def get_balance(self) -> float:
        return self._balance

    async def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        return _demo_spec(symbol)

    async def get_quote(self, symbol: str) -> Quote:
        base = self._last.get(symbol.upper(), _BASE_PRICE.get(symbol.upper(), 100.0))
        # Случайное блуждание ±0.05% за тик.
        mid = base * (1 + random.uniform(-0.0005, 0.0005))
        self._last[symbol.upper()] = mid
        spread = mid * 0.0001
        return Quote(symbol=symbol, bid=round(mid - spread / 2, 5), ask=round(mid + spread / 2, 5))

    async def place_order(self, *, symbol, side, order_type, volume, price, sl, tp) -> OrderResult:
        quote = await self.get_quote(symbol)
        fill = price if (order_type == OrderType.LIMIT and price) else quote.mid
        ticket = str(next(self._ticket_seq))
        self._positions[ticket] = Position(
            ticket=ticket, symbol=symbol, side=side, volume=volume, entry_price=fill, sl=sl, tp=tp
        )
        return OrderResult(ok=True, ticket=ticket)

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        return [p for p in self._positions.values() if symbol is None or p.symbol == symbol]

    async def modify_sl(self, ticket: str, new_sl: float) -> OrderResult:
        pos = self._positions.get(ticket)
        if pos is None:
            return OrderResult(ok=False, message="position not found")
        self._positions[ticket] = Position(
            ticket=pos.ticket, symbol=pos.symbol, side=pos.side, volume=pos.volume,
            entry_price=pos.entry_price, sl=new_sl, tp=pos.tp,
        )
        return OrderResult(ok=True, ticket=ticket)

    async def close_partial(self, ticket: str, volume: float) -> OrderResult:
        pos = self._positions.get(ticket)
        if pos is None:
            return OrderResult(ok=False, message="position not found")
        remaining = round(pos.volume - volume, 2)
        if remaining <= 0:
            del self._positions[ticket]
        else:
            self._positions[ticket] = Position(
                ticket=pos.ticket, symbol=pos.symbol, side=pos.side, volume=remaining,
                entry_price=pos.entry_price, sl=pos.sl, tp=pos.tp,
            )
        return OrderResult(ok=True, ticket=ticket)
