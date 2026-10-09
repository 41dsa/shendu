# 验收通知 — STD-P3（LLM 标准生成）

| 项目 | 内容 |
|------|------|
| 状态 | **已通过**（2026-10-09） |
| 完成日期 | 2026-10-09 |
| 任务 | STD-301～309 |

## 交付摘要

| ID | 内容 |
|----|------|
| STD-301 | P01 `generate_question_standard_llm` |
| STD-302 | P02 材料分析（无材料跳过） |
| STD-303/304 | P03 候选 + P04 合并 Rubric |
| STD-305 | `build_loss_rules` 失分规则模板 |
| STD-306 | 流水线步骤：candidates → merged → loss_rules → validate |
| STD-307 | `llm_json.call_standard_llm` 重试 + 失败 raw 片段 |
| STD-308 | `user_ai_usage.call_type=standard_p01…` |
| STD-309 | `scripts/verify_standard_pipeline_stub.py` |

## 运行模式

| 环境变量 | 行为 |
|----------|------|
| `STANDARD_GEN_MODE=stub` | 全程占位（无 LLM） |
| `STANDARD_GEN_MODE=llm` | 必须 Admin BYOK，否则失败 |
| `STANDARD_GEN_MODE=auto`（默认） | 创建 job 的管理员已配置主模型 → LLM；否则 stub |

## 验收 A — Stub（无需 Key）

```bash
cd services/api && source .venv/bin/activate
export STANDARD_GEN_MODE=stub
python scripts/verify_standard_pipeline_stub.py
```

## 验收 B — LLM（需管理员 BYOK）

1. 管理员在 Web **设置 · AI 服务** 配置主模型并测试连接。
2. 该管理员登录后：

```bash
export STANDARD_GEN_MODE=llm
# POST /admin/standards/jobs  {"question_id":"demo-essay-001","document_ids":[]}
# GET /admin/standards/jobs/{id}  → steps 含 rubric_candidates / rubric_merged
```

3. 检查 `user_ai_usage` 表存在 `call_type` 为 `standard_p01` 等记录（可选）。

## 结论

- [x] 通过  
- [ ] 需修改：___________
