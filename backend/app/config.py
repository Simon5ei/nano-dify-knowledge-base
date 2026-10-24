"""全局配置：全部支持环境变量覆盖。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]          # backend/
PROJECT_DIR = BASE_DIR.parent                           # 项目根目录
DATA_DIR = Path(os.getenv("NDK_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DB_PATH := DATA_DIR / "nano_dify.db")  # noqa: B018
UPLOAD_DIR = DATA_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---- Embedding 提供方（OpenAI 兼容接口）----
# 不配置时自动降级为本地 HashEmbedding（离线可用，仅供演示/开发）
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "")   # 例: https://api.openai.com/v1
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ---- Rerank 提供方（Jina / Cohere / SiliconFlow / TEI 等 /rerank 兼容接口）----
# 不配置时召回测试的 rerank 走本地关键词重叠打分（离线可用，仅供演示）
RERANK_BASE_URL = os.getenv("RERANK_BASE_URL", "")        # 例: https://api.siliconflow.cn/v1
RERANK_API_KEY = os.getenv("RERANK_API_KEY", "")
RERANK_MODEL = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

# ---- 分段默认参数 ----
DEFAULT_CHUNK_SIZE = int(os.getenv("DEFAULT_CHUNK_SIZE", "500"))
DEFAULT_CHUNK_OVERLAP = int(os.getenv("DEFAULT_CHUNK_OVERLAP", "50"))
MAX_CHUNK_SIZE = 4000

FRONTEND_DIR = PROJECT_DIR / "frontend"
