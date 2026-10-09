# 考试标准引擎 — 总规划（对齐 V0.1 设计 PDF）

| 项目 | 内容 |
|------|------|
| 依据文档 | 《AI 申论教练 · 考试标准引擎 V0.1 设计文档》（15 页 PDF，2026） |
| 编写日期 | 2026-10-09 |
| 现网基线 | **Track-A 大作文 V0.1-E + V0.2 + M-STD-E-AI 已通过** |
| 规划原则 | **DEC-09：仅大作文** — Track-A 持续演进；Track-B（小题）**冻结**；PDF 仍作方法论参考 |

---

## 1. 与 PDF 的战略分叉（必读）

PDF §1.1 建议 **先小题、后大作文**；本项目因 **产品 V1.2-E** 已收敛为 **学员端仅大作文批改**，故先落地 **Track-A**。PDF 中的「采分点 SP001」体系归属 **Track-B**，与 Track-A 的 **维度 Rubric（D01～D04 / RCxxx）** 并列，共用 M1～M3、M6～M8 基础设施。

| PDF 概念 | Track-A（现网） | Track-B（规划） |
|----------|-----------------|-----------------|
| M5 采分点生成 | **Rubric 准则生成**（P03/P04） | **ScoringPoint** 候选 + 合并 |
| QuestionStandard | 大作文 `essay_form` / `focus_points` | 小题 `question_type` / `task` / `answer_object` |
| 批改 Prompt 06 | 合并在 `grading_service` 维度 JSON | 语义命中 SP001… |
| 题量 | 20～80 道 essay（联调库） | **100～300 小题**（PDF §2） |
| 考试范围 | 2024～2026 国考 essay 先行 | **2024～2026 国考市地级小题** 先行，再六省 |

**不追求（PDF 与现网一致）**：全国省份自动检索、完美黑盒标准、LangGraph 多 Agent、平台统一 LLM Key。

---

## 2. PDF 八模块 — 现状与差距

| PDF 模块 | PDF 要求摘要 | Track-A 状态 | Track-B / 缺口 |
|----------|--------------|----------------|----------------|
| **M1 资料管理** | A～C 类资料、S～C 来源分级 | ✅ `StandardDocument`、上传、分级 | 缺 **考试大纲/公告** 专类索引；缺 Paper 级 bundle |
| **M2 文档解析** | PDF/DOCX/TXT → Document | ✅ `parse_service` + ingest | 页码/题号对齐（PDF §M2）弱；图片 OCR 未做 |
| **M3 真题结构化** | Paper → Question → Material | ⚠️ 单题 `Question` + CSV | 缺 **试卷（Paper）** 实体、题号/材料范围字段 |
| **M4 题目标准** | 题型→任务→对象→结构 | ✅ P01 + `QuestionStandardSchema`（essay） | 缺小题题型枚举与 `answer_structure` 完整链 |
| **M5 标准生成** | 候选采分点 + 合并 | ✅ P03/P04 Rubric（essay） | **整模块待建**（SP 两步法） |
| **M6 标准验证** | 5 项验证 + 置信度 | ✅ 规则 5 项 + P05 辅助（essay 映射） | 小题需 **材料证据逐点**、SP 重复/分值 |
| **M7 标准发布** | 版本/状态 | ✅ 题目级 + **ExamStandard** 聚合（V0.3～0.4） | — |
| **M8 批改调用** | 只读已发布标准 | ✅ `essay_context` + `grading_service` | 小题需 **SP 级 hit** 接口 |

---

## 3. 分阶段开发规划

### Phase 0 — 大作文闭环（**已完成**）

| 交付 | 证据 |
|------|------|
| 八模块 essay 映射、Prompt P01～P05、发布、批改注入 | `AI考试标准引擎/开发架构与技术选型.md` |
| Admin、Celery `standards`、缓存、双模型一致率 | V0.2 路线图 |
| 纯 AI 验收 M-STD-E-AI | [验收清单-STD-E.md](./开发进度/验收清单-STD-E.md) |

**维护**：联调题库扩充、LLM 质量运营、`run_pure_ai_pipeline` / CI。

### Phase 0.5 — V0.3 / V0.4-E 大作文收口（**2026-10-09**）

- [V0.3-E](./开发进度/V0.3-E-大作文路线图.md)：ExamStandard、M1 分类、Rubric 草稿  
- [V0.4-E](./开发进度/V0.4-E-大作文路线图.md)：40 题联调库、考试级批量、批改 policy、覆盖率里程碑  

---

### Phase 1 — PDF「第一阶段：资料」（Track-B 启动 + Track-A 增强）

**目标**：满足 PDF §8 第一阶段；为 **100～300 小题** 与 **国考市地级** 单范围聚焦做准备。

