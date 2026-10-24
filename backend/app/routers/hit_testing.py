"""召回测试：向量检索（粗排）+ 可选 Rerank（精排）。"""
import json

from fastapi import APIRouter, HTTPException

from ..db import get_conn
from ..embedding import cosine, embed_query
from ..rerank import rerank, rerank_provider_name
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

    rerank_provider = None
    if body.rerank and scored:
        # 两阶段检索：向量粗排取 3*top_k 候选 -> rerank 精排取 top_k
        candidates = scored[: max(body.top_k * 3, body.top_k)]
        pairs = rerank(body.query, [c["content"] for c in candidates], body.top_k)
        rerank_provider = rerank_provider_name()
        records = []
        for idx, rscore in pairs:
            rec = dict(candidates[idx])
            rec["vector_score"] = rec["score"]          # 保留原始向量分
            rec["score"] = round(rscore, 4)             # 最终展示 rerank 分
            records.append(rec)
    else:
        records = scored[: body.top_k]

    records = [r for r in records if r["score"] >= body.score_threshold]

    # 累计命中次数
    if records:
        with get_conn() as conn:
            conn.executemany(
                "UPDATE segments SET hit_count = hit_count + 1 WHERE id=?",
                [(r["segment_id"],) for r in records],
            )
    return {
        "query": body.query,
        "rerank": body.rerank,
        "rerank_provider": rerank_provider,
        "records": records,
    }
