# 产品决策记录（考试标准引擎）

| 日期 | 2026-10-09 |
| 状态 | **V0.1-E 默认采纳**（可后续修订） |

| ID | 决策 | 结论 |
|----|------|------|
| DEC-01 | 架构/契约审验 | **通过**（随各阶段验收通过闭合） |
| DEC-02 | 标准生成 BYOK | **仅 Admin** 创建 job 时使用 `created_by_user_id` 对应账号的主模型；学员端不可触发标准生成 |
| DEC-03 | 发布门槛 confidence | **维持 0.85**；Admin UI 提供 **强制发布**（`?force=true`） |
| DEC-04 | Prompt 06 | **合并主批改**（`focus_points` / `loss_rules` / `standard_version` 注入 user JSON） |
| DEC-05 | 数据库迁移 | **双轨**：开发仍 `init_db`；**V0.2 起 Alembic 基线**（`services/api/alembic`，`001_baseline` stamp）。生产切 `upgrade head` 前需 autogenerate 增量 revision |
| DEC-06 | 标准质量与验收 | **纯 AI、无人工教研**：`questions_for_labeling.csv` 由 **`STANDARD_AI_ANNOTATION=1`（默认）** 在 job `validated` 后反写；STD-704 指标为 **自洽率**，非对标官方金标准。M-STD-E 采用 **M-STD-E-AI**（工程冒烟 + 自洽 + 发布数） |
| DEC-07 | 发布 | **可选无人值守发布**：`STANDARD_AUTO_PUBLISH=1`；低于门槛时用 **`STANDARD_AUTO_PUBLISH_FORCE=1`**（等同 Admin 强制发布，无人工点击） |
| DEC-08 | 金标回归 | **AI 生成金标**（`seed_ai_gold.py` 高/中/低 + 期望分区间）；`run_ai_gold_regression.py` 用 BYOK 跑批改回归。期望分来自 Rubric 总分档位，非人工标分 |
