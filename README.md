# AI 申论教练（智观申论）

Web-only · 爱发电买断 License + BYOK · **V1 专注申论大作文 AI 批改与诊断**

学员自带题干、材料与正文，系统给出能对上原句的分项诊断；教研用同一套模型起草评分标准，人工审核后发布。它不是官方阅卷，也不是聊天窗口外包一层登录：批改走可审计的评分流水线，模型不直接决定总分。

- 产品基线：[`方案调研/产品需求-V1.2-大作文修订.md`](方案调研/产品需求-V1.2-大作文修订.md)
- 标准引擎文档：[`AI考试标准引擎/README.md`](AI考试标准引擎/README.md)
- 架构与模块：[`开发计划及进度/架构与模块说明.md`](开发计划及进度/架构与模块说明.md)

---

## 功能概览

### 学员端

| 模块 | 能力 |
|------|------|
| 账号 | 注册 / 登录，JWT 鉴权；未激活 License 时拦截批改 |
| 购买与激活 | 爱发电外链购买；站内兑换激活码（`POST /redeem`） |
| AI 设置 | BYOK，OpenAI 兼容接口；主模型 / 共识 / 第三评审 / Embedding 四个槽位，Key 用 AES-GCM 加密存储，支持测试连接 |
| 考试目标 | 记录考试级别与卷别，用于推荐题目与自备题评分口径 |
| 大作文批改 | 题库选题或「自备题干与材料」；可粘贴/导入给定材料；异步任务 + 进度轮询；字数校验与过短短路 |
| 批改报告 | 维度得分、问题标签、原句证据、修改建议、评分依据、改写示范 |
| 二次作答 | 基于报告重写并重新批改，对比问题改善与等级变化 |
| 能力画像 / 问题本 | 聚合历史报告，按能力维与问题标签汇总 |
| 首页 / 我的 | 能力概览、重点问题、推荐题目、最近批改与账号信息 |

### 教研后台（管理员）

| 模块 | 能力 |
|------|------|
| 标准生产 | 上传资料 → 分步生成标准卡 → 置信度/共识校验 → 人工审核 → 发布版本 |
| 题库与 Prompt | 大作文题目管理、评分 Prompt 版本管理与激活 |
| 金标与回归 | 金标样本、重跑回归、查看评分漂移 |
| 争议 | 学员提交异议、管理员查看与 CSV 导出（AI 复核按钮为占位） |
| 锚作文 | 锚作文上传、人工标注，提供相对尺度参照 |
| 难例池 | 按分歧、贴边、重写跳变自动入池，可导出用于后续迭代 |
| 运维 | 标准/批改任务列表、激活码生成、埋点事件 |

### 评分引擎

- **先定标准，再评分**：标准引擎回答「这道题应怎么评」，评价引擎回答「这篇写得怎么样」。
- **规则预评 + 模型诊断**：字数、过短、机械摘抄等硬规则可短路；立意、结构、论证、语言由模型按 Trait 输出等级与原文证据。
- **可追溯**：低置信时只显示等级，不显示精确总分；报告展示评分依据与标准版本。
- **可选增强**：双路复核（总分二次检验）、多模型投票、Embedding 语义匹配。只配置一把 Key 时投票会重复调用同一模型，不等同于独立三评。

---

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | React 18、TypeScript、Ant Design 5、React Router 6、TanStack Query、Vite 6 |
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2、Pydantic v2、Alembic |
| 存储 | 开发默认 SQLite；生产 PostgreSQL 16 |
| 异步 | 进程内线程（开发默认）或 Redis + Celery（`grading` / `standards` 队列） |
| 模型 | 用户自配 OpenAI 兼容 `chat/completions` 与 `embeddings`，平台不代付模型费用 |
| 部署 | Docker Compose、Nginx（子路径 `/shendu/`）、可选 HTTPS |

---

## 目录结构

