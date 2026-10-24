"""运行时设置：界面修改持久化到 SQLite，优先级 数据库 > 环境变量 > 内置默认。

支持项见 SETTINGS_KEYS。API Key 类字段在读取接口中脱敏返回。
"""
import os

from .db import get_conn

# key -> (env 名, 内置默认, 是否敏感)
SETTINGS_SCHEMA: dict[str, tuple[str, str, bool]] = {
    "EMBEDDING_BASE_URL": ("EMBEDDING_BASE_URL", "", False),
    "EMBEDDING_API_KEY": ("EMBEDDING_API_KEY", "", True),
    "EMBEDDING_MODEL": ("EMBEDDING_MODEL", "text-embedding-3-small", False),
    "RERANK_BASE_URL": ("RERANK_BASE_URL", "", False),
    "RERANK_API_KEY": ("RERANK_API_KEY", "", True),
    "RERANK_MODEL": ("RERANK_MODEL", "BAAI/bge-reranker-v2-m3", False),
}

SETTINGS_KEYS = list(SETTINGS_SCHEMA)


def get(key: str) -> str:
    """生效值：DB 设置 > 环境变量 > 内置默认。"""
    env_name, default, _sensitive = SETTINGS_SCHEMA[key]
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row and row["value"] != "":
        return row["value"]
    return os.getenv(env_name, default)


def is_sensitive(key: str) -> bool:
    return SETTINGS_SCHEMA[key][2]


def source_of(key: str) -> str:
    """当前值来源：ui / env / default，用于界面标注。"""
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row and row["value"] != "":
        return "ui"
    env_name, _default, _s = SETTINGS_SCHEMA[key]
    return "env" if os.getenv(env_name) else "default"


def update(mapping: dict[str, str]) -> None:
    """保存设置；敏感字段传空串表示保持原值不变。"""
    with get_conn() as conn:
        for key, value in mapping.items():
            if key not in SETTINGS_SCHEMA:
                continue
            value = (value or "").strip()
            if is_sensitive(key) and value == "":
                continue  # 不清空已保存的密钥
            conn.execute(
                "INSERT INTO settings (key, value) VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )


def clear(key: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM settings WHERE key=?", (key,))


def mask(value: str) -> str:
    """sk-abcdef... -> sk-***cdef"""
    if not value:
        return ""
    if len(value) <= 8:
        return "***"
    return f"{value[:3]}***{value[-4:]}"
