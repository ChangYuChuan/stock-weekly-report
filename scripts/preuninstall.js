#!/usr/bin/env node
"use strict";
/**
 * preuninstall.js
 *
 * Runs automatically before `npm uninstall -g stock-weekly-report`.
 * Removes the cron job so it doesn't point to deleted files.
 */

const { execSync } = require("child_process");

const CRON_MARKER = "# swr:stock-weekly-report";

function removeCronJob() {
  try {
    const current = execSync("crontab -l 2>/dev/null", {
      encoding: "utf8",
    }).trim();

    if (!current.includes(CRON_MARKER)) {
      return; // nothing to remove
    }

    const cleaned = current
      .split("\n")
      .filter((line) => !line.includes(CRON_MARKER))
      .join("\n")
      .trim();

    if (cleaned) {
      execSync(`echo "${cleaned}" | crontab -`);
    } else {
      execSync("crontab -r 2>/dev/null || true", { shell: true });
    }

    console.log("swr: removed cron job.");
  } catch {
    // crontab may not exist — not an error
  }
}

removeCronJob();

console.log(
  "\nswr: uninstalled.\n" +
  "  If you had Claude Desktop configured, remove the 'stock-weekly-report'\n" +
  "  entry from claude_desktop_config.json.\n"
);
