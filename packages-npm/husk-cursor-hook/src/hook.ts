// Hook handler — invoked by Cursor for each observability hook event.
//
// Contract: reads a JSON payload from stdin (Cursor's hook input), POSTs it to
// Husk as fire-and-forget, then writes an empty JSON response to stdout so
// Cursor proceeds without delay.
//
// Husk never blocks the agent — this bridge is observability-only. If the
// backend is unreachable, we still emit an empty response and exit cleanly.

import { huskUrl, postJson } from "./client";
import { basename, resolve as pathResolve } from "node:path";

interface HookInput {
  hook_event_name?: string;
  conversation_id?: string;
  generation_id?: string;
  workspace_roots?: string[];
  command?: string;
  cwd?: string;
  tool_name?: string;
  file_path?: string;
  [k: string]: unknown;
}

const NETWORK_TIMEOUT_MS = 1500;

async function readStdin(): Promise<string> {
  return new Promise((resolveP) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => {
      data += chunk;
    });
    process.stdin.on("end", () => resolveP(data));
    process.stdin.on("error", () => resolveP(data));
    // Some shells (looking at you, Windows) don't always close stdin promptly.
    setTimeout(() => resolveP(data), 1000);
  });
}

function deriveProject(input: HookInput): string | undefined {
  const root = input.workspace_roots?.[0] || input.cwd;
  return root ? basename(pathResolve(root)) : undefined;
}

function emit(json: unknown): void {
  process.stdout.write(JSON.stringify(json));
}

export async function runHook(event: string): Promise<void> {
  const raw = await readStdin();
  let payload: HookInput = {};
  if (raw.trim()) {
    try {
      payload = JSON.parse(raw);
    } catch {
      // Couldn't parse — pass an empty object to the backend, but record the hook event.
    }
  }
  payload.hook_event_name = payload.hook_event_name || event;

  try {
    await postJson(
      `${huskUrl()}/api/cursor/events`,
      {
        hook: event,
        payload,
        project: deriveProject(payload),
      },
      { timeoutMs: NETWORK_TIMEOUT_MS },
    );
  } catch {
    // Husk unreachable — observability is best-effort. Log to stderr and move on.
    process.stderr.write(
      `husk-cursor-hook: Husk not reachable at ${huskUrl()} — skipping observability record.\n`,
    );
  }

  emit({});
  process.exit(0);
}
