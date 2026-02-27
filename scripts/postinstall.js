#!/usr/bin/env node
"use strict";
/**
 * postinstall.js
 *
 * Run automatically after `npm install`.
 * Finds Python 3.10+, creates venv14/, and installs the swr + swr-mcp
 * entry points via `pip install -e .`.
 *
 * The pipeline venv (venv/) requires Python 3.9+ and heavier dependencies
 * (faster-whisper, etc.) — set it up separately:
 *   python3 -m venv venv && venv/bin/pip install -r requirements.txt
 */

const { execSync, execFileSync } = require("child_process");
const path = require("path");
const fs = require("fs");

const ROOT   = path.join(__dirname, "..");
const VENV14 = path.join(ROOT, "venv14");
const SWR    = path.join(VENV14, "bin", "swr");

// Skip if already installed
if (fs.existsSync(SWR)) {
  console.log("swr: CLI already installed, skipping setup.");
  process.exit(0);
}

// ── Find Python 3.10+ ────────────────────────────────────────────────────────
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
    "  npm install\n"
  );
  process.exit(1);
}

// ── Create venv14 and install ────────────────────────────────────────────────
console.log(`\nswr: Setting up Python venv with ${python}…`);
try {
  execFileSync(python, ["-m", "venv", VENV14], { stdio: "inherit", cwd: ROOT });

  const pip = path.join(VENV14, "bin", "pip");
  execFileSync(pip, ["install", "-e", "."], { stdio: "inherit", cwd: ROOT });

  console.log("\nswr: Setup complete. Run `swr --help` to get started.\n");
} catch (err) {
  console.error("\nswr postinstall failed:", err.message);
  console.error("You can retry manually:\n");
  console.error(`  ${python} -m venv ${VENV14}`);
  console.error(`  ${VENV14}/bin/pip install -e .`);
  process.exit(1);
}
