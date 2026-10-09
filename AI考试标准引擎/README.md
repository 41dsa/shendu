# AI 考试标准引擎（申论大作文）

| 项目 | 内容 |
|------|------|
| 文档集版本 | **V0.1-E（Essay）** |
| 依据 | 《AI 申论教练 · 考试标准引擎 V0.1 设计文档》（小题方法论）+ 本项目 [`方案调研/技术选型文档.md`](../方案调研/技术选型文档.md)、[`方案调研/产品需求-V1.2-大作文修订.md`](../方案调研/产品需求-V1.2-大作文修订.md) |
| 范围 | **仅申论大作文**；不包含归纳概括 / 综合分析 / 提出对策等小题型 |
| 状态 | **待审验** |

## 审验阅读顺序

1. **[开发架构与技术选型.md](./开发架构与技术选型.md)** — 目标边界、八模块架构、与「作答评价引擎」分工、技术栈、部署与演进、任务分期、验收指标（主文档）。
2. **[数据契约-V0.1-大作文.md](./数据契约-V0.1-大作文.md)** — 字段级 JSON / 表设计草案，可与现有 `Question.scoring_points` 对齐。
3. **[Prompt契约-V0.1-大作文.md](./Prompt契约-V0.1-大作文.md)** — 分职责 Prompt、输入输出 JSON、失败与校验。

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
