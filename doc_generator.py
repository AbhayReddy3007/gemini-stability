from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re, os

def clean_title_text(title: str) -> str:
    """Clean up titles for document sections."""
    if not title:
        return "Document"
    title = re.sub(r"\s+", " ", title.strip())
    return title


def create_doc(title, sections, filename="output.docx", images=None):
    """
    Create a Word Document with optional images.
    sections: list of {"title": str, "description": str}
    images: list of file paths or None (one per section)
    """
    doc = Document()

    # --- Title Page ---
    doc.add_heading(clean_title_text(title), level=0)
    doc.add_paragraph()

    # --- Content Sections ---
    for idx, section in enumerate(sections, start=1):
        sec_title = clean_title_text(section.get("title", f"Section {idx}"))
        description = section.get("description", "")

        # Section Heading
        heading = doc.add_heading(sec_title, level=1)
        heading.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

        # Section Content
        for para in description.split("\n"):
            if para.strip():
                p = doc.add_paragraph(para.strip())
                p.alignment = WD_PARAGRAPH_ALIGNMENT.JUSTIFY
                run = p.runs[0]
                run.font.size = Pt(11)

        # Add Image if available
        if images and idx - 1 < len(images) and images[idx - 1]:
            try:
                doc.add_paragraph()  # spacing before image
                doc.add_picture(images[idx - 1], width=Inches(5.5))
                last_paragraph = doc.paragraphs[-1]
                last_paragraph.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                doc.add_paragraph()  # spacing after image
            except Exception as e:
                print(f"⚠️ Failed to insert image for section {idx}: {e}")

        doc.add_page_break()

    doc.save(filename)
    return filename
