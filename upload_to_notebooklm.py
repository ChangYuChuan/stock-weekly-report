"""
upload_to_notebooklm.py

Creates a fresh NotebookLM notebook for a weekly run and uploads all
transcript .txt files as individual sources.

A fresh notebook is always created — if a notebook with the same title
already exists it is deleted first, so stale cached content never bleeds
into a new run.

Requires:
  pip install notebooklm-mcp-cli
  nlm login          # one-time browser auth

Usage:
  python upload_to_notebooklm.py                        # auto-detect latest run folder
  python upload_to_notebooklm.py --folder 20260218-20260225
  python upload_to_notebooklm.py --config my_config.yaml --folder 20260218-20260225
"""

import argparse
import json
import subprocess
import sys
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Config & helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def default_folder_name(lookback_days: int) -> str:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=lookback_days)
    return f"{start.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"


# ---------------------------------------------------------------------------
# nlm CLI wrappers
# ---------------------------------------------------------------------------

def _run_nlm(*args: str, capture: bool = True) -> subprocess.CompletedProcess:
    """Run an nlm command and return the CompletedProcess result."""
    cmd = ["nlm", *args]
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise RuntimeError(
            f"nlm command failed (exit {result.returncode}): {stderr or '(no stderr)'}"
        )
    return result


def check_nlm_auth() -> None:
    """Verify that nlm is installed and the user is authenticated."""
    try:
        _run_nlm("login", "--check")
    except FileNotFoundError:
        print(
            "ERROR: `nlm` command not found.\n"
            "Install it with:  pip install notebooklm-mcp-cli\n"
            "Then authenticate: nlm login"
        )
        sys.exit(1)
    except RuntimeError as exc:
        print(
            f"ERROR: NotebookLM authentication check failed.\n{exc}\n"
            "Run `nlm login` to authenticate."
        )
        sys.exit(1)


def list_notebooks() -> list[dict]:
    """Return all notebooks as a list of dicts (id, title, …)."""
    try:
        result = _run_nlm("notebook", "list", "--json")
        data = json.loads(result.stdout)
        # nlm may return a top-level list or {"notebooks": [...]}
        if isinstance(data, list):
            return data
        return data.get("notebooks", [])
    except Exception as exc:
        print(f"  WARNING: could not list notebooks: {exc}")
        return []


def find_notebook_by_title(title: str) -> "str | None":
    """Return the ID of the first notebook whose title matches, or None."""
    for nb in list_notebooks():
        nb_title = nb.get("title") or nb.get("name") or ""
        if nb_title.strip() == title.strip():
            return nb.get("notebook_id") or nb.get("id")
    return None


def delete_notebook(notebook_id: str) -> None:
    """Delete a notebook by ID (non-fatal on failure)."""
    try:
        _run_nlm("notebook", "delete", notebook_id)
        print(f"  Deleted stale notebook: {notebook_id}")
    except RuntimeError as exc:
        print(f"  WARNING: could not delete notebook {notebook_id}: {exc}")


def create_notebook(title: str) -> str:
    """Create a new NotebookLM notebook and return its ID."""
    result = _run_nlm("notebook", "create", title, "--json")
    data = json.loads(result.stdout)
    notebook_id = data.get("notebook_id") or data.get("id")
    if not notebook_id:
        raise RuntimeError(f"Could not parse notebook ID from response: {result.stdout}")
    return notebook_id


def add_source_file(notebook_id: str, file_path: Path) -> None:
    """Upload a single transcript file to a NotebookLM notebook."""
    # --wait blocks until NotebookLM finishes processing the source
    _run_nlm(
        "source", "add", notebook_id,
        "--file", str(file_path),
        "--wait",
        capture=False,  # stream live output so the user can see progress
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(config: dict, folder_name: str) -> None:
    parent_folder = Path(config["parent_folder"])
    transcript_dir = parent_folder / "transcripts" / folder_name

    if not transcript_dir.exists():
        print(f"ERROR: Transcript directory not found: {transcript_dir}")
        print("Run transcribe.py first to generate transcripts.")
        sys.exit(1)

    txt_files = sorted(transcript_dir.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {transcript_dir}")
        sys.exit(0)

    print(f"Transcript folder : {transcript_dir}")
    print(f"Files to upload   : {len(txt_files)}")
    print()

    # --- Auth check ---
    print("Checking NotebookLM authentication …")
    check_nlm_auth()
    print("Authenticated.\n")

    # --- Always create a fresh notebook ---
    # Delete any existing notebook with the same title first so stale
    # cached content from a previous run cannot leak into this week's output.
    notebook_prefix = config.get("notebooklm_notebook_prefix", "股市週報")
    notebook_title = f"{notebook_prefix} {folder_name}"

    print(f"Checking for existing notebook titled '{notebook_title}' …")
    stale_id = find_notebook_by_title(notebook_title)
    if stale_id:
        print(f"  Found stale notebook ({stale_id}) — deleting it for a clean slate …")
        delete_notebook(stale_id)
    else:
        print("  None found.")

    print(f"\nCreating fresh notebook: '{notebook_title}' …")
    notebook_id = create_notebook(notebook_title)
    print(f"Notebook created: {notebook_id}\n")

    # --- Upload each transcript ---
    success, failed = 0, []

    for idx, txt_file in enumerate(txt_files, start=1):
        print(f"[{idx}/{len(txt_files)}] Uploading: {txt_file.name}")
        try:
            add_source_file(notebook_id, txt_file)
            success += 1
        except RuntimeError as exc:
            print(f"  ERROR: {exc}")
            failed.append(txt_file.name)
        print()

    # --- Summary ---
    print("=" * 60)
    print(f"Done. {success}/{len(txt_files)} transcript(s) uploaded.")
    print(f"Notebook ID  : {notebook_id}")
    print(f"Open in browser: https://notebooklm.google.com/notebook/{notebook_id}")
    if failed:
        print(f"\nFailed uploads ({len(failed)}):")
        for name in failed:
            print(f"  - {name}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload podcast transcripts to a fresh NotebookLM notebook."
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML (default: config.yaml)",
    )
    parser.add_argument(
        "--folder",
        default=None,
        help=(
            "Run folder name, e.g. 20260218-20260225. "
            "Defaults to the current lookback window defined in config."
        ),
    )
    args = parser.parse_args()

    config = load_config(args.config)
    folder_name = args.folder or default_folder_name(int(config.get("lookback_days", 7)))

    print(f"Run folder: {folder_name}\n")
    run(config, folder_name)


if __name__ == "__main__":
    main()
