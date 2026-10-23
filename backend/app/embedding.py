"""向量化：优先走 OpenAI 兼容 /embeddings 接口；未配置时降级为本地 HashEmbedding。"""
import hashlib
import math

import httpx

from . import config

HASH_DIM = 256


def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    """返回 (向量列表, 模型名)。"""
    if config.EMBEDDING_BASE_URL and config.EMBEDDING_API_KEY:
        return _embed_openai_compatible(texts), config.EMBEDDING_MODEL
    return [_hash_embed(t) for t in texts], "local-hash-256"


def embed_query(text: str, model: str) -> list[float]:
    if model != "local-hash-256" and config.EMBEDDING_BASE_URL and config.EMBEDDING_API_KEY:
        return _embed_openai_compatible([text])[0]
    return _hash_embed(text)


def _embed_openai_compatible(texts: list[str]) -> list[list[float]]:
    url = config.EMBEDDING_BASE_URL.rstrip("/") + "/embeddings"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {config.EMBEDDING_API_KEY}"},
        json={"model": config.EMBEDDING_MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    data.sort(key=lambda d: d["index"])
    return [d["embedding"] for d in data]


def _hash_embed(text: str) -> list[float]:
    """确定性本地向量：对 unigram/bigram 做特征哈希 + L2 归一化。

    仅供无外部 embedding 服务时演示召回流程，不代表真实语义检索质量。
    """
    vec = [0.0] * HASH_DIM
    tokens = text.lower().split()
    feats = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
    # 中文等无空格语言按字符 bigram 补充
    compact = re_sub_space(text.lower())
    feats += [compact[i:i + 2] for i in range(len(compact) - 1)]
    for feat in feats:
        h = int(hashlib.md5(feat.encode("utf-8")).hexdigest(), 16)
        vec[h % HASH_DIM] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def re_sub_space(s: str) -> str:
    return "".join(s.split())


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)
