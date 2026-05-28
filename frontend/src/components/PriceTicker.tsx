import { usePrice } from "../usePrice";

export function PriceTicker({ symbol }: { symbol: string }) {
  const quote = usePrice(symbol);

  if (!symbol) return null;

  return (
    <div className="ticker">
      <span className="ticker-symbol">{symbol}</span>
      {quote ? (
        <>
          <span className="ticker-bid">Bid {quote.bid}</span>
          <span className="ticker-ask">Ask {quote.ask}</span>
        </>
      ) : (
        <span className="muted">нет цены (нет подключённого брокера)</span>
      )}
    </div>
  );
}
