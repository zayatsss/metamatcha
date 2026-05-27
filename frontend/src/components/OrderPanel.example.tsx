/**
 * Пример ключевого компонента фронтенда — «Панель входа в позицию».
 * Стек: React + TypeScript (внутри Next.js или Electron-renderer).
 *
 * Это иллюстрация контракта с backend (POST /orders/execute) и UX «в один клик»:
 * пользователь выбирает аккаунты, задаёт направление/SL/TP, нажимает «Вход» —
 * лот для каждого аккаунта считается на backend по его индивидуальному риску.
 */

import { useState } from "react";

const API = "http://localhost:8000";

type Side = "buy" | "sell";
type OrderType = "market" | "limit";

interface Account {
  id: number;
  label: string;
  balance: number;
  risk_percent: number;
  connected: boolean;
}

interface ExecResult {
  account_id: number;
  label: string;
  ok: boolean;
  lot: number | null;
  risk_amount: number | null;
  message: string;
}

export function OrderPanel({ accounts }: { accounts: Account[] }) {
  const [selected, setSelected] = useState<number[]>([]);
  const [symbol, setSymbol] = useState("EURUSD");
  const [side, setSide] = useState<Side>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [entry, setEntry] = useState("");
  const [sl, setSl] = useState("");
  const [tp, setTp] = useState("");
  const [results, setResults] = useState<ExecResult[]>([]);
  const [busy, setBusy] = useState(false);

  const toggle = (id: number) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  async function submit() {
    setBusy(true);
    try {
      const resp = await fetch(`${API}/orders/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_ids: selected,
          symbol,
          side,
          order_type: orderType,
          entry_price: orderType === "limit" ? Number(entry) : null,
          sl_price: Number(sl),
          tp_price: tp ? Number(tp) : null,
        }),
      });
      const data = await resp.json();
      setResults(data.results ?? []);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="order-panel">
      <h3>Вход в позицию</h3>

      <div className="accounts">
        {accounts.map((a) => (
          <label key={a.id} className={a.connected ? "" : "disabled"}>
            <input type="checkbox" checked={selected.includes(a.id)} onChange={() => toggle(a.id)} />
            {a.label} — ${a.balance.toLocaleString()} @ {a.risk_percent}%{" "}
            <span className={a.connected ? "dot-green" : "dot-red"} />
          </label>
        ))}
      </div>

      <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Symbol" />

      <div className="row">
        <select value={orderType} onChange={(e) => setOrderType(e.target.value as OrderType)}>
          <option value="market">Market</option>
          <option value="limit">Limit</option>
        </select>
        <select value={side} onChange={(e) => setSide(e.target.value as Side)}>
          <option value="buy">Buy</option>
          <option value="sell">Sell</option>
        </select>
      </div>

      {orderType === "limit" && (
        <input value={entry} onChange={(e) => setEntry(e.target.value)} placeholder="Entry price" />
      )}
      <input value={sl} onChange={(e) => setSl(e.target.value)} placeholder="Stop Loss" />
      <input value={tp} onChange={(e) => setTp(e.target.value)} placeholder="Take Profit (optional)" />

      <button disabled={busy || selected.length === 0 || !sl} onClick={submit}>
        {busy ? "Отправка..." : `Вход (${selected.length} акк.)`}
      </button>

      <ul className="results">
        {results.map((r) => (
          <li key={r.account_id} className={r.ok ? "ok" : "err"}>
            {r.label}: {r.ok ? `лот ${r.lot} (риск $${r.risk_amount})` : `ошибка — ${r.message}`}
          </li>
        ))}
      </ul>
    </div>
  );
}
