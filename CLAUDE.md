# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## 项目概述

Arboris-Novel 是一个 AI 辅助小说创作平台，提供设定管理、AI 大纲生成、写作搭档、RAG 检索等功能。

**技术栈**: Python 3.10+ / FastAPI / SQLAlchemy 2.0 / Vue 3 / TypeScript / Tailwind CSS

## 架构概览

```
maker_novel/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/routers/        # API 路由
│   │   │   ├── admin.py        # 管理后台
│   │   │   ├── auth.py         # 认证授权
│   │   │   ├── llm_config.py   # LLM 配置
│   │   │   ├── novels.py       # 小说管理
│   │   │   ├── updates.py      # 更新日志
│   │   │   └── writer/         # 写作功能（核心）
│   │   │       ├── auto.py     # 自动化/连续创作
│   │   │       ├── chapter.py  # 章节生成与管理
│   │   │       ├── outline.py  # 大纲生成与管理
│   │   │       ├── review.py   # 评审与润色
│   │   │       └── common.py   # 写作路由通用逻辑
│   │   ├── core/               # 核心配置
│   │   │   ├── config.py       # 应用配置
│   │   │   ├── dependencies.py # 依赖注入
│   │   │   └── security.py     # 安全模块
│   │   ├── db/                 # 数据库层
│   │   │   ├── base.py         # 基础模型
│   │   │   ├── init_db.py      # 数据库初始化
│   │   │   ├── session.py      # 会话管理
│   │   │   └── system_config_defaults.py  # 系统配置默认值
│   │   ├── llm/                # LLM 适配层
│   │   │   ├── adapters/       # OpenAI 兼容适配器
│   │   │   │   ├── base.py     # 适配器基类
│   │   │   │   └── openai_compat.py  # OpenAI 兼容实现
│   │   │   ├── config.py       # 模型配置 (ModelFactory)
│   │   │   ├── encoding_fix.py # 编码修复
│   │   │   ├── hooks.py        # 日志钩子
│   │   │   └── structured_guard.py  # 结构化输出守卫
│   │   ├── models/             # ORM 模型
│   │   │   ├── admin_setting.py     # 管理设置
│   │   │   ├── llm_config.py        # LLM 配置
│   │   │   ├── novel.py             # 小说（核心）
│   │   │   ├── prompt.py            # 提示词
│   │   │   ├── system_config.py     # 系统配置
│   │   │   ├── update_log.py        # 更新日志
│   │   │   ├── usage_metric.py      # 使用指标
│   │   │   ├── user.py              # 用户
│   │   │   └── user_daily_request.py # 用户每日请求
│   │   ├── repositories/       # 数据仓库层
│   │   ├── schemas/            # Pydantic 模式
│   │   ├── services/           # 业务服务
│   │   │   ├── admin_setting_service.py   # 管理设置服务
│   │   │   ├── auth_service.py            # 认证服务
│   │   │   ├── chapter_context_service.py # 章节上下文服务
│   │   │   ├── chapter_ingest_service.py  # 章节摄入服务
│   │   │   ├── config_service.py          # 配置服务
│   │   │   ├── llm_service.py             # LLM 服务（核心）
│   │   │   ├── novel_service.py           # 小说服务（核心）
│   │   │   ├── prompt_service.py          # 提示词服务
│   │   │   ├── provider_service.py        # 模型提供方服务
│   │   │   ├── review_rewrite_service.py  # 评审重写服务
│   │   │   ├── update_log_service.py      # 更新日志服务
│   │   │   ├── usage_service.py           # 使用统计服务
│   │   │   ├── user_service.py            # 用户服务
│   │   │   └── vector_store_service.py    # 向量存储服务
│   │   └── utils/              # 工具函数
│   │       ├── json_utils.py   # JSON 工具
│   │       └── retry_utils.py  # 重试工具
│   ├── config/                 # 配置文件
│   │   └── models.yaml         # 模型配置
│   ├── db/                     # 数据库
│   │   └── schema.sql          # 数据库 Schema
│   ├── prompts/                # 提示词模板
│   │   ├── concept.md          # 概念提示词
│   │   ├── evaluation.md       # 评估提示词
│   │   ├── evaluation_detailed.md  # 详细评估提示词
│   │   ├── extraction.md       # 提取提示词
│   │   ├── outline.md          # 大纲提示词
│   │   ├── revision.md         # 修订提示词
│   │   ├── screenwriting.md    # 剧本提示词
│   │   └── writing.md          # 写作提示词
│   └── storage/                # 数据存储目录
│
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── api/                # API 接口层
│       │   ├── admin.ts        # 管理接口
│       │   ├── llm.ts          # LLM/模型接口
│       │   ├── novel.ts        # 小说接口
│       │   └── updates.ts      # 更新日志接口
│       ├── components/         # Vue 组件
│       │   ├── admin/          # 管理组件
│       │   ├── icons/          # 图标组件
│       │   ├── novel-detail/   # 小说详情
│       │   ├── shared/         # 共享组件
│       │   ├── writing-desk/   # 写作台
│       │   ├── BlueprintCard.vue        # 蓝图卡片
│       │   ├── ChapterList.vue          # 章节列表
│       │   ├── ChapterWorkspace.vue     # 章节工作区
│       │   ├── CharactersEditor.vue     # 角色编辑器
│       │   ├── ProviderManagement.vue   # 模型提供方管理
│       │   └── ...                      # 其他组件
│       ├── composables/        # Vue 组合式函数
│       │   └── useAlert.ts     # 弹窗组合函数
│       ├── views/              # 页面视图
│       │   ├── AdminView.vue        # 管理后台
│       │   ├── InspirationMode.vue  # 灵感模式
│       │   ├── Login.vue            # 登录
│       │   ├── Register.vue         # 注册
│       │   ├── NovelWorkspace.vue   # 小说工作区
│       │   ├── WritingDesk.vue      # 写作台
│       │   ├── SettingsView.vue     # 设置页面
│       │   └── WorkspaceEntry.vue   # 工作区入口
│       ├── stores/             # Pinia 状态
│       │   ├── auth.ts         # 认证状态
│       │   └── novel.ts        # 小说状态
│       ├── router/             # 路由配置
│       └── assets/             # 静态资源
│
├── deploy/                     # Docker 部署
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── docker-entrypoint.sh
│   ├── nginx.conf
│   ├── supervisord.conf
│   ├── README.md               # 部署文档
│   └── .env.example
│
└── logs/                       # 日志目录
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/register` | POST | 用户注册 |
| `/api/novels` | GET/POST | 小说列表/创建 |
| `/api/novels/{id}` | GET/PUT/DELETE | 小说详情 |
| `/api/novels/{id}/chapters` | GET/POST | 章节管理 |
| `/api/writer/generate` | POST | AI 生成内容 |
| `/api/admin/*` | * | 管理后台 |
| `/health` | GET | 健康检查 |

