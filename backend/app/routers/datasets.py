"""知识库 CRUD。"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..schemas import DatasetCreate, DatasetUpdate

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row) -> dict:
    d = dict(row)
    return d


@router.get("")
def list_datasets():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT d.*,
                   (SELECT COUNT(*) FROM documents doc WHERE doc.dataset_id = d.id) AS document_count,
                   (SELECT COALESCE(SUM(doc.chunk_count), 0) FROM documents doc WHERE doc.dataset_id = d.id) AS segment_count
            FROM datasets d ORDER BY d.updated_at DESC
            """
        ).fetchall()
    return {"data": [_row_to_dict(r) for r in rows]}


@router.post("", status_code=201)
def create_dataset(body: DatasetCreate):
    ds_id = str(uuid.uuid4())
    now = _now()
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO datasets (id, name, description, embedding_model, chunk_size, chunk_overlap, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (ds_id, body.name, body.description, "", body.chunk_size, body.chunk_overlap, now, now),
        )
    return _get_or_404(ds_id)


@router.get("/{dataset_id}")
def get_dataset(dataset_id: str):
    return _get_or_404(dataset_id)


@router.patch("/{dataset_id}")
def update_dataset(dataset_id: str, body: DatasetUpdate):
    _get_or_404(dataset_id)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        fields["updated_at"] = _now()
        sets = ", ".join(f"{k}=?" for k in fields)
        with get_conn() as conn:
            conn.execute(f"UPDATE datasets SET {sets} WHERE id=?", (*fields.values(), dataset_id))
    return _get_or_404(dataset_id)


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str):
    _get_or_404(dataset_id)
    with get_conn() as conn:
        conn.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
    # 清理上传文件
    import shutil

    from ..config import UPLOAD_DIR
    shutil.rmtree(UPLOAD_DIR / dataset_id, ignore_errors=True)


def _get_or_404(dataset_id: str) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
    if not row:
        raise HTTPException(404, "知识库不存在")
    return _row_to_dict(row)
