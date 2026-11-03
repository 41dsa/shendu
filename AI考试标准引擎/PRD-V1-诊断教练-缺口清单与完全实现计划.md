# PRD V1《AI申论大作文诊断与提分教练》— 缺口清单与完全实现计划

| 项目 | 内容 |
|------|------|
| 依据文档 | document-6 / document-6_2（V1 产品 PRD & 技术架构） |
| 目标 | **按文档完全实现** V1 评分标准执行器 + 诊断报告；V2/V3 单列里程碑 |
| 当前基线 | 在线批改已切 `diagnostic_trait_v1`（规则 + 启发式 Trait + 2 路投票 + 区间）；**非文档完整版** |
| 编写日期 | 2026-10-16 |

---

## 0. 「完全实现」定义（Done 标准）

满足以下全部条件，方可称 V1 与 PRD 对齐：

1. **八模块 V1 范围**（§3.1 中 ①～④、⑦ 及 ⑤ 弱监督最小集、⑧ 主动学习最小闭环）有对应代码、数据表、API 与验收脚本；⑥ Anchor 为 **可运营最小集**（非空流程 + 数据结构）。
2. **§3.2 流水线逐步可追踪**：每步在 `engine_traces` / 日志中可审计，且顺序与文档一致。
3. **§十三报告模板 + §一 7 问**：报告 **唯一脊柱** 来自 Trait 引擎 + 标准卡；LLM 仅补文案/建议，不得另立总分或 Rubric。
4. **§二文案红线 + §7.1 冷启动禁止**：产品 UI 与 API 字段行为可验收（含「未校准不宣传估分」）。
5. **§7.5 无 Anchor 阶段指标**：有自动化回归（Evidence 子集校验、规则准确率、Trait 稳定性抽样等），阈值向文档靠拢。
6. **旧采分点池引擎**：自 **批改/报告/read path** 彻底移除或显式 `deprecated` 且不可被配置打开。

V2（Anchor 规模化 + 弱监督工厂完整）、V3（MFRM/Rasch + 专用模型）**不纳入**本清单 Done，但须预留字段（§十一）。

---

## 1. 总体架构与流水线（§3.2）

| ID | PRD | 现状 | 缺口 / 交付物 | 验收 |
|----|-----|------|---------------|------|
| P-01 | 作文输入 | ✅ | — | — |
| P-02 | 题目标准匹配 | Done | `standard_match_confidence` 入引擎/报告；`verify_standard_match_confidence.py` |
| P-03 | 规则检测 | Done | `verify_hard_rules_suite` + `verify_hard_rules_deterministic` |
| P-04 | Evidence 抽取 | Done | E-01～E-06 + `verify_evidence_accuracy.py` |
| P-05 | 8 Trait 等级 | Done | Rubric+Evidence 定级 + `verify_trait_gold_regression` / `verify_trait_stability` |
| P-06 | 多模型投票 | Done | 三路由 + evidence 写回；`verify_trait_voting_3model.py` |
| P-07 | 规则边界校验 | Done | `boundary_policy` 6 条 + `verify_boundary_policy_matrix.py` |
| P-08 | 区间估计 | Done | `trait_interval` + Rubric 调整项 + `multi_standard_views` |
| P-09 | 置信度 | Done | `trait_confidence` + `score_display_policy` |
| P-10 | 诊断报告生成 | Done | `trait_report_builder` + REP 门禁 + `verify_report_json_schema.py` |
| P-11 | 主动学习池 | Done | `active_learning_pool` + `/admin/active-learning` 列表/导出 |

**建议代码锚点**：`domain/scoring_engine/v1_engine.py` → 拆为显式 stage 模块；`services/scoring_engine/orchestrator.py` 仅编排。

---

## 2. 模块 ① 真题与材料库（§3.1-①）

| ID | 要求 | 缺口 | 交付物 |
|----|------|------|--------|
| Q-01 | 真题、材料、作答要求、考试说明 | Done | `EssayItemV1Schema` + `essay_item_v1` 快照；`essay_item_v1_locked` |
| Q-02 | 与标准卡关联 | Done | `question_standard_link.py`；Admin 题目列表 `standard_link` + `GET .../standard-link` |
| Q-03 | 导入/版本 | Done | `essay_item_import_service`；CSV/JSON API + `essay_import_audits` |

**验收**：`verify_question_bank_v1.py` — demo 题 A 类 prompt + 已发布标准卡；essay 行抽检。

---

## 3. 模块 ② 题目标准引擎（§4.1～4.3）

### 3.1 标准卡完整字段（§4.2）

