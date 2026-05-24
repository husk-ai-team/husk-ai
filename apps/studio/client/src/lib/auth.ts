// Local auth helpers for the studio.
// Talks to the FastAPI backend's /api/auth/* endpoints (served by husk-studio-backend).
// The backend in turn talks to husk-cloud — the studio never sees the cloud directly.

import { useEffect, useState } from "react";

export interface Session {
  email: string;
  name: string;
  plan: string;
  saved_at: number;
  expires_at: number | null;
  is_guest?: boolean;
}

export interface StartAuthResult {
  state: string;
  authorize_url: string;
}

async function jsonFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init.headers || {}) },
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => `${r.status}`);
    throw new AuthError(detail, r.status);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export class AuthError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export const auth = {
  me: () => jsonFetch<Session>("/api/auth/me"),
  start: () => jsonFetch<StartAuthResult>("/api/auth/start", { method: "POST", body: "{}" }),
  anonymous: () =>
    jsonFetch<void>("/api/auth/anonymous", { method: "POST", body: "{}" }),
  logout: () => jsonFetch<void>("/api/auth/logout", { method: "POST" }),
};

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let alive = true;
    auth
      .me()
      .then((s) => alive && setSession(s))
      .catch((e) => alive && setSession(null))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [refreshKey]);

  return {
    session,
    loading,
    refresh: () => setRefreshKey((k) => k + 1),
    clear: async () => {
      try {
        await auth.logout();
      } catch {
        // ignore
      }
      // useSession instances aren't shared across components; the simplest
      // way to propagate a cleared session to every consumer (App's gate
      // included) is to reload. Mirrors what WelcomeGate does on Try-free.
      window.location.reload();
    },
  };
}
