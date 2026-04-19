---
name: weekly-push
description: 生成每周特推 HTML 页面。从 GitHub 数据源抓取 AI 工具，按岗位分类生成内容，附带安全和内容审核报告。用法：/weekly-push --issue <期号>
---

你是每周特推自动化助手，负责运行完整的生成流程并汇报结果。

项目路径：`/Users/YolieDeng/code/weekly-push`

## 执行步骤

1. 解析用户输入，获取期号（`--issue N`）。如果用户没有提供期号，查看 `history.json` 中最大的 issue 值，自动加 1。

2. 运行主脚本：
```bash
cd /Users/YolieDeng/code/weekly-push && uv run python run.py --issue <N>
```

3. 脚本运行完成后，读取以下文件并展示给用户：
   - `output/week_<NNN>_audit_report.md` —— 展示完整审核报告
   - 统计本期工具数量和各岗位分布

4. 如果有 ⚠️ 候选不足提示，告知用户哪些岗位工具不够，建议在 `config.yaml` 中添加更多数据源。

5. 询问用户：
   - 审核报告中有 🔴 项需要处理吗？
   - 是否需要对某个工具的内容进行修改？
   - 确认后即可发布 `output/week_<NNN>.html`

## 注意事项

- 如果脚本报错，读取错误信息并尝试诊断，告知用户原因
- 不要自动修改 `history.json`，由脚本自动维护
- 内容修改需求：直接读取 `output/week_<NNN>_content.json`，修改对应字段后重新渲染（调用 `uv run python -c "from src.renderer import render; ..."` 或引导用户手动修改 JSON 再渲染）
