# 考试标准引擎 — 纯 AI 运行手册（无人工教研）

依据 [产品决策-DEC.md](./开发进度/产品决策-DEC.md) **DEC-06～08**。

## 一条命令（联调 / CI）

```bash
cd services/api
source .venv/bin/activate
python scripts/init_db.py
alembic stamp head   # 首次

python scripts/run_pure_ai_pipeline.py --limit 21 --mode stub
```

产出：`mstd_e_ai_report.md`（含 M-STD-E-AI 判定）、题库 published standard、AI 金标、自洽标注 CSV。

## 生产质量（LLM + BYOK）

```bash
export STANDARD_GEN_MODE=llm
python scripts/run_pure_ai_pipeline.py \
  --limit 10 \
  --mode llm \
  --admin-email your-admin@example.com \
  --run-gold-regression
```

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `STANDARD_AI_ANNOTATION` | `1` | validated 后反写标注 |
| `STANDARD_AUTO_PUBLISH` | batch 脚本设 `1` | 自动发布 |
| `STANDARD_AUTO_PUBLISH_FORCE` | `1` | 忽略 0.85 门槛 |
| `STANDARD_GEN_MODE` | `auto` | `stub` / `llm` |

详见 [运维说明-标准引擎.md](./运维说明-标准引擎.md)。

## Admin API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/mstd-e-ai-milestone` | 里程碑 JSON |
| GET | `/admin/standards/annotation-metrics` | 自洽指标 |
| POST | `/admin/gold-samples/seed-ai?question_id=` | AI 金标三档 |

## 验收

```bash
python scripts/run_pure_ai_pipeline.py --limit 21 --mode stub
python scripts/verify_mstd_e_ai_milestone.py   # 里程碑（pipeline 之后）
python scripts/verify_std_e_suite.py             # 工程冒烟
```

清单：[验收清单-STD-E.md](./开发进度/验收清单-STD-E.md) **M-STD-E-AI**。

## CI

GitHub Actions：`.github/workflows/std-engine-ai.yml`（push/PR 触达 `services/api` 时跑 stub 流水线 + 里程碑 + 工程冒烟）。

## 边界

- 不对标官方阅卷；自洽率与 AI 金标均为 **系统自检**。
- 真题正文请自行合规入库；仓库 CSV 多为联调示例。
