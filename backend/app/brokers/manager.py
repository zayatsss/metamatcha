"""Реестр живых подключений к брокерам.

На каждый Account создаётся один BrokerAdapter и переиспользуется между запросами
(исполнение ордеров) и фоновым воркером (мониторинг триггеров). Это in-memory
синглтон уровня процесса; при горизонтальном масштабировании выноси в отдельный
сервис-коннектор на хост (особенно для MT5, см. README)."""

import asyncio

from app.brokers.base import BrokerAdapter, Quote
from app.brokers.demo_adapter import DemoAdapter
from app.brokers.matchtrader_adapter import MatchTraderAdapter
from app.brokers.mt5_adapter import MT5Adapter
from app.models import Account, BrokerType
from app.security import decrypt_password


class BrokerManager:
    def __init__(self) -> None:
        self._adapters: dict[int, BrokerAdapter] = {}
        self._lock = asyncio.Lock()

    def _build(self, account: Account) -> BrokerAdapter:
        if account.broker == BrokerType.DEMO:
            return DemoAdapter(balance=account.balance)
        password = decrypt_password(account.password_enc)
        if account.broker == BrokerType.MT5:
            return MT5Adapter(login=account.login, password=password, server=account.server)
        return MatchTraderAdapter(
            login=account.login,
            password=password,
            server=account.server,
            api_base_url=account.api_base_url or "",
        )

    async def get_adapter(self, account: Account) -> BrokerAdapter:
        async with self._lock:
            adapter = self._adapters.get(account.id)
            if adapter is None:
                adapter = self._build(account)
                self._adapters[account.id] = adapter
            return adapter

    async def connect(self, account: Account) -> bool:
        adapter = await self.get_adapter(account)
        return await adapter.connect()

    async def disconnect(self, account_id: int) -> None:
        adapter = self._adapters.pop(account_id, None)
        if adapter:
            await adapter.disconnect()

    async def status(self, account_id: int) -> bool:
        adapter = self._adapters.get(account_id)
        return await adapter.is_connected() if adapter else False

    def active_adapters(self) -> dict[int, BrokerAdapter]:
        return dict(self._adapters)

    async def get_quote(self, symbol: str) -> Quote | None:
        """Котировка с первого подключённого брокера, у которого есть символ."""
        for adapter in self._adapters.values():
            try:
                if await adapter.is_connected():
                    return await adapter.get_quote(symbol)
            except Exception:  # noqa: BLE001 — пробуем следующего брокера
                continue
        return None


broker_manager = BrokerManager()