| 编号 | 任务 | 说明 | 优先级 |
|------|------|------|--------|
| PDF-P1-01 | **Paper 数据模型** | `ExamPaper`（exam/year/level）、`paper_id`、题目顺序、材料块 ID | P0 |
| PDF-P1-02 | **试卷导入器** | 一份 PDF/结构化 ZIP → 多 `Question` + `Material` 关联（M3） | P0 |
| PDF-P1-03 | **资料目录规范** | 对齐 PDF M1：公告/大纲(S)、真题(A)、参考解析(B/C) 目录与 metadata | P1 |
| PDF-P1-04 | **真题批量 100+** | 国考市地级 2024～2026 小题入库（合规来源） | P0 内容 |
| PDF-P1-05 | **题—参考答案—解析关联** | `StandardDocument` 与 `Question` 多对多 + 发布 job 默认引用 | P1 |
| PDF-P1-06 | **ExamStandard 草案** | 考试级 JSON：卷种、题型说明、默认分值规则（PDF §7） | P2 |

Track-A 同步：essay CSV 继续扩；**不阻塞** Track-B。

**验收**：≥1 套完整市地级卷导入；≥100 道小题 `Question` 可查询；每题可绑 ≥1 参考文档。

---

### Phase 2 — PDF「第二阶段：标准生成」（Track-B 核心）

**目标**：实现 PDF M4 + M5（小题 **ScoringPoint** 两步法）。

| 编号 | 任务 | 说明 | 优先级 |
|------|------|------|--------|
| PDF-P2-01 | **数据契约 V0.1-S** | `ScoringPoint` / `ScoringStandard`（SPxxx）独立 schema，与 essay Rubric 并存 | P0 |
| PDF-P2-02 | **Prompt S01～S04** | 映射 PDF Prompt01～04：题型识别、材料分析、候选点、合并（新 `PromptPurpose`） | P0 |
| PDF-P2-03 | **流水线 `subjective_pipeline`** | `question_std → material_analysis → sp_candidates → sp_merged`；复用 ingest/validate 框架 | P0 |
| PDF-P2-04 | **置信度公式（PDF §5）** | 来源 30% + 证据 25% + 参考 20% + 模型 15% + 题型 10%；SP 级 `<85%` 不默认发布 | P1 |
| PDF-P2-05 | **Admin 小题任务 UI** | 题型筛选、SP 表预览、与 essay 任务分 Tab 或 `question_type` 分流 | P1 |

**验收（对齐 PDF §9 小题指标）**：100 题抽样 — 题型 ≥95%、任务 ≥90%、**核心采分点召回 ≥90%**。

---

### Phase 3 — PDF「第三阶段：验证」（Track-B 加强 M6）

| 编号 | 任务 | 说明 |
|------|------|------|
| PDF-P3-01 | **材料证据验证** | 每 SP 绑定 `evidence` 句段；无证据 → 降 confidence |
| PDF-P3-02 | **参考答案覆盖** | LLM 辅助（类似 essay P05）+ 规则 |
| PDF-P3-03 | **题型一致性** | 归纳概括 vs 对策型 SP 互斥规则 |
| PDF-P3-04 | **SP 重复/包含检测** | 语义重复率 ≤5%（PDF §M6-4） |
| PDF-P3-05 | **分值求和** | Σ weight = total_score（已有 essay 版可复用） |

---

### Phase 4 — PDF「第四阶段：标准管理」（ largely Done，补 Exam 级）

| 编号 | 任务 | 说明 |
|------|------|------|
| PDF-P4-01 | **标准在线编辑** | Admin 改 SP/Rubric 草稿后再发布（可选） |
| PDF-P4-02 | **ExamStandard 发布** | 考试级版本 + 下属题目标准引用 |
| PDF-P4-03 | **生产 Alembic 增量** | DEC-05 收口：`002_subjective_*` revision |

现网已有：查看、发布、版本、回滚、强制发布。

---

### Phase 5 — PDF「第五阶段：AI 批改」（Track-B 消费）

| 编号 | 任务 | 说明 |
|------|------|------|
| PDF-P5-01 | **小题批改路径** | `question_type != essay` → 读 `ScoringStandard` |
| PDF-P5-02 | **Prompt S06 / 06** | 用户答案 ↔ SP 语义命中（full/partial/miss） |
| PDF-P5-03 | **失分规则联动** | `LossRules` 与小题 SP 绑定 |
| PDF-P5-04 | **产品入口** | 是否开放学员小题练习（产品决策，非引擎 alone） |

Track-A：essay 批改已具备；**自备题仍用默认 Rubric**（见 `essay_context`）。

---

### Phase 6 — 横向扩展（PDF §2「暂不并行」之后的扩展）

按 PDF 建议顺序，**单卷种跑通后再开**：

1. **国考副省级小题**（与市地级结构差异）
2. **湖北 → 浙江 → 广东 → 江苏 → 山东**（省考卷种模板 + ExamStandard 变体）
3. **ExamProfile 联通**（用户 `province` / `job_category` → 推荐 ExamStandard / 默认卷种，**非**自动全网检索）
4. **100～300 题规模运营** + PDF §9 全指标签字（人工或纯 AI 自洽两套门槛）

