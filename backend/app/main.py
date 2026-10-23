"""Nano Dify Knowledge Lib —— 迷你知识库服务入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db import init_db
from .routers import datasets, documents, hit_testing, segments

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


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "embedding_provider": (
            config.EMBEDDING_MODEL if config.EMBEDDING_BASE_URL and config.EMBEDDING_API_KEY else "local-hash-256"
        ),
    }


# ---- 前端静态资源（管理界面）----
if config.FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=config.FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.FRONTEND_DIR / "index.html")
