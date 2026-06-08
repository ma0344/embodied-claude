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
const isWin = process.platform === "win32";

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

function pathCandidatesOnPath() {
  if (process.env.CLAUDE_BIN && fs.existsSync(process.env.CLAUDE_BIN)) {
    return [process.env.CLAUDE_BIN];
  }

  const r = spawnSync(isWin ? "where" : "which", ["claude"], {
    encoding: "utf8",
    shell: isWin,
  });
  if (r.status !== 0 || !r.stdout) return [];
  return r.stdout
    .trim()
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseWindowsCmd(cmdPath) {
  const text = fs.readFileSync(cmdPath, "utf8");
  const dir = path.dirname(cmdPath);

  const dp0Match = text.match(/"%dp0%\\([^"\r\n]+)"/i);
  if (dp0Match) {
    const target = path.join(dir, dp0Match[1]);
    if (fs.existsSync(target)) return target;
  }

  const tildeMatch = text.match(/"%~dp0([^"\r\n]+)"/i);
  if (tildeMatch) {
    const target = path.join(dir, tildeMatch[1]);
    if (fs.existsSync(target)) return target;
  }

  return null;
}

function findInClaudePackage(root) {
  const pkg = path.join(root, "@anthropic-ai", "claude-code");
  if (!fs.existsSync(pkg)) return null;

  const names = [
    "cli.js",
    "cli.cjs",
    "index.js",
    "claude.exe",
    "claude",
    path.join("vendor", "claude.exe"),
    path.join("bin", "claude.exe"),
  ];
  for (const name of names) {
    const candidate = path.join(pkg, name);
    if (fs.existsSync(candidate)) return candidate;
  }

  try {
    const pkgJson = JSON.parse(fs.readFileSync(path.join(pkg, "package.json"), "utf8"));
    const bin = pkgJson.bin;
    if (typeof bin === "string") {
      const candidate = path.join(pkg, bin);
      if (fs.existsSync(candidate)) return candidate;
    } else if (bin && typeof bin === "object") {
      for (const rel of Object.values(bin)) {
        const candidate = path.join(pkg, rel);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  } catch {
    // ignore
  }

  return null;
}

function npmRoots() {
  return [
    path.join(process.env.APPDATA || "", "npm", "node_modules"),
    path.join(process.env.LOCALAPPDATA || "", "npm", "node_modules"),
    path.join(process.env.USERPROFILE || "", ".local", "bin", "node_modules"),
    path.join(process.env.ProgramFiles || "", "nodejs", "node_modules"),
  ];
}

function resolveClaudeTarget() {
  for (const candidate of pathCandidatesOnPath()) {
    if (!fs.existsSync(candidate)) continue;

    if (candidate.endsWith(".cmd") || candidate.endsWith(".bat")) {
      const parsed = parseWindowsCmd(candidate);
      if (parsed) return parsed;
      return candidate;
    }

    return candidate;
  }

  for (const root of npmRoots()) {
    const found = findInClaudePackage(root);
    if (found) return found;
  }

  try {
    return require.resolve("@anthropic-ai/claude-code/cli.js");
  } catch {
    // continue
  }

  return null;
}

function runClaude(claudeArgs) {
  const target = resolveClaudeTarget();

  if (!target) {
    const fallback = spawnSync(isWin ? "claude.cmd" : "claude", claudeArgs, {
      stdio: "inherit",
      env: process.env,
      cwd: REPO,
      shell: isWin,
    });
    if (fallback.error) throw fallback.error;
    return fallback;
  }

  const lower = target.toLowerCase();
  if (lower.endsWith(".js") || lower.endsWith(".cjs") || lower.endsWith(".mjs")) {
    return spawnSync(process.execPath, [target, ...claudeArgs], {
      stdio: "inherit",
      env: process.env,
      cwd: REPO,
    });
  }

  if (lower.endsWith(".cmd") || lower.endsWith(".bat")) {
    return spawnSync(target, claudeArgs, {
      stdio: "inherit",
      env: process.env,
      cwd: REPO,
      shell: true,
    });
  }

  return spawnSync(target, claudeArgs, {
    stdio: "inherit",
    env: process.env,
    cwd: REPO,
    shell: false,
  });
}

const model = loadModel();
const userArgs = process.argv.slice(2);
const hasModelFlag = userArgs.some((arg) => arg === "--model" || arg.startsWith("--model="));
const claudeArgs = hasModelFlag ? userArgs : ["--model", model, ...userArgs];

let result;
try {
  result = runClaude(claudeArgs);
} catch (error) {
  console.error(error.message || error);
  process.exit(1);
}

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
