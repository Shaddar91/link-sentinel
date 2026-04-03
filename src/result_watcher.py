"""Watch for completed analysis/summary results and deliver via Telegram."""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import structlog

from .pdf_generator import markdown_to_pdf

log = structlog.get_logger()

TRACKING_DIR = Path(__file__).parent.parent / "data" / "tracking"
MAX_MSG_LEN = 4000


def track_task(
    chat_id: int,
    message_id: int,
    task_type: str,
    result_path: Path,
    label: str,
    delivery_format: str = "msg",
) -> None:
    """Save a tracking record with delivery preference."""
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "chat_id": chat_id,
        "message_id": message_id,
        "task_type": task_type,
        "result_path": str(result_path),
        "label": label,
        "delivery_format": delivery_format,
        "created": datetime.now().timestamp(),
    }

    safe_label = label.replace("/", "_")
    filename = f"{task_type}_{safe_label}_{chat_id}.json"
    (TRACKING_DIR / filename).write_text(json.dumps(record, indent=2))
    log.info("task_tracked", filename=filename, delivery=delivery_format)


def split_message(text: str, max_len: int = MAX_MSG_LEN) -> list[str]:
    """Split text into chunks that fit Telegram's message limit."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    remaining = text

    while remaining:
        if len(remaining) <= max_len:
            chunks.append(remaining)
            break

        cut = remaining[:max_len].rfind("\n\n")
        if cut > max_len // 2:
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip("\n")
            continue

        cut = remaining[:max_len].rfind("\n")
        if cut > max_len // 2:
            chunks.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip("\n")
            continue

        chunks.append(remaining[:max_len])
        remaining = remaining[max_len:]

    return chunks


def _strip_md(text: str) -> str:
    """Strip markdown formatting to plain text."""
    import re
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    return text


def _md_to_plain(content: str) -> str:
    """Convert full markdown to clean plain text."""
    import re
    lines = []
    in_code = False

    for line in content.split("\n"):
        s = line.strip()

        if s.startswith("```"):
            in_code = not in_code
            continue

        if in_code:
            lines.append(f"    {line.rstrip()}")
            continue

        if s.startswith("# "):
            lines.append("")
            lines.append(s[2:].upper())
            lines.append("=" * len(s[2:]))
        elif s.startswith("## "):
            lines.append("")
            lines.append(s[3:])
            lines.append("-" * len(s[3:]))
        elif s.startswith("### "):
            lines.append("")
            lines.append(s[4:])
        elif s.startswith("- ") or s.startswith("* "):
            lines.append(f"  - {_strip_md(s[2:])}")
        elif s.startswith("  - ") or s.startswith("  * "):
            lines.append(f"    - {_strip_md(s[4:])}")
        elif s == "---":
            lines.append("")
            lines.append("-" * 60)
            lines.append("")
        elif s == "":
            lines.append("")
        else:
            lines.append(_strip_md(s))

    return "\n".join(lines)


def _textwrap_lines(text: str, max_chars: int = 90) -> str:
    """Wrap long lines to max_chars, preserving short lines and indentation."""
    import textwrap
    result = []
    for line in text.split("\n"):
        if len(line) <= max_chars:
            result.append(line)
        else:
            indent = len(line) - len(line.lstrip())
            prefix = line[:indent]
            wrapped = textwrap.fill(
                line.strip(), width=max_chars,
                initial_indent=prefix, subsequent_indent=prefix + "  ",
            )
            result.append(wrapped)
    return "\n".join(result)


async def check_results(bot_app) -> None:
    """Background loop — auto-delivers results in the format the user chose upfront."""
    while True:
        await asyncio.sleep(30)

        if not TRACKING_DIR.exists():
            continue

        for track_file in list(TRACKING_DIR.glob("*.json")):
            try:
                record = json.loads(track_file.read_text())
                result_path = Path(record["result_path"])
                task_created = record["created"]

                if not result_path.exists():
                    continue

                file_mtime = os.path.getmtime(result_path)
                if file_mtime < task_created:
                    continue

                content = result_path.read_text().strip()
                if not content:
                    continue

                chat_id = record["chat_id"]
                label = record["label"]
                delivery = record.get("delivery_format", "msg")

                if delivery == "pdf":
                    task_type = record.get("task_type", "repo_analysis")
                    template = "video_summary" if task_type == "video_summary" else "repo_analysis"
                    pdf_path = await markdown_to_pdf(content, label, template=template)
                    await bot_app.bot.send_document(
                        chat_id=chat_id,
                        document=open(pdf_path, "rb"),
                        filename=f"{label.replace('/', '_')}_analysis.pdf",
                        caption=f"Analysis: {label}",
                    )
                    log.info("result_sent_pdf", chat_id=chat_id, label=label)

                else:
                    header = f"Result: {label}\n{'='*30}\n\n"
                    full_text = header + content
                    chunks = split_message(full_text)
                    total = len(chunks)

                    for i, chunk in enumerate(chunks):
                        if total > 1 and i > 0:
                            chunk = f"[{i+1}/{total}]\n{chunk}"
                        await bot_app.bot.send_message(chat_id=chat_id, text=chunk)
                        if i < total - 1:
                            await asyncio.sleep(0.5)

                    log.info("result_sent_msg", chat_id=chat_id, label=label, parts=total)

                track_file.unlink()

            except Exception as e:
                log.error("result_check_failed", file=str(track_file), error=str(e))
