"""召回测试：对知识库做向量检索并返回命中分段。"""
import json

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..embedding import cosine, embed_query
from ..schemas import HitTestRequest

router = APIRouter(prefix="/api/datasets/{dataset_id}", tags=["hit-testing"])


@router.post("/hit-testing")
def hit_testing(dataset_id: str, body: HitTestRequest):
    with get_conn() as conn:
        ds = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if not ds:
            raise HTTPException(404, "知识库不存在")
        rows = conn.execute(
            """SELECT s.id, s.content, s.position, s.document_id, s.embedding, d.name AS document_name
               FROM segments s JOIN documents d ON d.id = s.document_id
               WHERE s.dataset_id=? AND s.enabled=1""",
            (dataset_id,),
        ).fetchall()

    if not rows:
        return {"query": body.query, "records": []}

    qvec = embed_query(body.query, ds["embedding_model"] or "local-hash-256")

    scored = []
    for r in rows:
        try:
            vec = json.loads(r["embedding"]) if r["embedding"] else []
        except json.JSONDecodeError:
            vec = []
        scored.append({
            "segment_id": r["id"],
            "document_id": r["document_id"],
            "document_name": r["document_name"],
            "position": r["position"],
            "content": r["content"],
            "score": round(cosine(qvec, vec), 4),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    records = [s for s in scored if s["score"] >= body.score_threshold][: body.top_k]

    # 累计命中次数
    if records:
        with get_conn() as conn:
            conn.executemany(
                "UPDATE segments SET hit_count = hit_count + 1 WHERE id=?",
                [(r["segment_id"],) for r in records],
            )
    return {"query": body.query, "records": records}
