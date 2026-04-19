"""
AI 内容生成：调用 claude --print 完成岗位分配和内容生成。
分两步：
  1. 岗位分配：从候选池为 11 个岗位各选 ≤5 个工具
  2. 内容生成：每批 10 个工具生成完整介绍（JSON）
"""

import json
import logging
import subprocess
from typing import Any

from src.fetcher import ToolRaw

logger = logging.getLogger(__name__)

TOOLS_PER_ROLE = 5
BATCH_SIZE = 10


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


def _extract_json(text: str) -> Any:
    """从 claude 输出中提取 JSON，兼容输出前后有多余文字的情况。"""
    # 优先找 ```json 代码块
    import re
    block = re.search(r"```json\s*([\s\S]*?)```", text)
    if block:
        return json.loads(block.group(1))
    # 找第一个 { 或 [ 开头的 JSON
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        idx = text.find(start_char)
        if idx >= 0:
            # 找对应结束位置
            depth = 0
            for i, ch in enumerate(text[idx:], idx):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        return json.loads(text[idx:i+1])
    raise ValueError(f"无法从输出中提取 JSON:\n{text[:300]}")


def assign_roles(candidates: list[ToolRaw], roles: list[dict]) -> dict[str, list[str]]:
    """
    调用 claude 为 11 个岗位分配工具，返回 {role_id: [tool_name, ...]}。
    """
    # 只传 name + readme 前 500 字，控制 token
    candidates_summary = [
        {
            "name": t.name,
            "source_url": t.source_url,
            "readme_summary": t.readme[:500],
        }
        for t in candidates
    ]

    roles_desc = "\n".join(
        f"- {r['id']}: {r['emoji']} {r['label']}" for r in roles
    )

    prompt = f"""你是一个 AI 工具编辑，负责为技术团队的周报选工具。

以下是候选工具列表（JSON 格式）：
{json.dumps(candidates_summary, ensure_ascii=False, indent=2)}

请为以下 11 个岗位各选最多 {TOOLS_PER_ROLE} 个最合适的工具：
{roles_desc}

规则：
1. 每个工具只能分配给一个岗位
2. 优先选功能清晰、来源可信（官方或知名维护者）的工具
3. 不确定分类的工具，选最贴近的岗位
4. 如果某个岗位没有合适工具，对应列表为空数组即可

输出格式（严格 JSON，不要多余文字）：
{{
  "ui-frontend": ["tool_name_1", "tool_name_2"],
  "qa-testing": [],
  ...
}}"""

    logger.info("调用 Claude 进行岗位分配...")
    output = _run_claude(prompt)
    assignment = _extract_json(output)
    logger.info("岗位分配完成")
    return assignment


def generate_tool_content(tools_batch: list[ToolRaw], role_map: dict[str, str]) -> list[dict]:
    """
    对一批工具（≤10个）调用 claude 生成完整内容，返回结构化 JSON 列表。
    role_map: {tool_name: role_id}
    """
    tools_input = [
        {
            "name": t.name,
            "role": role_map.get(t.name, "unknown"),
            "source_url": t.source_url,
            "readme": t.readme[:3000],  # 限制单工具 readme 长度
        }
        for t in tools_batch
    ]

    prompt = f"""你是一个技术内容编辑，负责为 AI 工具周报撰写工具介绍。
语言风格：简洁、直接、中文、面向开发者和产品团队。

以下是需要生成介绍的工具列表（JSON）：
{json.dumps(tools_input, ensure_ascii=False, indent=2)}

请为每个工具生成以下字段，输出 JSON 数组（严格 JSON，不要多余文字）：
[
  {{
    "name": "工具展示名称（简洁，保留英文品牌名）",
    "role": "对应的岗位 ID（从输入中取）",
    "platform": "mcp | claude-code | openai | other",
    "platform_label": "🧩 MCP | 🤖 Claude Code | 其他平台名",
    "platform_class": "from-mcp | from-cc | from-hermes | from-claw",
    "tags": ["标签1", "标签2"],
    "tagline": "一句话定位，20字以内，突出核心价值",
    "what": "它做什么，2-3句话，说清楚用户视角能得到什么",
    "why": "为啥特推，2-3句话，说竞品对比或独特优势",
    "example_biz": "商务例子，1句话场景，不要加💼前缀",
    "example_tech": "技术例子或安装说明，1句话，不要加⚡前缀",
    "install_cmd": "安装/调用命令，纯命令行，无则填 null"
  }}
]

要求：
- 不夸大，不写「革命性」「颠覆性」等词
- install_cmd 必须来自 README 原文，不要自己编造
- tags 只写关键词，如「官方」「2025 新星」「4.7k⭐」，最多 3 个
- platform_class 根据工具性质选择：MCP 服务用 from-mcp，Claude Code 原生 skill 用 from-cc，其他用 from-hermes"""

    logger.info(f"生成内容：{[t.name for t in tools_batch]}")
    output = _run_claude(prompt)
    results = _extract_json(output)
    if not isinstance(results, list):
        raise ValueError(f"期望 JSON 数组，得到: {type(results)}")
    return results


def generate_all(
    candidates: list[ToolRaw],
    roles: list[dict],
    tools_per_role: int = TOOLS_PER_ROLE,
) -> tuple[list[dict], list[str]]:
    """
    完整生成流程：分配岗位 → 批量生成内容。
    返回 (content_list, warnings)
    warnings: 候选不足时的提示信息
    """
    # Step 1: 岗位分配
    assignment = assign_roles(candidates, roles)

    # 验证并收集警告
    warnings = []
    tool_map: dict[str, ToolRaw] = {t.name.lower(): t for t in candidates}
    role_map: dict[str, str] = {}  # tool_name → role_id
    selected_tools: list[ToolRaw] = []

    for role in roles:
        role_id = role["id"]
        assigned = assignment.get(role_id, [])
        actual_count = len(assigned)

        if actual_count < tools_per_role:
            warnings.append(
                f"⚠️  {role['emoji']} {role['label']} 岗位只找到 {actual_count} 个工具（目标 {tools_per_role} 个）"
            )

        for tool_name in assigned[:tools_per_role]:
            key = tool_name.lower()
            if key in tool_map:
                raw = tool_map[key]
                role_map[raw.name] = role_id
                selected_tools.append(raw)
            else:
                logger.warning(f"分配了不存在的工具: {tool_name}")

    logger.info(f"共选出 {len(selected_tools)} 个工具，开始批量生成内容")

    # Step 2: 批量生成内容
    all_content: list[dict] = []
    for i in range(0, len(selected_tools), BATCH_SIZE):
        batch = selected_tools[i:i + BATCH_SIZE]
        logger.info(f"处理第 {i//BATCH_SIZE + 1} 批（{len(batch)} 个工具）")
        batch_content = generate_tool_content(batch, role_map)
        all_content.extend(batch_content)

    return all_content, warnings
