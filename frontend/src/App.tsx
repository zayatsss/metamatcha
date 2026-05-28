import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { AccountManagement } from "./components/AccountManagement";
import { OrderPanel } from "./components/OrderPanel";
import { TriggerPanel } from "./components/TriggerPanel";
import type { Account, Trigger } from "./types";

export default function App() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [tradeGroupId, setTradeGroupId] = useState<number | null>(null);
  const [activeSymbol, setActiveSymbol] = useState("EURUSD");
  const [offline, setOffline] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [accs, trigs] = await Promise.all([api.listAccounts(), api.listTriggers()]);
      setAccounts(accs);
      setTriggers(trigs);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Лёгкий поллинг: статусы подключений и состояние сработки триггеров.
    const id = setInterval(refresh, 2000);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="app">
      <header>
        <h1>MetaMatcha</h1>
        <span className="subtitle">Multi-Account Trading Dashboard</span>
        {offline && <span className="offline">backend offline</span>}
      </header>

      <div className="layout">
        <AccountManagement accounts={accounts} onChanged={refresh} />
        <OrderPanel
          accounts={accounts}
          onTradeOpened={(id, symbol) => {
            setTradeGroupId(id);
            setActiveSymbol(symbol);
            refresh();
          }}
        />
        <TriggerPanel
          tradeGroupId={tradeGroupId}
          symbol={activeSymbol}
          triggers={triggers}
          onChanged={refresh}
        />
      </div>
    </div>
  );
}
