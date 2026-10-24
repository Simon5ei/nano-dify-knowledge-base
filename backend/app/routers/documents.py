"""文档上传与管理。"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import UPLOAD_DIR
from ..db import get_conn
from ..indexing import index_document, save_upload
from ..parsing import SUPPORTED_EXT, ParseError, extract_text

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


def _find_doc(dataset_id: str, document_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND dataset_id=?", (document_id, dataset_id)
        ).fetchone()
    if not row:
        raise HTTPException(404, "文档不存在")
    return dict(row)


def _upload_path(doc: dict) -> Path:
    path = UPLOAD_DIR / doc["dataset_id"] / f"{doc['id']}{Path(doc['name']).suffix.lower()}"
    if not path.exists():
        raise HTTPException(404, "原始文件已丢失")
    return path


@router.get("/{document_id}/content")
def document_content(dataset_id: str, document_id: str):
    """查看文档解析后的全文内容（与分段索引所用的文本一致）。"""
    doc = _find_doc(dataset_id, document_id)
    try:
        text = extract_text(_upload_path(doc))
    except ParseError as e:
        raise HTTPException(422, str(e)) from e
    return {"id": doc["id"], "name": doc["name"], "content": text}


@router.get("/{document_id}/download")
def download_document(dataset_id: str, document_id: str):
    """下载原始上传文件。"""
    doc = _find_doc(dataset_id, document_id)
    return FileResponse(_upload_path(doc), filename=doc["name"])


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
