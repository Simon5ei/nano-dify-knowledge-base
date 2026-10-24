"""召回测试：按知识库召回模式路由 —— 向量检索 或 BM25 全文检索，均可叠加 Rerank 精排。"""
import json
from collections import Counter

from fastapi import APIRouter, HTTPException

from ..bm25 import score_document, tokenize, tokenizer_name
from ..db import get_conn
from ..embedding import cosine, embed_query
from ..rerank import rerank, rerank_provider_name
from ..schemas import HitTestRequest

router = APIRouter(prefix="/api/datasets/{dataset_id}", tags=["hit-testing"])

_TOP_N_RERANK_FACTOR = 3


@router.post("/hit-testing")
def hit_testing(dataset_id: str, body: HitTestRequest):
    with get_conn() as conn:
        ds = conn.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
        if not ds:
            raise HTTPException(404, "知识库不存在")

    mode = ds["retrieval_mode"] or "vector"
    if mode == "bm25":
        scored, search_label = _bm25_recall(dataset_id, body.query)
    else:
        scored, search_label = _vector_recall(ds, body.query)

    if not scored:
        return {"query": body.query, "search_mode": mode, "search_label": search_label,
                "rerank": body.rerank, "rerank_provider": None, "records": []}

    rerank_provider = None
    if body.rerank:
        # 两阶段检索：粗排取 factor*top_k 候选 -> rerank 精排取 top_k
        candidates = scored[: max(body.top_k * _TOP_N_RERANK_FACTOR, body.top_k)]
        pairs = rerank(body.query, [c["content"] for c in candidates], body.top_k)
        rerank_provider = rerank_provider_name()
        records = []
        for idx, rscore in pairs:
            rec = dict(candidates[idx])
            rec["vector_score"] = rec["score"]          # 保留粗排分（向量分或 BM25 归一分）
            rec["score"] = round(rscore, 4)
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
        "search_mode": mode,
        "search_label": search_label,
        "rerank": body.rerank,
        "rerank_provider": rerank_provider,
        "records": records,
    }


def _base_record(r) -> dict:
    return {
        "segment_id": r["id"],
        "document_id": r["document_id"],
        "document_name": r["document_name"],
        "position": r["position"],
        "content": r["content"],
        "score": 0.0,
    }


def _vector_recall(ds, query: str) -> tuple[list[dict], str]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT s.id, s.content, s.position, s.document_id, s.embedding, d.name AS document_name
               FROM segments s JOIN documents d ON d.id = s.document_id
               WHERE s.dataset_id=? AND s.enabled=1""",
            (ds["id"],),
        ).fetchall()
    if not rows:
        return [], "vector"

    qvec = embed_query(query, ds["embedding_model"] or "local-hash-256")
    scored = []
    for r in rows:
        try:
            vec = json.loads(r["embedding"]) if r["embedding"] else []
        except json.JSONDecodeError:
            vec = []
        rec = _base_record(r)
        rec["score"] = round(cosine(qvec, vec), 4)
        scored.append(rec)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored, "vector"


def _bm25_recall(dataset_id: str, query: str) -> tuple[list[dict], str]:
    label = f"bm25({tokenizer_name()})"
    q_terms = tokenize(query)
    if not q_terms:
        return [], label

    with get_conn() as conn:
        stat = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(AVG(token_len),0) AS avgdl FROM segments WHERE dataset_id=? AND enabled=1",
            (dataset_id,),
        ).fetchone()
        n_docs, avgdl = stat["n"], stat["avgdl"]
        if n_docs == 0:
            return [], label

        placeholders = ",".join("?" for _ in set(q_terms))
        rows = conn.execute(
            f"""SELECT s.id, s.content, s.position, s.document_id, s.token_len, d.name AS document_name,
                       t.term, t.tf
                FROM segment_terms t
                JOIN segments s ON s.id = t.segment_id
                JOIN documents d ON d.id = s.document_id
                WHERE s.dataset_id=? AND s.enabled=1 AND t.term IN ({placeholders})""",
            (dataset_id, *sorted(set(q_terms))),
        ).fetchall()

    # 聚合：每分段的词频表与元信息；每个词项的 DF
    seg_info: dict[str, dict] = {}
    seg_tf: dict[str, dict[str, int]] = {}
    seg_len: dict[str, int] = {}
    df: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    for r in rows:
        sid = r["id"]
        if sid not in seg_info:
            seg_info[sid] = _base_record(r)
            seg_tf[sid] = {}
            seg_len[sid] = r["token_len"] or 1
        seg_tf[sid][r["term"]] = r["tf"]
        key = (r["term"], sid)
        if key not in seen:
            seen.add(key)
            df[r["term"]] += 1

    scored = []
    for sid, rec in seg_info.items():
        rec["score"] = score_document(q_terms, seg_tf[sid], seg_len[sid], avgdl, n_docs, dict(df))
        scored.append(rec)
    scored.sort(key=lambda x: x["score"], reverse=True)

    # BM25 原始分无上界，归一化到 0~1（最高分=1），保持与向量分一致的阈值语义
    max_score = scored[0]["score"] if scored else 0.0
    if max_score > 0:
        for rec in scored:
            rec["score"] = round(rec["score"] / max_score, 4)
    return scored, label
