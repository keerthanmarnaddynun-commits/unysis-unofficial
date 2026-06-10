"""Robust HTML to PDF conversion for legal documents."""

from __future__ import annotations

import logging
import re
from html import unescape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger(__name__)

PDF_PAGE_CSS = """
@page { size: A4; margin: 2cm; }
body { font-family: Times-Roman, serif; font-size: 11pt; color: #000; }
h1 { font-size: 14pt; text-align: center; }
h2 { font-size: 12pt; border-bottom: 1px solid #000; margin-top: 16px; }
table { width: 100%; border-collapse: collapse; }
td, th { border: 1px solid #000; padding: 6px; font-size: 10pt; }
th { background-color: #f0f0f0; }
code { font-size: 9pt; }
"""


def html_to_pdf(html: str, output_path: Path) -> None:
    """Convert HTML to PDF using xhtml2pdf, then ReportLab platypus fallback."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    full_html = html if "<html" in html.lower() else f"<html><head><style>{PDF_PAGE_CSS}</style></head><body>{html}</body></html>"
    if "<style>" not in full_html.lower() and "<head>" in full_html.lower():
        full_html = full_html.replace("<head>", f"<head><style>{PDF_PAGE_CSS}</style>", 1)

    try:
        from xhtml2pdf import pisa

        with open(output_path, "wb") as f:
            status = pisa.CreatePDF(full_html.encode("utf-8"), dest=f, encoding="utf-8")
        if not status.err and output_path.stat().st_size > 500:
            return
    except Exception as exc:
        logger.warning("xhtml2pdf failed: %s", exc)

    try:
        from weasyprint import HTML

        HTML(string=full_html).write_pdf(str(output_path))
        if output_path.stat().st_size > 500:
            return
    except Exception as exc:
        logger.debug("WeasyPrint unavailable: %s", exc)

    _reportlab_platypus_from_html(full_html, output_path)


def _strip_html(html: str) -> str:
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</tr>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</h[1-6]>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    return unescape(re.sub(r"\n{3,}", "\n\n", html)).strip()


def _reportlab_platypus_from_html(html: str, output_path: Path) -> None:
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "LegalTitle",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=14,
        alignment=1,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "LegalHeading",
        parent=styles["Heading2"],
        fontName="Times-Bold",
        fontSize=12,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "LegalBody",
        parent=styles["Normal"],
        fontName="Times-Roman",
        fontSize=11,
        leading=14,
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    story: list = []

    for block in re.split(r"(?=<h1|<h2)", html, flags=re.IGNORECASE):
        block = block.strip()
        if not block:
            continue
        if re.match(r"<h1", block, re.I):
            text = _strip_html(block)
            if text:
                story.append(Paragraph(text, title_style))
                story.append(Spacer(1, 8))
        elif re.match(r"<h2", block, re.I):
            text = _strip_html(block)
            if text:
                story.append(Paragraph(text, heading_style))
        elif "<table" in block.lower():
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", block, re.DOTALL | re.IGNORECASE)
            data = []
            for row in rows:
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL | re.IGNORECASE)
                if cells:
                    data.append([_strip_html(c)[:200] for c in cells])
            if data:
                col_count = max(len(r) for r in data)
                col_width = (16 * cm) / max(col_count, 1)
                t = Table(data, colWidths=[col_width] * col_count)
                t.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ]
                    )
                )
                story.append(t)
                story.append(Spacer(1, 10))
        else:
            text = _strip_html(block)
            if text:
                for para in text.split("\n"):
                    para = para.strip()
                    if para:
                        story.append(Paragraph(para.replace("&", "&amp;"), body_style))
                        story.append(Spacer(1, 4))

    if not story:
        story.append(Paragraph(_strip_html(html)[:8000] or "Legal document", body_style))

    doc.build(story)
