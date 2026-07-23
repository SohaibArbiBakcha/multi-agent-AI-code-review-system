"""Renders the aggregated agent output into a downloadable PDF report."""
import io
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Core PDF fonts (Helvetica, etc.) only support Latin-1, which excludes
# characters routinely produced by the LLM (em dashes, curly quotes,
# emojis). DejaVu Sans ships with matplotlib (already a dependency) and
# covers a much wider Unicode range, so we reuse it instead of bundling
# a separate font file.
_FONT_DIR = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
FONT_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"


def _severity_chart(bugs: list[dict], smells: list[dict]) -> bytes:
    counts = {"bug": len(bugs), "smell": len(smells)}
    fig, ax = plt.subplots(figsize=(4, 2.5))
    ax.bar(counts.keys(), counts.values(), color=["#EF4444", "#F59E0B"])
    ax.set_title("Issues by category")
    ax.set_ylabel("Count")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


class ReportPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font("DejaVu", "", str(FONT_REGULAR))
        self.add_font("DejaVu", "B", str(FONT_BOLD))

    def header(self):
        self.set_font("DejaVu", "B", 14)
        self.cell(0, 10, "CodeSentinel - Analysis Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_font("DejaVu", "", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, "Generated locally - no data sent externally", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.set_text_color(0, 0, 0)
        self.ln(4)

    def section_title(self, title: str):
        self.set_font("DejaVu", "B", 12)
        self.set_fill_color(30, 41, 59)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f"  {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def body_text(self, text: str):
        self.set_font("DejaVu", "", 10)
        self.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def markdown_body(self, markdown_text: str):
        """Render Markdown produced by the LLM (agents/report_writer.py) as
        formatted PDF content instead of dumping raw '#'/'**' characters.

        This is a small line-based renderer, not a full Markdown parser: it
        covers the subset the ReportWriter prompt actually asks the model to
        produce (headings, bold, bullet lists, plain paragraphs), which is
        enough since the input is our own prompted output, not arbitrary
        user-supplied Markdown.
        """
        for raw_line in markdown_text.splitlines():
            # Full strip, not just rstrip: models occasionally emit a leading
            # space before the first '#' (observed live with Mistral), which
            # a strict `^#` heading regex misses entirely, leaking the raw
            # '#' into the PDF as plain text on that one line.
            line = raw_line.strip()

            if not line:
                self.ln(2)
                continue

            heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = self._strip_inline_markdown(heading_match.group(2))
                size = {1: 13, 2: 12, 3: 11}.get(level, 10.5)
                self.set_font("DejaVu", "B", size)
                self.multi_cell(0, 6.5, heading_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                self.set_font("DejaVu", "", 10)
                self.ln(1)
                continue

            bullet_match = re.match(r"^[\s]*[-*]\s+(.*)", line)
            if bullet_match:
                item_text = self._strip_inline_markdown(bullet_match.group(1))
                self.set_font("DejaVu", "", 10)
                # Root cause of a previous crash here: fpdf2's multi_cell()
                # defaults to new_x=XPos.RIGHT, leaving the cursor at the far
                # right edge of the page after this call instead of resetting
                # to the left margin. The *next* multi_cell() call (the next
                # bullet) then has ~0 width available and raises
                # "Not enough horizontal space to render a single character" -
                # a cursor-position bug, not a font/glyph issue. Passing
                # new_x/new_y explicitly avoids relying on some later ln()
                # call to fix it as a side effect.
                self.multi_cell(0, 5.5, f"  - {item_text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                continue

            self._render_paragraph_with_bold(line)

        self.ln(1)

    def _render_paragraph_with_bold(self, line: str):
        """Render one paragraph line, honoring **bold** spans inline."""
        parts = re.split(r"(\*\*.+?\*\*)", line)
        self.set_font("DejaVu", "", 10)
        for part in parts:
            if not part:
                continue
            if part.startswith("**") and part.endswith("**"):
                self.set_font("DejaVu", "B", 10)
                self.write(5.5, part[2:-2])
                self.set_font("DejaVu", "", 10)
            else:
                self.write(5.5, part)
        self.ln(6.5)

    @staticmethod
    def _strip_inline_markdown(text: str) -> str:
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
        return text


def generate_pdf(state: dict) -> bytes:
    """Build the final PDF from the shared orchestrator state and return bytes."""
    pdf = ReportPDF()
    pdf.add_page()

    pdf.section_title(f"File analyzed: {state.get('filename', 'n/a')}")
    score = state.get("score", {})
    pdf.body_text(
        f"Global score: {score.get('value', 'N/A')}/100  -  Grade: {score.get('grade', 'N/A')}"
    )

    bugs = state.get("agent1_result", []) or []
    smells = state.get("agent2_result", []) or []
    complexity = state.get("agent3_result", {}) or {}

    pdf.section_title(f"1. Bugs and Security ({len(bugs)})")
    if bugs:
        for b in bugs[:25]:
            pdf.body_text(f"L.{b.get('line', '?')} [{b.get('type', 'bug')}] {b.get('description', '')}")
    else:
        pdf.body_text("No bugs detected.")

    pdf.section_title(f"2. Code Smells ({len(smells)})")
    if smells:
        for s in smells[:25]:
            pdf.body_text(f"{s.get('smell_type', '')} - {s.get('location', '')} ({s.get('severity', '')})")
    else:
        pdf.body_text("No code smells detected.")

    pdf.section_title("3. Complexity")
    pdf.body_text(
        f"Average cyclomatic complexity: {complexity.get('cyclomatic_avg', 'N/A')}\n"
        f"Maintainability index: {complexity.get('maintainability_index', 'N/A')}\n"
        f"Grade: {complexity.get('grade', 'N/A')}"
    )

    try:
        chart = _severity_chart(bugs, smells)
        pdf.image(io.BytesIO(chart), w=100)
    except Exception:
        pass

    pdf.section_title("4. Pedagogical Report")
    agent5 = state.get("agent5_result", {})
    report_markdown = agent5.get("markdown", "Report not generated.") if isinstance(agent5, dict) else str(agent5)
    pdf.markdown_body(report_markdown)

    return bytes(pdf.output())
