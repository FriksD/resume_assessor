"""PDF 转换文本，提取关键信息"""
import hashlib
import re
from io import BytesIO

import pdfplumber


def compute_md5(file_bytes: bytes) -> str:
    return hashlib.md5(file_bytes).hexdigest()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """清洗PDF文本，保留换行和空格，去除多余的空行和空格"""
    pages = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            raw = page.extract_text()
            if raw:
                pages.append(raw)
    return clean_text("\n".join(pages))


def clean_text(text: str) -> str:
    """移除多余的空行和空格，保留换行和空格"""
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
