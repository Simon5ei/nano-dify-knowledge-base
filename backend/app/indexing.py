"""索引流水线：解析 -> 分段 -> 按召回模式索引（向量化 / BM25 词项）-> 落库。"""
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .bm25 import term_freqs
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
    mode = ds["retrieval_mode"] or "vector"
    try:
        text = extract_text(src)
        chunks = split_text(text, ds["chunk_size"], ds["chunk_overlap"])
        if not chunks:
            raise ParseError("文档为空或分段结果为空")

        now = _now()
        # 向量化在 DB 锁外完成（内部会读 settings_store，且网络调用不应占锁）
        vectors, model = ([], "") if mode == "bm25" else embed_texts(chunks)
        with get_conn() as conn:
            conn.execute("DELETE FROM segments WHERE document_id=?", (document_id,))
            if mode == "bm25":
                # 纯本地索引：只写词项表，零 token 零网络
                for i, chunk in enumerate(chunks):
                    write_bm25_segment(conn, str(uuid.uuid4()), doc["dataset_id"], document_id, chunk, i, now)
            else:
                for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
                    conn.execute(
                        """INSERT INTO segments
                           (id, dataset_id, document_id, content, position, enabled, hit_count, embedding, created_at)
                           VALUES (?,?,?,?,?,1,0,?,?)""",
                        (str(uuid.uuid4()), doc["dataset_id"], document_id, chunk, i, json.dumps(vec), now),
                    )
                conn.execute(
                    "UPDATE datasets SET embedding_model=? WHERE id=? AND (embedding_model='' OR embedding_model IS NULL)",
                    (model, doc["dataset_id"]),
                )
            conn.execute(
                "UPDATE documents SET status='completed', chunk_count=?, error='' WHERE id=?",
                (len(chunks), document_id),
            )
            conn.execute("UPDATE datasets SET updated_at=? WHERE id=?", (now, doc["dataset_id"]))
    except Exception as e:  # noqa: BLE001 - 任何失败都落到文档状态上
        with get_conn() as conn:
            conn.execute(
                "UPDATE documents SET status='error', error=? WHERE id=?",
                (str(e)[:500], document_id),
            )


def write_bm25_segment(conn, seg_id: str, dataset_id: str, document_id: str,
                       content: str, position: int, now: str) -> None:
    """写入一个 BM25 模式分段及其倒排词项（embedding 留空）。"""
    tfs, token_len = term_freqs(content)
    conn.execute(
        """INSERT INTO segments
           (id, dataset_id, document_id, content, position, enabled, hit_count, embedding, token_len, created_at)
           VALUES (?,?,?,?,?,1,0,'',?,?)""",
        (seg_id, dataset_id, document_id, content, position, token_len, now),
    )
    conn.executemany(
        "INSERT INTO segment_terms (segment_id, term, tf) VALUES (?,?,?)",
        [(seg_id, term, tf) for term, tf in tfs.items()],
    )


def reindex_segment_terms(conn, segment) -> None:
    """分段内容变更后刷新 BM25 词项（conn 内调用）。"""
    conn.execute("DELETE FROM segment_terms WHERE segment_id=?", (segment["id"],))
    tfs, token_len = term_freqs(segment["content"])
    conn.executemany(
        "INSERT INTO segment_terms (segment_id, term, tf) VALUES (?,?,?)",
        [(segment["id"], term, tf) for term, tf in tfs.items()],
    )
    conn.execute("UPDATE segments SET token_len=? WHERE id=?", (token_len, segment["id"]))


def save_upload(dataset_id: str, document_id: str, filename: str, fileobj) -> Path:
    ext = Path(filename).suffix.lower()
    dest_dir = config.UPLOAD_DIR / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{document_id}{ext}"
    with dest.open("wb") as f:
        shutil.copyfileobj(fileobj, f)
    return dest
