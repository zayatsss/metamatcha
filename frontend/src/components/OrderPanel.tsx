import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Account, ExecResult, OrderSide, OrderType } from "../types";
import { PriceTicker } from "./PriceTicker";

interface Props {
  accounts: Account[];
  onTradeOpened: (tradeGroupId: number, symbol: string) => void;
}

export function OrderPanel({ accounts, onTradeOpened }: Props) {
  const [selected, setSelected] = useState<number[]>([]);
  const [symbol, setSymbol] = useState("EURUSD");
  const [side, setSide] = useState<OrderSide>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [entry, setEntry] = useState("");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [preview, setPreview] = useState<ExecResult[]>([]);
  const [previewing, setPreviewing] = useState(false);
  const [results, setResults] = useState<ExecResult[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const connectedAccounts = accounts.filter((a) => a.connected);

  const inputsValid =
    selected.length > 0 && !!sl && (orderType === "market" || !!entry);

  const buildPayload = useCallback(
    () => ({
      account_ids: selected,
      symbol,
      side,
      order_type: orderType,
      entry_price: orderType === "limit" ? Number(entry) : null,
      sl_price: Number(sl),
      tp_price: tp ? Number(tp) : null,
    }),
    [selected, symbol, side, orderType, entry, sl, tp],
  );

  // Авторасчёт лотов: при изменении входных данных дёргаем предпросмотр
  // (с дебаунсом) и периодически обновляем, т.к. рыночная цена двигается.
  useEffect(() => {
    if (!inputsValid) {
      setPreview([]);
      return;
    }
    let cancelled = false;

    async function run() {
      setPreviewing(true);
      try {
        const data = await api.previewOrder(buildPayload());
        if (!cancelled) setPreview(data.results);
      } catch {
        if (!cancelled) setPreview([]);
      } finally {
        if (!cancelled) setPreviewing(false);
      }
    }

    const debounce = setTimeout(run, 400);
    const interval = setInterval(run, 3000);
    return () => {
      cancelled = true;
      clearTimeout(debounce);
      clearInterval(interval);
    };
  }, [inputsValid, buildPayload]);

  async function submit() {
    setBusy(true);
    setError("");
    setResults([]);
    try {
      const data = await api.executeOrder(buildPayload());
      setResults(data.results);
      onTradeOpened(data.trade_group_id, symbol);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const totalLot = preview.reduce((sum, r) => sum + (r.lot ?? 0), 0);

  return (
    <section className="panel">
      <h2>Вход в позицию</h2>

      <PriceTicker symbol={symbol} />

      <div className="account-picker">
        {connectedAccounts.length === 0 && <p className="muted">Нет подключённых аккаунтов</p>}
        {connectedAccounts.map((a) => (
          <label key={a.id} className="checkbox">
            <input type="checkbox" checked={selected.includes(a.id)} onChange={() => toggle(a.id)} />
            {a.label} <span className="muted">${a.balance.toLocaleString()} @ {a.risk_percent}%</span>
          </label>
        ))}
      </div>

      <div className="form-grid">
        <label>
          Символ
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} />
        </label>
        <label>
          Тип
          <select value={orderType} onChange={(e) => setOrderType(e.target.value as OrderType)}>
            <option value="market">Market</option>
            <option value="limit">Limit</option>
          </select>
        </label>
        <label>
          Направление
          <select value={side} onChange={(e) => setSide(e.target.value as OrderSide)}>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </label>
        {orderType === "limit" && (
          <label>
            Цена входа
            <input type="number" value={entry} onChange={(e) => setEntry(e.target.value)} />
          </label>
        )}
        <label>
          Stop Loss
          <input type="number" value={sl} onChange={(e) => setSl(e.target.value)} />
        </label>
        <label>
          Take Profit
          <input type="number" value={tp} onChange={(e) => setTp(e.target.value)} placeholder="опц." />
        </label>
      </div>

      {/* Авторасчёт лотов до отправки */}
      {inputsValid && (
        <div className="preview">
          <div className="preview-head">
            <span>Расчёт лотов {previewing && <span className="muted">обновление…</span>}</span>
            <span className="muted">Σ {totalLot.toFixed(2)} лот</span>
          </div>
          <table className="preview-table">
            <thead>
              <tr>
                <th>Аккаунт</th>
                <th>Баланс</th>
                <th>Цена</th>
                <th>Лот</th>
                <th>Риск $</th>
              </tr>
            </thead>
            <tbody>
              {preview.map((r) => (
                <tr key={r.account_id} className={r.ok ? "" : "err"}>
                  <td>{r.label}</td>
                  <td>{r.ok ? `$${r.balance?.toLocaleString()}` : "—"}</td>
                  <td>{r.ok ? r.reference_price : "—"}</td>
                  <td className="lot">{r.ok ? r.lot : "—"}</td>
                  <td>{r.ok ? `$${r.risk_amount}` : r.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <button className={`primary ${side}`} disabled={!inputsValid || busy} onClick={submit}>
        {busy ? "Отправка…" : `Вход ${side.toUpperCase()} (${selected.length} акк.)`}
      </button>

      {error && <p className="error">{error}</p>}

      {results.length > 0 && (
        <ul className="results">
          {results.map((r) => (
            <li key={r.account_id} className={r.ok ? "ok" : "err"}>
              <b>{r.label}:</b>{" "}
              {r.ok
                ? `лот ${r.lot} · баланс $${r.balance?.toLocaleString()} @ ${r.reference_price} · риск $${r.risk_amount} · #${r.ticket}`
                : `ошибка — ${r.message}`}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
