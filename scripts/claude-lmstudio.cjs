#!/usr/bin/env node
/**
 * Claude Code entry shim for ma-home (LM Studio + forced --model).
 * .cjs because repo package.json has "type": "module".
 */
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const REPO = path.resolve(__dirname, "..");
const DEFAULT_MODEL = "google/gemma-4-12b-qat";

function loadModel() {
  let model = process.env.CLAUDE_MODEL || process.env.LMSTUDIO_MODEL || DEFAULT_MODEL;
  const settingsPath = path.join(REPO, ".claude", "settings.local.json");
  try {
    const settings = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    if (settings.model) model = settings.model;
    if (settings.env?.CLAUDE_MODEL) model = settings.env.CLAUDE_MODEL;
  } catch {
    // settings.local.json optional when env is set by parent process
  }
  return model;
}

function findClaudeCli() {
  try {
    return require.resolve("@anthropic-ai/claude-code/cli.js");
  } catch {
    // global npm on Windows
  }

  const roots = [
    path.join(process.env.APPDATA || "", "npm", "node_modules"),
    path.join(process.env.LOCALAPPDATA || "", "npm", "node_modules"),
    path.join(process.env.USERPROFILE || "", ".local", "bin", "node_modules"),
  ];

  for (const root of roots) {
    const candidate = path.join(root, "@anthropic-ai", "claude-code", "cli.js");
    if (fs.existsSync(candidate)) return candidate;
  }

  throw new Error(
    "Could not find @anthropic-ai/claude-code/cli.js. Install: npm install -g @anthropic-ai/claude-code",
  );
}

const model = loadModel();
const claudeCli = findClaudeCli();
const userArgs = process.argv.slice(2);

const hasModelFlag = userArgs.some((arg) => arg === "--model" || arg.startsWith("--model="));
const args = hasModelFlag ? userArgs : ["--model", model, ...userArgs];

const result = spawnSync(process.execPath, [claudeCli, ...args], {
  stdio: "inherit",
  env: process.env,
  cwd: REPO,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