| ID | 字段 | 现状 | 缺口 |
|----|------|------|------|
| M-01 | 题目主题 / 任务 | Done | `StandardCardV1Schema` + `standard_card_validation.py` |
| M-02 | 关键词及关系 | Done | 字段 + 发布校验 keywords≥2 时 relations |
| M-03 | 核心矛盾/问题 | Done | `standard_card_enrich.py` + 流水线 `material_enriched` 共识步 |
| M-04 | 核心立意 / 可接受 / 边缘立意 | Done | enrichment 写入 `thesis_space.core` 等 |
| M-05 | 偏题 / 严重跑题方向 | Done | `thesis_space.off_topic` / `severe_off_topic` → `QuestionStandardCard` |
| M-06 | 材料关键事实与逻辑关系 | Done | enrichment 写入 `material_facts` / `material_logic` |
| M-07 | 推荐论证/分析/对策方向 | Done | `recommended_*_directions` enrichment |
| M-08 | 本题 Rubric 调整项 | Done | `trait_rubric_adjustments` from rubric confidence |
| M-09 | 材料关键句锚点 | Done | `material_anchor_phrases` → T4 Evidence + `verify_material_anchor_evidence.py` |
| M-10 | 标准版本号 / 争议点标记 | Done | 标准卡 `dispute_marks` + 报告总体卡 Alert |

**Schema 建议**：扩展 `QuestionStandardSchema` 或新增 `StandardCardV1Schema`（与现网 `question_standard` JSON 迁移脚本）。

### 3.2 多模型标准共识（§4.3）

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| M-11 | 3 模型独立分析题意 | Done | `standard_consensus_pipeline` + `STANDARD_CONSENSUS_3MODEL_ENABLED` |
| M-12 | 高共识入库，分歧标「标准依赖」 | Done | `merge_standard_cards_v1` + `dispute_marks` |
| M-13 | 未审核仅诊断、不输出分数 | Done | `review_status` + `score_display_policy` / draft 卡 |
| M-14 | 教研 30 分钟审核发布 | Done | `standard_card_review_service.py`；`/admin/standards/standard-card-review-queue` + 审核/通过并发布；`AdminStandardsPage` 待审队列 |

**验收**：`verify_standard_card_v1.py` + `verify_standard_consensus_3model.py`（mock 三路由）。

---

## 4. 模块 ③ Rubric 引擎（§5.1～5.4）

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| R-01 | 8 Trait 维度定义 | Done | `trait_rubric_v1.json` 目录字段 + `verify_r01_trait_catalog.py` |
| R-02 | 每 Trait L0～L4 等级描述 + 加减分条件 | Done | `trait_rubric_v1.json` 8×L0–L4 + `plus_conditions`/`minus_conditions`；本题 override 见标准卡 `trait_rubric_adjustments` |
| R-03 | 硬/软/争议三层 | Done | `hard_rules` 文体/身份 + `must_avoid`/`must_address` 范围规则 |
| R-04 | B 档：Rubric 判定等级 | Done | `trait_level_from_rubric` + `verify_rubric_level_stability` |
| R-05 | C 档：双标准视图文案 | Done | `view_templates` in JSON + `multi_standard_view_copy.py` |

**验收**：`verify_rubric_engine_v1.py` — 同类作文同题 Rubric 等级稳定（§7.5 Rubric 一致性）。

---

## 5. 模块 ④ Evidence 引擎（§九）

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| E-01 | 三类证据 | Done | `evidence_engine.extract_evidence()` 统一入口 |
| E-02 | B 档：LLM **只抽原文**，不评总分 | Done | `trait_evidence_llm` + 三模型投票 evidence 写回 + grounding |
| E-03 | 段落号 / 可定位 | Done | `EvidenceSpan` + 报告 `evidence_spans` + 前端定位提示 |
| E-04 | 负向 / 缺失 | Done | Rubric `minus_conditions` → missing（无正向证据时） |
| E-05 | Evidence 准确率 >90% | Done | `verify_evidence_accuracy.py`（合成金标 ≥ `evidence_accuracy_min_rate`） |
| E-06 | 与 Trait 判定解耦 | Done | `verify_trait_evidence_decouple.py`（幻觉 evidence 不改等级） |

---

## 6. 模块 ⑤ 弱监督数据工厂（§7.4）— V1 最小集

