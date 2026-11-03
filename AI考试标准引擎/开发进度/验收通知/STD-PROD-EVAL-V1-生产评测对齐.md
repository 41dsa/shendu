# 验收通知 — STD-PROD-EVAL V1（生产与评测引擎方案对齐）

| 项目 | 内容 |
|------|------|
| 状态 | **自动化已通过**（2026-10-16；产品签核待填） |
| 依据 | [AI考试标准生产与评测引擎-对齐说明.md](../../AI考试标准生产与评测引擎-对齐说明.md) |
| 范围 | 大作文 Track-A；不含小题采分点 Track-B |

## PRD V1 诊断教练映射（DEP-04，2026）

| 旧 STD-PROD 表述 | 现网 V1 脊柱 |
|------------------|--------------|
| ④ 分层评分引擎 + 确定性总分 | **`diagnostic_trait_v1`**：`v1_engine` + Trait 区间，LLM 总分弱标签 |
| 采分点池 L0～L3 批改 | **已废弃批改路径**；点池仅标准生产可选（`point_pool_pipeline_enabled`） |
| 证据链 | Trait `evidence_engine` + 报告 `evidence_chain` |
| 校准/QWK | **V3**；V1 用锚作文相对尺度 + `anchor_count` 控制展示 |
| 合规门禁 | `python scripts/verify_prd_v1_compliance.py`（CI：`std-engine-ai.yml`） |
| V3 校准 | `python scripts/verify_v3_calibration_gate.py`；运维 `run_calibration_gate.py` |

## 交付摘要

1. **产品定位文档**：七模块映射、三阶段路线、与现网差距说明  
2. **① 试题解析**：标准任务 `structured` 步含 `parse`（考试/卷种/字数/能力）  
3. **③ 验证增强**：准则 `usage_band`、区间分校验、验证步 `criterion_confidence_tiers`、发布后 enriched rubric  
4. **④ 分层评分引擎**：`domain/scoring_engine` + `services/scoring_engine`；`grading_service` 以确定性总分为脊柱融合 LLM  
5. **⑤ 证据链**：批改输出 `evidence_chain`；报告「评分依据」展示（有则显示）  
6. **⑥ 校准导出**：`scripts/export_calibration_dataset.py`（金标 + 争议）  
7. **契约扩展**：`RubricCriterionSchema` 增加 `score_min`/`score_max`/`usage_band`  

## 验收步骤

### 自动化

```bash
cd services/api && source .venv/bin/activate
python scripts/verify_prod_eval_alignment.py
python scripts/verify_prd_v1_compliance.py
python scripts/verify_scoring_engine.py
python scripts/verify_standard_pipeline_stub.py
python scripts/verify_std_e_suite.py
python scripts/verify_trait_stability.py
```

### Admin / 产品（建议）

1. **考试标准引擎** → 任选一题跑 stub/LLM 任务 → 打开 **validate** 步，确认含 `criterion_confidence_tiers`  
2. 发布标准 → 题库模式批改 → 报告 **评分依据** 可见标准版本；模型若返回 `evidence_chain` 则见「评分证据链」  
3. （可选）`python scripts/export_calibration_dataset.py /tmp/calibration.csv` 有金标时非空  

### 自备批改

- 默认 **走标准引擎**：`custom_essay_standard.py`（批改步 `custom_standard` → 缓存 → `custom_engine`）
- 关闭：`.env` 设 `CUSTOM_ESSAY_STANDARD_ENGINE_ENABLED=false` 回退默认四维
- 模式：`CUSTOM_ESSAY_STANDARD_MODE=auto|stub|llm`（auto=有 BYOK 则 LLM 生成标准，否则 stub）

## 通过标准

- [ ] 上述脚本全部 exit 0  
- [ ] 对齐说明文档与代码路径一致  
- [ ] 接受 Track-B / 三评审 / 自动进化 **不在本轮**  

验收人：__________　日期：__________
