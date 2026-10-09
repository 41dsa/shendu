# 验收通知 — STD-P1 工程底座（批次）

| 项目 | 内容 |
|------|------|
| 状态 | **已通过**（2026-10-09） |
| 完成日期 | 2026-10-09 |
| 范围 | STD-101～110；另含 STD-201、202、208、209 起步 |

---

## STD-101 领域模块 `domain/standard_engine`

**交付**：置信度加权、M6 规则验证器。

**验收**：

```bash
cd services/api && .venv/bin/python scripts/verify_standard_engine.py
```

---

## STD-102 Pydantic 契约

**交付**：`app/schemas/standard_engine.py`（Document、QuestionStandard、RubricStandard 等）。

**验收**：同上脚本；或 import `QuestionStandardSchema` 无报错。

---

## STD-103 数据模型

**交付**：`standard_documents`、`standard_generation_jobs`、`standard_job_steps`、`exam_question_standards`；`PromptPurpose.standard_p01`～`p07`。

**验收**：

```bash
cd services/api && .venv/bin/python scripts/init_db.py
```

重启 API 后表自动 `create_all`。

---

## STD-104 / STD-105 Prompt 枚举与种子

**交付**：`prompt_defaults.py`；`init_db.py` → `seed_standard_prompts()`。

**验收**：DB 中 `prompt_versions` 含 `standard_p01` 等 7 条（可 SQL 或 Admin 后续页查看）。

---

## STD-106 / STD-107 流水线与 Celery

**交付**：`pipeline.py`（ingest→validate）；`worker/tasks.run_standard_generation_task`。

**验收**：

```bash
cd services/api && .venv/bin/python -c "
from app.database import SessionLocal
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, Question
from app.services.standard_engine.pipeline import run_standard_generation_job
db = SessionLocal()
job = StandardGenerationJob(question_id='demo-essay-001', status=StandardGenerationJobStatus.pending)
db.add(job); db.commit(); db.refresh(job)
run_standard_generation_job(db, job.id)
db.refresh(job)
print(job.status.value, job.error_message)
db.close()
"
```

期望：`validated` 且 `error_message` 为 `None`。

---

## STD-108 库表迁移策略

**交付**：沿用 `Base.metadata.create_all` + `init_db.py`（与主站 DEC-05 一致，未单独 Alembic revision）。

**验收**：新库跑 `init_db` 后 SQLite/PG 存在上述四表。

---

## STD-109 单元冒烟

**交付**：`scripts/verify_standard_engine.py`。

**验收**：输出 `verify_standard_engine: ok`。

---

## STD-110 解析依赖

**交付**：`requirements.txt` 增加 pymupdf、python-docx、beautifulsoup4（M2 实现 STD-204 时使用）。

**验收**：`.venv/bin/pip install -r requirements.txt` 成功。

---

## 附加（STD-P2 起步）

| ID | 交付 | 验收 |
|----|------|------|
| STD-201 | `data/standards/README.md` | 阅读目录规范 |
| STD-202 | `POST/GET /admin/standards/documents` | 见下 HTTP |
| STD-208 | `POST /admin/standards/jobs` | 见下 HTTP |
| STD-209 | `GET /admin/standards/jobs`、`.../jobs/{id}` | 见下 HTTP |

### Admin HTTP 验收（需管理员 JWT）

1. 启动 API：`uvicorn app.main:app --reload`（`services/api` 目录）。
2. 管理员登录（`BOOTSTRAP_ADMIN_EMAIL` 与注册邮箱一致）。
3. 创建资料：

```http
POST /admin/standards/documents
{"title":"2024国考说明","source_level":"S","content":"…"}
```

4. 创建标准任务：

```http
POST /admin/standards/jobs
{"question_id":"demo-essay-001","document_ids":[]}
```

5. 轮询 `GET /admin/standards/jobs/{id}` 直至 `status` 为 `validated`，`steps` 含 6 步。

---

## 结论栏（请你填写）

- [x] STD-P1 全部通过  
- [ ] 需修改：___________
