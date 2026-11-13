/**
 * REST API client — wraps fetch with:
 *  - credentials: 'include' (sends cookies)
 *  - X-CSRF-Token header on mutating requests
 *  - Typed responses
 */

export interface User {
  id: string;
  email: string;
  role: "admin" | "analyst" | "viewer";
}

export interface ChatSession {
  id: string;
  title: string | null;
  dataset_id: string | null;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface SessionDetail extends ChatSession {
  messages: Message[];
}

export interface Dataset {
  id: string;
  name: string;
  description: string | null;
  has_key: boolean;
  model_name: string | null;
  rdb_imported: boolean;
}

export interface ChatDataset {
  id: string;
  name: string;
  description: string | null;
}

export interface AdminUser {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface RbacGrant {
  id: string;
  user_id: string;
  dataset_id: string;
  entity_type: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function getCsrfToken(): string {
  const match = document.cookie.match(/csrf_token=([^;]+)/);
  return match ? match[1] : "";
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (["POST", "DELETE", "PATCH", "PUT"].includes(method)) {
    headers["X-CSRF-Token"] = getCsrfToken();
  }

  const res = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }

  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

async function uploadFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(path, {
    method: "POST",
    headers: { "X-CSRF-Token": getCsrfToken() },
    credentials: "include",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export const auth = {
  login: (email: string, password: string) =>
    request<{ user: User; csrf_token: string }>("POST", "/api/auth/login", { email, password }),
  logout: () => request<{ ok: boolean }>("POST", "/api/auth/logout"),
  me: () => request<User>("GET", "/api/auth/me"),
};

// ── Chats ──────────────────────────────────────────────────────────────────────

export const chats = {
  list: () => request<ChatSession[]>("GET", "/api/chats"),
  get: (id: string) => request<SessionDetail>("GET", `/api/chats/${id}`),
  delete: (id: string) => request<void>("DELETE", `/api/chats/${id}`),
};

// ── Datasets a user can chat with ──────────────────────────────────────────────

export const datasets = {
  list: () => request<ChatDataset[]>("GET", "/api/datasets"),
};

// ── Admin ──────────────────────────────────────────────────────────────────────

export const admin = {
  listUsers: () => request<AdminUser[]>("GET", "/api/admin/users"),
  createUser: (email: string, password: string, role: string) =>
    request<AdminUser>("POST", "/api/admin/users", { email, password, role }),
  deleteUser: (id: string) => request<void>("DELETE", `/api/admin/users/${id}`),

  listDatasets: () => request<Dataset[]>("GET", "/api/admin/datasets"),
  createDataset: (name: string, description?: string) =>
    request<Dataset>("POST", "/api/admin/datasets", { name, description }),

  uploadKey: (dataset_id: string, aes_key_hex: string) =>
    request<{ key_ref: string }>("POST", `/api/admin/datasets/${dataset_id}/key`, { aes_key_hex }),
  deleteKey: (dataset_id: string) =>
    request<void>("DELETE", `/api/admin/datasets/${dataset_id}/key`),

  importRdb: (dataset_id: string, file: File) =>
    uploadFile<{ imported_tokens: number }>(`/api/admin/datasets/${dataset_id}/import-rdb`, file),
  uploadModel: (dataset_id: string, file: File) =>
    uploadFile<{ model_name: string }>(`/api/admin/datasets/${dataset_id}/upload-model`, file),

  listGrants: () => request<RbacGrant[]>("GET", "/api/admin/rbac"),
  addGrant: (user_id: string, dataset_id: string, entity_type: string) =>
    request<{ id: string }>("POST", "/api/admin/rbac", { user_id, dataset_id, entity_type }),
  removeGrant: (id: string) => request<void>("DELETE", `/api/admin/rbac/${id}`),
};
