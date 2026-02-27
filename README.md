# stock-weekly-report

By [Chang Yu Chuan](https://github.com/ChangYuChuan)

Automated pipeline that fetches Taiwanese stock podcast episodes, transcribes them with Whisper, uploads to NotebookLM, and emails a structured weekly investment report.

---

## Installation

### Via npm (recommended)

```bash
npm install -g stock-weekly-report
```

`postinstall` automatically finds Python 3.10+ on your system and creates the `venv14/` environment. After that, `swr` and `swr-mcp` are available globally.

Then set up the pipeline venv (needed for actual transcription runs):

```bash
cd $(npm root -g)/stock-weekly-report
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```

Finally run the setup wizard:
```bash
swr init
```

---

## Manual Setup

### 1. Prerequisites

- Python 3.9+ (pipeline) and Python 3.10+ (CLI/MCP — Homebrew `python3.14` recommended)
- [nlm](https://github.com/OpenClaw-AI/notebooklm-mcp-cli) binary (`~/.openclaw/workspace/venv/bin/nlm`)
- Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)

### 2. Pipeline venv (Python 3.9)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. CLI + MCP venv (Python 3.10+)

```bash
/opt/homebrew/bin/python3.14 -m venv venv14
venv14/bin/pip install -e .
```

This installs two entry points:
- `venv14/bin/swr` — the CLI
- `venv14/bin/swr-mcp` — the MCP server

Optionally add `venv14/bin` to your `PATH`:
```bash
echo 'export PATH="/path/to/stock-weekly-report/venv14/bin:$PATH"' >> ~/.zprofile
```

### 4. First-time configuration

```bash
swr init
```

The wizard prompts for data folder, nlm path, Gmail app password, sender/recipient emails, and retention periods. It writes `config.yaml` (git-ignored) and optionally installs the cron job.

To start from a template instead:
```bash
cp config.yaml.example config.yaml
# edit config.yaml, then export EMAIL_SMTP_PASSWORD in ~/.zprofile
```

---

## CLI reference

```
swr [--config PATH]
├── init                     Interactive setup wizard
├── run                      Run the pipeline
│     --skip-fetch           Skip podcast download
│     --skip-transcribe      Skip Whisper transcription
│     --skip-upload          Skip NotebookLM upload
│     --skip-email           Skip report generation entirely
│     --skip-cleanup         Skip data cleanup
│     --save-report-only     Generate report but don't send email
│     --folder FOLDER        e.g. 20260218-20260225
│     --notebook-id ID       Reuse an existing notebook (skips upload)
│
├── podcast
│   ├── list                 List configured feeds
│   ├── add NAME URL         Add a feed
│   └── remove NAME          Remove a feed
│
├── receiver
│   ├── list                 List configured recipients
│   ├── add EMAIL            Add a recipient
│   └── remove EMAIL         Remove a recipient
│
├── cron
│   ├── install [--schedule EXPR]   Install (or update) the cron job
│   ├── remove                      Remove the cron job
│   └── status                      Show cron job status
│
├── config
│   ├── show                 Display current config (passwords redacted)
│   └── set KEY VALUE        Set a value (e.g. retention.audio_months 6)
│
└── mcp                      Start the MCP server (stdio transport)
```

### Common examples

```bash
# Full pipeline run
swr run

# Skip fetch + transcribe, reuse existing notebook, only send email
swr run --skip-fetch --skip-transcribe --notebook-id e08a19e4-b8b7-48dc-88d6-2f2393239c36

# Generate and save report locally without sending email
swr run --skip-fetch --skip-transcribe --notebook-id <id> --save-report-only

# Manage feeds
swr podcast list
swr podcast add "新節目" https://example.com/feed.xml
swr podcast remove "新節目"

# Manage recipients
swr receiver list
swr receiver add colleague@example.com
swr receiver remove colleague@example.com

# Cron job — install on Sundays at 8 AM
swr cron install
swr cron install --schedule "0 9 * * 0"   # Sundays at 9 AM
swr cron status
swr cron remove

# Config
swr config show
swr config set retention.audio_months 6
swr config set retention.transcripts_months 3
```

---

## Retention

By default, audio files older than 3 months are deleted. Transcripts and reports are kept forever. Adjust in config:

```yaml
retention:
  audio_months: 3         # 0 = keep forever
  transcripts_months: 6   # 0 = keep forever
  reports_months: 12      # 0 = keep forever
```

Or via CLI:
```bash
swr config set retention.audio_months 6
```

---

## MCP server

The MCP server exposes four tools for use with Claude Desktop or any MCP client:

| Tool | Description |
|---|---|
| `run_pipeline` | Run the pipeline (with stage selection, save-only mode) |
| `get_report` | Read a saved report (defaults to latest) |
| `list_reports` | List all available report folders |
| `get_logs` | Tail the pipeline log |

### Claude Desktop integration

If installed via npm:
```json
{
  "mcpServers": {
    "stock-weekly-report": {
      "command": "swr-mcp"
    }
  }
}
```

If installed manually:
```json
{
  "mcpServers": {
    "stock-weekly-report": {
      "command": "/Users/yuchuan/Projects/stock-weekly-report/venv14/bin/swr-mcp"
    }
  }
}
```

Start the server manually for testing:
```bash
swr mcp
# or
venv14/bin/swr-mcp
```

---

## Cron job

The cron job calls `run.sh`, which sources `~/.zprofile` (for `EMAIL_SMTP_PASSWORD`) and logs output to `logs/pipeline.log`.

```bash
swr cron install                          # Sundays at 8 AM (default)
swr cron install --schedule "0 9 * * 0"  # Sundays at 9 AM
```

---

## Project structure

```
stock-weekly-report/
├── pipeline.py           # Orchestrates all stages
├── fetch_episodes.py     # Stage 1: download podcast episodes
├── transcribe.py         # Stage 2: Whisper transcription
├── upload_to_notebooklm.py  # Stage 3: NotebookLM upload
├── send_report.py        # Stage 4: report generation + email
├── cli.py                # swr CLI (click)
├── mcp_server.py         # MCP server (FastMCP)
├── config_manager.py     # Atomic config read/write helper
├── run.sh                # Shell wrapper (sources ~/.zprofile, logs to file)
├── config.yaml           # Your config (git-ignored, create with `swr init`)
├── config.yaml.example   # Template
├── pyproject.toml        # Entry point declarations
├── requirements.txt      # Pipeline dependencies
├── venv/                 # Python 3.9 venv (pipeline + transcription)
└── venv14/               # Python 3.14 venv (CLI + MCP server)
```
