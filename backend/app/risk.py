"""Расчёт размера позиции (лота) на основе индивидуального риска аккаунта.

Базовая формула из ТЗ:
    Лот = (Баланс * %Риска) / (StopLoss в пунктах * Стоимость пункта)

Нюанс реального рынка: "стоимость пункта" зависит от инструмента, валюты счёта,
размера контракта и валютной пары котировки. Поэтому мы не зашиваем константу, а
берём спецификацию символа (SymbolSpec), которую адаптер брокера получает
напрямую из терминала/брокера (для MT5 это mt5.symbol_info, для MatchTrader —
ответ инструментного эндпоинта).
"""

from dataclasses import dataclass
from math import floor, isfinite


@dataclass(frozen=True)
class SymbolSpec:
    """Спецификация торгового инструмента в терминах конкретного брокера."""

    symbol: str
    # Размер одного пункта в цене. Для EURUSD (5 знаков) пункт = 0.0001.
    pip_size: float
    # Денежная стоимость движения на 1 пункт при объёме 1.0 лот, в валюте счёта.
    pip_value_per_lot: float
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01


@dataclass(frozen=True)
class LotCalculation:
    lot: float                 # итоговый объём, округлённый под шаг и лимиты
    raw_lot: float             # объём до округления/клампа
    risk_amount: float         # сумма риска в валюте счёта
    sl_pips: float             # дистанция SL в пунктах
    risk_amount_effective: float  # фактический риск после округления лота
    capped: bool               # True, если объём упёрся в min/max брокера


def price_distance_to_pips(entry_price: float, sl_price: float, pip_size: float) -> float:
    if pip_size <= 0:
        raise ValueError("pip_size must be positive")
    return abs(entry_price - sl_price) / pip_size


def round_to_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    # Округление ВНИЗ под шаг лота, чтобы не превысить заданный риск.
    return floor(value / step + 1e-9) * step


def calculate_lot(
    *,
    balance: float,
    risk_percent: float,
    sl_pips: float,
    spec: SymbolSpec,
) -> LotCalculation:
    """Считает объём так, чтобы потенциальный убыток по SL ≈ balance * risk%."""

    if balance <= 0:
        raise ValueError("balance must be positive")
    if risk_percent <= 0:
        raise ValueError("risk_percent must be positive")
    if sl_pips <= 0:
        raise ValueError("sl_pips must be positive (entry и SL не должны совпадать)")
    if spec.pip_value_per_lot <= 0:
        raise ValueError("pip_value_per_lot must be positive")

    risk_amount = balance * (risk_percent / 100.0)
    raw_lot = risk_amount / (sl_pips * spec.pip_value_per_lot)

    if not isfinite(raw_lot):
        raise ValueError("lot calculation produced a non-finite value")

    lot = round_to_step(raw_lot, spec.volume_step)
    capped = False
    if lot < spec.volume_min:
        lot = spec.volume_min
        capped = True
    elif lot > spec.volume_max:
        lot = spec.volume_max
        capped = True

    risk_amount_effective = lot * sl_pips * spec.pip_value_per_lot

    return LotCalculation(
        lot=round(lot, 2),
        raw_lot=raw_lot,
        risk_amount=risk_amount,
        sl_pips=sl_pips,
        risk_amount_effective=risk_amount_effective,
        capped=capped,
    )


def calculate_lot_from_prices(
    *,
    balance: float,
    risk_percent: float,
    entry_price: float,
    sl_price: float,
    spec: SymbolSpec,
) -> LotCalculation:
    """Удобная обёртка: дистанцию SL считаем из цен входа и стопа."""

    sl_pips = price_distance_to_pips(entry_price, sl_price, spec.pip_size)
    return calculate_lot(balance=balance, risk_percent=risk_percent, sl_pips=sl_pips, spec=spec)
