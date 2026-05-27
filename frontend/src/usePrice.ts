import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Quote } from "./types";

/**
 * Живая котировка по символу: каждые `intervalMs` тянет /api/prices,
 * который берёт цену напрямую с подключённого MT5/MatchTrader.
 * Возвращает null, если символ пуст или цена недоступна (нет коннекта).
 */
export function usePrice(symbol: string, intervalMs = 1000): Quote | null {
  const [quote, setQuote] = useState<Quote | null>(null);
  const symbolRef = useRef(symbol);
  symbolRef.current = symbol;

  useEffect(() => {
    if (!symbol) {
      setQuote(null);
      return;
    }
    let cancelled = false;

    async function poll() {
      try {
        const quotes = await api.getPrices([symbolRef.current]);
        if (!cancelled) setQuote(quotes[0] ?? null);
      } catch {
        if (!cancelled) setQuote(null);
      }
    }

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [symbol, intervalMs]);

  return quote;
}
