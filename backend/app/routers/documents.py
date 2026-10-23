"""文档上传与管理。"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from ..db import get_conn
from ..indexing import index_document, save_upload
from ..parsing import SUPPORTED_EXT

router = APIRouter(prefix="/api/datasets/{dataset_id}/documents", tags=["documents"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_dataset(dataset_id: str) -> None:
    with get_conn() as conn:
        if not conn.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone():
            raise HTTPException(404, "知识库不存在")


@router.get("")
def list_documents(dataset_id: str):
    _check_dataset(dataset_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE dataset_id=? ORDER BY created_at DESC", (dataset_id,)
        ).fetchall()
    return {"data": [dict(r) for r in rows]}


@router.post("/upload", status_code=201)
async def upload_document(dataset_id: str, file: UploadFile):
    _check_dataset(dataset_id)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise HTTPException(400, f"不支持的文件类型 {ext}，支持: {', '.join(sorted(SUPPORTED_EXT))}")

    doc_id = str(uuid.uuid4())
    dest = save_upload(dataset_id, doc_id, file.filename or "unnamed", file.file)
    size = dest.stat().st_size

    with get_conn() as conn:
        conn.execute(
            """INSERT INTO documents (id, dataset_id, name, mime, size, status, error, chunk_count, created_at)
               VALUES (?,?,?,?,?,'queuing','',0,?)""",
            (doc_id, dataset_id, file.filename, file.content_type or "", size, _now()),
        )

    index_document(doc_id)  # 迷你版同步执行；生产应进队列

    with get_conn() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return dict(row)


@router.delete("/{document_id}", status_code=204)
def delete_document(dataset_id: str, document_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM documents WHERE id=? AND dataset_id=?", (document_id, dataset_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
        conn.execute("DELETE FROM documents WHERE id=?", (document_id,))


@router.post("/{document_id}/reindex")
def reindex_document(dataset_id: str, document_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM documents WHERE id=? AND dataset_id=?", (document_id, dataset_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "文档不存在")
    index_document(document_id)
    with get_conn() as conn:
        return dict(conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone())
