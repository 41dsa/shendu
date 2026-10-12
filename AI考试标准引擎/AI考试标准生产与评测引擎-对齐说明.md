# AI 考试标准生产与评测引擎 — 方案对齐说明

| 项目 | 内容 |
|------|------|
| 依据 | 产品方案 PDF《AI考试标准生产与评测引擎方案》（document-4） |
| 现网基线 | V0.1-E 大作文 Track-A + M-STD-E-AI |
| 本次 | **V1-PROD-EVAL** 定位重述 + 七模块映射 + 可验收增量 |

## 1. 产品重新定义

| 原表述 | 新表述（采纳） |
|--------|----------------|
| 有标准才能评 | **先生产/验证「尺子」，再批改** |
| 简单 AI 批改 | **标准生产 · 验证 · 评测 · 校准 · 版本管理** |

大作文线（DEC-09）：**RubricCriterion** 对应方案中的「语义采分单元」；小题 **ScoringPoint（P001…）** 仍属 Track-B 规划，未在本轮实现。

## 2. 七模块 ↔ 代码映射

| 模块 | 大作文现网 | 路径/能力 |
|------|------------|-----------|
| ① 试题解析 | **增强** | `question_parse.parse_essay_question_metadata`；流水线 step `structured.parse` |
| ② 标准生产 | 已有 | `pipeline.py` P01～P04 / stub / LLM |
| ③ 标准验证 | **增强** | `validation.py` + 准则 **usage_band**、区间分、置信度分层摘要 |
| ④ 评分执行 | **自备已接入** | `custom_essay_standard.py`：批改前生成/缓存标准；`grading_standard_mode=custom_engine` |
| ⑤ 证据解释 | **增强** | 批改 JSON `evidence_chain`；报告「评分证据链」 |
| ⑥ 评分校准 | **增量** | 金标回归 + `export_calibration_dataset.py`；争议导出（人工闭环待运营） |
| ⑦ 标准版本 | 已有 | `exam_question_standards.version`；报告 `standard_version` |

## 3. 方案要点落地

| 方案章节 | 落地 |
|----------|------|
| §7 准则置信度 high/medium/low | `criterion_confidence.py` → `usage_band`；低置信 **失分规则 advisory_only** |
| §9 区间评分 + score_confidence | `score_min`/`score_max`；`scoring_rules.score_confidence_declaration`（默认 medium） |
| §8 语义采分 | 批改 Prompt：`acceptable_expressions` / `typical_gaps`，禁止纯关键词匹配 |
| §11 多评审 | 现网 **双路总分复核**（非三评审完整版） |
| §17 人工 | 采纳 **人工审标准、不重复批改**；DEC-06 纯 AI 路径仍可用于联调 |
| §18 三阶段 | **V1** 标准生产（本轮）· **V2** 批改证据链（本轮 partial）· **V3** 校准 Benchmark（导出脚本，闭环待数据） |

## 4. 未纳入本轮（路线图）

- 小题题型 + 材料段落级 **P001 采分点** 与 Track-B 流水线  
- 三模型评审 + 自动仲裁  
- 评分标准 **自动进化**（仍须 Admin 改 Prompt / 重新发布标准）  
- 官方真题 **自动采集**

## 5. 验收

见 [开发进度/验收通知/STD-PROD-EVAL-V1-生产评测对齐.md](./开发进度/验收通知/STD-PROD-EVAL-V1-生产评测对齐.md)。

```bash
cd services/api && source .venv/bin/activate
python scripts/verify_prod_eval_alignment.py
python scripts/verify_std_e_suite.py   # 含对齐冒烟
```
