"""
AI 双重审核：安全审核 + 内容审核。
调用 claude --print 各一次，输出 Markdown 报告。
"""

import json
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


def _run_claude(prompt: str) -> str:
    """调用 claude --print，返回输出文本。"""
    result = subprocess.run(
        ["claude", "--print", prompt],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude 调用失败: {result.stderr[:500]}")
    return result.stdout.strip()


def _extract_json(text: str):
    """从输出中提取 JSON。"""
    import re
    block = re.search(r"```json\s*([\s\S]*?)```", text)
    if block:
        return json.loads(block.group(1))
    idx = text.find("[")
    if idx >= 0:
        depth = 0
        for i, ch in enumerate(text[idx:], idx):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return json.loads(text[idx:i+1])
    raise ValueError(f"无法提取 JSON:\n{text[:300]}")


def run_security_audit(content_list: list[dict]) -> str:
    """安全审核，返回 Markdown 格式结果。"""
    tools_input = [
        {
            "name": t.get("name"),
            "install_cmd": t.get("install_cmd"),
            "source_url": t.get("source_url", ""),
            "platform": t.get("platform"),
        }
        for t in content_list
    ]

    prompt = f"""你是一个安全审核员，负责审查 AI 工具周报中推荐工具的安全性。

本期工具列表（JSON）：
{json.dumps(tools_input, ensure_ascii=False, indent=2)}

请对每个工具进行安全审核，检查以下维度：
1. 安装命令风险：命令是否来自可信来源（官方域名/npm 官方包），是否有恶意特征（随机字符串包名、奇怪域名）
2. 来源可信度：是否为官方维护、维护者身份是否可查
3. 数据隐私：工具是否涉及抓取、代理、数据外传等行为
4. 灰色地带：如爬取竞品、LinkedIn 抓取等，是否存在法律/合规风险

输出格式（严格 JSON 数组，不要多余文字）：
[
  {{
    "name": "工具名",
    "level": "pass | warn | danger",
    "issues": ["问题描述1"]
  }}
]

level 定义：
- pass：无明显风险
- warn：存在需要注意的点，建议加说明
- danger：不建议推荐，或必须修改后才能推荐"""

    logger.info("运行安全审核...")
    output = _run_claude(prompt)
    results = _extract_json(output)

    # 格式化为 Markdown
    danger_items = [r for r in results if r["level"] == "danger"]
    warn_items = [r for r in results if r["level"] == "warn"]
    pass_items = [r for r in results if r["level"] == "pass"]

    lines = ["## 安全审核\n"]

    lines.append(f"### 🔴 Danger（{len(danger_items)} 项）")
    if danger_items:
        for r in danger_items:
            issues = "；".join(r.get("issues", []))
            lines.append(f"- **[{r['name']}]** {issues}")
    else:
        lines.append("- 无")

    lines.append(f"\n### 🟡 Warn（{len(warn_items)} 项）")
    if warn_items:
        for r in warn_items:
            issues = "；".join(r.get("issues", []))
            lines.append(f"- **[{r['name']}]** {issues}")
    else:
        lines.append("- 无")

    lines.append(f"\n### 🟢 Pass（{len(pass_items)} 个）")
    if pass_items:
        lines.append(", ".join(r["name"] for r in pass_items))

    return "\n".join(lines)


def run_content_audit(content_list: list[dict]) -> str:
    """内容审核，返回 Markdown 格式结果。"""
    # 只传关键字段，减少 token
    tools_input = [
        {
            "name": t.get("name"),
            "role": t.get("role"),
            "platform": t.get("platform"),
            "tagline": t.get("tagline"),
            "what": t.get("what"),
            "why": t.get("why"),
            "install_cmd": t.get("install_cmd"),
            "tags": t.get("tags"),
        }
        for t in content_list
    ]

    prompt = f"""你是一个内容审核员，负责审查 AI 工具周报的内容质量。

本期内容（JSON）：
{json.dumps(tools_input, ensure_ascii=False, indent=2)}

请检查以下维度：
1. 夸大表述：是否有无依据的效果承诺（「秒变专家」「10倍效率」「革命性」等）
2. 准确性：install_cmd 格式是否正确，platform 分类是否合理
3. 完整性：tagline / what / why 是否填写完整，是否有空值
4. 一致性：同岗位工具的描述风格是否统一

严格按以下 Markdown 格式输出（不要输出 JSON）：

## 内容审核

### 🔴 必须修（N 项）
- [工具名] 字段：问题描述

### 🟡 建议修（N 项）
- [工具名] 字段：问题描述

### 🟢 通过（N 个）
工具名列表

### 总结
总体质量评估一句话。"""

    logger.info("运行内容审核...")
    output = _run_claude(prompt)
    return output


def run_audit(content_list: list[dict], issue: int, warnings: list[str]) -> str:
    """执行完整审核，返回 Markdown 报告字符串。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total = len(content_list)

    security_section = run_security_audit(content_list)
    content_section = run_content_audit(content_list)

    parts = [
        f"# 第 {issue} 期审核报告",
        f"\n生成时间：{now}  ",
        f"工具总数：{total}",
    ]

    if warnings:
        parts.append("\n## ⚠️ 候选不足提示\n")
        parts.extend(warnings)

    parts.append(f"\n---\n\n{security_section}")
    parts.append(f"\n---\n\n{content_section}")
    parts.append("""
---

## 发布清单

- [ ] 处理所有 🔴 Danger 工具（移除或修改）
- [ ] 处理所有 🔴 必须修内容
- [ ] 酌情处理 🟡 项
- [ ] 确认后发布 HTML""")

    return "\n".join(parts)
