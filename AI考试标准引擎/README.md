# AI 考试标准引擎（申论大作文）

| 项目 | 内容 |
|------|------|
| 文档集版本 | **V0.1-E（Essay）** |
| 依据 | PDF《考试标准引擎 V0.1 设计文档》→ **[PDF对齐-考试标准引擎总规划.md](./PDF对齐-考试标准引擎总规划.md)**；现网 Track-A 大作文 + 规划 Track-B 小题 |
| 产品 | [`方案调研/技术选型文档.md`](../方案调研/技术选型文档.md)、[`方案调研/产品需求-V1.2-大作文修订.md`](../方案调研/产品需求-V1.2-大作文修订.md) |
| 范围 | **仅申论大作文**；不包含归纳概括 / 综合分析 / 提出对策等小题型 |
| 状态 | **M-STD-E-AI 已通过**（2026-10-09）；见 [验收清单-STD-E.md](./开发进度/验收清单-STD-E.md) · [纯AI运行手册.md](./纯AI运行手册.md) |

## 纯 AI 快速开始

```bash
cd services/api && source .venv/bin/activate
python scripts/run_pure_ai_pipeline.py --limit 21 --mode stub
```

## 开发进度

任务分解与状态跟踪见 **[开发进度/](./开发进度/)**：

- [PDF对齐-考试标准引擎总规划.md](./PDF对齐-考试标准引擎总规划.md) · [V1.0-P-产品级路线图.md](./开发进度/V1.0-P-产品级路线图.md)
- [开发任务与进度.md](./开发进度/开发任务与进度.md)
- [进度总览.md](./开发进度/进度总览.md)
- [验收清单-STD-E.md](./开发进度/验收清单-STD-E.md)
- [运维说明-标准引擎.md](./运维说明-标准引擎.md)

**V0.1-E 状态**：后端 + Admin 闭环已交付。**V0.1.1** 增强见 [验收通知/V0.1.1-增强.md](./开发进度/验收通知/V0.1.1-增强.md)。**V0.2**（P05、Celery `standards` 队列、输入缓存、双模型一致率、金标×标准版本）见路线图与 [运维说明-标准引擎.md](./运维说明-标准引擎.md) 环境变量表。

## 审验阅读顺序

1. **[PDF对齐-考试标准引擎总规划.md](./PDF对齐-考试标准引擎总规划.md)** — 对齐 PDF 的分阶段规划（Track-A 已交付 / Track-B 小题路线图）。
2. **[开发架构与技术选型.md](./开发架构与技术选型.md)** — Track-A 目标边界、八模块、双引擎、技术栈（主技术文档）。
3. **[数据契约-V0.1-大作文.md](./数据契约-V0.1-大作文.md)** — 字段级 JSON / 表设计草案，可与现有 `Question.scoring_points` 对齐。
4. **[Prompt契约-V0.1-大作文.md](./Prompt契约-V0.1-大作文.md)** — 分职责 Prompt、输入输出 JSON、失败与校验。

## 与现网代码的关系（摘要）

| 现网模块 | 路径 | 引擎落地后角色 |
|----------|------|----------------|
| 作答评价引擎 | `services/api/app/services/grading_service.py` | 消费已发布标准，不再内联「默认 Rubric」 |
| BYOK 调用 | `services/api/app/services/ai_client.py` | 标准生成与批改共用同一 OpenAI 兼容客户端 |
| 题目 Rubric | `Question.scoring_points` | 发布态快照；完整标准存 `exam_standards` 等新表 |
| Prompt 版本 | `PromptVersion` | 批改 Prompt 与标准生成 Prompt **分 purpose 管理** |
| 教研后台 | `admin_research` | 扩展：资料导入、标准生成任务、发布 |

## 核心结论（供快速审验）

- **双引擎**：标准引擎回答「应如何评」；评价引擎回答「这篇写得怎么样」— 与 PDF §10 一致，对象改为**维度 Rubric + 失分规则**，非材料采分点。
- **编排**：**一条主流程 + 多个独立 AI 任务**（不用 LangChain / LangGraph V0.1）。
- **技术栈**：延续 **FastAPI + Celery + PostgreSQL + httpx（BYOK）**；文档解析用轻量 Python 库；契约用 **Pydantic v2**。
