"""SQLite 存储层（零依赖，单文件数据库）。"""
import sqlite3
import threading
from contextlib import contextmanager

from .config import DATA_DIR

DB_FILE = DATA_DIR / "nano_dify.db"
_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT DEFAULT '',
    embedding_model TEXT DEFAULT '',
    chunk_size      INTEGER DEFAULT 500,
    chunk_overlap   INTEGER DEFAULT 50,
    retrieval_mode  TEXT DEFAULT 'vector',  -- vector / bm25
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id          TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    mime        TEXT DEFAULT '',
    size        INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'completed',   -- queuing/indexing/completed/error
    error       TEXT DEFAULT '',
    chunk_count INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_dataset ON documents(dataset_id);

CREATE TABLE IF NOT EXISTS segments (
    id          TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    position    INTEGER DEFAULT 0,
    enabled     INTEGER DEFAULT 1,
    hit_count   INTEGER DEFAULT 0,
    embedding   TEXT DEFAULT '',            -- JSON 数组（vector 模式）
    token_len   INTEGER DEFAULT 0,          -- 分词长度（bm25 模式）
    created_at  TEXT NOT NULL
);

-- BM25 倒排：词项 -> 分段词频
CREATE TABLE IF NOT EXISTS segment_terms (
    segment_id TEXT NOT NULL REFERENCES segments(id) ON DELETE CASCADE,
    term       TEXT NOT NULL,
    tf         INTEGER NOT NULL,
    PRIMARY KEY (segment_id, term)
);
CREATE INDEX IF NOT EXISTS idx_segment_terms_term ON segment_terms(term);
CREATE INDEX IF NOT EXISTS idx_segments_dataset ON segments(dataset_id);
CREATE INDEX IF NOT EXISTS idx_segments_document ON segments(document_id);

-- 界面可改的运行时配置（优先级高于环境变量）
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        _migrate(conn)


def _migrate(conn) -> None:
    """旧库自动升级：补新增列。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(datasets)")}
    if "retrieval_mode" not in cols:
        conn.execute("ALTER TABLE datasets ADD COLUMN retrieval_mode TEXT DEFAULT 'vector'")
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(segments)")}
    if "token_len" not in cols:
        conn.execute("ALTER TABLE segments ADD COLUMN token_len INTEGER DEFAULT 0")


@contextmanager
def get_conn():
    with _lock:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