```text
.
├── apps/web/                  # React 前端
│   ├── src/pages/             # 学员页面 + admin/ 教研后台
│   ├── src/api/client.ts      # 统一请求前缀 /shendu/api
│   └── vite.config.ts         # base=/shendu/，开发代理到 127.0.0.1:8000
├── services/api/              # FastAPI 后端
│   ├── app/routers/           # auth/license/ai/exam/questions/submissions/grading/coach/admin
│   ├── app/services/          # 批改编排、标准生产、改写示范、Embedding、难例池
│   ├── app/domain/scoring_engine/   # Trait 诊断与规则引擎
│   ├── app/domain/standard_engine/  # 标准卡校验、置信度、一致率
│   ├── scripts/               # 初始化、导入、验收与冒烟脚本
│   └── data/                  # 镜像内置 Prompt / Rubric / 题库 CSV
├── data/                      # 标准资料、标注模板、写作技巧参考
├── deploy/                    # nginx 配置、HTTPS、日志说明、ECS 启动脚本
├── 方案调研/                  # 产品需求与技术选型
├── 开发计划及进度/            # 计划、验收清单、架构说明
├── AI考试标准引擎/            # 标准引擎规划、契约、路线图与运维说明
├── docker-compose.yml         # 本地 Postgres + Redis（可选）
├── docker-compose.prod.yml    # 生产编排
└── docker-compose.https.yml   # HTTPS 叠加配置
```

---

## 快速开始（本地开发）

### 环境要求

- Python 3.12 / 3.13（依赖已按 3.12 锁定）
- Node.js 20+（构建镜像使用 Node 22）
- Docker 可选：仅在使用 PostgreSQL / Redis 时需要

### 1. 可选：启动基础设施

默认 SQLite 开箱即用，无需 Docker：

```bash
docker compose up -d          # Postgres 5432 + Redis 6379
```

如使用 Postgres，在 `services/api/.env` 中修改 `DATABASE_URL`。

### 2. 启动后端

```bash
cd services/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # 默认 sqlite:///./shendu_dev.db
python scripts/init_db.py     # 建表 + 轻量迁移 + 种子数据
uvicorn app.main:app --reload --port 8000
```

- API：<http://localhost:8000>
- 健康检查：<http://localhost:8000/health>
- 接口文档：<http://localhost:8000/docs>

若终端里 export 过 `DATABASE_URL` 指向 Postgres，请先 `unset DATABASE_URL`，或确认 `services/api/.env` 中的配置。

可选 Celery Worker（未启用时开发环境在 API 进程内起线程同步跑批改）：

```bash
export GRADING_USE_CELERY=1
celery -A app.worker.celery_app.celery_app worker -Q grading,standards -l info
```

### 3. 启动前端

```bash
cd apps/web
npm install
npm run dev
```

打开 **<http://localhost:5173/shendu/>**（前端 `base` 为 `/shendu/`，访问根路径会 404）。开发服务器把 `/shendu/api` 代理到 `http://127.0.0.1:8000`。

### 4. 首次使用流程

1. 注册账号。
2. 进入「购买/激活」，兑换开发测试码 `TEST-DEV-LICENSE`（由 `init_db.py` 写入）。
3. 在「AI 设置」填写主模型 API Key、Base URL 与模型名，点击「测试连接」。
4. 在「考试目标」选择目标卷别。
5. 进入「批改」，选题库题目或自备题干/材料，提交全文并查看报告。
6. 在报告中查看证据与建议，或进入「二次作答」重写对比。

### 5. 管理员

注册前在 `services/api/.env` 设置 `BOOTSTRAP_ADMIN_EMAIL`，用该邮箱注册即成为管理员。管理员默认进入 `/admin` 教研后台；侧栏「体验用户端」保留批改、报告、AI 设置、我的四个验货入口。

---

## 常用脚本

均在 `services/api` 目录、激活虚拟环境后执行：

