"""
从 GitHub 目录 URL 抓取工具信息。
支持匿名 API，限速 60次/小时，每次请求间隔 1s。
"""

import re
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
REQUEST_INTERVAL = 1.2  # 秒，留余量


@dataclass
class ToolRaw:
    name: str
    source_url: str
    readme: str
    stars: int = 0
    source_repo: str = ""
    tags: list = field(default_factory=list)


def _parse_github_url(url: str) -> tuple[str, str, str]:
    """
    解析 GitHub 目录 URL，返回 (owner, repo, path)。
    例：https://github.com/anthropics/skills/tree/main/skills
    → ("anthropics", "skills", "skills")
    """
    pattern = r"github\.com/([^/]+)/([^/]+)/tree/[^/]+/?(.*)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"无法解析 GitHub URL: {url}")
    owner, repo, path = match.group(1), match.group(2), match.group(3)
    return owner, repo, path.rstrip("/")


def _get(url: str, params: Optional[dict] = None) -> dict | list:
    """带限速的 GitHub API GET 请求。"""
    headers = {"Accept": "application/vnd.github+json"}
    resp = requests.get(url, headers=headers, params=params, timeout=15)
    time.sleep(REQUEST_INTERVAL)

    if resp.status_code == 403:
        raise RuntimeError("GitHub API 限速（60次/小时），请稍后再试")
    resp.raise_for_status()
    return resp.json()


def _fetch_readme(owner: str, repo: str, path: str) -> str:
    """
    抓取某路径下的说明文件内容（base64 解码）。
    按优先级依次尝试：README.md → SKILL.md → README.rst
    """
    import base64
    candidates = ["README.md", "SKILL.md", "README.rst"]
    for filename in candidates:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}/{filename}"
        try:
            data = _get(url)
            if isinstance(data, dict) and data.get("encoding") == "base64":
                return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            continue
    logger.warning(f"获取说明文件失败 {path}：未找到 {candidates}")
    return ""


def _fetch_repo_stars(owner: str, repo: str) -> int:
    """获取 repo 的 star 数。"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        data = _get(url)
        return data.get("stargazers_count", 0)
    except Exception:
        return 0


def fetch_from_source(github_url: str) -> list[ToolRaw]:
    """
    从一个 GitHub 目录 URL 抓取所有子目录作为工具条目。
    每个子目录视为一个工具，抓取其 README.md。
    """
    owner, repo, path = _parse_github_url(github_url)
    logger.info(f"抓取数据源: {owner}/{repo}/{path}")

    api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    try:
        items = _get(api_url)
    except Exception as e:
        logger.error(f"获取目录列表失败: {e}")
        return []

    if not isinstance(items, list):
        logger.error(f"返回格式异常，期望 list: {type(items)}")
        return []

    tools: list[ToolRaw] = []
    dirs = [item for item in items if item.get("type") == "dir"]
    logger.info(f"发现 {len(dirs)} 个子目录")

    for item in dirs:
        tool_name = item["name"]
        tool_path = item["path"]
        source_url = f"https://github.com/{owner}/{repo}/tree/main/{tool_path}"

        readme = _fetch_readme(owner, repo, tool_path)
        if not readme:
            logger.warning(f"跳过 {tool_name}：无 README")
            continue

        tools.append(ToolRaw(
            name=tool_name,
            source_url=source_url,
            readme=readme,
            source_repo=f"{owner}/{repo}",
        ))
        logger.debug(f"  已抓取: {tool_name}")

    logger.info(f"共抓取 {len(tools)} 个工具")
    return tools


def fetch_all(sources: list[str]) -> list[ToolRaw]:
    """从多个数据源抓取，合并结果（按 name 去重）。"""
    all_tools: list[ToolRaw] = []
    seen_names: set[str] = set()

    for url in sources:
        tools = fetch_from_source(url)
        for tool in tools:
            key = tool.name.lower()
            if key not in seen_names:
                seen_names.add(key)
                all_tools.append(tool)
            else:
                logger.debug(f"同批去重跳过: {tool.name}")

    logger.info(f"所有数据源合并后共 {len(all_tools)} 个候选工具")
    return all_tools
