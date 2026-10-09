"""M2 文档解析：PDF / Word / HTML / TXT → 纯文本。"""

from pathlib import Path


class ParseError(Exception):
    pass


def _quality_from_ratio(extracted_len: int, file_size: int) -> str:
    if file_size <= 0:
        return "medium"
    ratio = extracted_len / file_size
    if ratio >= 0.02:
        return "high"
    if ratio >= 0.005:
        return "medium"
    return "low"


def parse_text_file(path: Path) -> tuple[str, str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw.strip(), "high"


def parse_html_file(path: Path) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    raw = path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text("\n", strip=True)
    return text, _quality_from_ratio(len(text), path.stat().st_size)


def parse_pdf_file(path: Path) -> tuple[str, str]:
    import fitz

    doc = fitz.open(path)
    parts: list[str] = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    text = "\n".join(parts).strip()
    quality = _quality_from_ratio(len(text), path.stat().st_size)
    if len(text) < 80:
        quality = "low"
    return text, quality


def parse_docx_file(path: Path) -> tuple[str, str]:
    from docx import Document

    doc = Document(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(parts).strip()
    return text, _quality_from_ratio(len(text), path.stat().st_size)


def parse_file(path: Path) -> tuple[str, str, str]:
    """返回 (content, parse_quality, mime_hint)。"""
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        content, quality = parse_text_file(path)
        return content, quality, "text/plain"
    if suffix in {".html", ".htm"}:
        content, quality = parse_html_file(path)
        return content, quality, "text/html"
    if suffix == ".pdf":
        try:
            content, quality = parse_pdf_file(path)
        except Exception as exc:
            raise ParseError(f"PDF 解析失败: {exc}") from exc
        if not content.strip():
            raise ParseError("PDF 无可提取文本（可能是扫描版，V1 不做 OCR）")
        return content, quality, "application/pdf"
    if suffix == ".docx":
        try:
            content, quality = parse_docx_file(path)
        except Exception as exc:
            raise ParseError(f"Word 解析失败: {exc}") from exc
        return content, quality, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    raise ParseError(f"不支持的文件类型: {suffix}")
