# ============================================
# 单阶段构建：后端 + nginx（前端需本地预构建）
# ============================================
# 使用方法：
#   1. 本地执行: cd frontend && npm run build-only
#   2. 然后执行: docker compose build
# ============================================
FROM python:3.11-slim

# 配置 apt 使用中国镜像源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|security.debian.org/debian-security|mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources

WORKDIR /app

# 安装系统依赖：nginx、supervisor、curl、mysql客户端、时区数据等
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    nginx \
    supervisor \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 配置 pip 使用中国镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端依赖文件
COPY backend/requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端应用代码
COPY backend/ ./

# 保留种子数据到 /app/storage-seed，用于首次启动时初始化
RUN mv /app/storage /app/storage-seed || mkdir -p /app/storage-seed
RUN mkdir -p /app/storage

# 保留提示词模板到 /app/prompts-seed，用于首次启动时初始化
RUN mv /app/prompts /app/prompts-seed || mkdir -p /app/prompts-seed
RUN mkdir -p /app/prompts

# 从本地预构建的 dist 目录复制静态资源
COPY frontend/dist /usr/share/nginx/html

# 复制部署配置
COPY deploy/nginx.conf /etc/nginx/sites-available/default
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

# 允许入口脚本在启动时修正宿主机挂载目录权限
RUN chmod +x /app/docker-entrypoint.sh

# 创建非 root 用户（供 supervisor 使用）
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# 暴露端口（nginx 80端口）
EXPOSE 80

# 使用 supervisor 启动 nginx 和 uvicorn
# 注意：容器以 root 启动，supervisor 会根据配置降权运行各个进程
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
