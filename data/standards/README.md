# 考试标准引擎 — 资料与题库

## 目录

| 路径 | 说明 |
|------|------|
| `国考/2024/demo_essay_batch.csv` | 大作文元数据（国考 + 部分省考 **联调示例**，供引擎压测；导入后题量以 DB 为准） |
| `annotation/` | 教研标注模板与 `questions_for_labeling.csv` |

## 导入题库

```bash
cd services/api
python scripts/seed_standard_essay_batch.py
# 或
python scripts/import_standard_questions_csv.py ../data/standards/国考/2024/demo_essay_batch.csv
```

## 标注与指标（纯 AI，DEC-06）

默认 **无需人工**：标准 job `validated` 后自动反写 `questions_for_labeling.csv`。

```bash
python scripts/export_annotation_skeleton.py   # 仅补新题空行
python scripts/bootstrap_annotation_from_jobs.py --all-essay --overwrite
python scripts/eval_standard_metrics.py ../data/standards/annotation/questions_for_labeling.csv
python scripts/mstd_e_ai_report.py
```

## 批量生成标准（Admin BYOK）

```bash
export STANDARD_GEN_MODE=llm   # 或 stub
python scripts/batch_standard_jobs.py --all-essay --limit 15 --sync --delay 2 \
  --admin-email your-admin@example.com
```

## 纯 AI 无人值守（推荐联调）

```bash
STANDARD_GEN_MODE=stub STANDARD_AUTO_PUBLISH=1 STANDARD_AUTO_PUBLISH_FORCE=1 \\
  python scripts/run_ai_standard_batch.py --all-essay --limit 21
```

含 **AI 金标**（每题 3 条 stub 范文）。批改回归（需 BYOK）：

```bash
python scripts/seed_ai_gold.py --question-id demo-essay-001 --mode stub
python scripts/run_ai_gold_regression.py --admin-email your-admin@example.com
```

> 真题正文请以教研核实为准；CSV 中部分题为 **引擎联调示例**，不代官方题库。

## M-STD-E 实测建议顺序

1. 导入/扩充 CSV → 上传参考解析 → `batch_standard_jobs.py` 生成并发布标准  
2. Admin **金标回归**跑分；对比「按标准版本分组」通过率（需题目已发布 `exam_question_standards`）  
3. 填写 `annotation/questions_for_labeling.csv` 后跑 `eval_standard_metrics.py`，对照 [验收清单-STD-E.md](../../AI考试标准引擎/开发进度/验收清单-STD-E.md)