| ID | 标签类型 | 现状 | 缺口 |
|----|----------|------|------|
| W-01 | 规则标签 | Done | `weak_labels` 表 + `WeakLabelType.rule` |
| W-02 | Rubric 标签 | Done | `labels_from_engine_result` rubric 行含 source/证据计数 |
| W-03 | 多模型一致标签 | Done | per-trait + `engine_high_consensus`；`verify_w01_w03_weak_labels.py` |
| W-04 | 成对比较标签 | Done | `trait_pair_compare` + admin API |
| W-05 | 自一致性 | Done | 高 `vote_spread` → `WeakLabelType.self_consistency` |
| W-06 | 反例库 | Done | `COUNTEREXAMPLE_TEMPLATES` + seed API |
| W-07 | 对比修订标签 | Done | `persist_retry_trait_delta` + `verify_w07_retry_weak_label.py` |
| W-08 | 严禁冒充真值 | 文档 | 导出/训练接口强制 `is_weak_label=true` |

**验收**：`verify_weak_supervision_factory.py`。

---

## 7. 模块 ⑥ Anchor Set（§6.2、§8.1）— V1 可运营最小集

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| AN-01 | 锚作文 10～20 篇/题 | 金标零散 | `anchor_essays` 表 + L0～L4 覆盖 |
| AN-02 | 人工 Trait + 证据 + 争议 | Done | `GET/POST .../anchor-essays/{id}` + `AdminAnchorAnnotationPage` |
| AN-03 | 3 评者不强制一致 | Done | `anchor_trait_reviews` 多行 + dispute_note |
| AN-04 | 新作文 vs 锚作文定尺度 | Done | `anchor_scale_service.nearest_anchor_match` |
| AN-05 | 无 Anchor 时不宣称绝对分有效 | Done | `score_display_policy` + 报告 `NO_ANCHOR_CALIBRATION_SUFFIX` |

**V2 扩展**：成对比较、Bradley-Terry（§6.3）— 单独里程碑 **V2-ANCHOR**。

---

## 8. 模块 ⑦ 评分引擎（§7.3、§十）— 深化

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| S-01 | 规则+Rubric+LLM 证据+多模型投票 | Done | `v1_engine` + `trait_pipeline`；在线 evidence/vote 可选 |
| S-02 | LLM 禁止直接总分 | Done | `TRAIT_V1_LLM_APPEND` + merge 锁定脊柱；issues 须含 `trait_id` |
| S-03 | 无 Anchor 仅等级 + 未校准区间 | Done | `score_display_policy` + `verify_score_display_policy.py` |
| S-04 | 低置信不输出分数 | Done | `human_review_note` + 报告页复核 Alert |
| S-05 | §6.5 多标准视图 | Done | `multi_standard_views` + 报告 UI 卡片 |
| S-06 | 主要失分来源 | Done | `trait_interval.primary_loss_traits` → 报告 q5 + issues 权重排序 |

**硬规则补全（§5.3 L1、§7.2）**：

| A-ID | 能力 | 现状 |
|------|------|------|
| A-01 | 文体 | Done | `hard_rules._genre_issue` |
| A-02 | 身份 / 写作对象 | Done | `hard_rules._identity_issue` |
| A-03 | 作答范围 | Done | `scope_violation` + `verify_a03_scope_hard_rules` + requirement_scoring |
| A-04 | 错别字 / 语病 / 搭配 | Done | `hard_rules._typo_heuristic` + `verify_hard_rules_a04_a06.py` |
| A-05 | 机械摘抄 | Done | `mechanical_copy_ratio` + suite / a04_a06 |
| A-06 | 严重跑题 | Done | `severe_off_topic` + `main_point_hit` 信号 |

---

## 9. 模块 ⑧ 持续校准 + 主动学习（§8.3）

| ID | 触发条件 | 现状 | 缺口 |
|----|----------|------|------|
| AL-01 | Trait 模型分歧大 | Done | `active_learning_pool` + vote_spread 触发 |
| AL-02 | 同模型多次波动 | Done | `enqueue_retry_trait_volatility` + weak `retry_delta` |
| AL-03 | Evidence 不足 | Done | grounding 低 / evidence_insufficient 入池 |
| AL-04 | 标准匹配置信度低 | Done | orchestrator 使用 `QuestionStandardCard.match_confidence` 入池 |
| AL-05 | 等级边界样本 | Done | L1–L3 低置信计数 + `active_learning_boundary_confidence_max` |
| AL-06 | 申诉 / 点踩 | Done | `POST /reports/{id}/disputes` → `enqueue_dispute_sample`；`verify_al06_dispute_pool.py` |

**闭环**：`active_learning_pool` → 教研导出 → `rubric_version` bump → 回归 §7.5。

---

## 10. 诊断报告与产品红线（§一、§二、§十三）

