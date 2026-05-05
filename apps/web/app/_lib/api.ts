"use client";

export type ApiError = {
  error?: {
    code?: string;
    message?: string;
    details?: Record<string, unknown>;
  };
};

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

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function parseError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiError;
    return body.error?.message ?? `Request failed with ${res.status}`;
  } catch {
    return `Request failed with ${res.status}`;
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
    throw new Error(await parseError(res));
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

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}

export async function me(): Promise<User> {
  return apiFetch<User>("/auth/me");
}

export async function entities(): Promise<Entity[]> {
  return apiFetch<Entity[]>("/entities");
}

export async function listSkills(): Promise<SkillManifest[]> {
  return apiFetch<SkillManifest[]>("/skills");
}
