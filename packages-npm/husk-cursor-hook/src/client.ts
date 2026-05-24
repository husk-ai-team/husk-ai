// Tiny HTTP client used by the hook handler. Uses global `fetch` (Node 18+).

export function huskUrl(): string {
  return (process.env.HUSK_URL || "http://localhost:7654").replace(/\/$/, "");
}

interface PostOpts {
  timeoutMs?: number;
}

export async function postJson<T = any>(
  url: string,
  body: unknown,
  opts: PostOpts = {},
): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 5000);
  try {
    const r = await fetch(url, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!r.ok) {
      throw new Error(`${url}: ${r.status} ${r.statusText}`);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export async function getJson<T = any>(
  url: string,
  opts: PostOpts = {},
): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 30_000);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) {
      throw new Error(`${url}: ${r.status} ${r.statusText}`);
    }
    return (await r.json()) as T;
  } finally {
    clearTimeout(t);
  }
}

export async function longPollDecision(
  base: string,
  eventId: string,
  timeoutMs: number,
): Promise<{ permission?: string; user_message?: string; agent_message?: string }> {
  const seconds = Math.max(5, Math.floor(timeoutMs / 1000));
  // The backend's long-poll waits up to `timeout=` seconds.
  return await getJson(
    `${base}/api/cursor/events/${encodeURIComponent(eventId)}/decision?timeout=${seconds}`,
    { timeoutMs: timeoutMs + 5000 },
  );
}
