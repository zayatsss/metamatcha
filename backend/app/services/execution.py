"""Исполнение сделки в один клик на всех выбранных аккаунтах.

Для каждого аккаунта:
  1) берём спецификацию символа у его брокера,
  2) считаем индивидуальный лот по риску аккаунта,
  3) отправляем ордер.
Аккаунты обрабатываются параллельно (asyncio.gather), чтобы вход был
максимально одновременным."""

import asyncio
from dataclasses import asdict, dataclass

from sqlalchemy.orm import Session

from app.brokers.manager import broker_manager
from app.models import Account, OrderSide, OrderType, TradeGroup
from app.risk import calculate_lot_from_prices


@dataclass
class AccountExecution:
    account_id: int
    label: str
    ok: bool
    lot: float | None = None
    risk_amount: float | None = None
    ticket: str | None = None
    message: str = ""


async def _execute_on_account(
    account: Account,
    *,
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    reference_price: float,
    sl_price: float,
    tp_price: float | None,
) -> AccountExecution:
    try:
        adapter = await broker_manager.get_adapter(account)
        if not await adapter.is_connected():
            return AccountExecution(account.id, account.label, ok=False, message="not connected")

        spec = await adapter.get_symbol_spec(symbol)
        calc = calculate_lot_from_prices(
            balance=account.balance,
            risk_percent=account.risk_percent,
            entry_price=reference_price,
            sl_price=sl_price,
            spec=spec,
        )
        result = await adapter.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            volume=calc.lot,
            price=reference_price if order_type == OrderType.LIMIT else None,
            sl=sl_price,
            tp=tp_price,
        )
        return AccountExecution(
            account_id=account.id,
            label=account.label,
            ok=result.ok,
            lot=calc.lot,
            risk_amount=round(calc.risk_amount_effective, 2),
            ticket=result.ticket,
            message=result.message,
        )
    except Exception as exc:  # noqa: BLE001 — на уровне аккаунта изолируем сбой
        return AccountExecution(account.id, account.label, ok=False, message=str(exc))


async def execute_trade(
    db: Session,
    *,
    account_ids: list[int],
    symbol: str,
    side: OrderSide,
    order_type: OrderType,
    entry_price: float | None,
    sl_price: float,
    tp_price: float | None,
) -> tuple[TradeGroup, list[dict]]:
    accounts = db.query(Account).filter(Account.id.in_(account_ids), Account.is_active.is_(True)).all()

    # Для market-ордера эталонную цену (для расчёта дистанции SL) берём с рынка
    # у первого доступного адаптера; для limit — это сама цена входа.
    reference_price = entry_price
    if order_type == OrderType.MARKET and accounts:
        adapter = await broker_manager.get_adapter(accounts[0])
        reference_price = await adapter.get_price(symbol)

    results = await asyncio.gather(
        *[
            _execute_on_account(
                acc,
                symbol=symbol,
                side=side,
                order_type=order_type,
                reference_price=reference_price,
                sl_price=sl_price,
                tp_price=tp_price,
            )
            for acc in accounts
        ]
    )

    group = TradeGroup(
        symbol=symbol,
        side=side,
        order_type=order_type,
        entry_price=reference_price,
        sl_price=sl_price,
        tp_price=tp_price,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    return group, [asdict(r) for r in results]
