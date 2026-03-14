from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def markdown_to_paragraphs(markdown_text: str) -> list[tuple[str, str]]:
    paragraphs: list[tuple[str, str]] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            paragraphs.append(("spacer", ""))
            continue
        if line.startswith("# "):
            paragraphs.append(("title", line[2:].strip()))
        elif line.startswith("## "):
            paragraphs.append(("heading", line[3:].strip()))
        else:
            paragraphs.append(("body", line))
    return paragraphs


def build_pdf(markdown_path: Path, output_path: Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        title="Short Report",
        author="ARMORIQ x OPENCLAW Team",
    )

    story = []
    for kind, text in markdown_to_paragraphs(markdown_path.read_text(encoding="utf-8")):
        if kind == "spacer":
            story.append(Spacer(1, 8))
        elif kind == "title":
            story.append(Paragraph(f"<b>{text}</b>", styles["Title"]))
            story.append(Spacer(1, 10))
        elif kind == "heading":
            story.append(Paragraph(f"<b>{text}</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
        else:
            story.append(Paragraph(text, styles["BodyText"]))
            story.append(Spacer(1, 4))

    doc.build(story)


if __name__ == "__main__":
    docs_dir = Path(__file__).resolve().parent
    md = docs_dir / "short_report.md"
    pdf = docs_dir / "short_report.pdf"
    build_pdf(md, pdf)
    print(f"PDF created: {pdf}")
