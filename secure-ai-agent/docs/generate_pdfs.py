"""Convert architecture_diagram.html and report.html to PDF using Playwright."""
from __future__ import annotations

import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)


def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    print(f"  Saved: {pdf_path}")


if __name__ == "__main__":
    print("Generating PDFs...")
    html_to_pdf(DOCS / "architecture_diagram.html", DOCS / "architecture_diagram.pdf")
    html_to_pdf(DOCS / "report.html",               DOCS / "report.pdf")
    print("Done.")
