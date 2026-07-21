#!/usr/bin/env node
// claude-packs — npm shim. The real CLI is the bash script shipped in ../bin;
// this just points it at the packaged registry (this package's root) and runs it.
"use strict";

const { spawnSync } = require("child_process");
const path = require("path");

const root = path.join(__dirname, "..");
const cli = path.join(root, "bin", "claude-packs");

const env = Object.assign({}, process.env);
if (!env.CLAUDE_PACKS_HOME) env.CLAUDE_PACKS_HOME = root;
if (!env.CLAUDE_PACKS_DIST) env.CLAUDE_PACKS_DIST = "npm";

const result = spawnSync("bash", [cli].concat(process.argv.slice(2)), {
  stdio: "inherit",
  env,
});

if (result.error && result.error.code === "ENOENT") {
  console.error(
    "claude-packs: bash is required but was not found on PATH " +
      "(on Windows, run inside Git Bash or WSL)."
  );
  process.exit(127);
}
process.exit(result.status == null ? 1 : result.status);