| 脚本 | 用途 |
|------|------|
| `python scripts/init_db.py` | 建表、轻量列迁移、写入 demo 题与测试激活码 |
| `python scripts/seed_gold_cases.py` | 写入 QA-702 金标验收样例 |
| `python scripts/seed_standard_essay_batch.py` | 导入内置大作文题库 CSV |
| `python scripts/import_essay_writing_guide.py` | 导入写作技巧参考（自备题增强） |
| `python scripts/seed_reference_documents.py` | 导入标准引擎参考文档 |
| `python scripts/run_pure_ai_pipeline.py --limit 21 --mode stub` | 纯 AI 标准生产流水线（联调/CI） |
| `python scripts/reconcile_stale_grading_jobs.py` | 回收卡住的批改任务 |
| `bash scripts/backup_sqlite.sh` | 备份开发 SQLite |
| `bash scripts/backup_postgres.sh` | 备份生产 PostgreSQL（需 compose 已启动） |

质量与验收脚本（`scripts/verify_*.py`）：

```bash
python scripts/verify_std_e_suite.py        # 标准引擎工程冒烟
python scripts/verify_prd_v1_compliance.py  # PRD V1 诊断教练合规检查
python scripts/verify_prod_eval_alignment.py
```

仓库当前以 `verify_*.py` 脚本做冒烟与验收，尚未引入 pytest 套件。CI 配置见 [`.github/workflows/std-engine-ai.yml`](.github/workflows/std-engine-ai.yml)。

---

## 生产部署

### Docker Compose

```bash
# 1. 准备后端环境变量
cp services/api/.env.example services/api/.env
#    必须修改 JWT_SECRET / MASTER_KEY；设置 BOOTSTRAP_ADMIN_EMAIL、AFDIAN_PLAN_URL

# 2. 准备根目录 .env（供 compose 使用）
cat > .env <<'EOF'
POSTGRES_PASSWORD=<强密码>
PUBLIC_ORIGIN=https://your.domain
EOF

# 3. 首次部署需创建 compose 引用的外部网络
docker network create docker_default   # 已存在可忽略

# 4. 构建并启动
docker compose -f docker-compose.prod.yml up -d --build
```

当前 `docker-compose.prod.yml` 将 Web 映射为 **8081 → 80**，访问地址为：

```text
http://<服务器地址>:8081/shendu/
```

API 容器启动时 `RUN_INIT_DB=1`，会等待数据库就绪并执行 `init_db.py`；Worker 同时消费 `grading` 与 `standards` 队列。

### HTTPS

将证书放到 `deploy/certs/`：

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

叠加 HTTPS 编排（该覆盖会把发布端口替换为 443）：

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.https.yml up -d
# 访问 https://<域名>/shendu/
```

Nginx 配置见 [`deploy/nginx.conf`](deploy/nginx.conf) 与 [`deploy/nginx.https.conf`](deploy/nginx.https.conf)。

### 阿里云 ECS 一键脚本

```bash
sudo bash deploy/ecs-up.sh --email you@example.com --origin http://<公网IP>
```

脚本会安装 Docker、生成根目录 `.env` 与 `services/api/.env`，并启动生产编排。注意：脚本按 80 端口回显访问地址，而当前 compose 固定映射 8081；如需 80/443，请调整 `docker-compose.prod.yml` 的 `web.ports` 或叠加 HTTPS 配置。大陆地域使用域名对外提供网站前需完成 ICP 备案。

### 备份与日志

- SQLite：`bash services/api/scripts/backup_sqlite.sh`
- PostgreSQL：`bash services/api/scripts/backup_postgres.sh`
- 日志脱敏要求见 [`deploy/LOGGING.md`](deploy/LOGGING.md)：禁止输出 API Key、JWT、作文全文与题干全文。

---

## 关键环境变量

后端同时读取仓库根目录 `.env` 与 `services/api/.env`（见 `app/config.py`）。同名变量请只在一处设置，避免加载顺序造成覆盖。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./shendu_dev.db` | 开发 SQLite；生产为 `postgresql+psycopg://...` |
| `REDIS_URL` | `redis://localhost:6379/0` | Celery broker / backend |
| `JWT_SECRET` | 开发占位值 | 生产必须替换，至少 32 字符 |
| `MASTER_KEY` | 开发占位值 | AES-GCM 加密用户 API Key，生产必须替换 |
| `CORS_ORIGINS` | `http://localhost:5173` | 逗号分隔的允许来源 |
| `APP_ENV` | `development` | `development` 时批改默认走进程内线程 |
| `BOOTSTRAP_ADMIN_EMAIL` | 空 | 该邮箱注册后自动获得管理员权限 |
| `AFDIAN_PLAN_URL` | 爱发电首页 | 「购买」页外链地址 |
| `MAX_CONCURRENT_GRADING_JOBS_PER_USER` | `2` | 单用户并发批改上限 |
| `GRADING_USE_CELERY` | 未设置 | 设为 `1` 时强制入 Celery 队列 |
| `RUN_INIT_DB` | `0` | 容器启动时是否执行 `init_db.py`（生产 API 设为 `1`） |
| `EMBEDDING_ENABLED` | `true` | 是否启用 Embedding 语义匹配 |
| `EMBEDDING_API_URL` / `EMBEDDING_MODEL` | 空 / `bge-base-zh` | Embedding 服务地址与模型 |

