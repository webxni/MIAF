"use client";

export type ApiError = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

export class ApiRequestError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

export type User = {
  id: string;
  tenant_id: string;
  email: string;
  name: string;
  is_active: boolean;
};

export type Entity = {
  id: string;
  name: string;
  mode: "personal" | "business";
  currency: string;
};

export type SkillManifest = {
  name: string;
  version: string;
  description: string;
  mode: "personal" | "business" | "both";
  permissions: string[];
  triggers: string[];
  tools_used: string[];
  requires_confirmation: boolean;
  risk_level: "low" | "medium" | "high";
  entrypoint: string;
  builtin: boolean;
  enabled: boolean;
};

export type AIProvider = "heuristic" | "anthropic" | "openai" | "gemini";

export type UserSettings = {
  id: string;
  user_id: string;
  tenant_id: string;
  jurisdiction: string | null;
  base_currency: string | null;
  fiscal_year_start_month: number | null;
  ai_provider: AIProvider | null;
  ai_model: string | null;
  ai_api_key_hint: string | null;
  ai_api_key_present: boolean;
  created_at: string;
  updated_at: string;
};

export type UserSettingsUpdatePayload = {
  jurisdiction?: string | null;
  base_currency?: string | null;
  fiscal_year_start_month?: number | null;
  ai_provider?: AIProvider | null;
  ai_model?: string | null;
  ai_api_key?: string | null;
  ai_api_key_clear?: boolean;
};

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function parseError(res: Response): Promise<ApiRequestError> {
  try {
    const body = (await res.json()) as ApiError;
    return new ApiRequestError(
      body.error?.message ?? `Request failed with ${res.status}`,
      res.status,
      body.error?.code,
    );
  } catch {
    return new ApiRequestError(`Request failed with ${res.status}`, res.status);
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...(init?.body ? { "content-type": "application/json" } : {}),
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw await parseError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<User> {
  return apiFetch<User>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function registerOwner(name: string, email: string, password: string): Promise<User> {
  return apiFetch<User>("/auth/register-owner", {
    method: "POST",
    body: JSON.stringify({ name, email, password }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}

export async function me(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export async function getSettings(): Promise<UserSettings> {
  return apiFetch<UserSettings>("/settings");
}

export async function updateSettings(payload: UserSettingsUpdatePayload): Promise<UserSettings> {
  return apiFetch<UserSettings>("/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function entities(): Promise<Entity[]> {
  return apiFetch<Entity[]>("/entities");
}

export async function listSkills(): Promise<SkillManifest[]> {
  return apiFetch<SkillManifest[]>("/skills");
}

export type Budget = {
  id: string;
  entity_id: string;
  name: string;
  period_start: string;
  period_end: string;
  notes: string | null;
  lines: Array<{
    id: string;
    account_id: string;
    planned_amount: string;
    notes: string | null;
  }>;
};

export type BudgetActuals = {
  budget_id: string;
  entity_id: string;
  period_start: string;
  period_end: string;
  total_planned: string;
  total_actual: string;
  total_variance: string;
  lines: Array<{
    account_id: string;
    account_code: string;
    account_name: string;
    planned_amount: string;
    actual_amount: string;
    variance_amount: string;
    overspent: boolean;
  }>;
};

export type Debt = {
  id: string;
  entity_id: string;
  name: string;
  kind: string;
  original_principal: string | null;
  current_balance: string;
  interest_rate_apr: string | null;
  minimum_payment: string | null;
  due_day_of_month: number | null;
  next_due_date: string | null;
  linked_account_id: string | null;
  status: string;
  notes: string | null;
};

export type Invoice = {
  id: string;
  entity_id: string;
  customer_id: string;
  number: string;
  invoice_date: string;
  due_date: string;
  memo: string | null;
  subtotal: string;
  total: string;
  balance_due: string;
  status: string;
  posted_at: string | null;
  posted_entry_id: string | null;
};

export type Bill = {
  id: string;
  entity_id: string;
  vendor_id: string;
  number: string;
  bill_date: string;
  due_date: string;
  memo: string | null;
  subtotal: string;
  total: string;
  balance_due: string;
  status: string;
};

export type StatementRow = {
  account_id: string;
  code: string;
  name: string;
  amount: string;
};

export type BalanceSheet = {
  entity_id: string;
  as_of: string;
  assets: StatementRow[];
  liabilities: StatementRow[];
  equity: StatementRow[];
  current_earnings: string;
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  is_balanced: boolean;
};

export type IncomeStatement = {
  entity_id: string;
  date_from: string;
  date_to: string;
  income: StatementRow[];
  expenses: StatementRow[];
  total_income: string;
  total_expenses: string;
  net_income: string;
};

export type AgingRow = {
  object_id: string;
  number: string;
  counterparty_name: string;
  due_date: string;
  balance_due: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_91_plus: string;
};

export type AgingReport = {
  entity_id: string;
  as_of: string;
  total_balance_due: string;
  rows: AgingRow[];
};

export async function listBudgets(entityId: string): Promise<Budget[]> {
  return apiFetch<Budget[]>(`/entities/${entityId}/personal/budgets`);
}

export async function getBudgetActuals(entityId: string, budgetId: string): Promise<BudgetActuals> {
  return apiFetch<BudgetActuals>(`/entities/${entityId}/personal/budgets/${budgetId}/actuals`);
}

export async function listDebts(entityId: string): Promise<Debt[]> {
  return apiFetch<Debt[]>(`/entities/${entityId}/personal/debts`);
}

export async function listInvoices(entityId: string): Promise<Invoice[]> {
  return apiFetch<Invoice[]>(`/entities/${entityId}/business/invoices`);
}

export async function listBills(entityId: string): Promise<Bill[]> {
  return apiFetch<Bill[]>(`/entities/${entityId}/business/bills`);
}

export async function getBalanceSheet(entityId: string, asOf: string): Promise<BalanceSheet> {
  return apiFetch<BalanceSheet>(`/entities/${entityId}/business/reports/balance-sheet?as_of=${asOf}`);
}

export async function getIncomeStatement(
  entityId: string,
  dateFrom: string,
  dateTo: string,
): Promise<IncomeStatement> {
  return apiFetch<IncomeStatement>(
    `/entities/${entityId}/business/reports/income-statement?date_from=${dateFrom}&date_to=${dateTo}`,
  );
}

export async function getArAging(entityId: string, asOf: string): Promise<AgingReport> {
  return apiFetch<AgingReport>(`/entities/${entityId}/business/reports/ar-aging?as_of=${asOf}`);
}

export async function getApAging(entityId: string, asOf: string): Promise<AgingReport> {
  return apiFetch<AgingReport>(`/entities/${entityId}/business/reports/ap-aging?as_of=${asOf}`);
}

export type Goal = {
  id: string;
  entity_id: string;
  name: string;
  kind: string;
  target_amount: string;
  target_date: string | null;
  current_amount: string;
  linked_account_id: string | null;
  status: string;
  notes: string | null;
};

export type InvestmentHolding = {
  id: string;
  symbol: string;
  name: string | null;
  kind: string;
  shares: string;
  cost_basis_per_share: string | null;
  current_price: string | null;
  last_priced_at: string | null;
};

export type InvestmentAccount = {
  id: string;
  entity_id: string;
  name: string;
  broker: string | null;
  kind: string;
  currency: string;
  linked_account_id: string | null;
  notes: string | null;
  holdings: InvestmentHolding[];
};

export type Account = {
  id: string;
  entity_id: string;
  parent_id: string | null;
  code: string;
  name: string;
  type: "asset" | "liability" | "equity" | "income" | "expense";
  normal_side: "debit" | "credit";
  is_active: boolean;
  description: string | null;
};

export type JournalLine = {
  id: string;
  account_id: string;
  line_no: number;
  debit: string;
  credit: string;
  description: string | null;
};

export type JournalEntry = {
  id: string;
  entity_id: string;
  entry_date: string;
  memo: string | null;
  reference: string | null;
  status: "draft" | "posted" | "voided";
  posted_at: string | null;
  voided_at: string | null;
  voided_reason: string | null;
  lines: JournalLine[];
};

export async function listGoals(entityId: string): Promise<Goal[]> {
  return apiFetch<Goal[]>(`/entities/${entityId}/personal/goals`);
}

export async function listInvestments(entityId: string): Promise<InvestmentAccount[]> {
  return apiFetch<InvestmentAccount[]>(`/entities/${entityId}/personal/investments`);
}

export async function listAccounts(entityId: string): Promise<Account[]> {
  return apiFetch<Account[]>(`/entities/${entityId}/accounts`);
}

export async function listJournalEntries(entityId: string): Promise<JournalEntry[]> {
  return apiFetch<JournalEntry[]>(`/entities/${entityId}/journal-entries`);
}

export function findEntityByMode(items: Entity[], mode: Entity["mode"]): Entity | null {
  return items.find((item) => item.mode === mode) ?? null;
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function monthStartIso(asOf: string = todayIso()): string {
  return `${asOf.slice(0, 7)}-01`;
}
