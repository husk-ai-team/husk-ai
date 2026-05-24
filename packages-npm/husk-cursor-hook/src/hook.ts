// Hook handler — invoked by Cursor for each hook event.
//
// Contract: reads a JSON payload from stdin (Cursor's hook input), POSTs to
// Husk, long-polls for a decision, then writes the appropriate JSON to stdout
// for Cursor.
//
// Fails OPEN on backend errors / timeouts so Cursor isn't blocked when Husk
// isn't running locally.

import { huskUrl, postJson, longPollDecision } from "./client";
import { basename, dirname, resolve as pathResolve } from "node:path";

interface HookInput {
  hook_event_name?: string;
  conversation_id?: string;
  generation_id?: string;
  workspace_roots?: string[];
  command?: string;
  cwd?: string;
  tool_name?: string;
  file_path?: string;
  prompt?: string;
  [k: string]: unknown;
}

const TIMEOUT_MS = 25_000;
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
      // Couldn't parse — pass an empty object to backend, but record the hook event.
    }
  }
  payload.hook_event_name = payload.hook_event_name || event;

  // Fire the event to Husk; if the backend isn't reachable, fail open.
  let eventId: string | null = null;
  let blocking = isBlocking(event);
  try {
    const resp = await postJson(`${huskUrl()}/api/cursor/events`, {
      hook: event,
      payload,
      project: deriveProject(payload),
    }, { timeoutMs: NETWORK_TIMEOUT_MS });
    eventId = resp?.event_id ?? null;
    blocking = resp?.blocking ?? blocking;
  } catch {
    // Husk unreachable — allow + log to stderr.
    process.stderr.write(`husk-cursor-hook: Husk not reachable at ${huskUrl()} — failing open.\n`);
    emit(allowResponse(event));
    process.exit(0);
  }

  if (!blocking || !eventId) {
    emit(allowResponse(event));
    process.exit(0);
  }

  // Long-poll for a decision.
  let decision: { permission?: string; user_message?: string; agent_message?: string } = {};
  try {
    decision = await longPollDecision(huskUrl(), eventId, TIMEOUT_MS);
  } catch {
    // Treat unreachable as ask (let Cursor prompt the user) for safety.
    decision = { permission: "ask", user_message: "Husk poll failed." };
  }

  emit(formatResponse(event, decision));
  // Exit 2 = explicit block per Cursor docs; we prefer stdout JSON ("permission":"deny").
  process.exit(0);
}

function isBlocking(event: string): boolean {
  return (
    event === "beforeShellExecution" ||
    event === "beforeMCPExecution" ||
    event === "beforeReadFile" ||
    event === "beforeSubmitPrompt"
  );
}

function allowResponse(event: string): unknown {
  // Hook-specific "allow" shape.
  if (event === "beforeSubmitPrompt") return { continue: true };
  if (event === "afterFileEdit") return {};
  if (event === "stop") return {};
  return { permission: "allow" };
}

function formatResponse(
  event: string,
  decision: { permission?: string; user_message?: string; agent_message?: string },
): unknown {
  const perm = decision.permission || "allow";
  if (event === "beforeSubmitPrompt") {
    return {
      continue: perm !== "deny",
      user_message: decision.user_message,
    };
  }
  if (event === "afterFileEdit" || event === "stop") {
    return {};
  }
  return {
    permission: perm === "deny" || perm === "ask" ? perm : "allow",
    user_message: decision.user_message,
    agent_message: decision.agent_message,
  };
}
