"""Адаптер MetaTrader 5.

Библиотека `MetaTrader5` работает только на Windows и требует запущенного
терминала MT5. Она синхронная и не потокобезопасна на уровне одного процесса,
поэтому каждый вызов выносим в отдельный поток через asyncio.to_thread, а на
один аккаунт держим отдельный процесс/инстанс терминала (см. README -> Деплой).

Импорт MetaTrader5 ленивый, чтобы код собирался и тестировался на Linux/CI без
этой зависимости.
"""

import asyncio

from app.brokers.base import BrokerAdapter, OrderResult, Position, Quote
from app.models import OrderSide, OrderType
from app.risk import SymbolSpec


class MT5Adapter(BrokerAdapter):
    def __init__(self, login: str, password: str, server: str, terminal_path: str | None = None):
        self._login = int(login)
        self._password = password
        self._server = server
        self._terminal_path = terminal_path
        self._mt5 = None
        self._connected = False

    def _ensure_lib(self):
        if self._mt5 is None:
            try:
                import MetaTrader5 as mt5  # ленивый импорт (только на Windows-хосте)
            except ImportError as exc:
                raise RuntimeError(
                    "Пакет MetaTrader5 не установлен. MT5 работает только на Windows "
                    "с установленным пакетом (pip install MetaTrader5) и запущенным "
                    "терминалом MT5. Для теста без терминала используйте брокера 'demo'."
                ) from exc

            self._mt5 = mt5
        return self._mt5

    def _connect_sync(self) -> bool:
        mt5 = self._ensure_lib()
        kwargs = {"login": self._login, "password": self._password, "server": self._server}
        if self._terminal_path:
            kwargs["path"] = self._terminal_path
        ok = mt5.initialize(**kwargs)
        self._connected = bool(ok)
        return self._connected

    async def connect(self) -> bool:
        return await asyncio.to_thread(self._connect_sync)

    async def disconnect(self) -> None:
        if self._mt5 and self._connected:
            await asyncio.to_thread(self._mt5.shutdown)
        self._connected = False

    async def is_connected(self) -> bool:
        if not self._connected:
            return False
        info = await asyncio.to_thread(self._mt5.account_info)
        return info is not None

    async def get_balance(self) -> float:
        info = await asyncio.to_thread(self._mt5.account_info)
        return float(info.balance) if info else 0.0

    async def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        mt5 = self._mt5
        info = await asyncio.to_thread(mt5.symbol_info, symbol)
        if info is None:
            raise RuntimeError(f"symbol {symbol} not found in MT5")
        # MT5 отдаёт сырые свойства инструмента напрямую — пробрасываем их как есть.
        # trade_tick_value уже учитывает contract_size и конвертацию в валюту счёта.
        return SymbolSpec(
            symbol=symbol,
            digits=info.digits,
            point=info.point,
            contract_size=info.trade_contract_size,
            tick_size=info.trade_tick_size,
            tick_value=info.trade_tick_value,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
        )

    async def get_quote(self, symbol: str) -> Quote:
        tick = await asyncio.to_thread(self._mt5.symbol_info_tick, symbol)
        if tick is None:
            raise RuntimeError(f"no tick for {symbol}")
        return Quote(symbol=symbol, bid=tick.bid, ask=tick.ask)

    async def place_order(self, *, symbol, side, order_type, volume, price, sl, tp) -> OrderResult:
        mt5 = self._mt5
        is_buy = side == OrderSide.BUY
        if order_type == OrderType.MARKET:
            action = mt5.TRADE_ACTION_DEAL
            mt5_type = mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL
            tick = await asyncio.to_thread(mt5.symbol_info_tick, symbol)
            exec_price = tick.ask if is_buy else tick.bid
        else:
            action = mt5.TRADE_ACTION_PENDING
            mt5_type = mt5.ORDER_TYPE_BUY_LIMIT if is_buy else mt5.ORDER_TYPE_SELL_LIMIT
            exec_price = price

        request = {
            "action": action,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_type,
            "price": float(exec_price),
            "sl": float(sl) if sl else 0.0,
            "tp": float(tp) if tp else 0.0,
            "deviation": 20,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            msg = getattr(result, "comment", "order_send failed")
            return OrderResult(ok=False, message=f"MT5: {msg}")
        return OrderResult(ok=True, ticket=str(result.order))

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        mt5 = self._mt5
        raw = await asyncio.to_thread(mt5.positions_get, symbol=symbol) if symbol else await asyncio.to_thread(mt5.positions_get)
        positions = []
        for p in raw or []:
            positions.append(
                Position(
                    ticket=str(p.ticket),
                    symbol=p.symbol,
                    side=OrderSide.BUY if p.type == mt5.POSITION_TYPE_BUY else OrderSide.SELL,
                    volume=p.volume,
                    entry_price=p.price_open,
                    sl=p.sl or None,
                    tp=p.tp or None,
                )
            )
        return positions

    async def modify_sl(self, ticket: str, new_sl: float) -> OrderResult:
        mt5 = self._mt5
        positions = await self.get_positions()
        pos = next((p for p in positions if p.ticket == ticket), None)
        if pos is None:
            return OrderResult(ok=False, message="position not found")
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(ticket),
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": float(pos.tp) if pos.tp else 0.0,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(ok=False, message=getattr(result, "comment", "modify failed"))
        return OrderResult(ok=True, ticket=ticket)

    async def close_partial(self, ticket: str, volume: float) -> OrderResult:
        mt5 = self._mt5
        positions = await self.get_positions()
        pos = next((p for p in positions if p.ticket == ticket), None)
        if pos is None:
            return OrderResult(ok=False, message="position not found")
        is_buy = pos.side == OrderSide.BUY
        tick = await asyncio.to_thread(mt5.symbol_info_tick, pos.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": float(volume),
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,  # встречный ордер закрывает объём
            "position": int(ticket),
            "price": tick.bid if is_buy else tick.ask,
            "deviation": 20,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(ok=False, message=getattr(result, "comment", "partial close failed"))
        return OrderResult(ok=True, ticket=ticket)
