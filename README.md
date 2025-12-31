# Arboris-Novel | AI 辅助小说创作平台

> 给写小说的人，一个有意思的写作空间

**在线体验：** [https://arboris.aozhiai.com](https://arboris.aozhiai.com)

---

## 功能特性

- **设定管理** - 角色、地点、派系、关系，世界观设定，防止前后矛盾
- **灵感模式** - 和 AI 聊聊想法，梳理出完整故事线和大纲
- **写作搭档** - 多模型并行生成候选版本，支持版本对比、评估与润色
- **章节工作台** - 章节大纲编辑、内容生成、多版本管理
- **模型管理** - 自定义 LLM Provider，支持 OpenAI API / Ollama 本地模型
- **RAG 检索** - 基于向量存储的上下文检索，确保内容一致性
- **用户系统** - 完整的认证授权、管理后台、使用量统计

---

## 本地启动

### 1. 后端启动

```bash
cd backend

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 创建 .env 配置文件
cp env.example .env
```

**编辑 .env 文件，必须配置以下项：**

```bash
# 必填：JWT 密钥（随机字符串）
SECRET_KEY=your-random-secret-key-here

# 必填：使用 SQLite（默认是 MySQL，必须显式指定）
DB_PROVIDER=sqlite

# 必填：LLM API Key
OPENAI_API_KEY=sk-xxx

# 可选：修改管理员密码（默认 ChangeMe123!）
ADMIN_DEFAULT_PASSWORD=YourPassword123
```

**启动后端服务：**

```bash
# 在 backend 目录下运行
uvicorn app.main:app --reload --host 0.0.0.0 --port 9527
```

### 2. 前端启动

```bash
cd frontend

# 安装依赖（需要 Node.js >= 20.19.0 或 >= 22.12.0）
npm install

# 启动开发服务器
npm run dev
```

### 3. 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3456 |
| 后端 API | http://127.0.0.1:9527 |
| API 文档 | http://127.0.0.1:9527/docs |
| 健康检查 | http://127.0.0.1:9527/health |

### 4. 首次登录

系统首次启动会自动创建管理员账号：
- 用户名：`admin`
- 密码：`.env` 中的 `ADMIN_DEFAULT_PASSWORD`（默认 `ChangeMe123!`）

---

## 配置说明

### 必填配置

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `SECRET_KEY` | JWT 加密密钥 | 随机字符串 |
| `DB_PROVIDER` | 数据库类型 | `sqlite` 或 `mysql` |
| `OPENAI_API_KEY` | LLM API Key | `sk-xxx` |

### 数据库配置

**SQLite（推荐本地开发）：**
```bash
DB_PROVIDER=sqlite
# 数据库自动存储在 backend/storage/arboris.db
```

**MySQL：**
```bash
DB_PROVIDER=mysql
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=xxx
MYSQL_DATABASE=arboris
```

### RAG 向量检索配置（可选）

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
VECTOR_DB_URL=file:./storage/rag_vectors.db
```

---

## 项目结构

```
maker_novel/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/routers/        # API 路由
│   │   ├── core/config.py      # 配置加载（.env）
│   │   ├── db/                 # 数据库层
│   │   ├── llm/                # LLM 适配层
│   │   ├── models/             # ORM 模型
│   │   ├── services/           # 业务服务
│   │   └── main.py             # 应用入口
│   ├── storage/                # SQLite 数据库目录
│   ├── prompts/                # 提示词模板
│   ├── env.example             # 环境变量示例
│   └── requirements.txt
│
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── api/                # API 接口
│       ├── components/         # Vue 组件
│       ├── views/              # 页面视图
│       └── stores/             # Pinia 状态
│
├── deploy/                     # Docker 部署
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── README.md               # 部署文档
│
└── logs/                       # 日志目录
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI 0.110 / SQLAlchemy 2.0 / Pydantic 2.x |
| 前端 | Vue 3.5 / TypeScript 5.8 / Tailwind CSS 4.x / Naive UI / Pinia 3.x / Vite 7.x |
| 数据库 | SQLite (aiosqlite) / MySQL (asyncmy) |
| LLM | OpenAI API / Ollama (本地模型) |
| 向量存储 | libsql (RAG) / langchain-text-splitters |
| 部署 | Docker / Docker Compose / Nginx / Supervisor |

---

## 常见问题

### Q1: 启动报错 `SECRET_KEY` 未配置

确保 `.env` 文件在 `backend/` 目录下，且包含 `SECRET_KEY=xxx`

### Q2: 数据库连接失败

检查 `DB_PROVIDER` 是否设置为 `sqlite`，以及 `storage/` 目录是否存在

### Q3: 前端无法连接后端

确保后端运行在 `http://127.0.0.1:9527`，前端开发模式会自动代理到该地址

---

## 致谢

本项目基于 [arboris-novel](https://github.com/t59688/arboris-novel) 进行二次开发，感谢原作者 [@t59688](https://github.com/t59688) 的开源贡献。

## 许可证

MIT License
