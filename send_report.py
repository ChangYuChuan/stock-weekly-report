from __future__ import annotations
"""
send_report.py

Stage 4: Generate a weekly insight report from a NotebookLM notebook
and email it to the configured recipient.

Steps:
  1. Run `nlm report create` to create a Briefing Doc inside the notebook
  2. Run `nlm query notebook` to capture a text summary for the email body
  3. Send the summary + notebook link via SMTP

SMTP password is read from the EMAIL_SMTP_PASSWORD environment variable.
If not set, it falls back to smtp_password in config.yaml (not recommended
for production — prefer the env var so credentials stay out of the repo).

Usage (standalone):
  python send_report.py --notebook-id <id>
  python send_report.py --notebook-id <id> --folder 20260218-20260225
  python send_report.py --config my_config.yaml --notebook-id <id>
"""

import argparse
import json
import os
import smtplib
import subprocess
import sys
import yaml
import markdown as md
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# A meaningful weekly summary should comfortably exceed this.
# If NotebookLM returns less, something went wrong and we should not send it.
MIN_REPORT_CHARS = 5_000

# ---------------------------------------------------------------------------
# Report sections — each is queried independently so we are not limited
# by a single response's length cap.
# ---------------------------------------------------------------------------
REPORT_SECTIONS = [
    (
        "一、宏觀經濟與全球市場總覽",
        (
            "請用繁體中文，針對本週各 Podcast 節目中涉及的所有宏觀經濟議題，"
            "提供極為詳盡的深度分析報告。\n\n"
            "請完整涵蓋節目中討論到的每一個總體經濟主題，每個子項目須充分展開，"
            "引用節目中提到的具體數字、數據、預測與主持人觀點，不要省略細節。\n\n"
            "分析架構建議（依節目實際內容靈活調整）：\n"
            "1. 主要央行貨幣政策動向與市場預期\n"
            "2. 貿易政策、關稅或政府政策對市場的影響\n"
            "3. 全球與區域主要股市的表現與資金流向\n"
            "4. 地緣政治風險與對資本市場的潛在衝擊\n"
            "5. 匯率走勢、原物料與大宗商品動態\n"
            "6. 景氣週期判斷與中長期總體展望\n\n"
            "目標：讓讀者讀完後對本週總體經濟環境有完整且深入的理解。"
        ),
    ),
    (
        "二、個股與產業深度分析",
        (
            "請用繁體中文，將本週各 Podcast 節目中提到的所有個股與產業，"
            "進行逐一深度分析，不要遺漏任何一支個股或產業群組。\n\n"
            "【重要】台股與美股個股皆須完整納入分析。"
            "節目中提到的所有美股（例如 NVDA、AAPL、TSLA、META 等）必須與台股同等對待，不得遺漏。\n\n"
            "每支個股或每個子產業的分析須充分展開，包含：\n"
            "- 節目討論的基本面現況與數據（營收、獲利、EPS 預估、本益比、目標價等）\n"
            "- 產業趨勢與競爭格局\n"
            "- 主持人或來賓的投資觀點、評等與操作建議\n"
            "- 【重點】主持人推薦或看好該股的完整投資邏輯：\n"
            "    * 他/她為什麼看好或看壞這支股票？核心理由是什麼？\n"
            "    * 背後的思考框架與分析方法（例如：用本益比、產業趨勢、護城河、供需缺口等角度）\n"
            "    * 是什麼觸發他/她現在討論這支股票？有何時機判斷？\n"
            "    * 他/她預期的股價催化劑或關鍵轉折點為何？\n"
            "    * 他/她設定的停損或出場條件是什麼？\n"
            "- 潛在上行催化劑與下行風險\n\n"
            "請先依市場分組（台股 / 美股 / 其他），再依產業類別分組（例如：科技、半導體、能源、金融、傳統產業等），"
            "每個類別下再逐一展開個股分析。\n\n"
            "目標：讀者不只知道主持人推薦什麼，更能完全理解他/她為什麼這樣想、怎麼想到的。"
        ),
    ),
    (
        "三、各節目逐集完整內容摘要",
        (
            "請用繁體中文，對本週收錄的每一集 Podcast，"
            "逐集提供完整且詳盡的內容摘要。\n\n"
            "每集摘要須達到足夠深度，讓完全沒有收聽的讀者也能完整掌握該集所有重點。"
            "每集至少涵蓋：\n"
            "1. 本集核心主題與主持人的開場論點\n"
            "2. 主要觀點與完整論述邏輯（詳細展開，不要壓縮或跳過論述過程）\n"
            "3. 節目中引用的具體數字、案例、研究或歷史背景\n"
            "4. 【重點】主持人的投資思維與決策邏輯：\n"
            "    * 他/她是如何分析問題、得出結論的？思考路徑是什麼？\n"
            "    * 他/她看事情的獨特視角或框架（例如：總經驅動、籌碼面、產業趨勢、價值投資等）\n"
            "    * 他/她為何在此時提出這個觀點？背後的時機判斷是什麼？\n"
            "    * 他/她對市場共識的看法：是順勢還是逆勢思考？\n"
            "5. 對投資人的明確建議、操作策略或風險提示\n"
            "6. 本集中最值得關注的獨特見解或預測\n\n"
            "請在每集標題標明節目名稱與播出日期，並依播出時間順序排列。"
        ),
    ),
    (
        "四、投資策略總結與關鍵風險提示",
        (
            "請用繁體中文，綜合本週所有 Podcast 節目的觀點，"
            "提供完整的投資策略總結與風險分析。\n\n"
            "每個子項目須充分展開，給出具體且有深度的分析：\n"
            "1. 本週整體市場情緒判斷：多頭 / 空頭 / 震盪？各節目觀點是否一致或存在分歧？\n"
            "2. 【重點】各主持人的投資哲學與風格比較：\n"
            "    * 不同主持人面對相同市場環境時，思考角度有何不同？\n"
            "    * 誰偏向保守、誰偏向積極？各自的理由是什麼？\n"
            "    * 本週各節目的觀點在哪些地方不謀而合、在哪些地方出現分歧？分歧的根本原因是什麼？\n"
            "3. 短線操作方向（近一個月）：節目中提到哪些近期布局機會與進出場條件？\n"
            "4. 中線趨勢布局（三至六個月）：哪些趨勢值得中線持有？論述依據為何？\n"
            "5. 長線核心配置邏輯（一年以上）：哪些產業或資產被視為長期結構性機會？\n"
            "6. 需特別警惕的風險因子：節目中提到的黑天鵝、政策風險、估值風險或流動性風險\n"
            "7. 未來需持續追蹤的關鍵指標與事件：哪些數據或消息面將左右後市？\n"
            "8. 資產配置建議：節目中對股票、債券、黃金、現金的配置有何觀點？"
        ),
    ),
    (
        "五、本週個股推薦總表",
        (
            "請用繁體中文，將本週所有 Podcast 節目中提到的個股或投資標的，"
            "整理成一份結構化的 Markdown 表格，格式如下：\n\n"
            "| 股票代號／名稱 | 市場 | 推薦方向 | 推薦理由（投資邏輯） | 推薦人／節目 |\n"
            "|---|---|---|---|---|\n\n"
            "欄位說明：\n"
            "- 股票代號／名稱：台股填代號加公司名稱（例如：2330 台積電）；"
            "美股填英文代號加中文名稱（例如：NVDA 輝達、AAPL 蘋果、TSLA 特斯拉）\n"
            "- 市場：台股 🇹🇼 / 美股 🇺🇸 / 其他\n"
            "- 推薦方向：看多 📈 / 看空 📉 / 觀察 👀\n"
            "- 推薦理由（投資邏輯）：主持人推薦的核心理由，"
            "說明他/她為什麼看好或看壞，以及背後的思考邏輯，盡量詳細（至少 50 字）\n"
            "- 推薦人／節目：哪個節目的哪位主持人提出\n\n"
            "【重要】台股與美股皆須列入，不得遺漏任何一支節目中提及的美股標的。"
            "若同一支股票被多個節目提及，請分開列出各自的觀點。"
        ),
    ),
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# nlm helpers
# ---------------------------------------------------------------------------

def _run_nlm(nlm_path: str, *args: str) -> subprocess.CompletedProcess:
    cmd = [nlm_path, *args]
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        raise RuntimeError(
            f"nlm command failed (exit {result.returncode}): {stderr or '(no stderr)'}"
        )
    return result


def create_briefing_doc(nlm_path: str, notebook_id: str, language: str = "zh-TW") -> None:
    """Ask NotebookLM to generate a Briefing Doc studio artifact."""
    try:
        _run_nlm(
            nlm_path,
            "report", "create", notebook_id,
            "--format", "Briefing Doc",
            "--language", language,
            "--confirm",
        )
        print("  Briefing Doc created in NotebookLM.")
    except RuntimeError as exc:
        # Non-fatal: the email can still be sent even if this fails
        print(f"  WARNING: Could not create Briefing Doc: {exc}")


def query_notebook(nlm_path: str, notebook_id: str, question: str) -> str:
    """Send a question to the notebook and return the text response."""
    result = _run_nlm(nlm_path, "query", "notebook", notebook_id, question)
    raw = result.stdout.strip()
    # nlm returns a JSON envelope: {"value": {"answer": "...", ...}}
    # Extract just the markdown answer text.
    try:
        data = json.loads(raw)
        answer = (
            data.get("value", {}).get("answer")
            or data.get("answer")
            or raw
        )
        return answer.strip()
    except (json.JSONDecodeError, AttributeError):
        return raw


def query_all_sections(nlm_path: str, notebook_id: str) -> str:
    """Run each report section query independently and combine into one document."""
    parts = []
    for idx, (title, question) in enumerate(REPORT_SECTIONS, start=1):
        print(f"  [{idx}/{len(REPORT_SECTIONS)}] Querying: {title} …")
        try:
            answer = query_notebook(nlm_path, notebook_id, question)
        except RuntimeError as exc:
            print(f"    WARNING: query failed — {exc}")
            answer = "（此章節查詢失敗，請直接開啟 NotebookLM 筆記本查看。）"
        parts.append(f"## {title}\n\n{answer}")
        print(f"    → {len(answer):,} chars")
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Email helpers
# ---------------------------------------------------------------------------

def _format_date_range(folder_name: str) -> str:
    """Turn '20260218-20260225' into '2026/02/18 – 2026/02/25'."""
    try:
        start, end = folder_name.split("-")
        return f"{start[:4]}/{start[4:6]}/{start[6:]} – {end[:4]}/{end[4:6]}/{end[6:]}"
    except Exception:
        return folder_name


def build_email_body(folder_name: str, notebook_id: str, summary: str) -> str:
    """Return the plain-text version of the report (saved to disk)."""
    notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
    lines = [
        summary,
        "",
        "-" * 60,
        f"完整 NotebookLM 筆記本：{notebook_url}",
        "",
        "（本郵件由 stock-weekly-report 自動生成）",
    ]
    return "\n".join(lines)


def build_html_email(folder_name: str, notebook_id: str, summary: str) -> str:
    """Render the summary markdown into a styled HTML email."""
    notebook_url = f"https://notebooklm.google.com/notebook/{notebook_id}"
    date_range = _format_date_range(folder_name)
    content_html = md.markdown(summary, extensions=["extra", "tables"])

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue",
                 Arial, "PingFang TC", "Microsoft JhengHei", sans-serif;
    background: #f4f6f9;
    margin: 0; padding: 0;
    color: #1a1a2e;
  }}
  .wrapper {{
    max-width: 720px;
    margin: 32px auto;
    background: #ffffff;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  }}
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    color: #ffffff;
    padding: 36px 40px 28px;
  }}
  .header h1 {{
    margin: 0 0 6px;
    font-size: 24px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }}
  .header .date {{
    font-size: 14px;
    opacity: 0.7;
    margin: 0;
  }}
  .content {{
    padding: 36px 40px;
    line-height: 1.8;
    font-size: 15px;
  }}
  .content h3 {{
    font-size: 17px;
    font-weight: 700;
    color: #0f3460;
    border-left: 4px solid #e94560;
    padding-left: 12px;
    margin: 28px 0 14px;
  }}
  .content ul {{
    padding-left: 20px;
    margin: 8px 0 16px;
  }}
  .content li {{
    margin-bottom: 8px;
  }}
  .content ul ul {{
    margin: 6px 0 6px;
  }}
  .content strong {{
    color: #0f3460;
  }}
  .content hr {{
    border: none;
    border-top: 1px solid #e8ecf0;
    margin: 28px 0;
  }}
  .content table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 24px;
    font-size: 14px;
  }}
  .content th {{
    background: #0f3460;
    color: #ffffff;
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
  }}
  .content td {{
    padding: 10px 14px;
    border-bottom: 1px solid #e8ecf0;
    vertical-align: top;
  }}
  .content tr:nth-child(even) td {{
    background: #f8f9fc;
  }}
  .cta {{
    margin: 32px 0 8px;
    text-align: center;
  }}
  .cta a {{
    display: inline-block;
    background: #e94560;
    color: #ffffff;
    text-decoration: none;
    padding: 13px 32px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 15px;
    letter-spacing: 0.3px;
  }}
  .footer {{
    background: #f4f6f9;
    text-align: center;
    padding: 20px 40px;
    font-size: 12px;
    color: #999;
    border-top: 1px solid #e8ecf0;
  }}
