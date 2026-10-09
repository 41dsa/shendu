# 验收通知 — STD-P4 / STD-P5

| 项目 | 内容 |
|------|------|
| 状态 | **已通过**（2026-10-09） |
| 完成日期 | 2026-10-09 |

## STD-P4（验证与置信度）

- 五项验证器：`domain/standard_engine/validation.py`（已有）
- 流水线 `validate` 步增加 `standard_confidence`、`confidence_band`
- 发布门槛：`settings.standard_publish_min_confidence`（默认 **0.85**），不足则 `POST .../publish` 返回 400

## STD-P5（发布与批改）

| API | 说明 |
|-----|------|
| `POST /admin/standards/jobs/{id}/publish?force=false` | 发布标准，写 `exam_question_standards` + 同步 `questions.scoring_points` |
| `GET /admin/standards/questions/{id}/versions` | 版本列表 |
| `POST /admin/standards/questions/{id}/rollback?version=N` | 回滚激活版本 |
| `GET /admin/standards/questions/{id}/active` | 当前生效标准包 |

- `essay_context.resolve_essay_context(..., db)`：有已发布标准时使用其 Rubric / focus_points / loss_rules
- `grading_service` 用户 JSON 增加 `focus_points`、`loss_rules`、`standard_version`（Prompt 06 合并主批改，DEC-04）

## 验收步骤

```bash
cd services/api && source .venv/bin/activate
export STANDARD_GEN_MODE=stub
python scripts/verify_standard_publish.py
```

### HTTP 联调（管理员 Token）

1. `POST /admin/standards/jobs` → `question_id: demo-essay-001`
2. `GET /admin/standards/jobs/{id}` → `status: validated`
3. `POST /admin/standards/jobs/{id}/publish`
4. `GET /admin/standards/questions/demo-essay-001/active`
5. 用户提交该题批改，报告应带 `standard_version`（若 payload 中有）

## 结论

- [x] 通过  
- [ ] 需修改：___________
