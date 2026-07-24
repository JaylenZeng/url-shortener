// Base URL for the backend API. Empty string means "same origin", which works
// with the Vite dev proxy (see vite.config.ts). Set VITE_API_BASE_URL to point
// at the backend directly in other environments.
const API_BASE: string = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ApiErrorBody {
  error?: string;
  status_code?: number;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false } = opts;

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("Unable to reach the server. Please try again.", 0);
  }

  // 204 No Content (e.g. delete) has no body to parse.
  if (res.status === 204) return undefined as T;

  const data = (await res.json().catch(() => null)) as
    | (ApiErrorBody & Record<string, unknown>)
    | null;

  if (!res.ok) {
    if (res.status === 401) {
      // Token missing/expired — drop it so the app returns to the login screen.
      clearToken();
      throw new ApiError("Your session has expired. Please sign in again.", 401);
    }
    // The backend returns validation failures as { error: "Validation failed" };
    // surface something more actionable for the common password-length case.
    if (res.status === 422) {
      throw new ApiError(
        "Please check your details. Password must be at least 8 characters.",
        res.status,
      );
    }
    const message =
      (data && typeof data.error === "string" && data.error) ||
      "Something went wrong. Please try again.";
    throw new ApiError(message, res.status);
  }

  return data as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "POST", body });
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  created_at: string;
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return post<TokenResponse>("/auth/login", { email, password });
}

export function register(
  email: string,
  password: string,
): Promise<UserResponse> {
  return post<UserResponse>("/auth/register", { email, password });
}

export interface Link {
  id: string;
  short_code: string;
  original_url: string;
  created_at: string;
  expires_at: string | null;
  click_count: number;
}

export interface CreateLinkInput {
  original_url: string;
  custom_alias?: string;
  expires_at?: string | null;
}

export function listLinks(): Promise<Link[]> {
  return request<Link[]>("/links", { auth: true });
}

export function createLink(input: CreateLinkInput): Promise<Link> {
  return request<Link>("/links", { method: "POST", body: input, auth: true });
}

export function deleteLink(id: string): Promise<void> {
  return request<void>(`/links/${id}`, { method: "DELETE", auth: true });
}

// Base origin that serves the short links / redirects. In dev the redirect
// route lives on the backend (port 8000), so point there; in production the
// short links are served from the same origin as the app.
const SHORT_BASE: string =
  import.meta.env.VITE_SHORT_BASE_URL ??
  (import.meta.env.DEV ? "http://localhost:8000" : window.location.origin);

export function shortUrl(code: string): string {
  return `${SHORT_BASE}/${code}`;
}

const TOKEN_KEY = "access_token";

export function storeToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}
