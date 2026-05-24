import { build, context } from "esbuild";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const watch = process.argv.includes("--watch");

mkdirSync(resolve(root, "dist"), { recursive: true });

const cfg = {
  entryPoints: [resolve(root, "src", "extension.ts")],
  outfile: resolve(root, "dist", "extension.js"),
  bundle: true,
  platform: "node",
  target: "node18",
  format: "cjs",
  external: ["vscode"],
  sourcemap: false,
  logLevel: "info",
};

if (watch) {
  const ctx = await context(cfg);
  await ctx.watch();
  console.log("watching…");
} else {
  await build(cfg);
}
