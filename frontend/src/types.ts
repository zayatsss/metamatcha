export type BrokerType = "mt5" | "matchtrader";
export type OrderSide = "buy" | "sell";
export type OrderType = "market" | "limit";
export type TriggerAction = "break_even" | "partial_tp" | "custom_sl_move";

export interface Account {
  id: number;
  label: string;
  broker: BrokerType;
  login: string;
  server: string;
  balance: number;
  risk_percent: number;
  is_active: boolean;
  connected: boolean;
}

export interface AccountCreate {
  label: string;
  broker: BrokerType;
  login: string;
  password: string;
  server: string;
  api_base_url?: string | null;
  balance: number;
  risk_percent: number;
}

export interface OrderRequest {
  account_ids: number[];
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  entry_price: number | null;
  sl_price: number;
  tp_price: number | null;
}

export interface ExecResult {
  account_id: number;
  label: string;
  ok: boolean;
  lot: number | null;
  risk_amount: number | null;
  ticket: string | null;
  message: string;
}

export interface OrderResponse {
  trade_group_id: number;
  results: ExecResult[];
}

export interface TriggerCreate {
  trade_group_id: number;
  account_id: number | null;
  symbol: string;
  target_price: number;
  action: TriggerAction;
  partial_percent?: number | null;
  new_sl_price?: number | null;
}

export interface Trigger {
  id: number;
  trade_group_id: number;
  account_id: number | null;
  symbol: string;
  target_price: number;
  action: TriggerAction;
  partial_percent: number | null;
  new_sl_price: number | null;
  is_armed: boolean;
  is_fired: boolean;
}
