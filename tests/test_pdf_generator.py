from pypdf import PdfReader
from io import BytesIO

from tools.pdf_generator import ReportPDF, generate_pdf


def _extract_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "".join(page.extract_text() for page in reader.pages)


def test_markdown_body_renders_consecutive_bullets_without_raising():
    # Regression test: fpdf2's multi_cell() defaults to new_x=XPos.RIGHT,
    # leaving the cursor at the page's right edge. A bullet list rendered
    # without an explicit new_x=LMARGIN reset crashed on the second item
    # with "Not enough horizontal space to render a single character".
    pdf = ReportPDF()
    pdf.add_page()
    pdf.markdown_body("- First item\n- Second item\n- Third item")


def test_markdown_body_strips_headings_and_bold_markers():
    pdf = ReportPDF()
    pdf.add_page()
    pdf.markdown_body("# Title\n\n## Subtitle\n\nSome **bold** text and a normal sentence.")
    pdf_bytes = bytes(pdf.output())
    text = _extract_text(pdf_bytes)
    assert "#" not in text
    assert "**" not in text
    assert "Title" in text
    assert "bold" in text


def test_generate_pdf_with_full_markdown_report_has_no_raw_markdown():
    state = {
        "filename": "bad_code.py",
        "score": {"value": 30.1, "grade": "F"},
        "agent1_result": [],
        "agent2_result": [],
        "agent3_result": {},
        "agent5_result": {
            "markdown": (
                "# Rapport pedagogique\n\n"
                "## Synthese\n"
                "Score de **30.1/100** (note F).\n\n"
                "## Bugs et securite\n"
                "- Mot de passe en clair\n"
                "- Utilisation dangereuse de pickle.loads\n"
                "- Concatenation SQL non securisee\n"
            )
        },
    }
    pdf_bytes = generate_pdf(state)
    text = _extract_text(pdf_bytes)
    assert "#" not in text
    assert "**" not in text
    assert "Synthese" in text
    assert "Mot de passe en clair" in text


def test_markdown_body_strips_heading_with_leading_space():
    # Regression test: observed live with Mistral, which occasionally emits
    # a leading space before the first '#' (" # Title" instead of "# Title").
    # The heading regex originally only matched '#' at position 0 of the
    # rstrip()'d line, so this leaked a literal '#' into the PDF as plain text.
    pdf = ReportPDF()
    pdf.add_page()
    pdf.markdown_body(" # Title With A Leading Space\n\nBody text.")
    pdf_bytes = bytes(pdf.output())
    text = _extract_text(pdf_bytes)
    assert "#" not in text
    assert "Title With A Leading Space" in text


def test_generate_pdf_handles_missing_report_gracefully():
    state = {"filename": "empty.py", "score": {}, "agent1_result": [], "agent2_result": [], "agent3_result": {}}
    pdf_bytes = generate_pdf(state)
    assert len(pdf_bytes) > 0
