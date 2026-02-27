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
- Gmail account with an [App Password](https://support.google.com/accounts/answer/185833)
- `nlm` — installed automatically by `postinstall` into `~/.config/swr/venv/bin/nlm`

### 2. Pipeline venv (Python 3.9)

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

### 3. CLI + MCP venv

The CLI venv is created automatically at `~/.config/swr/venv` during `npm install`. To set it up manually:

```bash
/opt/homebrew/bin/python3.14 -m venv ~/.config/swr/venv
~/.config/swr/venv/bin/pip install -e .
~/.config/swr/venv/bin/pip install notebooklm-mcp-cli
```

### 4. First-time configuration

```bash
swr init
```

The wizard prompts for data folder, Gmail app password, sender/recipient emails, and retention periods. It writes `~/.config/swr/config.yaml` and optionally installs the cron job.

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

## Configuration

Config is stored at `~/.config/swr/config.yaml` and is created by `swr init`. Here is a full annotated example:

```yaml
# Where to store downloaded audio, transcripts, and reports
parent_folder: /Users/yourname/stock-weekly-report/data

# Path to the project (pipeline.py + venv/)
project_root: /Users/yourname/stock-weekly-report

# Podcast RSS feeds to fetch each week
feeds:
  - name: 股癌
    url: https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml
  - name: M觀點
    url: https://feeds.soundon.fm/podcasts/b8f5a471-f4f7-4763-9678-65887beda63a.xml
  - name: 財經一路發
    url: https://feed.firstory.me/rss/user/ckuydilxj0ys508026gxkhbp4
  - name: 盧燕俐
    url: https://feeds.soundon.fm/podcasts/3066dd74-f792-49dd-a506-4c6997f2dc8c.xml

# How many days back to look for new episodes
lookback_days: 7

# Whisper transcription settings
whisper_model: medium       # tiny / base / small / medium / large / large-v3
whisper_language: zh        # language hint speeds up transcription

# NotebookLM settings
notebooklm_notebook_prefix: 股市週報
nlm_path: /Users/yourname/.config/swr/venv/bin/nlm   # auto-set by postinstall

# Email settings — use EMAIL_SMTP_PASSWORD env var for the password
email:
  to: you@example.com
  # Multiple recipients:
  # to:
  #   - you@example.com
  #   - colleague@example.com
  from: sender@gmail.com
  smtp_host: smtp.gmail.com
  smtp_port: 587
  smtp_user: sender@gmail.com
  smtp_password: ""   # leave blank; set EMAIL_SMTP_PASSWORD in ~/.zprofile instead

# Data retention (0 = keep forever)
retention:
  audio_months: 3         # delete audio older than N months
  transcripts_months: 0   # 0 = keep forever
  reports_months: 0       # 0 = keep forever
```

Set or update individual values without opening the file:

```bash
swr config set retention.audio_months 6
swr config set whisper_model large-v3
swr podcast add "新節目" https://example.com/feed.xml
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
      "command": "/Users/yourname/.config/swr/venv/bin/swr-mcp"
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
├── pipeline.py              # Orchestrates all stages
├── fetch_episodes.py        # Stage 1: download podcast episodes
├── transcribe.py            # Stage 2: Whisper transcription
├── upload_to_notebooklm.py  # Stage 3: NotebookLM upload
├── send_report.py           # Stage 4: report generation + email
├── cli.py                   # swr CLI (click)
├── mcp_server.py            # MCP server (FastMCP)
├── config_manager.py        # Atomic config read/write helper
├── run.sh                   # Shell wrapper (sources ~/.zprofile, logs to file)
├── config.yaml.example      # Config template
├── pyproject.toml           # Entry point declarations
├── requirements.txt         # Pipeline dependencies
└── venv/                    # Python 3.9 venv (pipeline + transcription)

~/.config/swr/
├── config.yaml              # Your config (created by `swr init`)
├── venv/                    # Python 3.10+ venv (CLI, MCP server, nlm)
└── venv/bin/nlm             # NotebookLM CLI (auto-installed by postinstall)
```
