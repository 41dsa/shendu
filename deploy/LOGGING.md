# 日志与脱敏（BE-702）

## 原则

- **禁止**在日志中输出：API Key、JWT、用户作文全文、题干/材料全文。
- 访问日志仅记录：`METHOD path status duration`（见 `SafeAccessLogMiddleware`）。
- 批改与 AI 调用错误信息只保留上游状态码与截断后的 error message，不包含 request payload。

## 运维

- 生产环境将 uvicorn access log 设为 warning，依赖应用层 `shendu.access`。
- 数据库备份见 `scripts/backup_sqlite.sh`（OPS-702 本地/SQLite）。
