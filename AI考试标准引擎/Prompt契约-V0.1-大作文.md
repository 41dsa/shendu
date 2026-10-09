# Prompt 契约 V0.1-E（申论大作文）

| 项目 | 内容 |
|------|------|
| 状态 | **待审验** |
| 原则 | **职责单一**、**JSON 输出**、**Pydantic 校验**、失败可重试 |

与现网 `PromptVersion` 扩展：新增 `purpose` 枚举值 `standard_p01` … `standard_p06`（或与批改 `essay_grading` 并列）。

---

## 通用约定

| 项 | 约定 |
|----|------|
| 模型 | 教研 BYOK；温度 **0～0.3**（生成/验证偏低） |
| 输出 | 仅 JSON，无 Markdown 围栏；解析失败重试 ≤ 2 |
| 语言 | 简体中文字段内容；**键名英文 snake_case** |
| 安全 | 用户作文 **不** 进入标准生成 Prompt |
| 校验 | 解析 → `json.loads` → Pydantic model → 业务验证器 |

---

## Prompt 01 — 大作文命题与题目标准

**职责**：识别命题形式、审题任务、立意边界、结构期望（M4）。

| 项 | 内容 |
|----|------|
| 输入 | `prompt`, `requirements`, `material_optional`, `exam`, `score`, `word_min`, `word_max` |
| 输出 | `QuestionStandard` 子集（不含 version/source_refs） |

**输出 JSON 骨架**

```json
{
  "essay_form": "topic",
  "proposition_task": "论证观点",
  "thesis_scope": {"must_address": [], "must_avoid": []},
  "structure_expectation": {"paragraphs_min": 4, "has_thesis_statement": true, "sub_thesis_count_hint": [2, 3]},
  "answer_scope": "自选角度",
  "abilities_focus": ["A1", "A2", "A3"],
  "keywords": [],
  "focus_points": []
}
```

**失败处理**

| 错误 | 处理 |
|------|------|
| JSON 无效 | 重试；附加 system「仅输出合法 JSON」 |
| `essay_form` 不在枚举 | 映射为 `topic` 并写 `review_flag` |
| 空 `focus_points` | 阻塞发布，标记 `needs_review` |

---

## Prompt 02 — 参考背景分析（可选）

**职责**：当 `material_optional` 非空时，提取主题与可用论据（**非采分点**）。

| 项 | 内容 |
|----|------|
| 输入 | `material_optional`, `QuestionStandard.keywords` |
| 输出 | `MaterialAnalysis` |

**跳过条件**：无背景材料 → 输出空对象 `{}`，不调用 LLM。

---

## Prompt 03 — 维度 Rubric 候选准则

**职责**：第一步生成候选（M5.1）。

| 项 | 内容 |
|----|------|
| 输入 | `QuestionStandard`, `MaterialAnalysis`, `reference_excerpts[]`, `dimension_skeleton[]`（D01～D04 固定） |
| 输出 | `{"candidates": [ RubricCriterion 不含 confidence ]}` |

**System 要点**

- 明确：**申论大作文**，勿生成「从材料概括要点」类准则。
- 每条准则必须 **可在用户全文中观察**（结构、立意句、论据、语言等）。
- 每维 2～5 条候选；含 `typical_gaps`、`issue_tags` 建议。

**输出验证**

- `dimension_id` 必须属于 skeleton。
- 单维候选数 ≤ 8，否则截断并告警。

---

## Prompt 04 — Rubric 合并与赋分

**职责**：第二步合并、去重、分配 `max_score`/`weight`（M5.2）。

| 项 | 内容 |
|----|------|
| 输入 | `candidates`, `total_score`, `dimension_skeleton` |
| 输出 | `RubricStandard` 的 `dimensions` + `criteria`（无 `loss_rules`） |

**规则（写入 System）**

- 同维语义合并；保留更具体、可观察的一条。
- Σ 维度 `max_score` = `total_score`。
- 与 `abilities_focus` 弱相关的准则降权或删除。

**失败处理**

| 错误 | 处理 |
|------|------|
| 分值和不等于总分 | 自动按比例微调 ±0.5 分内；仍失败则进入 M6 `score_sum` 失败 |

---

## Prompt 05 — 标准验证（LLM 辅助）

**职责**：对规则验证器未覆盖的项做语义判断（M6 补充）。

| 项 | 内容 |
|----|------|
| 输入 | `QuestionStandard`, `RubricStandard`, `reference_excerpts[]` |
| 输出 | `{"coverage_gaps": [], "questionable_criteria_ids": [], "notes": ""}` |

**说明**：硬性五项（分值和、重复率等）由 **纯代码** 完成；本 Prompt 只做「范文是否覆盖核心评价点」等语义检查。

---

## Prompt 06 — 用户答案维度匹配（作答评价引擎）

**职责**：标准发布后，批改时按 Rubric 匹配（可在 `grading_service` 内分步或合并在主批改 Prompt）。

| 项 | 内容 |
|----|------|
| 输入 | `RubricStandard.criteria`, `user_essay`, `QuestionStandard` |
| 输出 | 与现网批改 JSON 对齐的 `scoring_points[]`（`hit`: full/partial/miss） |

**与现网关系**

- 当前 V1 为 **单次** `chat_completion_json` 主批改（`grading_service.SYSTEM_PROMPT`）。
- V0.1-E 建议：**主批改 Prompt 注入已发布 Rubric**；Prompt 06 可作为 **第二遍**「仅匹配」调用（共识前），P1 再拆。

**输出验证**

- 每个 `dimension_id` 至少一条 hit 记录。
- `earned` ≤ 对应维 `max_score`。

---

## Prompt 07 — 失分规则生成（可选，可与 Prompt 04 合并）

**职责**：从 `typical_gaps` + `issue_tags` 生成 `loss_rules[]`。

| 输出字段 | 说明 |
|----------|------|
| `when` | 枚举：`thesis_off_topic`, `weak_structure`, `argument_gap`, … |
| `issue_tag` | Q21～Q25 等 |
| `deduction_cap` | 不超过维度满分 |

---

## 失败与重试策略（全局）

```text
LLM 调用
  → HTTP 错误：指数退避 3 次（ai_client 已有）
  → JSON 解析失败：同 Prompt 重试 2 次
  → Pydantic 失败：带「错误字段列表」的 repair 重试 1 次
  → 仍失败：job.step = failed，保留 raw 响应供 Admin 查看
```

---

## 版本与 A/B

| 字段 | 说明 |
|------|------|
| `prompt_version_id` | 绑定 `PromptVersion.id` |
| `standard_version` | 发布标准版本 |
| 回归 | 固定 10 题金样 + `scripts/verify_*` 扩展 |

---

## 审验点

- [ ] Prompt 03/04 **两步** 是否保留（相对一步生成）？
- [ ] Prompt 06 是 **独立调用** 还是 **合并进主批改**（成本 vs 可解释性）？
- [ ] 是否在 V0.1 即引入 Prompt 07，还是 `loss_rules` 由规则从 `issue_tags` 模板生成？