更多评分/标准引擎开关见 `services/api/app/config.py` 与 [`AI考试标准引擎/运维说明-标准引擎.md`](AI考试标准引擎/运维说明-标准引擎.md)。

---

## 架构与批改主流程

```text
React (apps/web, /shendu/)
        │  /shendu/api  (Nginx 反代或 Vite proxy)
        ▼
FastAPI (services/api)
        │
        ├── SQLite / PostgreSQL
        ├── 进程内线程 或 Redis + Celery (grading / standards)
        └── 用户 BYOK → OpenAI 兼容 chat/completions
```

一次批改：

```text
POST /submissions → POST /submissions/{id}/grade → enqueue_grading_job
→ 规则预评 / Trait 诊断 / 可选投票与双路复核 → Report
→ 前端轮询 GET /grading-jobs/{id} → GET /reports/{id}
```

主要接口分组：`/auth`、`/license`、`/ai`、`/exam`、`/questions`、`/submissions`、`/grading`、`/coach`、`/admin/*`。

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [`方案调研/产品需求-V1.2-大作文修订.md`](方案调研/产品需求-V1.2-大作文修订.md) | 产品需求基线（大作文修订版） |
| [`方案调研/技术选型文档.md`](方案调研/技术选型文档.md) | 技术选型 |
| [`开发计划及进度/架构与模块说明.md`](开发计划及进度/架构与模块说明.md) | 逻辑架构、领域边界、目录约定 |
| [`开发计划及进度/前后端开发计划.md`](开发计划及进度/前后端开发计划.md) | 开发计划与阶段 |
| [`AI考试标准引擎/README.md`](AI考试标准引擎/README.md) | 标准生产与评测引擎总览 |
| [`AI考试标准引擎/开发架构与技术选型.md`](AI考试标准引擎/开发架构与技术选型.md) | 标准引擎架构与双引擎设计 |
| [`AI考试标准引擎/数据契约-V0.1-大作文.md`](AI考试标准引擎/数据契约-V0.1-大作文.md) | 标准字段级数据契约 |
| [`AI考试标准引擎/Prompt契约-V0.1-大作文.md`](AI考试标准引擎/Prompt契约-V0.1-大作文.md) | 分职责 Prompt 契约 |
| [`data/standards/README.md`](data/standards/README.md) | 题库导入、标注与批量标准生产 |
| [`deploy/LOGGING.md`](deploy/LOGGING.md) | 日志与脱敏规范 |

---

## 已知边界

- 仅支持申论大作文；归纳概括、综合分析、提出对策等小题不在 V1 范围。
- 不提供站内支付、OCR、移动端 App、平台统一模型 Key 或真人批改。
- 争议页的「AI 复核」当前为占位，不调用模型。
- 只配置一把模型 Key 时，多模型投票会重复请求同一 Key，不能视为独立多模型共识。
- 开发环境默认 SQLite；生产切换 PostgreSQL 后请使用 `backup_postgres.sh` 备份。
