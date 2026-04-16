"""Watch for completed analysis/summary results and deliver via Telegram.

Delivery is PDF-only — direct-to-chat text output was removed so that every
analysis flows through the same styled PDF pipeline regardless of content type
or depth.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import structlog

from .pdf_generator import markdown_to_pdf

log = structlog.get_logger()

TRACKING_DIR = Path(__file__).parent.parent / "data" / "tracking"


def track_task(
    chat_id: int,
    message_id: int,
    task_type: str,
    result_path: Path,
    label: str,
    analysis_depth: str = "standard",
) -> None:
    """Save a tracking record so the watcher can deliver the PDF when the result lands."""
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "chat_id": chat_id,
        "message_id": message_id,
        "task_type": task_type,
        "result_path": str(result_path),
        "label": label,
        "analysis_depth": analysis_depth,
        "created": datetime.now().timestamp(),
    }

    safe_label = label.replace("/", "_")
    filename = f"{task_type}_{safe_label}_{chat_id}.json"
    (TRACKING_DIR / filename).write_text(json.dumps(record, indent=2))
    log.info("task_tracked", filename=filename, depth=analysis_depth)


async def check_results(bot_app) -> None:
    """Background loop — delivers every completed analysis as a styled PDF."""
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
                task_type = record.get("task_type", "repo_analysis")
                depth = record.get("analysis_depth", "standard")

                template = "video_summary" if task_type == "video_summary" else "repo_analysis"
                metadata = {"analysis_depth": depth.capitalize()}
                pdf_path = await markdown_to_pdf(content, label, template=template, metadata=metadata)

                safe_label = label.replace("/", "_")
                suffix = "_detailed" if depth == "detailed" else ""
                await bot_app.bot.send_document(
                    chat_id=chat_id,
                    document=open(pdf_path, "rb"),
                    filename=f"{safe_label}{suffix}_analysis.pdf",
                    caption=f"{depth.capitalize()} analysis: {label}",
                )
                log.info("result_sent_pdf", chat_id=chat_id, label=label, depth=depth)

                track_file.unlink()

            except Exception as e:
                log.error("result_check_failed", file=str(track_file), error=str(e))
