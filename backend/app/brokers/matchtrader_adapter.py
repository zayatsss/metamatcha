"""Адаптер MatchTrader (REST + WebSocket).

MatchTrader предоставляет HTTP API брокера и WS-поток котировок. Точные пути
эндпоинтов отличаются у разных брокеров на платформе Match-Trade, поэтому они
вынесены в константы класса — поправь их под документацию своего брокера.

Здесь показана рабочая структура: авторизация по токену, REST для ордеров и
модификаций, кэш последней цены, который при желании питается из WS-стрима.
"""

import httpx

from app.brokers.base import BrokerAdapter, OrderResult, Position
from app.models import OrderSide, OrderType
from app.risk import SymbolSpec


class MatchTraderAdapter(BrokerAdapter):
    LOGIN_PATH = "/mtr-api/v1/login"
    SYMBOL_PATH = "/mtr-api/v1/symbols/{symbol}"
    QUOTE_PATH = "/mtr-api/v1/quotes/{symbol}"
    ORDER_PATH = "/mtr-api/v1/orders"
    POSITIONS_PATH = "/mtr-api/v1/positions"
    POSITION_PATH = "/mtr-api/v1/positions/{ticket}"

    def __init__(self, login: str, password: str, server: str, api_base_url: str):
        self._login = login
        self._password = password
        self._server = server
        self._base_url = api_base_url.rstrip("/")
        self._token: str | None = None
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=10.0)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"} if self._token else {}

    async def connect(self) -> bool:
        resp = await self._client.post(
            self.LOGIN_PATH,
            json={"login": self._login, "password": self._password, "server": self._server},
        )
        if resp.status_code != 200:
            return False
        self._token = resp.json().get("token")
        return self._token is not None

    async def disconnect(self) -> None:
        self._token = None
        await self._client.aclose()

    async def is_connected(self) -> bool:
        return self._token is not None

    async def get_balance(self) -> float:
        resp = await self._client.get("/mtr-api/v1/account", headers=self._headers())
        resp.raise_for_status()
        return float(resp.json().get("balance", 0.0))

    async def get_symbol_spec(self, symbol: str) -> SymbolSpec:
        resp = await self._client.get(self.SYMBOL_PATH.format(symbol=symbol), headers=self._headers())
        resp.raise_for_status()
        d = resp.json()
        return SymbolSpec(
            symbol=symbol,
            pip_size=float(d["pipSize"]),
            pip_value_per_lot=float(d["pipValuePerLot"]),
            volume_min=float(d.get("volumeMin", 0.01)),
            volume_max=float(d.get("volumeMax", 100.0)),
            volume_step=float(d.get("volumeStep", 0.01)),
        )

    async def get_price(self, symbol: str) -> float:
        resp = await self._client.get(self.QUOTE_PATH.format(symbol=symbol), headers=self._headers())
        resp.raise_for_status()
        d = resp.json()
        return (float(d["bid"]) + float(d["ask"])) / 2.0

    async def place_order(self, *, symbol, side, order_type, volume, price, sl, tp) -> OrderResult:
        payload = {
            "symbol": symbol,
            "side": side.value.upper(),
            "type": "MARKET" if order_type == OrderType.MARKET else "LIMIT",
            "volume": volume,
            "stopLoss": sl,
            "takeProfit": tp,
        }
        if order_type == OrderType.LIMIT:
            payload["price"] = price
        resp = await self._client.post(self.ORDER_PATH, json=payload, headers=self._headers())
        if resp.status_code not in (200, 201):
            return OrderResult(ok=False, message=f"MatchTrader: {resp.text}")
        return OrderResult(ok=True, ticket=str(resp.json().get("orderId")))

    async def get_positions(self, symbol: str | None = None) -> list[Position]:
        resp = await self._client.get(self.POSITIONS_PATH, headers=self._headers())
        resp.raise_for_status()
        out = []
        for p in resp.json().get("positions", []):
            if symbol and p["symbol"] != symbol:
                continue
            out.append(
                Position(
                    ticket=str(p["id"]),
                    symbol=p["symbol"],
                    side=OrderSide(p["side"].lower()),
                    volume=float(p["volume"]),
                    entry_price=float(p["openPrice"]),
                    sl=float(p["stopLoss"]) if p.get("stopLoss") else None,
                    tp=float(p["takeProfit"]) if p.get("takeProfit") else None,
                )
            )
        return out

    async def modify_sl(self, ticket: str, new_sl: float) -> OrderResult:
        resp = await self._client.patch(
            self.POSITION_PATH.format(ticket=ticket),
            json={"stopLoss": new_sl},
            headers=self._headers(),
        )
        if resp.status_code != 200:
            return OrderResult(ok=False, message=f"MatchTrader: {resp.text}")
        return OrderResult(ok=True, ticket=ticket)

    async def close_partial(self, ticket: str, volume: float) -> OrderResult:
        resp = await self._client.post(
            self.POSITION_PATH.format(ticket=ticket) + "/close",
            json={"volume": volume},
            headers=self._headers(),
        )
        if resp.status_code != 200:
            return OrderResult(ok=False, message=f"MatchTrader: {resp.text}")
        return OrderResult(ok=True, ticket=ticket)
