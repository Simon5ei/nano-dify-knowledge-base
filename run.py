"""启动入口：python run.py 然后访问 http://127.0.0.1:8000

HOST/PORT 可用环境变量覆盖；容器内必须监听 0.0.0.0 才能被端口映射访问。
"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
