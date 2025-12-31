#!/bin/sh

set -e

STORAGE_DIR="${STORAGE_DIR:-/app/storage}"
STORAGE_SEED_DIR="/app/storage-seed"
PROMPTS_DIR="${PROMPTS_DIR:-/app/prompts}"
PROMPTS_SEED_DIR="/app/prompts-seed"

# 初始化目录的通用函数
init_dir_from_seed() {
    local target_dir="$1"
    local seed_dir="$2"
    local name="$3"

    # 确保目标目录存在
    if [ ! -d "$target_dir" ]; then
        mkdir -p "$target_dir"
    fi

    # 首次启动：如果目标目录为空，从种子目录复制初始数据
    if [ -d "$seed_dir" ] && [ "$(ls -A "$seed_dir" 2>/dev/null)" ]; then
        file_count=$(find "$target_dir" -type f ! -name '.gitkeep' 2>/dev/null | wc -l)
        if [ "$file_count" -eq 0 ]; then
            echo "首次启动：从种子目录初始化${name}..."
            cp -r "$seed_dir"/* "$target_dir"/ 2>/dev/null || true
            echo "${name}初始化完成"
        else
            echo "检测到已有${name}数据，跳过初始化"
        fi
    fi

    # 修正目录权限
    if [ "$(stat -c %u "$target_dir" 2>/dev/null || echo)" != "1000" ] || \
       [ "$(stat -c %g "$target_dir" 2>/dev/null || echo)" != "1000" ]; then
        chown -R appuser:appuser "$target_dir" || echo "Warning: unable to adjust ownership of $target_dir"
    fi
}

# 初始化 storage 目录
init_dir_from_seed "$STORAGE_DIR" "$STORAGE_SEED_DIR" "存储"

# 初始化 prompts 目录
init_dir_from_seed "$PROMPTS_DIR" "$PROMPTS_SEED_DIR" "提示词"

exec "$@"
