"""文档解析：txt / md / pdf / docx -> 纯文本。"""
from pathlib import Path

SUPPORTED_EXT = {".txt", ".md", ".markdown", ".pdf", ".docx"}


class ParseError(Exception):
    pass


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in (".txt", ".md", ".markdown"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    raise ParseError(f"不支持的文件类型: {ext}（支持: {', '.join(sorted(SUPPORTED_EXT))}）")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as e:  # pragma: no cover
        raise ParseError("缺少 pypdf 依赖，无法解析 PDF") from e
    reader = PdfReader(str(path))
    parts = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(parts).strip()
    if not text:
        raise ParseError("PDF 未提取到文本（可能是扫描件，需 OCR）")
    return text


def _extract_docx(path: Path) -> str:
    try:
        import docx
    except ImportError as e:  # pragma: no cover
        raise ParseError("缺少 python-docx 依赖，无法解析 DOCX") from e
    doc = docx.Document(str(path))
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    if not text:
        raise ParseError("DOCX 未提取到文本")
    return text
