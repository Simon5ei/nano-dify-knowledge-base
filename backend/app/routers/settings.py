"""模型设置：界面可查看/修改 Embedding 与 Rerank 接入配置，附连接测试。"""
import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from .. import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    values: dict[str, str]


@router.get("")
def get_settings():
    """返回生效配置；敏感字段只返回脱敏提示，不回传明文。"""
    data = {}
    for key in settings_store.SETTINGS_KEYS:
        value = settings_store.get(key)
        item = {
            "value": "" if settings_store.is_sensitive(key) else value,
            "source": settings_store.source_of(key),   # ui / env / default
        }
        if settings_store.is_sensitive(key):
            item["is_set"] = bool(value)
            item["hint"] = settings_store.mask(value)
        data[key] = item
    return {"data": data}


@router.put("")
def update_settings(body: SettingsUpdate):
    settings_store.update(body.values)
    return get_settings()


@router.post("/test")
def test_connections(body: SettingsUpdate | None = None):
    """测试 Embedding / Rerank 连通性。

    body.values 里非空的项会临时覆盖已保存配置（测完不落库），方便保存前先验证。
    """
    overrides = {k: v for k, v in (body.values if body else {}).items() if v}

    def val(key: str) -> str:
        return overrides.get(key) or settings_store.get(key)

    result = {"embedding": _test_embedding(val), "rerank": _test_rerank(val)}
    return result


def _test_embedding(val) -> dict:
    base, key, model = val("EMBEDDING_BASE_URL"), val("EMBEDDING_API_KEY"), val("EMBEDDING_MODEL")
    if not base or not key:
        return {"ok": False, "detail": "未配置（当前使用本地 local-hash-256 兜底）"}
    try:
        resp = httpx.post(
            base.rstrip("/") + "/embeddings",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "input": ["连接测试"]},
            timeout=30,
        )
        resp.raise_for_status()
        dim = len(resp.json()["data"][0]["embedding"])
        return {"ok": True, "detail": f"{model} 可用，向量维度 {dim}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"连接失败：{str(e)[:200]}"}


def _test_rerank(val) -> dict:
    base, key, model = val("RERANK_BASE_URL"), val("RERANK_API_KEY"), val("RERANK_MODEL")
    if not base or not key:
        return {"ok": False, "detail": "未配置（当前使用本地 local-keyword 兜底）"}
    try:
        resp = httpx.post(
            base.rstrip("/") + "/rerank",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "query": "连接测试", "documents": ["测试文档一", "测试文档二"], "top_n": 2},
            timeout=30,
        )
        resp.raise_for_status()
        n = len(resp.json().get("results", []))
        return {"ok": True, "detail": f"{model} 可用，返回 {n} 条结果"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "detail": f"连接失败：{str(e)[:200]}"}
