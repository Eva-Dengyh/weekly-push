# 架构设计

## 整体流程

```
┌─────────────────────────────────────┐
│  config.yaml                        │
│  - 多个 GitHub 目录 URL              │
│  - 11 个固定岗位                     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 1: Fetcher（fetcher.py）       │
│                                     │
│  对每个 URL：                         │
│  GET /repos/{owner}/{repo}/contents │
│       /{path}?ref={branch}          │
│  → 列出子目录                         │
│  → 每个子目录抓 README.md            │
│  → 解析工具名、描述、安装命令、stars  │
│                                     │
│  输出：List[ToolRaw]                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: Dedup（dedup.py）           │
│                                     │
│  对比 history.json：                 │
│  - 工具名精确匹配                     │
│  - 工具名模糊匹配（防改名重复）         │
│                                     │
│  输出：List[ToolRaw]（去重后候选池）   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 3: Generator（generator.py）   │
│                                     │
│  调用 claude --print：               │
│  - 从候选池按 11 个岗位各选 5 个      │
│  - 生成每个工具的完整内容             │
│    · tagline（一句话定位）            │
│    · 它做什么                        │
│    · 为啥特推                        │
│    · 使用例子（商务 / 技术 两种视角） │
│    · 安装/调用命令                   │
│  - 输出结构化 JSON                   │
│                                     │
│  输出：week_N_content.json           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 4: Auditor（auditor.py）       │
│                                     │
│  调用 claude --print（安全审核）：    │
│  - 安装命令是否有风险（恶意包特征）   │
│  - 工具来源可信度（官方 vs 社区）     │
│  - 是否涉及数据隐私 / 爬取灰色地带   │
│                                     │
│  调用 claude --print（内容审核）：    │
│  - 是否有夸大不实表述                │
│  - 岗位分类是否准确                  │
│  - 描述一致性 / 格式规范             │
│                                     │
│  输出：week_N_audit_report.md        │
│  问题分级：🔴 必须修 / 🟡 建议修 / 🟢 通过 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 5: Renderer（renderer.py）     │
│                                     │
│  week_N_content.json + template.html │
│  → Jinja2 渲染                       │
│  → week_N.html                       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 6: 更新 history.json           │
│  把本期 55 个工具追加进历史库         │
└─────────────────────────────────────┘
```

## 数据模型

### ToolRaw（抓取原始数据）
```json
{
  "name": "figma-dev-mode",
  "source_url": "https://github.com/anthropics/skills/tree/main/skills/figma-dev-mode",
  "readme": "...",
  "stars": 1200,
  "source_repo": "anthropics/skills"
}
```

### ToolContent（AI 生成后）
```json
{
  "name": "Figma Dev Mode MCP",
  "role": "ui-frontend",
  "platform": "mcp",
  "platform_label": "🧩 MCP",
  "tags": ["Figma 官方"],
  "tagline": "让 AI 直接读你 Figma 设计稿里的真实图层",
  "what": "...",
  "why": "...",
  "example_biz": "...",
  "example_tech": "...",
  "install_cmd": "claude mcp add figma-dev-mode https://www.figma.com/mcp"
}
```

### history.json 结构
```json
{
  "tools": [
    {
      "name": "Figma Dev Mode MCP",
      "issue": 1,
      "date": "2026-04-19"
    }
  ]
}
```

## 固定岗位列表

| ID | 名称 | emoji |
|----|------|-------|
| ui-frontend | UI / 前端 | 🎨 |
| qa-testing | QA 测试 | 🧪 |
| product-manager | 产品经理 | 📊 |
| backend-dev | 后端开发 | 💻 |
| devops | 运维 | 🛠️ |
| seo | SEO / 站群 | 🚀 |
| biz-service | 商务 / 客服 | 🤝 |
| data-bi | 数据 / BI | 📈 |
| hr | HR / 招聘 | 👥 |
| finance | 财务 | 💰 |
| content | 内容创作 | 🎬 |

## 关键约束

- 每期固定 11 岗位 × 5 工具 = 55 个工具
- 候选池不足时：该岗位用已有数量，不强行凑数，运行结束时打印提示（如「⚠️ devops 岗位只找到 3 个工具」）
- 去重范围：全历史（不只是上一期），对比 history.json 中所有已推工具
- GitHub API 匿名模式：60次/小时，fetcher 需要控制请求频率（每次请求间隔 1s）
- `claude --print` 内容生成：每批 10 个工具调用一次，55 个工具共约 6 次调用
- `history.json` 更新时机：HTML 渲染完成后自动追加本期工具，无需手动操作
