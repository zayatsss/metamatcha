import type {
  Account,
  AccountCreate,
  OrderRequest,
  OrderResponse,
  Trigger,
  TriggerCreate,
} from "./types";

// В dev все запросы идут через vite-прокси на /api -> http://localhost:8000.
const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  listAccounts: () => request<Account[]>("/accounts"),
  createAccount: (payload: AccountCreate) =>
    request<Account>("/accounts", { method: "POST", body: JSON.stringify(payload) }),
  connectAccount: (id: number) =>
    request<Account>(`/accounts/${id}/connect`, { method: "POST" }),
  disconnectAccount: (id: number) =>
    request<{ ok: boolean }>(`/accounts/${id}/disconnect`, { method: "POST" }),

  executeOrder: (payload: OrderRequest) =>
    request<OrderResponse>("/orders/execute", { method: "POST", body: JSON.stringify(payload) }),

  listTriggers: () => request<Trigger[]>("/triggers"),
  createTrigger: (payload: TriggerCreate) =>
    request<Trigger>("/triggers", { method: "POST", body: JSON.stringify(payload) }),
  deleteTrigger: (id: number) =>
    request<{ ok: boolean }>(`/triggers/${id}`, { method: "DELETE" }),
};
