# 验收通知 — M-STD-E-AI（纯 AI，DEC-06～08）

| 项目 | 内容 |
|------|------|
| 状态 | **已通过** |
| 完成日期 | 2026-10-09 |
| 里程碑 | **M-STD-E-AI**（替代原 M-STD-E 人工教研路径） |

## 交付摘要

- 标准流水线：资料 → P01～P05 → validate → **自动发布**（DEC-07）→ 批改读标准
- **自动反写** `questions_for_labeling.csv`（DEC-06）
- **AI 金标** 高/中/低 + 回归记录 `standard_version`（DEC-08）
- 一键：`run_pure_ai_pipeline.py`；CI：`.github/workflows/std-engine-ai.yml`
- Admin：自洽指标、M-STD-E-AI 里程碑 Alert

## 验收命令（复现）

```bash
cd services/api && source .venv/bin/activate
python scripts/init_db.py && alembic stamp head
python scripts/run_pure_ai_pipeline.py --limit 25 --mode stub
python scripts/verify_mstd_e_ai_milestone.py
STANDARD_AUTO_PUBLISH=0 python scripts/verify_std_e_suite.py
```

## 边界

- 自洽指标 **不对标** 官方阅卷；联调 CSV 非官方题库全文。
- 生产 LLM 质量需 BYOK 下另跑 `--mode llm` 与可选 `--run-gold-regression`。

## 结论

- [x] 通过
- [ ] 需修改：___________
