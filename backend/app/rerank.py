"""重排序（Rerank）：对向量召回的候选分段做精排。

优先级：远程 /rerank 兼容接口（Jina / Cohere v2 / SiliconFlow / TEI）→ 本地关键词重叠打分。
"""
import httpx

from . import config


def rerank_available() -> bool:
    return bool(config.RERANK_BASE_URL and config.RERANK_API_KEY)


def rerank_provider_name() -> str:
    return config.RERANK_MODEL if rerank_available() else "local-keyword"


def rerank(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """返回 [(原文档下标, 得分)]，按得分降序。"""
    if not documents:
        return []
    top_n = min(top_n, len(documents))
    if rerank_available():
        return _rerank_remote(query, documents, top_n)
    return _rerank_local(query, documents, top_n)


def _rerank_remote(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """Jina / Cohere v2 / SiliconFlow / TEI 兼容的 /rerank 协议。"""
    url = config.RERANK_BASE_URL.rstrip("/") + "/rerank"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {config.RERANK_API_KEY}"},
        json={"model": config.RERANK_MODEL, "query": query, "documents": documents, "top_n": top_n},
        timeout=60,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    return [(int(r["index"]), float(r["relevance_score"])) for r in results]


def _rerank_local(query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
    """离线兜底：query 与文档的词/字 bigram 集合 Jaccard 重叠度。"""
    q_terms = _terms(query)
    scored = []
    for i, doc in enumerate(documents):
        d_terms = _terms(doc)
        inter = len(q_terms & d_terms)
        union = len(q_terms | d_terms) or 1
        scored.append((i, inter / union))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_n]


def _terms(text: str) -> set[str]:
    t = text.lower()
    terms = set(t.split())
    compact = "".join(t.split())
    terms |= {compact[i:i + 2] for i in range(len(compact) - 1)}
    return terms