| ID | 要求 | 现状 | 缺口 |
|----|------|------|------|
| REP-01 | 7 问固定开篇 | Done | `verify_rep01_diagnostic_seven.py`（七问 + 等级锁定） |
| REP-02 | 总体：能力+区间+置信度 | Done | Trait 总体卡：等级/区间/置信度/多标准中心/tier_only |
| REP-03 | T1～T8 分项+证据 | Done | `evidence_insufficient` + scoring_points withheld（trait_report_builder） |
| REP-04 | 主要问题按失分权重 | Done | `primary_loss_traits` + `verify_trait_report_spine` issues/trait_id |
| REP-05 | 修改建议可操作 | Done | `structured_suggestions` + `verify_rep05_structured_suggestions.py` |
| REP-06 | 争议提示 | Done | `standard_dispute_marks` 并入第 6 问 + 多标准 dependency |
| REP-07 | 免责声明 | Done | `ReportPrdDisclaimer` + 报告/列表/顶栏一致（PDF 导出待产品接） |
| REP-08 | 不宣称估分准 / 非官方 | Done | AppLayout 顶栏说明 + 报告/列表 Disclaimer |

**配置开关（§十-2 最简方案）**：

| REP-09 | `diagnostic_only_mode` | Done | `config.diagnostic_only_mode` + 报告强制 tier_only |

---

## 11. 数据存储（§十一）

| ID | 字段 | 现状 | 缺口 |
|----|------|------|------|
| D-01 | 单条 Trait 评分记录 | Done | `trait_scoring_records` 双写 + `verify_trait_scoring_records.py` |
| D-02 | model_votes / human_review | Done | `trait_scoring_records.model_votes` + evidence_payload 扩展 |
| D-03 | final_calibrated_score | V1 空 | 保持 NULL；V3 写入 |

**迁移**：自 hit_log 迁移脚本 + 双写过渡期。

---

## 12. 验证体系（§7.5）

| 指标 | 阈值 | 现状 | 缺口 |
|------|------|------|------|
| Evidence 准确率 | >90% | Done | `verify_evidence_accuracy.py` |
| 成对排序一致性 | >0.7 | Done | `verify_pair_rank_consistency.py`（BT 合成链） |
| 规则准确率 | 100% 确定性样例 | Done | `verify_hard_rules_deterministic.py` + 原 suite |
| Trait 稳定性 | 文档要求 | Done | `verify_trait_stability.py`（5 次同等级） |
| QWK（有 Anchor 后） | >0.6 | 骨架 | `verify_v3_calibration_gate` + 金标/锚多评 |

**交付**：`scripts/verify_prd_v1_compliance.py` 聚合门禁（CI 可选）。

---

## 13. 与旧系统关系（必须清理）

| ID | 项 | 动作 |
|----|-----|------|
| DEP-01 | 采分点池批改路径 | Done | `verify_prd_dep_guard.py` + 默认 `grading_point_pool_engine_allowed=0` |
| DEP-02 | `merge` LLM 维度覆盖 Trait | Done | `trait_report_builder` / `TRAIT_V1_LLM_APPEND` 锁定脊柱 |
| DEP-03 | 标准生产点池 L0～L3 | Done | `point_pool_pipeline_enabled=0` + `verify_dep03_point_pool_optional.py` |
| DEP-04 | 文档对齐说明 STD-PROD-EVAL | 重写为 **PRD-V1-诊断教练** 映射 |

---

## 14. V2 / V3 范围（本清单不阻塞 V1 Done，但需预留）

| 里程碑 | 内容 | PRD |
|--------|------|-----|
| V2-WS | 弱监督工厂完整 + 成对比较图 | §7.4、§6.3 |
| V2-ANCHOR | Anchor 规模化 + 相对尺度 | §8.1、§6.2 |
| V3-CAL | MFRM/Rasch + ICC/QWK 门禁 | §6.4 |
| V3-MODEL | 专用评分模型 | 骨架 Done：`v3_model_router.py` stub + `V3_TRAIT_MODEL_ENABLED` |

---

## 15. 推荐实施顺序（完全实现路径）

```text
Phase 0  文档与门禁：本清单 + verify_prd_v1_compliance 骨架 + 报告 JSON Schema
Phase 1  ② 标准卡全字段 + review_status + ③ Rubric 全量配置
Phase 2  ④ Evidence 引擎（LLM 抽取 + 子串校验）→ 重写 ⑦ B 档 Trait 判定
Phase 3  P-06 三模型 Trait 投票 + §6.5 多标准视图 + 置信度/展示策略（S-03/S-04）
Phase 4  ⑩ 报告生成器单一脊柱（REP-01～08）+ 前端对齐
Phase 5  ⑤ W-01～W-08 弱监督最小集 + ⑪ 数据表 + ⑧ 主动学习池
Phase 6  ⑥ Anchor 最小运营 + §7.5 指标达标 + DEP 清理旧引擎
Phase 7  V2/V3 立项（不在 V1 Done 内）
```

