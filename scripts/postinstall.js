#!/usr/bin/env node
"use strict";
/**
 * postinstall.js
 *
 * Run automatically after `npm install -g`.
 * Creates the CLI venv at ~/.config/swr/venv (stable across reinstalls)
 * and installs swr + swr-mcp entry points via `pip install .`.
 *
 * Re-runs only when the package version changes, so reinstalls are fast.
 *
 * The pipeline venv (venv/) requires Python 3.9+ and heavier dependencies
 * (faster-whisper, etc.) — set it up separately inside the project dir:
 *   python3 -m venv venv && venv/bin/pip install -r requirements.txt
 */

const { execSync, execFileSync } = require("child_process");
const path = require("path");
const fs   = require("fs");
const os   = require("os");

const ROOT        = path.join(__dirname, "..");
const SWR_DIR     = path.join(os.homedir(), ".config", "swr");
const VENV        = path.join(SWR_DIR, "venv");
const SWR_BIN     = path.join(VENV, "bin", "swr");
const VERSION_FILE = path.join(SWR_DIR, ".cli_version");

const pkg         = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
const CURRENT_VER = pkg.version;

// ── Skip if already installed at this version ─────────────────────────────
if (fs.existsSync(SWR_BIN) && fs.existsSync(VERSION_FILE)) {
  const installedVer = fs.readFileSync(VERSION_FILE, "utf8").trim();
  if (installedVer === CURRENT_VER) {
    console.log(`swr: CLI v${CURRENT_VER} already installed at ${VENV}, skipping.`);
    process.exit(0);
  }
  console.log(`swr: Upgrading CLI from v${installedVer} to v${CURRENT_VER}…`);
}

// ── Find Python 3.10+ ─────────────────────────────────────────────────────
function findPython() {
  const candidates = [
    "python3.14", "python3.13", "python3.12", "python3.11", "python3.10",
    "python3", "python",
  ];
  for (const cmd of candidates) {
    try {
      const out = execSync(`${cmd} --version 2>&1`, { encoding: "utf8" }).trim();
      const m = out.match(/Python 3\.(\d+)/);
      if (m && parseInt(m[1], 10) >= 10) return cmd;
    } catch { /* not found */ }
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error(
    "\nswr postinstall: Python 3.10+ is required but was not found.\n" +
    "Install it from https://www.python.org/downloads/ then run:\n" +
    "  npm install -g stock-weekly-report\n"
  );
  process.exit(1);
}

// ── Create venv and install ───────────────────────────────────────────────
fs.mkdirSync(SWR_DIR, { recursive: true });
console.log(`\nswr: Setting up Python venv at ${VENV} with ${python}…`);
try {
  execFileSync(python, ["-m", "venv", VENV], { stdio: "inherit", cwd: ROOT });

  const pip = path.join(VENV, "bin", "pip");
  execFileSync(pip, ["install", "."], { stdio: "inherit", cwd: ROOT });

  fs.writeFileSync(VERSION_FILE, CURRENT_VER + "\n", "utf8");
  console.log(`\nswr: Setup complete (v${CURRENT_VER}). Run \`swr --help\` to get started.\n`);
} catch (err) {
  console.error("\nswr postinstall failed:", err.message);
  console.error("You can retry manually:\n");
  console.error(`  ${python} -m venv ${VENV}`);
  console.error(`  ${VENV}/bin/pip install ${ROOT}`);
  process.exit(1);
}
