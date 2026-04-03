#!/usr/bin/env python3
"""End-to-end PDF quality validation for Gotenberg integration.

Component 5 of link-sentinel-gotenberg-pdf-integration plan.

Tests:
  1. Markdown → HTML rendering (template injection, content fidelity)
  2. Gotenberg PDF generation (if container available)
  3. PDF quality checks (size, content)
  4. Error handling when Gotenberg is down
  5. Both repo_analysis and video_summary templates
"""
import asyncio
import os
import sys
import time
from pathlib import Path

#Add src to path so we can import link-sentinel modules
SRC_DIR = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_DIR.parent))
sys.path.insert(0, str(SRC_DIR))

import httpx
import mistune

TEMPLATES_DIR = SRC_DIR / "templates"
ANALYSIS_DIR = Path.home() / "Documents/workspace/personal/projects/github/repo-analysis/analysis-docs"
PDF_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "pdfs"
GOTENBERG_URL = os.environ.get("GOTENBERG_URL", "http://localhost:3000")

#Test markdown with ALL formatting features
RICH_MARKDOWN = """# Test Report: feature-rich-repo

**Repository:** https://github.com/test/repo
**Analyzed:** 2026-04-03

---

## 1. Overview

This is a **bold** and *italic* test with `inline code` and a [link](https://example.com).

Unicode test: ✅ ❌ 🚀 → ← é à ü ñ 日本語

## 2. Architecture

### Module System

| Module | Role | Status |
|--------|------|--------|
| api | HTTP server | ✅ Active |
| chromium | PDF render | ✅ Active |
| libreoffice | Doc convert | ⚠️ Optional |

### Data Flow

1. Client sends POST request
2. Server parses form data
3. Chromium renders HTML
4. PDF returned

## 3. Code Examples

```python
async def generate_pdf(html: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{GOTENBERG_URL}/forms/chromium/convert/html",
            files={"files": ("index.html", html.encode(), "text/html")},
        )
        return resp.content
```

```bash
docker run --rm -p 3000:3000 gotenberg/gotenberg:8
curl http://localhost:3000/health
```

## 4. Nested Lists

- Top level item
  - Sub item 1
  - Sub item 2
    - Deep nested
- Another top item
  1. Numbered sub
  2. Numbered sub 2

## 5. Blockquote

> This is a blockquote with **bold** text inside.
> It spans multiple lines.

---

## Bottom Line

Everything works. ✅
"""

PASSED = 0
FAILED = 0
WARNINGS = 0


def check(name: str, condition: bool, detail: str = "") -> bool:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✅ {name}")
        return True
    else:
        FAILED += 1
        msg = f"  ❌ {name}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        return False


def warn(name: str, detail: str = "") -> None:
    global WARNINGS
    WARNINGS += 1
    msg = f"  ⚠️  {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


def load_template(name: str) -> str:
    css = (TEMPLATES_DIR / "style.css").read_text()
    html = (TEMPLATES_DIR / f"{name}.html").read_text()
    return html.replace("{{css}}", css)


def render_html(content: str, template: str, metadata: dict) -> str:
    md = mistune.create_markdown(plugins=["table", "strikethrough", "url"])
    html_body = md(content)
    html = load_template(template)
    html = html.replace("{{content}}", html_body)
    html = html.replace("{{analysis_date}}", "2026-04-03")
    for key, value in metadata.items():
        html = html.replace(f"{{{{{key}}}}}", value)
    return html


