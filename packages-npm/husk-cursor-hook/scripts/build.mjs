import { build, context } from "esbuild";
import { mkdirSync, cpSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const watch = process.argv.includes("--watch");

mkdirSync(resolve(root, "dist"), { recursive: true });

// Copy templates into dist so the install command can find them post-publish.
cpSync(resolve(root, "src", "templates"), resolve(root, "dist", "templates"), {
  recursive: true,
});

const cfg = {
  entryPoints: [resolve(root, "src", "cli.ts")],
  outfile: resolve(root, "dist", "cli.js"),
  bundle: true,
  platform: "node",
  target: "node18",
  format: "cjs",
  banner: { js: "#!/usr/bin/env node" },
  external: [],
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
