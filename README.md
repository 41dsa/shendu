# AI申论教练（智观申论）

Web-only · 爱发电买断 · BYOK · **V1 专注申论大作文 AI 批改**

产品基线：[`方案调研/产品需求-V1.2-大作文修订.md`](方案调研/产品需求-V1.2-大作文修订.md)（源自 PRD V1.2 PDF，题型改为大作文）

## 快速开始

### 1. 基础设施

```bash
cd /Users/houbx/Documents/code/shendu
docker compose up -d   # 本地 Postgres + Redis（可选；默认 SQLite 可不启）
cp services/api/.env.example services/api/.env
```

生产编排模板（需自行配置密钥与域名/HTTPS）：

```bash
docker compose -f docker-compose.prod.yml up -d --build
# 访问 http://localhost:8080 ，API 经 nginx /api 反代
```

### 2. 后端

```bash
cd services/api
python3 -m venv .venv   # 建议 Python 3.12/3.13；3.14 需较新 SQLAlchemy
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 默认 SQLite，无需 Docker
python scripts/init_db.py
uvicorn app.main:app --reload --port 8000
```

若终端里曾 export 过 `DATABASE_URL` 指向 Postgres，请先 `unset DATABASE_URL` 或改用 `services/api/.env` 中的 SQLite。

可选 Celery Worker（无 Redis 时会同步跑批改）：

```bash
celery -A app.worker.celery_app.celery_app worker -Q grading -l info
```

### 3. 前端

```bash
cd apps/web
npm install
npm run dev
```

浏览器打开 http://localhost:5173

## 验收路径（M1）

1. 注册 → 兑换激活码 `TEST-DEV-LICENSE` → 配置 DeepSeek（或 OpenAI 兼容）API Key → 测试连接  
2. 保存考试目标 → 批改页选择大作文题 → 撰写全文并提交批改 → 查看报告  

本地初始化：`python scripts/init_db.py`（占位题 + demo 参考题 `demo-essay-001`）。  
金标验收：`python scripts/seed_gold_cases.py`（QA-702 三例）。  
SQLite 备份：`bash scripts/backup_sqlite.sh`。

管理员：`.env` 设置 `BOOTSTRAP_ADMIN_EMAIL` 与注册邮箱一致 → `/admin/codes` 生成爱发电发货码  

## 目录

- `apps/web` — React 前端  
- `services/api` — FastAPI 后端  
- `方案调研/` — 技术选型  
- `开发计划及进度/` — 开发计划  
