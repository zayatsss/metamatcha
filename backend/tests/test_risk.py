import math

import pytest

from app.risk import (
    SymbolSpec,
    calculate_lot,
    calculate_lot_from_pips,
    calculate_lot_from_prices,
)

# --- Инструменты с разными свойствами ---------------------------------------

# EURUSD (FX): contract 100k, 5 знаков. Tick 0.00001 даёт $1 на лот при USD-счёте.
# => value_per_price_unit = 1/0.00001 = 100000; pip=0.0001 => $10/пункт на лот.
EURUSD = SymbolSpec(
    symbol="EURUSD", digits=5, point=0.00001,
    contract_size=100_000, tick_size=0.00001, tick_value=1.0,
)

# XAUUSD (золото): contract 100 унций, 2 знака. Tick 0.01 даёт $1 на лот.
# => value_per_price_unit = 1/0.01 = 100 (== contract_size).
XAUUSD = SymbolSpec(
    symbol="XAUUSD", digits=2, point=0.01,
    contract_size=100, tick_size=0.01, tick_value=1.0,
)

# US30 (индекс CFD): contract 1, tick 0.1 даёт $0.1 на лот => value_per_unit = 1.
US30 = SymbolSpec(
    symbol="US30", digits=1, point=0.1,
    contract_size=1, tick_size=0.1, tick_value=0.1,
)


def test_fx_basic_formula():
    # $50k * 1% = $500; SL 20 пунктов = 0.0020 цены; value=100000.
    # raw = 500 / (0.0020 * 100000) = 2.5
    calc = calculate_lot_from_pips(balance=50_000, risk_percent=1.0, sl_pips=20, spec=EURUSD)
    assert math.isclose(calc.raw_lot, 2.5, rel_tol=1e-9)
    assert calc.lot == 2.5
    assert math.isclose(calc.risk_amount, 500.0)
    assert math.isclose(calc.value_per_price_unit_per_lot, 100_000.0)


def test_fx_from_prices():
    # дистанция 50 пунктов (0.0050); $10k * 2% = $200; raw = 200 / (0.0050*100000) = 0.4
    calc = calculate_lot_from_prices(
        balance=10_000, risk_percent=2.0, entry_price=1.1000, sl_price=1.0950, spec=EURUSD
    )
    assert math.isclose(calc.sl_pips, 50.0, rel_tol=1e-9)
    assert calc.lot == 0.4


def test_gold_different_contract_size():
    # Золото: SL $5 (2000.00 -> 1995.00); $10k * 1% = $100; value_per_unit = 100.
    # raw = 100 / (5 * 100) = 0.2
    calc = calculate_lot_from_prices(
        balance=10_000, risk_percent=1.0, entry_price=2000.00, sl_price=1995.00, spec=XAUUSD
    )
    assert math.isclose(calc.value_per_price_unit_per_lot, 100.0)
    assert calc.lot == 0.2


def test_index_cfd():
    # US30: SL 50 пунктов цены (35000 -> 34950); $50k * 1% = $500; value_per_unit = 1.
    # raw = 500 / (50 * 1) = 10
    calc = calculate_lot(balance=50_000, risk_percent=1.0, sl_distance_price=50, spec=US30)
    assert math.isclose(calc.value_per_price_unit_per_lot, 1.0)
    assert calc.lot == 10.0


def test_rounding_down_to_step():
    calc = calculate_lot_from_pips(balance=3_000, risk_percent=1.5, sl_pips=17, spec=EURUSD)
    # raw = 45 / (0.0017 * 100000) = 45/170 = 0.2647 -> вниз до 0.26
    assert calc.lot == 0.26
    assert calc.lot <= calc.raw_lot


def test_min_volume_cap():
    calc = calculate_lot_from_pips(balance=200, risk_percent=1.0, sl_pips=50, spec=EURUSD)
    # raw = 2 / (0.0050*100000) = 0.004 -> ниже минимума, поднимаем до 0.01.
    assert calc.lot == 0.01
    assert calc.capped is True


def test_from_contract_derives_tick_value():
    # tick_value не задан -> выводится как contract_size * tick_size * rate.
    spec = SymbolSpec.from_contract(
        symbol="EURUSD", digits=5, point=0.00001, contract_size=100_000
    )
    assert math.isclose(spec.tick_value, 1.0, rel_tol=1e-9)
    assert math.isclose(spec.pip_value_per_lot, 10.0, rel_tol=1e-9)


def test_zero_sl_rejected():
    with pytest.raises(ValueError):
        calculate_lot(balance=1000, risk_percent=1, sl_distance_price=0, spec=EURUSD)
