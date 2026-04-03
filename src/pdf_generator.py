"""Generate PDFs via Gotenberg (Chromium HTML→PDF)."""
import os
from datetime import datetime
from pathlib import Path

import httpx
import mistune
import structlog

log = structlog.get_logger()

GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://gotenberg:3000")
PDF_DIR = Path(__file__).parent.parent / "data" / "pdfs"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> str:
    """Load an HTML template and inject the shared CSS."""
    css = (TEMPLATES_DIR / "style.css").read_text()
    html = (TEMPLATES_DIR / f"{name}.html").read_text()
    return html.replace("{{css}}", css)


def _render_html(content: str, template: str, metadata: dict[str, str]) -> str:
    """Convert markdown content to full HTML document via template."""
    md = mistune.create_markdown(
        plugins=["table", "strikethrough", "url"],
    )
    html_body = md(content)

    html = _load_template(template)
    html = html.replace("{{content}}", html_body)
    html = html.replace("{{analysis_date}}", datetime.now().strftime("%Y-%m-%d"))

    for key, value in metadata.items():
        html = html.replace(f"{{{{{key}}}}}", value)

    return html


async def markdown_to_pdf(
    content: str,
    label: str,
    template: str = "repo_analysis",
    metadata: dict[str, str] | None = None,
) -> Path:
    """Convert markdown content to styled PDF via Gotenberg.

    Args:
        content: Markdown text to render.
        label: Used for filename and header (e.g. "owner/repo").
        template: Template name — "repo_analysis" or "video_summary".
        metadata: Extra template variables (e.g. repo_name, video_title, video_url).
    """
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    if metadata is None:
        metadata = {}

    #Set default template variables from label
    if template == "repo_analysis":
        metadata.setdefault("repo_name", label)
    elif template == "video_summary":
        metadata.setdefault("video_title", label)
        metadata.setdefault("video_url", "")

    html = _render_html(content, template, metadata)
    footer_html = (TEMPLATES_DIR / "footer.html").read_text()

    safe_label = label.replace("/", "_").replace(" ", "_")[:80]
    filepath = PDF_DIR / f"{safe_label}.pdf"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{GOTENBERG_URL}/forms/chromium/convert/html",
                files={
                    "files": ("index.html", html.encode("utf-8"), "text/html"),
                    "footer": ("footer.html", footer_html.encode("utf-8"), "text/html"),
                },
                data={
                    "paperWidth": "8.27",
                    "paperHeight": "11.7",
                    "marginTop": "0.5",
                    "marginBottom": "0.75",
                    "marginLeft": "0.5",
                    "marginRight": "0.5",
                    "printBackground": "true",
                    "emulatedMediaType": "screen",
                    "generateDocumentOutline": "true",
                },
            )
            resp.raise_for_status()

        filepath.write_bytes(resp.content)
        log.info("pdf_generated", path=str(filepath), size=len(resp.content))
        return filepath

    except httpx.ConnectError:
        log.error("gotenberg_unavailable", url=GOTENBERG_URL)
        raise RuntimeError(f"Gotenberg is not reachable at {GOTENBERG_URL}")
    except httpx.HTTPStatusError as exc:
        log.error("gotenberg_error", status=exc.response.status_code)
        raise RuntimeError(f"Gotenberg returned {exc.response.status_code}")
