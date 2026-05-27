import { useState } from "react";
import { api } from "../api";
import type { Trigger, TriggerAction } from "../types";

interface Props {
  tradeGroupId: number | null;
  symbol: string;
  triggers: Trigger[];
  onChanged: () => void;
}

const ACTION_LABELS: Record<TriggerAction, string> = {
  break_even: "Безубыток (SL → вход)",
  partial_tp: "Частичная фиксация",
  custom_sl_move: "Перенос SL на цену",
};

export function TriggerPanel({ tradeGroupId, symbol, triggers, onChanged }: Props) {
  const [target, setTarget] = useState("");
  const [actions, setActions] = useState<Set<TriggerAction>>(new Set());
  const [partialPercent, setPartialPercent] = useState("50");
  const [newSl, setNewSl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const toggleAction = (a: TriggerAction) =>
    setActions((prev) => {
      const next = new Set(prev);
      next.has(a) ? next.delete(a) : next.add(a);
      return next;
    });

  async function submit() {
    if (tradeGroupId === null) return;
    setBusy(true);
    setError("");
    try {
      // Каждое выбранное действие = отдельный триггер на одну целевую цену.
      for (const action of actions) {
        await api.createTrigger({
          trade_group_id: tradeGroupId,
          account_id: null, // все активные аккаунты
          symbol,
          target_price: Number(target),
          action,
          partial_percent: action === "partial_tp" ? Number(partialPercent) : null,
          new_sl_price: action === "custom_sl_move" ? Number(newSl) : null,
        });
      }
      setTarget("");
      setActions(new Set());
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: number) {
    await api.deleteTrigger(id);
    onChanged();
  }

  const canSubmit =
    tradeGroupId !== null &&
    !!target &&
    actions.size > 0 &&
    (!actions.has("custom_sl_move") || !!newSl) &&
    !busy;

  return (
    <section className="panel">
      <h2>Сопровождение (триггеры)</h2>

      {tradeGroupId === null ? (
        <p className="muted">Сначала откройте сделку — триггеры привяжутся к ней.</p>
      ) : (
        <p className="muted">
          Сделка #{tradeGroupId} · {symbol}
        </p>
      )}

      <div className="form-grid">
        <label>
          Целевая цена
          <input
            type="number"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            disabled={tradeGroupId === null}
          />
        </label>
      </div>

      <div className="trigger-actions">
        <label className="checkbox">
          <input
            type="checkbox"
            checked={actions.has("break_even")}
            onChange={() => toggleAction("break_even")}
            disabled={tradeGroupId === null}
          />
          {ACTION_LABELS.break_even}
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            checked={actions.has("partial_tp")}
            onChange={() => toggleAction("partial_tp")}
            disabled={tradeGroupId === null}
          />
          {ACTION_LABELS.partial_tp}
          {actions.has("partial_tp") && (
            <input
              className="inline-num"
              type="number"
              value={partialPercent}
              onChange={(e) => setPartialPercent(e.target.value)}
            />
          )}
          {actions.has("partial_tp") && <span>% объёма</span>}
        </label>

        <label className="checkbox">
          <input
            type="checkbox"
            checked={actions.has("custom_sl_move")}
            onChange={() => toggleAction("custom_sl_move")}
            disabled={tradeGroupId === null}
          />
          {ACTION_LABELS.custom_sl_move}
          {actions.has("custom_sl_move") && (
            <input
              className="inline-num"
              type="number"
              value={newSl}
              onChange={(e) => setNewSl(e.target.value)}
              placeholder="новый SL"
            />
          )}
        </label>
      </div>

      <button className="primary" disabled={!canSubmit} onClick={submit}>
        {busy ? "Сохранение…" : "Поставить триггеры"}
      </button>

      {error && <p className="error">{error}</p>}

      <h3>Активные триггеры</h3>
      <ul className="trigger-list">
        {triggers.length === 0 && <li className="muted">Нет триггеров</li>}
        {triggers.map((t) => (
          <li key={t.id} className={t.is_fired ? "fired" : ""}>
            <span>
              {t.symbol} @ {t.target_price} → {ACTION_LABELS[t.action]}
              {t.action === "partial_tp" && ` (${t.partial_percent}%)`}
              {t.action === "custom_sl_move" && ` (SL ${t.new_sl_price})`}
            </span>
            <span className="badge">{t.is_fired ? "сработал" : "взведён"}</span>
            <button className="link" onClick={() => remove(t.id)}>
              ✕
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
