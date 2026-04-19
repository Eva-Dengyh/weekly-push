"""
渲染器：将生成的内容 JSON 通过 Jinja2 模板渲染为 HTML。
"""

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent.parent / "template.html"


def render(content_list: list[dict], roles: list[dict], issue: int, date: str) -> str:
    """
    将内容 JSON 渲染为 HTML 字符串。
    content_list: generator 生成的工具列表
    roles: config 中的岗位列表
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_PATH.parent)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template(TEMPLATE_PATH.name)

    # 按岗位分组
    role_tool_map: dict[str, list[dict]] = {r["id"]: [] for r in roles}
    for tool in content_list:
        role_id = tool.get("role", "")
        if role_id in role_tool_map:
            role_tool_map[role_id].append(tool)

    # 组装渲染数据
    sections = []
    for role in roles:
        tools = role_tool_map.get(role["id"], [])
        sections.append({
            "id": f"r{role['order']}",
            "label": role["label"],
            "emoji": role["emoji"],
            "order": role["order"],
            "tools": tools,
        })

    total_tools = len(content_list)

    html = template.render(
        issue=issue,
        date=date,
        total_tools=total_tools,
        sections=sections,
    )
    logger.info(f"HTML 渲染完成，共 {total_tools} 个工具")
    return html
