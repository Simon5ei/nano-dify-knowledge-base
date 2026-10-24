"""分段（chunk）管理：查看 / 新增 / 编辑 / 启停 / 删除。"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..embedding import embed_texts
from ..indexing import reindex_segment_terms
from ..schemas import SegmentCreate, SegmentUpdate

router = APIRouter(prefix="/api/datasets/{dataset_id}/documents/{document_id}/segments", tags=["segments"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_doc(dataset_id: str, document_id: str) -> None:
    with get_conn() as conn:
        if not conn.execute(
            "SELECT 1 FROM documents WHERE id=? AND dataset_id=?", (document_id, dataset_id)
        ).fetchone():
            raise HTTPException(404, "文档不存在")


@router.get("")
def list_segments(dataset_id: str, document_id: str):
    _check_doc(dataset_id, document_id)
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id, dataset_id, document_id, content, position, enabled, hit_count, created_at
               FROM segments WHERE document_id=? ORDER BY position""",
            (document_id,),
        ).fetchall()
    return {"data": [dict(r) for r in rows]}


def _dataset_mode(conn, dataset_id: str) -> str:
    row = conn.execute("SELECT retrieval_mode FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    return (row["retrieval_mode"] if row else None) or "vector"


@router.post("", status_code=201)
def create_segment(dataset_id: str, document_id: str, body: SegmentCreate):
    _check_doc(dataset_id, document_id)
    seg_id = str(uuid.uuid4())
    now = _now()
    # 模式判定与向量化都在 DB 锁外完成（embed_texts 内部会读 settings_store）
    with get_conn() as conn:
        mode = _dataset_mode(conn, dataset_id)
    vectors = [] if mode == "bm25" else embed_texts([body.content])
    with get_conn() as conn:
        max_pos = conn.execute(
            "SELECT COALESCE(MAX(position), -1) AS m FROM segments WHERE document_id=?", (document_id,)
        ).fetchone()["m"]
        if mode == "bm25":
            from ..indexing import write_bm25_segment
            write_bm25_segment(conn, seg_id, dataset_id, document_id, body.content, max_pos + 1, now)
        else:
            conn.execute(
                """INSERT INTO segments (id, dataset_id, document_id, content, position, enabled, hit_count, embedding, created_at)
                   VALUES (?,?,?,?,?,1,0,?,?)""",
                (seg_id, dataset_id, document_id, body.content, max_pos + 1, json.dumps(vectors[0]), now),
            )
        _refresh_chunk_count(conn, document_id)
        row = conn.execute(
            "SELECT id, dataset_id, document_id, content, position, enabled, hit_count, created_at FROM segments WHERE id=?",
            (seg_id,),
        ).fetchone()
    return dict(row)


@router.patch("/{segment_id}")
def update_segment(dataset_id: str, document_id: str, segment_id: str, body: SegmentUpdate):
    seg = _get_segment(document_id, segment_id)
    with get_conn() as conn:
        mode = _dataset_mode(conn, dataset_id)
    content_changed = body.content is not None and body.content != seg["content"]
    # 向量化在 DB 锁外完成
    new_embedding = ""
    if content_changed and mode != "bm25":
        vectors, _model = embed_texts([body.content])
        new_embedding = json.dumps(vectors[0])
    with get_conn() as conn:
        fields: dict = {}
        if content_changed:
            fields["content"] = body.content
            fields["embedding"] = new_embedding  # bm25 模式下清空为 ''
        if body.enabled is not None:
            fields["enabled"] = 1 if body.enabled else 0
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE segments SET {sets} WHERE id=?", (*fields.values(), segment_id))
            if "content" in fields and mode == "bm25":
                reindex_segment_terms(conn, {**seg, "content": body.content})
    return _get_segment(document_id, segment_id)


@router.delete("/{segment_id}", status_code=204)
def delete_segment(dataset_id: str, document_id: str, segment_id: str):
    _get_segment(document_id, segment_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM segments WHERE id=?", (segment_id,))
        _refresh_chunk_count(conn, document_id)


def _get_segment(document_id: str, segment_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id, dataset_id, document_id, content, position, enabled, hit_count, created_at
               FROM segments WHERE id=? AND document_id=?""",
            (segment_id, document_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "分段不存在")
    return dict(row)


def _refresh_chunk_count(conn, document_id: str) -> None:
    conn.execute(
        "UPDATE documents SET chunk_count=(SELECT COUNT(*) FROM segments WHERE document_id=?) WHERE id=?",
        (document_id, document_id),
    )
