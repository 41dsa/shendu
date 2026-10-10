# 自备大作文批改 · 写作技巧参考

- 默认文件：`essay_writing_technique.txt`（UTF-8）
- 导入：`cd services/api && python scripts/import_essay_writing_guide.py /path/to/你的.pdf`
- 默认 **关闭**；开启：`.env` 中 `ESSAY_WRITING_GUIDE_ENABLED=true`
- 自定义路径：`ESSAY_WRITING_GUIDE_PATH=/abs/path/to.txt`
- 长度上限：`ESSAY_WRITING_GUIDE_MAX_CHARS=10000`（约 21 页 PDF 全文可截断）

仅 **用户自备题干/材料** 批改时注入；题库选题 + 已发布考试标准不受影响。

版权：请仅导入你有权使用的资料；参考文不对学员端展示全文，仅用于模型上下文。