---

## 4. PDF 开发任务清单映射（§8）

| PDF 阶段 | PDF 勾选项 | 规划编号 | Track-A | Track-B |
|----------|------------|----------|---------|---------|
| 第一阶段 | 资料目录、100～300 题、格式、等级、关联 | PDF-P1-* | 部分 | **主战场** |
| 第二阶段 | 题型/任务/材料/候选/合并/权重 | PDF-P2-* | essay 等价物 ✅ | **待开发** |
| 第三阶段 | 五项验证 + 置信度 | PDF-P3-* | essay 简化版 ✅ | 加强 |
| 第四阶段 | 查看/修改/发布/版本/状态 | PDF-P4-* | ✅ | Exam 级待补 |
| 第五阶段 | 输入/匹配/得分/失分/建议 | PDF-P5-* | essay ✅ | 待开发 |

---

## 5. 验收指标（PDF §9 vs 现网）

| PDF 指标（小题） | V0.1 目标 | Track-A（essay 自洽） | Track-B 目标阶段 |
|------------------|-----------|------------------------|------------------|
| 题型识别 | ≥95% | `essay_form` 自洽 | Phase 2 末 |
| 作答任务识别 | ≥90% | `proposition_task` 自洽 | Phase 2 末 |
| 核心采分点召回 | ≥90% | 准则关键词自洽 | **Phase 2 核心** |
| 明显错误 SP 比例 | ≤10% | — | Phase 3 |
| 重复率 | ≤5% | validate ✅ | Phase 3 |
| 材料证据可追溯 | ≥95% | 部分（P05/启发式） | Phase 3 |
| 置信度校准 | ≥85% | 发布门槛 0.85 | Phase 2～3 |
| 用户答案语义匹配 | ≥90% | essay 维度 JSON | Phase 5 |

**M-STD-E-AI** 继续作为 **Track-A 签字**；**M-STD-B（小题）** 建议在 Phase 2 结束后新增验收清单 `验收清单-STD-S.md`。

---

## 6. 技术架构（继承 PDF §3）

- **编排**：一条主流程 + 分步 LLM（`pipeline.py` / 未来 `subjective_pipeline.py`），**不用** LangChain/LangGraph。
- **双引擎**：标准引擎只写发布物；`grading_service` 只读（PDF §10）。
- **栈**：FastAPI + Celery（`grading` / `standards`）+ SQLAlchemy + httpx BYOK + Pydantic v2。
- **Prompt**：分 purpose 存 `PromptVersion`；小题新增 `standard_s01`…`standard_s06`（命名待定）。

---

## 7. 近期执行顺序（建议 2026 Q4 → 2027 Q1）

```text
1. [文档] 数据契约 V0.1-S（小题 SP）+ Prompt 契约 S 系列 — 先于编码
2. [PDF-P1] Paper 模型 + 单卷导入脚本 — 1 套市地级卷 end-to-end 入库
3. [PDF-P2] subjective_pipeline stub → LLM — 10 题 SP 生成试点
4. [PDF-P3] M6 五项小题验证器 — 对接发布门槛
5. [PDF-P5] 批改读 ScoringStandard — 仅 Admin/金标试点
6. [Phase 6] 题量与省考扩展 — 产品排期
```

**并行维护 Track-A**：`run_pure_ai_pipeline`、CI、LLM 质量；**不**在小题未就绪前改 essay 契约。

---

## 8. 文档索引

| 文档 | 用途 |
|------|------|
| 本文件 | **PDF 对齐总规划**（产品 + 研发排期） |
| [开发架构与技术选型.md](./开发架构与技术选型.md) | Track-A 技术详设 |
| [开发进度/开发任务与进度.md](./开发进度/开发任务与进度.md) | 历史 STD 任务（64 项） |
| [开发进度/V0.2-路线图.md](./开发进度/V0.2-路线图.md) | Track-A 增强（已完成项） |
| [纯AI运行手册.md](./纯AI运行手册.md) | Track-A 运维 |
| **待增** | `数据契约-V0.1-小题.md`、`Prompt契约-V0.1-小题.md`（Phase 2 前） |

---

## 9. 决策记录

| ID | 决策 |
|----|------|
| PDF-PLAN-01 | PDF 为全引擎北极星；**Track-B 小题** 按本规划推进，**不删除** Track-A |
| PDF-PLAN-02 | 先做 **国考市地级单卷种**（PDF §2），六省并行列入 Phase 6 |
| PDF-PLAN-03 | `ExamProfile` 联通列入 Phase 6，不做「全自动省岗检索」除非另开 DEC |
| PDF-PLAN-04 | 小题验收指标沿用 PDF §9；Track-A 继续 **M-STD-E-AI 自洽** 门槛 |
| DEC-09 | **仅大作文** | Track-B 冻结；研发按 V0.3-E 收口 Track-A（ExamStandard、M1 分类、草稿编辑） |

**文档结束**
