# Weekly Push — 每周特推自动化流程

每周自动从多个 GitHub 数据源抓取 AI 工具，生成图文并茂的 HTML 特推页面，并附带 AI 安全 + 内容审核报告。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（生成第 2 期）
python run.py --issue 2
```

输出文件：
- `output/week_002.html` — 本期特推页面
- `output/week_002_audit_report.md` — AI 审核报告

## 目录结构

```
weekly-push/
├── README.md
├── requirements.txt
├── config.yaml              # 数据源 URL、岗位配置
├── history.json             # 历史已推工具库（自动维护）
├── template.html            # HTML 渲染模板
├── run.py                   # 主入口
├── src/
│   ├── fetcher.py           # 抓取 GitHub 数据
│   ├── dedup.py             # 跨期去重
│   ├── generator.py         # AI 内容生成
│   ├── auditor.py           # AI 安全 + 内容审核
│   └── renderer.py          # JSON → HTML
├── output/                  # 生成结果（gitignore）
└── docs/
    ├── architecture.md      # 架构设计
    ├── prompt-design.md     # AI Prompt 设计
    └── audit-criteria.md    # 审核标准
```

## 依赖

- Python 3.10+
- `claude` CLI 已登录（复用 Claude Code 账号）
- 无需 GitHub Token（使用匿名 API，限速 60次/小时）

## 详细文档

- [架构设计](docs/architecture.md)
- [Prompt 设计](docs/prompt-design.md)
- [审核标准](docs/audit-criteria.md)
