import type { User } from "../types";

const PERSISTENT_KEY = "li_agent_token";
const SESSION_KEY = "li_agent_token_session";

// Token survives browser restarts only when the user chose "Remember me";
// otherwise it lives in sessionStorage (cleared when the browser closes).
export function getToken(): string | null {
  return localStorage.getItem(PERSISTENT_KEY) ?? sessionStorage.getItem(SESSION_KEY);
}

export function setToken(token: string, remember = true) {
  clearToken();
  (remember ? localStorage : sessionStorage).setItem(remember ? PERSISTENT_KEY : SESSION_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(PERSISTENT_KEY);
  sessionStorage.removeItem(SESSION_KEY);
}

export async function me(): Promise<User | null> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch("/api/auth/me", {
    credentials: "include",
    headers,
  });
  if (!res.ok) return null;
  return res.json();
}

// After "Sign in with LinkedIn" the backend redirects back with a short-lived
// one-time `code`. Exchange it for a Bearer token (like guests use) so the
// session works even on browsers that drop cookies during cross-site redirects.
export async function exchangeAuthCode(): Promise<void> {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");
  if (!code) return;
  try {
    const res = await fetch(`/api/auth/session?code=${encodeURIComponent(code)}`, {
      credentials: "include",
    });
    if (res.ok) {
      const body = (await res.json()) as { token?: string };
      if (body?.token) setToken(body.token, true);
    }
  } catch {
    /* fall back to the cookie if anything goes wrong */
  } finally {
    // Drop the one-time code from the URL so it can't be replayed or shared.
    window.history.replaceState(null, "", window.location.pathname);
  }
}

export async function guestLogin(name = "", remember = true): Promise<User | null> {
  const res = await fetch("/api/auth/guest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ name }),
  });
  if (!res.ok) return null;
  const body = await res.json();
  setToken(body.token, remember);
  return body.user as User;
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
  }).catch(() => undefined);
  clearToken();
}

export function linkedinLoginUrl(remember = true): string {
  return `/api/auth/linkedin/login?remember=${remember ? 1 : 0}`;
}