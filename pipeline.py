"""
pipeline.py

Master pipeline: fetch → transcribe → upload to NotebookLM.

All three stages share the same config and run folder so output
paths are always consistent.

Usage:
  python pipeline.py                              # full run, auto date range
  python pipeline.py --folder 20260218-20260225   # target a specific week
  python pipeline.py --skip-upload                # fetch + transcribe only
  python pipeline.py --skip-fetch --skip-transcribe  # upload only (re-run)
  python pipeline.py --config my_config.yaml

Note: the upload stage always creates a FRESH notebook, deleting any stale
notebook with the same title first. This prevents old cached content from
bleeding into a new week's output.
"""

import argparse
import sys
import time
import traceback
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def default_folder_name(lookback_days: int) -> str:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=lookback_days)
    return f"{start.strftime('%Y%m%d')}-{today.strftime('%Y%m%d')}"


def banner(title: str) -> None:
    width = 60
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def elapsed(start: float) -> str:
    secs = int(time.time() - start)
    m, s = divmod(secs, 60)
    return f"{m}m {s}s" if m else f"{s}s"


# ---------------------------------------------------------------------------
# Stage runners
# ---------------------------------------------------------------------------

def run_fetch(config: dict, folder_name: str) -> bool:
    import fetch_episodes
    banner("STAGE 1 / 3 — Fetch & Download Episodes")
    t = time.time()
    try:
        fetch_episodes.fetch_and_download(config, folder_name=folder_name)
        print(f"\n[fetch] Done in {elapsed(t)}")
        return True
    except Exception:
        print("\n[fetch] FAILED:")
        traceback.print_exc()
        return False


def run_transcribe(config: dict, folder_name: str) -> bool | str:
    """Returns True (all OK), 'partial' (some failed verification), or False (crashed)."""
    import transcribe
    banner("STAGE 2 / 3 — Transcribe Audio")
    t = time.time()
    try:
        transcribe.transcribe_folder(config, folder_name)
        print(f"\n[transcribe] Done in {elapsed(t)}")
        return True
    except SystemExit as exc:
        print(f"\n[transcribe] Done in {elapsed(t)}")
        if exc.code == 2:
            # exit code 2 = verification found some failures, but not a crash
            return "partial"
        return False
    except Exception:
        print("\n[transcribe] FAILED:")
        traceback.print_exc()
        return False


def run_upload(config: dict, folder_name: str) -> bool:
    import upload_to_notebooklm
    banner("STAGE 3 / 3 — Upload Transcripts to NotebookLM")
    t = time.time()
    try:
        upload_to_notebooklm.run(config, folder_name)
        print(f"\n[upload] Done in {elapsed(t)}")
        return True
    except SystemExit as exc:
        # upload_to_notebooklm calls sys.exit on auth failure — treat as error
        print(f"\n[upload] FAILED (exit {exc.code})")
        return False
    except Exception:
        print("\n[upload] FAILED:")
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end podcast pipeline: fetch → transcribe → NotebookLM upload."
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config YAML (default: config.yaml)")
    parser.add_argument("--folder", default=None,
                        help="Run folder, e.g. 20260218-20260225. Defaults to the current lookback window.")
    parser.add_argument("--skip-fetch", action="store_true",
                        help="Skip the fetch/download stage.")
    parser.add_argument("--skip-transcribe", action="store_true",
                        help="Skip the transcription stage.")
    parser.add_argument("--skip-upload", action="store_true",
                        help="Skip the NotebookLM upload stage.")
    args = parser.parse_args()

    config = load_config(args.config)
    folder_name = args.folder or default_folder_name(int(config.get("lookback_days", 7)))

    pipeline_start = time.time()

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           Stock Weekly Report — Pipeline                 ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print(f"  Config     : {args.config}")
    print(f"  Run folder : {folder_name}")
    print(f"  Stages     : "
          + ("fetch " if not args.skip_fetch else "")
          + ("transcribe " if not args.skip_transcribe else "")
          + ("upload" if not args.skip_upload else ""))

    results: dict[str, bool | str] = {}

    # ── Stage 1: Fetch ──────────────────────────────────────────────
    if not args.skip_fetch:
        ok = run_fetch(config, folder_name)
        results["fetch"] = ok
        if not ok:
            print("\nPipeline aborted after fetch failure.")
            _print_summary(results, pipeline_start)
            sys.exit(1)
    else:
        results["fetch"] = "skipped"

    # ── Stage 2: Transcribe ─────────────────────────────────────────
    if not args.skip_transcribe:
        ok = run_transcribe(config, folder_name)
        results["transcribe"] = ok
        if not ok:
            print("\nPipeline aborted after transcribe failure.")
            _print_summary(results, pipeline_start)
            sys.exit(1)
    else:
        results["transcribe"] = "skipped"

    # ── Stage 3: Upload ─────────────────────────────────────────────
    if not args.skip_upload:
        ok = run_upload(config, folder_name)
        results["upload"] = ok
    else:
        results["upload"] = "skipped"

    _print_summary(results, pipeline_start)
    if results.get("upload") is False:
        sys.exit(1)


def _print_summary(results: dict, start: float) -> None:
    banner("Pipeline Summary")
    icons = {True: "✓", False: "✗", "skipped": "–"}
    for stage, status in results.items():
        icon = icons.get(status, "?")
        label = "OK" if status is True else ("FAILED" if status is False else "skipped")
        print(f"  {icon}  {stage:<12} {label}")
    print(f"\n  Total time: {elapsed(start)}")
    print()


if __name__ == "__main__":
    main()
