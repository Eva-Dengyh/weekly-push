"""
跨期去重：对比 history.json，过滤掉历史上已推过的工具。
使用名称模糊匹配，防止改名后重复推。
"""

import json
import logging
from pathlib import Path

from src.fetcher import ToolRaw

logger = logging.getLogger(__name__)

HISTORY_PATH = Path(__file__).parent.parent / "history.json"


def _normalize(name: str) -> str:
    """标准化工具名，用于模糊匹配。"""
    return name.lower().replace("-", "").replace("_", "").replace(" ", "")


def load_history() -> dict:
    if not HISTORY_PATH.exists():
        return {"tools": []}
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(tools: list[dict], issue: int, date: str) -> None:
    """追加本期工具到 history.json。"""
    history = load_history()
    existing_names = {_normalize(t["name"]) for t in history["tools"]}

    added = 0
    for tool in tools:
        norm = _normalize(tool["name"])
        if norm not in existing_names:
            history["tools"].append({
                "name": tool["name"],
                "issue": issue,
                "date": date,
            })
            existing_names.add(norm)
            added += 1

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"history.json 已更新，新增 {added} 条记录")


def filter_candidates(tools: list[ToolRaw]) -> list[ToolRaw]:
    """过滤掉历史已推工具，返回候选池。"""
    history = load_history()
    seen = {_normalize(t["name"]) for t in history["tools"]}

    candidates = []
    skipped = []
    for tool in tools:
        if _normalize(tool.name) in seen:
            skipped.append(tool.name)
        else:
            candidates.append(tool)

    if skipped:
        logger.info(f"去重过滤 {len(skipped)} 个历史工具: {', '.join(skipped[:5])}{'...' if len(skipped) > 5 else ''}")
    logger.info(f"去重后候选池: {len(candidates)} 个工具")
    return candidates
