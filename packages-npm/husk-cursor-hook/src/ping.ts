// `husk-cursor-hook ping` — diagnostic for verifying Husk reachability.

import { getJson, huskUrl } from "./client";

export async function ping(url?: string): Promise<void> {
  const base = (url || huskUrl()).replace(/\/$/, "");
  try {
    const r = await getJson<{ ok?: boolean; service?: string; version?: string }>(
      `${base}/api/health`,
      { timeoutMs: 3000 },
    );
    if (r.ok) {
      process.stdout.write(`Husk OK — ${r.service ?? ""} ${r.version ?? ""}\n`);
      process.exit(0);
    }
    process.stderr.write(`Unexpected response: ${JSON.stringify(r)}\n`);
    process.exit(1);
  } catch (e) {
    process.stderr.write(`Cannot reach Husk at ${base}: ${e}\n`);
    process.exit(1);
  }
}
