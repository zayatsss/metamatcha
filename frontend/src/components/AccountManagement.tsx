import { useState } from "react";
import { api } from "../api";
import type { Account, AccountCreate, BrokerType } from "../types";

interface Props {
  accounts: Account[];
  onChanged: () => void;
}

const EMPTY: AccountCreate = {
  label: "",
  broker: "mt5",
  login: "",
  password: "",
  server: "",
  api_base_url: "",
  balance: 0,
  risk_percent: 1,
};

export function AccountManagement({ accounts, onChanged }: Props) {
  const [form, setForm] = useState<AccountCreate>(EMPTY);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const set = <K extends keyof AccountCreate>(key: K, value: AccountCreate[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  async function submit() {
    setError("");
    try {
      await api.createAccount({
        ...form,
        balance: Number(form.balance),
        risk_percent: Number(form.risk_percent),
        api_base_url: form.broker === "matchtrader" ? form.api_base_url : null,
      });
      setForm(EMPTY);
      onChanged();
    } catch (e) {
      setError(String(e));
    }
  }

  async function toggleConnect(acc: Account) {
    setBusyId(acc.id);
    setError("");
    try {
      if (acc.connected) await api.disconnectAccount(acc.id);
      else await api.connectAccount(acc.id);
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="panel">
      <h2>Аккаунты</h2>

      <table className="accounts-table">
        <thead>
          <tr>
            <th>Метка</th>
            <th>Брокер</th>
            <th>Баланс</th>
            <th>Риск %</th>
            <th>Статус</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {accounts.length === 0 && (
            <tr>
              <td colSpan={6} className="muted">
                Нет аккаунтов — добавьте ниже
              </td>
            </tr>
          )}
          {accounts.map((a) => (
            <tr key={a.id}>
              <td>{a.label}</td>
              <td>{a.broker.toUpperCase()}</td>
              <td>${a.balance.toLocaleString()}</td>
              <td>{a.risk_percent}%</td>
              <td>
                <span className={a.connected ? "dot dot-green" : "dot dot-red"} />
                {a.connected ? "Коннект" : "Дисконнект"}
              </td>
              <td>
                <button disabled={busyId === a.id} onClick={() => toggleConnect(a)}>
                  {a.connected ? "Отключить" : "Подключить"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <details className="add-account">
        <summary>+ Добавить аккаунт</summary>
        <div className="form-grid">
          <label>
            Метка
            <input value={form.label} onChange={(e) => set("label", e.target.value)} />
          </label>
          <label>
            Брокер
            <select value={form.broker} onChange={(e) => set("broker", e.target.value as BrokerType)}>
              <option value="mt5">MetaTrader 5</option>
              <option value="matchtrader">MatchTrader</option>
            </select>
          </label>
          <label>
            Логин
            <input value={form.login} onChange={(e) => set("login", e.target.value)} />
          </label>
          <label>
            Пароль
            <input type="password" value={form.password} onChange={(e) => set("password", e.target.value)} />
          </label>
          <label>
            Сервер
            <input value={form.server} onChange={(e) => set("server", e.target.value)} />
          </label>
          {form.broker === "matchtrader" && (
            <label>
              API base URL
              <input
                value={form.api_base_url ?? ""}
                onChange={(e) => set("api_base_url", e.target.value)}
                placeholder="https://broker.example.com"
              />
            </label>
          )}
          <label>
            Баланс ($)
            <input
              type="number"
              value={form.balance}
              onChange={(e) => set("balance", Number(e.target.value))}
            />
          </label>
          <label>
            Риск (%)
            <input
              type="number"
              step="0.1"
              value={form.risk_percent}
              onChange={(e) => set("risk_percent", Number(e.target.value))}
            />
          </label>
        </div>
        <button className="primary" disabled={!form.label || !form.login} onClick={submit}>
          Сохранить аккаунт
        </button>
      </details>

      {error && <p className="error">{error}</p>}
    </section>
  );
}