---

## 16. 进度跟踪（实施时更新）

| Phase | 状态 | 摘要 |
|-------|------|------|
| 0 | Done | `verify_prd_v1_compliance.py` 聚合门禁 + Rubric JSON 完整性校验 |
| 1 | Done | `StandardCardV1Schema` + builder；`trait_rubric_v1.json` 8×L0–L4；`review_status` 控制出分 |
| 2 | Done | `evidence_engine.py` 规则+LLM 合并与子串校验；`rubric_trait_level` B/C 定级；管线 `evidence_engine` trace；在线 `trait_llm_evidence_enabled`；`verify_evidence_grounding.py` |
| 3 | Done | 三模型 Trait 投票（primary/consensus/reviewer）；`multi_standard_views` strict/loose/dependency；`score_display_mode` + 人工复核文案；`verify_multi_standard_views.py` / `verify_score_display_policy.py` |
| 4 | Done | `trait_report_builder.py` 报告脊柱；LLM `TRAIT_V1_LLM_APPEND` 仅润色；issues/trait_id+weight；structured_suggestions；`ReportPrdDisclaimer`；`verify_trait_report_spine.py` |
| 5 | Done | `weak_labels` / `active_learning_pool` / `trait_pair_compare_tasks` 表；`weak_supervision_factory` + 入池；admin 导出 JSONL（`is_weak_label`）；重作 delta、争议入池；`verify_weak_supervision_factory.py` |
| 6 | Done | `anchor_essays` / `anchor_trait_reviews` / `trait_scoring_records`；`anchor_scale_service` 相对尺度；admin 锚作文 API；§7.5 `verify_prd_metrics_gate` + 硬规则套件；DEP merge 禁覆盖 Trait、点池 deprecated 标注 |
| 6+ | Done | A-01～A-06 硬规则 + `verify_hard_rules_a04_a06`；R-01 Rubric 目录外置；`boundary_policy` P-07；报告非官方文案 |
| 7 | Done | CI 合规门禁；V2 WS/BT；V3 QWK 骨架；`verify_trait_stability`；STD-PROD-EVAL 自动化 |

### Post-V1 优先级（Phase 7 / V2 入口）

| 优先级 | 项 | 说明 |
|--------|-----|------|
| P0 | M-11～M-14 | **Done（骨架+审核）**：`standard_consensus_pipeline.py` + `standard_consensus_3model_enabled`；M-14 `verify_standard_card_review.py` + Admin 审核队列 |
| P0 | 锚规模 10～20/题 | **运营 UI Done**：`/admin/anchors` + summary/seed-demo/PATCH；CLI `seed_demo_anchors.py`；相对尺度仍依赖真实录入规模 |
| P1 | R-02 全 8×L0–L4 Rubric 文案 | **Done**（v1.0.1 + 加减分条件） |
| P1 | Q-01～Q-03 | **Done**（`verify_essay_item_import.py`） |
| P2 | V2-WS / V2-ANCHOR | **骨架 Done**：`weak_supervision_v2_export` + `anchor_bradley_terry`；`verify_v2_ws_anchor.py`；Admin BT 摘要 |
| P3 | V3-CAL | **骨架 Done**：`calibration_metrics.py`（QWK/ICC/Rasch）；`trait_calibration_service` + `verify_v3_calibration_gate.py`；`GET /admin/calibration/metrics` |

---

## 17. 相关路径（现网基线）

| 能力 | 路径 |
|------|------|
| V1 编排 | `services/api/app/services/scoring_engine/orchestrator.py` |
| Trait 核心 | `services/api/app/domain/scoring_engine/v1_engine.py`, `trait_pipeline.py` |
| 标准卡（简） | `domain/scoring_engine/question_standard_card.py` |
| 投票 | `services/api/app/services/scoring_engine/trait_voting.py` |
| 报告 UI | `apps/web/src/components/ReportTraitDiagnostic.tsx` |
| 旧点池 | `services/api/app/services/point_pool_pipeline/`（标准生产，非 PRD V1 ⑦） |

---

**说明**：本文件为「完全实现」的**唯一缺口总表**；每完成一项应在对应 ID 打 `Done` 并补充验收命令一行摘要（与 `implementation-plan` 用户规则一致时可同步更新分 Phase 日志）。