def test_html_rendering():
    """Test 1: Markdown → HTML rendering quality."""
    print("\n=== Test 1: HTML Rendering Quality ===\n")

    html = render_html(RICH_MARKDOWN, "repo_analysis", {"repo_name": "test/repo"})

    #Headers
    check("H1 rendered", "<h1>" in html)
    check("H2 rendered", "<h2>" in html)
    check("H3 rendered", "<h3>" in html)

    #Code blocks
    check("Code blocks rendered", "<pre>" in html and "<code>" in html)
    check("Multiple code blocks", html.count("<pre>") >= 2, f"found {html.count('<pre>')}")

    #Tables
    check("Table rendered", "<table>" in html)
    check("Table headers", "<thead>" in html or "<th>" in html)
    check("Table rows", html.count("<tr>") >= 3, f"found {html.count('<tr>')} rows")

    #Inline formatting
    check("Bold text", "<strong>" in html)
    check("Italic text", "<em>" in html)
    check("Inline code", "inline code" in html)
    check("Links preserved", "example.com" in html)

    #Lists
    check("Unordered lists", "<ul>" in html)
    check("Ordered lists", "<ol>" in html)
    check("List items", html.count("<li>") >= 6, f"found {html.count('<li>')} items")

    #Unicode
    check("Unicode emoji ✅", "✅" in html)
    check("Unicode emoji 🚀", "🚀" in html)
    check("Unicode arrows →", "→" in html)
    check("Unicode accented chars", "é" in html and "ü" in html)
    check("CJK characters", "日本語" in html)

    #Horizontal rule
    check("Horizontal rules", "<hr" in html)

    #Blockquote
    check("Blockquotes", "<blockquote>" in html)

    #Template structure
    check("Report header present", "report-header" in html)
    check("Report meta present", "report-meta" in html)
    check("Repo name injected", "test/repo" in html)
    check("Date injected", "2026-04-03" in html)

    #CSS present
    check("CSS injected", "break-inside: avoid" in html)
    check("Code styling CSS", "SFMono-Regular" in html or "monospace" in html)
    check("Table styling CSS", "border-collapse" in html)

    return html


def test_video_summary_template():
    """Test 2: Video summary template rendering."""
    print("\n=== Test 2: Video Summary Template ===\n")

    video_md = """## Overview
This video covers advanced prompt engineering techniques.

## Key Points
- Chain of thought prompting improves accuracy by 40%
- Few-shot examples are more effective than lengthy instructions
- Temperature 0.7 is the sweet spot for creative tasks

## Technical Details
The presenter demonstrates using `system prompts` and `function calling`.

## Actionable Steps
1. Start with a clear system prompt
2. Add 2-3 examples
3. Test with edge cases
"""
    metadata = {
        "video_title": "Advanced Prompt Engineering — Claude Tips",
        "video_url": "https://youtube.com/watch?v=abc123",
    }

    html = render_html(video_md, "video_summary", metadata)

    check("Video title injected", "Advanced Prompt Engineering" in html)
    check("Video URL injected", "youtube.com/watch?v=abc123" in html)
    check("Video-specific CSS", "video-url" in html)
    check("Content rendered", "chain of thought" in html.lower() or "Chain of thought" in html)
    check("Lists rendered", "<li>" in html)

    return html


def test_real_analysis_doc():
    """Test 3: Render an actual repo analysis doc."""
    print("\n=== Test 3: Real Analysis Document ===\n")

    #Pick the gotenberg analysis (richest content)
    analysis_path = ANALYSIS_DIR / "gotenberg_gotenber_analysis.md"
    if not analysis_path.exists():
        warn("Analysis doc not found", str(analysis_path))
        #Try any available doc
        docs = list(ANALYSIS_DIR.glob("*_analysis.md"))
        if not docs:
            warn("No analysis docs available, skipping")
            return None
        analysis_path = docs[0]
        print(f"  Using: {analysis_path.name}")

    content = analysis_path.read_text()
    check("Content loaded", len(content) > 500, f"{len(content)} chars")

    html = render_html(content, "repo_analysis", {"repo_name": "gotenberg/gotenberg"})

    check("HTML generated", len(html) > len(content))
    check("Tables from real doc", "<table>" in html)
    check("Code blocks from real doc", "<pre>" in html)
    check("Multiple sections", html.count("<h2>") >= 5)

    #Save HTML for manual inspection
    output_path = PDF_OUTPUT_DIR / "test_repo_analysis.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"  📄 HTML saved: {output_path}")

    return html


