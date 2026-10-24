"""Nano Dify Knowledge Lib —— 迷你知识库服务入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .bm25 import tokenizer_name as bm25_tokenizer_name
from .db import init_db
from .embedding import embedding_provider_name
from .rerank import rerank_provider_name
from .routers import datasets, documents, hit_testing, segments, settings

app = FastAPI(title="Nano Dify Knowledge Lib", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(documents.router)
app.include_router(segments.router)
app.include_router(hit_testing.router)
app.include_router(settings.router)


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "embedding_provider": embedding_provider_name(),
        "rerank_provider": rerank_provider_name(),
        "bm25_tokenizer": bm25_tokenizer_name(),
    }


@app.middleware("http")
async def no_cache_frontend(request, call_next):
    """前端静态资源与首页不缓存，保证发版后浏览器立即拿到新文件。"""
    resp = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


# ---- 前端静态资源（管理界面）----
if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.FRONTEND_DIR / "index.html")
