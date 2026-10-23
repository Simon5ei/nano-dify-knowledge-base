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
    embedding   TEXT DEFAULT '',            -- JSON 数组
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segments_dataset ON segments(dataset_id);
CREATE INDEX IF NOT EXISTS idx_segments_document ON segments(document_id);
"""


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)


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