## 核心服务

| 服务 | 文件 | 职责 |
|------|------|------|
| NovelService | novel_service.py | 小说 CRUD、状态管理 |
| VectorStoreService | vector_store_service.py | RAG 向量存储检索 |
| LLMService | llm_service.py | LLM 调用、流式响应 |
| AuthService | auth_service.py | 用户认证、JWT |
| PromptService | prompt_service.py | 提示词管理 |

## 开发规范

- Python >= 3.10，UTF-8 编码
- 前端使用 Vue 3 + TypeScript + Tailwind CSS
- 数据库使用 SQLAlchemy 2.0 异步模式
- API 使用 FastAPI，Pydantic 校验
- 遵循 KISS/YAGNI/DRY 原则

## AI 协作技能 (SKILLs)

### 何时使用哪个

| Skill | 适用场景 |
|-------|----------|
| `collaborating-with-codex` | 后端逻辑、算法实现、复杂调试、代码评审；需要严格 sandbox 或图像输入 |
| `collaborating-with-gemini` | 前端/UI/CSS、创意构思、方案设计、文档编写（上下文 < 32k） |

### collaborating-with-codex

**Quick Start**:
```bash
python /root/.claude/skills/collaborating-with-codex/scripts/codex_bridge.py \
  --cd "<project_root>" --PROMPT "Your task"
```

**参数表**:

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--PROMPT` | 任务指令 | 必填 |
| `--cd` | 工作区根目录 | 必填 |
| `--sandbox` | `read-only` / `workspace-write` / `danger-full-access` | `read-only` |
| `--SESSION_ID` | 继续指定会话 | `None` |
| `--skip-git-repo-check` | 允许在非 Git 目录运行 | `False` |
| `--return-all-messages` | 返回全部消息（含推理/工具调用） | `False` |
| `--image` | 附加图片（多文件用逗号分隔或重复传入） | 可选 |
| `--yolo` | 跳过审批和 sandbox（仅当 sandbox 无法应用时） | `False` |
| `--model` | 指定模型（仅用户明确指定时允许） | 禁用 |
| `--profile` | 加载 `~/.codex/config.toml` 配置（仅用户明确指定时允许） | 禁用 |

**多轮会话**:
```bash
# 初次任务 - 获取 SESSION_ID
python .../codex_bridge.py --cd "<project_root>" --PROMPT "Analyze auth module"
# 继续对话
python .../codex_bridge.py --cd "<project_root>" --SESSION_ID "uuid-xxx" --PROMPT "Write tests"
```

### collaborating-with-gemini

**Quick Start**:
```bash
python /root/.claude/skills/collaborating-with-gemini/scripts/gemini_bridge.py \
  --cd "<project_root>" --PROMPT "Your task"
```

**参数表**:

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--PROMPT` | 任务指令 | 必填 |
| `--cd` | 工作区根目录 | 必填 |
| `--sandbox` | 启用 sandbox 模式 | `False` |
| `--SESSION_ID` | 继续指定会话 | 空字符串 |
| `--return-all-messages` | 返回全部消息（含推理/工具调用） | `False` |
| `--model` | 指定模型（仅用户明确指定时允许） | 禁用 |

**多轮会话**:
```bash
# 初次任务
python .../gemini_bridge.py --cd "<project_root>" --PROMPT "Design optimization plan"
# 继续对话
python .../gemini_bridge.py --cd "<project_root>" --SESSION_ID "uuid-xxx" --PROMPT "Detail API definitions"
```
