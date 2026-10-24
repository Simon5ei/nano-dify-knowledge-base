"""BM25 全文检索：零 token、零网络的本地召回。

分词策略：装了 jieba 用 jieba（中文按词），否则退化为 英文按词 + 中文字 bigram。
打分：标准 BM25Okapi（k1=1.5, b=0.75）。
"""
import math
import re
from collections import Counter

try:
    import jieba

    jieba.setLogLevel(20)  # 关掉加载日志
    _JIEBA = True
except ImportError:  # pragma: no cover
    _JIEBA = False

K1 = 1.5
B = 0.75

_VALID = re.compile(r"[a-z0-9一-鿿]", re.I)
_WORD_RE = re.compile(r"[a-z0-9]+")
_CJK_RE = re.compile(r"[一-鿿]")


def tokenizer_name() -> str:
    return "jieba" if _JIEBA else "char-bigram"


def tokenize(text: str) -> list[str]:
    """文本 -> 词项列表（小写，去纯标点/空白）。"""
    if _JIEBA:
        return [t.lower() for t in jieba.lcut(text) if _VALID.search(t)]
    return _fallback_tokenize(text)


def _fallback_tokenize(text: str) -> list[str]:
    t = text.lower()
    words = _WORD_RE.findall(t)
    cjk = "".join(_CJK_RE.findall(t))
    return words + [cjk[i : i + 2] for i in range(len(cjk) - 1)]


def term_freqs(text: str) -> tuple[Counter, int]:
    """返回 (词项频率表, 文档 token 长度)。"""
    terms = tokenize(text)
    return Counter(terms), len(terms)


def idf(n_docs: int, df: int) -> float:
    """BM25 IDF（+1 平滑，保证非负）。"""
    return math.log(1 + (n_docs - df + 0.5) / (df + 0.5))


def score_document(query_terms: list[str], tf: dict[str, int], doc_len: int,
                   avgdl: float, n_docs: int, dfs: dict[str, int]) -> float:
    """对单个文档打 BM25 分。tf: 该文档的词频表，dfs: 每个 query 词项的文档频率。"""
    if avgdl <= 0:
        return 0.0
    score = 0.0
    for term in query_terms:
        f = tf.get(term, 0)
        if f == 0:
            continue
        df = dfs.get(term, 0)
        denom = f + K1 * (1 - B + B * doc_len / avgdl)
        score += idf(n_docs, df) * f * (K1 + 1) / (denom or 1e-9)
    return score
