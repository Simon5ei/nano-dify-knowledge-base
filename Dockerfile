FROM python:3.11-slim

WORKDIR /app

# 可选构建参数：指定 PyPI 镜像加速依赖安装
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple .
ARG PIP_INDEX_URL=""
COPY backend/requirements.txt ./backend/requirements.txt
RUN if [ -n "$PIP_INDEX_URL" ]; then pip config set global.index-url "$PIP_INDEX_URL"; fi \
    && pip install --no-cache-dir -r backend/requirements.txt

COPY backend ./backend
COPY frontend ./frontend
COPY run.py ./run.py

EXPOSE 8000
CMD ["python", "run.py"]
