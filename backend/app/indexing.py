"""索引流水线：解析 -> 分段 -> 向量化 -> 落库。"""
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .chunking import split_text
from .db import get_conn
from .embedding import embed_texts
from .parsing import ParseError, extract_text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def index_document(document_id: str) -> None:
    """同步构建一个文档的全部分段（迷你版不做队列，状态即时更新）。"""
    with get_conn() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not doc:
            return
        ds = conn.execute("SELECT * FROM datasets WHERE id = ?", (doc["dataset_id"],)).fetchone()
        conn.execute("UPDATE documents SET status='indexing', error='' WHERE id=?", (document_id,))

    src = config.UPLOAD_DIR / doc["dataset_id"] / f"{document_id}{Path(doc['name']).suffix.lower()}"
    try:
        text = extract_text(src)
        chunks = split_text(text, ds["chunk_size"], ds["chunk_overlap"])
        if not chunks:
            raise ParseError("文档为空或分段结果为空")
        vectors, model = embed_texts(chunks)

        now = _now()
        with get_conn() as conn:
            conn.execute("DELETE FROM segments WHERE document_id=?", (document_id,))
            for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                conn.execute(
                    """INSERT INTO segments
                       (id, dataset_id, document_id, content, position, enabled, hit_count, embedding, created_at)
                       VALUES (?,?,?,?,?,1,0,?,?)""",
                    (str(uuid.uuid4()), doc["dataset_id"], document_id, chunk, i, json.dumps(vec), now),
                )
            conn.execute(
                "UPDATE documents SET status='completed', chunk_count=?, error='' WHERE id=?",
                (len(chunks), document_id),
            )
            conn.execute(
                "UPDATE datasets SET embedding_model=?, updated_at=? WHERE id=? AND (embedding_model='' OR embedding_model IS NULL)",
                (model, now, doc["dataset_id"]),
            )
    except Exception as e:  # noqa: BLE001 - 任何失败都落到文档状态上
        with get_conn() as conn:
            conn.execute(
                "UPDATE documents SET status='error', error=? WHERE id=?",
                (str(e)[:500], document_id),
            )


def save_upload(dataset_id: str, document_id: str, filename: str, fileobj) -> Path:
    ext = Path(filename).suffix.lower()
    dest_dir = config.UPLOAD_DIR / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{document_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(fileobj, f)
    return dest
