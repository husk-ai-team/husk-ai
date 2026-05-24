// Entry point for the `husk-cursor-hook` CLI.
//
// Subcommands:
//   husk-cursor-hook install [path]        write .cursor/hooks.json into [path] (default: cwd)
//   husk-cursor-hook hook --event=<name>   handle a Cursor hook event (stdin → stdout)
//   husk-cursor-hook ping                  verify Husk backend reachability

import { runHook } from "./hook";
import { install } from "./install";
import { ping } from "./ping";

function help(): void {
  process.stderr.write(
    `husk-cursor-hook — Cursor SDK Hooks bridge for Husk.

Commands:
  install [path]            Write .cursor/hooks.json into [path] (default: cwd).
  hook --event=<name>       Handle a Cursor hook event (called by Cursor; reads stdin, writes stdout).
  ping [--url=URL]          Probe the Husk backend (default: http://localhost:7654).

Env:
  HUSK_URL                  Override the Husk backend URL (default: http://localhost:7654).
`,
  );
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const cmd = argv[0];

  if (!cmd || cmd === "--help" || cmd === "-h") {
    help();
    process.exit(0);
  }

  if (cmd === "install") {
    await install(argv[1]);
    process.exit(0);
  }

  if (cmd === "hook") {
    const eventArg = argv.find((a) => a.startsWith("--event="));
    const event = eventArg ? eventArg.slice("--event=".length) : "";
    if (!event) {
      process.stderr.write("husk-cursor-hook: --event=<name> is required\n");
      // Fail open so Cursor isn't stuck.
      process.stdout.write("{}");
      process.exit(0);
    }
    await runHook(event);
    return;
  }

  if (cmd === "ping") {
    const urlArg = argv.find((a) => a.startsWith("--url="));
    const url = urlArg ? urlArg.slice("--url=".length) : undefined;
    await ping(url);
    return;
  }

  help();
  process.exit(1);
}

main().catch((e) => {
  process.stderr.write(`husk-cursor-hook: ${e}\n`);
  process.exit(1);
});
