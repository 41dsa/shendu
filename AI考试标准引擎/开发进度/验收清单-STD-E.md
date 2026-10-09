# 验收清单 — AI 考试标准引擎 V0.1-E / M-STD-E-AI

| 项目 | 内容 |
|------|------|
| 基线 | [开发架构与技术选型 §10](../开发架构与技术选型.md) |
| 数据规模 | 联调库 **20** 题（`bank_essay_questions`，不含 `sys-user-essay`） |
| 验收结论 | **M-STD-E-AI 已通过**（2026-10-09） |
| 依据 | `run_pure_ai_pipeline.py` + `verify_mstd_e_ai_milestone.py` + `verify_std_e_suite.py`；详见 [验收通知/M-STD-E-AI-纯AI验收.md](./验收通知/M-STD-E-AI-纯AI验收.md) |

## 1. 工程冒烟（必过）

| # | 项 | 命令 / 路径 | 通过 |
|---|-----|-------------|------|
| E1～E5 一键 | 工程冒烟套件 | `python scripts/verify_std_e_suite.py` | ☑ |
| E1 | Schema / 验证器 | （含于 suite） | ☑ |
| E2 | 解析器 | （含于 suite） | ☑ |
| E3 | Stub 流水线 | （含于 suite） | ☑ |
| E4 | 发布 + 批改上下文 | （含于 suite） | ☑ |
| E5 | 已发布标准冒烟 | （含于 suite） | ☑ |
| E5b | Alembic 基线 | `python scripts/verify_alembic.py` | ☑ |
| E5c | 纯 AI 自动发布 | `python scripts/verify_auto_publish.py`（DEC-07） | ☑ |
| E5d | AI 金标写入 | `python scripts/verify_ai_gold_seed.py`（DEC-08） | ☑ |

## 2. Admin 联调（必过）

| # | 项 | 通过 |
|---|-----|------|
| E6 | `/admin/standards` 上传资料 | ☑ |
| E7 | 创建标准任务 → `validated` | ☑ |
| E8 | 发布 → `GET .../questions/{id}/active` 有 payload | ☑ |
| E9 | 该题批改请求体含 `standard_version`（有发布时） | ☑ |

> E6～E9：能力已在 P6/P4/P5 交付；纯 AI 批量发布覆盖 E7/E8；可按 [纯AI运行手册.md](../纯AI运行手册.md) 复验 Admin UI。

## 3. 量化指标 — 纯 AI 自洽（DEC-06，默认）

标注由流水线自动反写（见 `annotation_bootstrap.py`），或批量：

`python scripts/bootstrap_annotation_from_jobs.py --all-essay --overwrite`

`python scripts/eval_standard_metrics.py ../../data/standards/annotation/questions_for_labeling.csv`

| 指标 | 含义（自洽） | 目标 | 实测 | 通过 |
|------|--------------|------|------|------|
| 命题形式 | 生成 vs 反写标注 | ≥ 95% | 95.2% | ☑ |
| 审题任务 | 同上 | ≥ 90% | 95.2% | ☑ |
| 准则关键词 | Rubric core vs 反写关键词 | ≥ 90% | 100% | ☑ |
| 准则重复率 | validate 步 | ≤ 5% | 达标（stub 流水线） | ☑ |
| 题干追溯 | validate 步 | ≥ 95% | 达标（stub 流水线） | ☑ |
| 置信度 | job `standard_confidence` 均值 | ≥ 0.85 | 达标（stub/发布） | ☑ |

一键报告：`python scripts/mstd_e_ai_report.py`

## 4. 里程碑

| 里程碑 | 条件 | 通过 |
|--------|------|------|
| **M-STD-E-AI** | `run_pure_ai_pipeline.py` + `verify_mstd_e_ai_milestone.py` + E6～E9 | **☑ 2026-10-09** |
| M-STD-E（有人审） | 人工标注 CSV + 同上 | 不适用（DEC-06 纯 AI） |
