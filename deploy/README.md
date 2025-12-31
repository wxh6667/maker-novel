# Docker 部署指南

## 快速启动

```bash
# 1. 本地构建前端（开发机上执行）
cd frontend && npm run build-only

# 2. 复制环境变量配置
cd deploy && cp .env.example .env

# 3. 编辑 .env，至少修改以下必填项
#    - SECRET_KEY（安全密钥）
#    - OPENAI_API_KEY（LLM API密钥）

# 4. 构建并启动服务
docker compose up -d --build
```

> **注意**：前端需要在本地预构建，Docker 只负责后端和部署。

## 数据持久化

| 宿主机路径 | 容器路径 | 说明 |
|------------|----------|------|
| `./data/` | `/app/storage` | SQLite 数据库、向量数据库 |
| `./prompts/` | `/app/prompts` | 提示词模板（可自定义） |
| `./logs/` | `/app/logs` | 应用日志 |

**首次启动**：自动从镜像初始化种子数据

**后续启动**：使用已有数据，不会覆盖

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 停止服务
docker compose down

# 更新代码并重新构建
git pull && docker compose up -d --build

# 使用 MySQL（可选）
docker compose --profile mysql up -d --build
```

## 环境变量

### 必填配置

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | JWT 安全密钥 |
| `OPENAI_API_KEY` | LLM API 密钥 |

### 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_PORT` | 7526 | 服务端口 |
| `DB_PROVIDER` | sqlite | 数据库类型 (sqlite/mysql) |
| `ADMIN_DEFAULT_PASSWORD` | ChangeMe123! | 管理员初始密码 |
| `EMBEDDING_PROVIDER` | openai | 向量嵌入提供方 |
| `TZ` | Asia/Shanghai | 时区 |

### Ollama 本地模型

```bash
OLLAMA_EMBEDDING_BASE_URL=http://host.docker.internal:11434
OLLAMA_EMBEDDING_MODEL=nomic-embed-text:latest
```

### 自定义路径

```bash
STORAGE_PATH=/your/data/path
PROMPTS_PATH=/your/prompts/path
LOG_PATH=/your/logs/path
```
