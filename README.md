# Nano Dify Knowledge Lib

参考开源项目 [Dify](https://github.com/langgenius/dify) 的**知识库（Dataset）**模块，
独立实现的一个迷你版本：只包含知识库本身及其管理界面，单进程、零中间件、开箱即用。

> 本仓库为原创代码，不包含 Dify 源码。许可证与归属说明见下方 [许可证](#许可证)。

## 功能

- **知识库管理**：新建 / 重命名 / 删除知识库，配置分段长度与重叠
- **文档管理**：上传 `txt / md / pdf / docx`，自动解析、分段、向量化；支持重新索引与删除
- **分段管理**：查看分段内容、在线编辑（自动重新向量化）、启用 / 禁用、手动新增、删除，统计命中次数
- **召回测试**：输入问题即时检索，返回 TopK 命中分段、来源文档与相似度得分，支持得分阈值过滤
- **向量化可插拔**：
  - 配置 OpenAI 兼容接口（`EMBEDDING_BASE_URL` + `EMBEDDING_API_KEY` + `EMBEDDING_MODEL`）即用真实语义向量
  - 不配置时自动降级为本地 Hash Embedding（离线可跑通全流程，仅供演示）

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + SQLite（单文件库，无外部服务依赖） |
| 前端 | 原生 HTML / CSS / JS 管理界面，由后端直接托管 |
| 向量检索 | 余弦相似度（纯 Python 实现） |

## 快速开始

```bash
pip install -r backend/requirements.txt
python run.py
```

打开 <http://127.0.0.1:8000> 即可进入管理界面；API 文档见 <http://127.0.0.1:8000/docs>。

### 使用真实 Embedding 服务（可选）

```bash
# Windows PowerShell
$env:EMBEDDING_BASE_URL="https://api.openai.com/v1"
$env:EMBEDDING_API_KEY="sk-..."
$env:EMBEDDING_MODEL="text-embedding-3-small"
python run.py
```

## API 概览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET/POST | `/api/datasets` | 知识库列表 / 新建 |
| GET/PATCH/DELETE | `/api/datasets/{id}` | 详情 / 更新 / 删除 |
| GET | `/api/datasets/{id}/documents` | 文档列表 |
| POST | `/api/datasets/{id}/documents/upload` | 上传并索引文档 |
| POST | `/api/datasets/{id}/documents/{docId}/reindex` | 重新索引 |
| GET/POST | `/api/datasets/{id}/documents/{docId}/segments` | 分段列表 / 新增 |
| PATCH/DELETE | `.../segments/{segId}` | 编辑 / 启停 / 删除分段 |
| POST | `/api/datasets/{id}/hit-testing` | 召回测试 |

## 目录结构

```
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口，托管前端静态资源
│   │   ├── config.py        # 环境变量配置
│   │   ├── db.py            # SQLite 存储层
│   │   ├── parsing.py       # txt/md/pdf/docx 文本提取
│   │   ├── chunking.py      # 递归分隔符分段 + 重叠合并
│   │   ├── embedding.py     # OpenAI 兼容接口 / 本地 Hash 向量
│   │   ├── indexing.py      # 解析→分段→向量化→落库流水线
│   │   └── routers/         # datasets / documents / segments / hit_testing
│   └── requirements.txt
├── frontend/                # 管理界面（原生 HTML/CSS/JS）
├── licenses/LICENSE-dify    # Dify 官方许可证（归属参考）
├── LICENSE                  # Apache License 2.0（本项目）
├── NOTICE                   # 归属说明
└── run.py
```

## 与 Dify 的对应关系

| Dify 概念 | 本项目实现 |
|---|---|
| Dataset 知识库 | `datasets` 表 + 侧边栏管理 |
| Document 文档 | 上传解析 + 状态机（queuing/indexing/completed/error） |
| Segment 分段 | 可编辑、可启停、命中计数 |
| Hit Testing 召回测试 | `/hit-testing` 接口 + 测试面板 |
| 索引方式（高质量/经济） | OpenAI 兼容 Embedding / 本地 Hash Embedding |

## 许可证

本项目代码以 [Apache License 2.0](LICENSE) 发布。

产品概念参考自 [Dify](https://github.com/langgenius/dify)，Dify 由 LangGenius, Inc. 版权所有，
采用基于 Apache 2.0 修改的许可证（全文见 [licenses/LICENSE-dify](licenses/LICENSE-dify)）。
本项目未复制 Dify 源码，与其无任何隶属关系，详见 [NOTICE](NOTICE)。
