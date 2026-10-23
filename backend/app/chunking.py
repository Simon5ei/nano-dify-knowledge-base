"""文本分段：按分隔符递归切分，带重叠窗口（对齐 Dify 通用分段思路）。"""
import re

_SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", ". ", "! ", "? ", "; ", "，", ", ", " "]


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    text = re.sub(r"\r\n?", "\n", text).strip()
    if not text:
        return []
    pieces = _recursive_split(text, chunk_size, _SEPARATORS)
    return _merge_with_overlap(pieces, chunk_size, chunk_overlap)


def _recursive_split(text: str, chunk_size: int, seps: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    sep = seps[0] if seps else ""
    rest = seps[1:]
    if not sep:
        # 没有可用分隔符，硬切
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    parts = text.split(sep)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= chunk_size:
            out.append(part)
        else:
            out.extend(_recursive_split(part, chunk_size, rest))
    return out


def _merge_with_overlap(pieces: list[str], chunk_size: int, overlap: int) -> list[str]:
    """把碎片合并到接近 chunk_size，并在相邻分段间保留 overlap 字符重叠。"""
    chunks: list[str] = []
    buf = ""
    for piece in pieces:
        if not buf:
            buf = piece
        elif len(buf) + 1 + len(piece) <= chunk_size:
            buf = f"{buf}\n{piece}"
        else:
            chunks.append(buf)
            tail = buf[-overlap:] if overlap > 0 and len(buf) > overlap else ""
            buf = (tail + "\n" + piece).strip() if tail else piece
    if buf:
        chunks.append(buf)
    return chunks