async def test_gotenberg_pdf(html: str, label: str = "test_repo") -> Path | None:
    """Test 4: Generate actual PDF via Gotenberg."""
    print(f"\n=== Test 4: Gotenberg PDF Generation ({label}) ===\n")

    #Check Gotenberg health
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{GOTENBERG_URL}/health")
            if health.status_code != 200:
                warn("Gotenberg unhealthy", f"status {health.status_code}")
                return None
            check("Gotenberg reachable", True)
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        warn("Gotenberg not available", f"{e} — start with: docker compose up -d gotenberg")
        return None

    footer_html = (TEMPLATES_DIR / "footer.html").read_text()

    start = time.monotonic()
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
    elapsed = time.monotonic() - start

    check("HTTP 200 response", resp.status_code == 200, f"got {resp.status_code}")

    if resp.status_code != 200:
        print(f"  Response: {resp.text[:300]}")
        return None

    pdf_bytes = resp.content
    size_kb = len(pdf_bytes) / 1024
    size_mb = size_kb / 1024

    check("PDF not empty", len(pdf_bytes) > 0)
    check("PDF header valid", pdf_bytes[:5] == b"%PDF-", f"got {pdf_bytes[:10]!r}")
    check(f"File size reasonable (< 5MB)", size_mb < 5, f"{size_kb:.0f} KB")
    check(f"File size not trivially small (> 10KB)", size_kb > 10, f"{size_kb:.0f} KB")
    check(f"Generation time < 10s", elapsed < 10, f"{elapsed:.1f}s")

    #Save PDF
    pdf_path = PDF_OUTPUT_DIR / f"test_{label}.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(pdf_bytes)
    print(f"  📄 PDF saved: {pdf_path} ({size_kb:.0f} KB, {elapsed:.1f}s)")

    return pdf_path


async def test_gotenberg_error_handling():
    """Test 5: Error handling when Gotenberg is unavailable."""
    print("\n=== Test 5: Error Handling (Gotenberg Unavailable) ===\n")

    #Point to a non-existent endpoint
    bad_url = "http://localhost:19999"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{bad_url}/forms/chromium/convert/html",
                files={"files": ("index.html", b"<h1>test</h1>", "text/html")},
                data={"printBackground": "true"},
            )
        #Should not get here
        check("ConnectError raised for bad URL", False, "request succeeded unexpectedly")
    except httpx.ConnectError:
        check("ConnectError raised for bad URL", True)
    except Exception as e:
        check("Error raised for bad URL", True, f"type: {type(e).__name__}")

    #Verify pdf_generator.py handles this properly
    #Import the module's logic
    try:
        from pdf_generator import GOTENBERG_URL as configured_url
        check("pdf_generator imports cleanly", True)
        check("GOTENBERG_URL configured", bool(configured_url), configured_url)
    except ImportError as e:
        warn("Cannot import pdf_generator directly", str(e))

    print("  ℹ️  Manual fallback test: stop gotenberg container, send a link, check error message")


async def test_video_summary_pdf(html: str) -> Path | None:
    """Test 6: Generate video summary PDF via Gotenberg."""
    print("\n=== Test 6: Video Summary PDF ===\n")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            health = await client.get(f"{GOTENBERG_URL}/health")
            if health.status_code != 200:
                warn("Gotenberg not available, skipping")
                return None
    except (httpx.ConnectError, httpx.TimeoutException):
        warn("Gotenberg not available, skipping video PDF test")
        return None

    return await test_gotenberg_pdf(html, label="test_video_summary")


async def main():
    global PASSED, FAILED, WARNINGS

    print("=" * 60)
    print("Link Sentinel — Gotenberg PDF E2E Validation")
    print("=" * 60)
    print(f"\nGotenberg URL: {GOTENBERG_URL}")
    print(f"Templates dir: {TEMPLATES_DIR}")
    print(f"Analysis docs: {ANALYSIS_DIR}")

    #Test 1: HTML rendering with rich markdown
    html_repo = test_html_rendering()

    #Test 2: Video summary template
    html_video = test_video_summary_template()

    #Test 3: Real analysis doc rendering
    html_real = test_real_analysis_doc()

    #Test 4: Actual PDF generation (repo analysis)
    if html_real:
        await test_gotenberg_pdf(html_real, label="repo_analysis_gotenberg")

    #Test 5: Error handling
    await test_gotenberg_error_handling()

    #Test 6: Video summary PDF
    if html_video:
        await test_video_summary_pdf(html_video)

    #Summary
    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Results: {PASSED}/{total} passed, {FAILED} failed, {WARNINGS} warnings")
    print("=" * 60)

    if FAILED > 0:
        print("\n⚠️  Some tests failed. Review the output above.")
        sys.exit(1)
    elif WARNINGS > 0:
        print("\n✅ All checks passed (some tests skipped — Gotenberg may not be running).")
        print("   Run with Gotenberg up to get full coverage:")
        print("   cd /home/shaddar/Documents/workspace/personal/projects/link-sentinel")
        print("   docker compose up -d gotenberg")
        print("   python3 tests/test_pdf_e2e.py")
    else:
        print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