</style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>📈 股市週報</h1>
      <p class="date">{date_range}</p>
    </div>
    <div class="content">
      {content_html}
      <div class="cta">
        <a href="{notebook_url}">開啟 NotebookLM 筆記本 →</a>
      </div>
    </div>
    <div class="footer">
      本郵件由 stock-weekly-report 自動生成
    </div>
  </div>
</body>
</html>"""


def send_email(config: dict, subject: str, plain_body: str, html_body: str) -> None:
    email_cfg = config.get("email", {})
    if not email_cfg:
        raise RuntimeError("No 'email' section found in config.yaml.")

    # Support email.to as either a string or a list of strings
    to_raw    = email_cfg["to"]
    to_list   = to_raw if isinstance(to_raw, list) else [to_raw]
    to_header = ", ".join(to_list)

    from_addr = email_cfg["from"]
    smtp_host = email_cfg.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(email_cfg.get("smtp_port", 587))
    smtp_user = email_cfg.get("smtp_user", from_addr)

    # Prefer env var; fall back to config value (empty string → error)
    smtp_password = os.environ.get("EMAIL_SMTP_PASSWORD") or email_cfg.get("smtp_password", "")
    if not smtp_password:
        raise RuntimeError(
            "SMTP password not set.\n"
            "  Export EMAIL_SMTP_PASSWORD=<your-app-password>\n"
            "  or set smtp_password in config.yaml."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_header
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body,  "html",  "utf-8"))

    print(f"  Sending to {to_header} via {smtp_host}:{smtp_port} …")
    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.sendmail(from_addr, to_list, msg.as_string())
    print("  Email sent.")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def validate_report(summary: str) -> None:
    """Raise RuntimeError if the report summary looks malformed or too short."""
    stripped = summary.strip()
    if not stripped:
        raise RuntimeError("Report summary is empty — not sending email.")
    if len(stripped) < MIN_REPORT_CHARS:
        raise RuntimeError(
            f"Report summary is suspiciously short ({len(stripped)} chars < {MIN_REPORT_CHARS}). "
            "NotebookLM may not have processed the sources yet. Not sending email."
        )


def save_report(config: dict, folder_name: str, body: str) -> Path:
    """Save the report text to disk and return the file path."""
    report_dir = Path(config["parent_folder"]) / "reports" / folder_name
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"weekly_report_{folder_name}.txt"
    report_path.write_text(body, encoding="utf-8")
    print(f"  Report saved to: {report_path}")
    return report_path


def run(config: dict, folder_name: str, notebook_id: str, send_email_flag: bool = True) -> None:
    nlm_path        = config.get("nlm_path", "nlm")
    notebook_prefix = config.get("notebooklm_notebook_prefix", "股市週報")
    date_range      = _format_date_range(folder_name)

    # Step 1: Create a Briefing Doc artifact inside NotebookLM
    print("Generating Briefing Doc in NotebookLM …")
    create_briefing_doc(nlm_path, notebook_id, language="zh-TW")

    # Step 2: Query the notebook section by section for a deep, detailed report
    print(f"\nQuerying notebook ({len(REPORT_SECTIONS)} sections) …")
    summary = query_all_sections(nlm_path, notebook_id)

    if not summary:
        summary = (
            "（NotebookLM 未返回摘要，請直接開啟筆記本查看。）\n"
            f"https://notebooklm.google.com/notebook/{notebook_id}"
        )

    # Step 3: Validate report before doing anything with it
    print("\nValidating report …")
    validate_report(summary)
    print(f"  ✓ Report looks good ({len(summary.strip())} chars).")

    subject    = f"{notebook_prefix}｜{date_range}"
    plain_body = build_email_body(folder_name, notebook_id, summary)
    html_body  = build_html_email(folder_name, notebook_id, summary)

    # Step 4: Save report to disk
    print("\nSaving report …")
    save_report(config, folder_name, plain_body)

    # Step 5: Send the email (skipped when save_email_flag=False)
    if send_email_flag:
        print("\nSending email report …")
        send_email(config, subject, plain_body, html_body)
    else:
        print("\nEmail sending skipped (save-report-only mode).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a NotebookLM report and email it."
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Path to config YAML (default: config.yaml)")
    parser.add_argument("--notebook-id", required=True,
                        help="NotebookLM notebook ID to query and report on.")
    parser.add_argument("--folder", default=None,
                        help="Run folder name, e.g. 20260218-20260225.")
    args = parser.parse_args()

    config      = load_config(args.config)
    folder_name = args.folder or "unknown"

    run(config, folder_name, args.notebook_id)


if __name__ == "__main__":
    main()
