# 验收通知 — STD-P6 Admin 前端

| 项目 | 内容 |
|------|------|
| 状态 | **已通过**（2026-10-09） |
| 完成日期 | 2026-10-09 |

## 交付

| ID | 路径 / 说明 |
|----|-------------|
| STD-601 | `/admin/standards` + 侧栏「考试标准引擎」 |
| STD-602 | 资料上传 + 列表（`AdminStandardsPage`） |
| STD-603 | 任务表 + Modal 步骤 Collapse（自动轮询 running） |
| STD-604 | 任务详情 JSON 预览；验证/置信度 Descriptions |
| STD-605 | `validated` 任务显示「发布标准」按钮 |
| STD-606 | `api/upload.ts` + 与现有 Admin 布局一致 |

## 验收步骤

1. 启动 API + Web（`apps/web`：`npm run dev`）。
2. 管理员登录 → **教研后台 → 考试标准引擎**。
3. 上传一个 `.txt` 资料，列表出现新条目。
4. 选择题目（如 demo 或 CSV 导入题）→ **生成标准** → 任务 Modal 中步骤走完后 `validated`。
5. 点击 **发布标准** → 无报错 Toast。
6. （可选）`GET /admin/standards/questions/{id}/active` 有数据。

## 未做（可 P6.1）

- 版本回滚 UI（API 已有 `POST .../rollback?version=`）
- Rubric 表格化预览（当前为 JSON Collapse）

## 结论

- [x] 通过  
- [ ] 需修改：___________
