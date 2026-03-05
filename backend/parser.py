"""PDF parsing utilities."""
import hashlib
import re
from io import BytesIO

import pdfplumber


def compute_md5(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract and clean text from a PDF (supports multi-page)."""
    pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            raw = page.extract_text()
            if raw:
                pages.append(raw)
    return clean_text("\n".join(pages))


def clean_text(text: str) -> str:
    """Normalize whitespace and remove junk characters."""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
