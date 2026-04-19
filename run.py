#!/usr/bin/env python3
"""
每周特推自动化主入口。

用法：
  python run.py --issue 2
"""

import argparse
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

import yaml

# 确保项目根目录在 sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.fetcher import fetch_all
from src.dedup import filter_candidates, save_history
from src.generator import generate_all
from src.auditor import run_audit
from src.renderer import render

OUTPUT_DIR = ROOT / "output"
CONFIG_PATH = ROOT / "config.yaml"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="每周特推自动化生成工具")
    parser.add_argument("--issue", type=int, required=True, help="期号，如 2")
    args = parser.parse_args()

    issue = args.issue
    today = date.today().isoformat()
    OUTPUT_DIR.mkdir(exist_ok=True)

    config = load_config()
    sources = [s["url"] for s in config["sources"]]
    roles = config["roles"]
    tools_per_role = config.get("tools_per_role", 5)

    # 从 .env 加载环境变量
    env_path = ROOT / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    # 注入 GitHub Token
    from src import fetcher
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        fetcher.set_token(token)
        logger.info("已使用 GitHub Token（限速 5000次/小时）")
    else:
        logger.info("未配置 GitHub Token，使用匿名模式（限速 60次/小时）")

    logger.info(f"===== 开始生成第 {issue} 期 =====")

    # Step 1: 抓取
    logger.info("Step 1/5: 抓取 GitHub 数据源")
    raw_tools = fetch_all(sources)
    if not raw_tools:
        logger.error("未抓取到任何工具，请检查数据源配置")
        sys.exit(1)

    # Step 2: 去重
    logger.info("Step 2/5: 跨期去重")
    candidates = filter_candidates(raw_tools)
    if not candidates:
        logger.error("去重后候选池为空，所有工具都已推过")
        sys.exit(1)

    # Step 3: AI 生成内容
    logger.info("Step 3/5: AI 生成内容")
    content_list, warnings = generate_all(candidates, roles, tools_per_role)

    if warnings:
        logger.warning("候选工具不足提示：")
        for w in warnings:
            logger.warning(f"  {w}")

    # 保存中间 JSON（便于调试）
    content_json_path = OUTPUT_DIR / f"week_{issue:03d}_content.json"
    with open(content_json_path, "w", encoding="utf-8") as f:
        json.dump(content_list, f, ensure_ascii=False, indent=2)
    logger.info(f"内容 JSON 已保存: {content_json_path}")

    # Step 4: AI 审核
    logger.info("Step 4/5: AI 审核（安全 + 内容）")
    audit_report = run_audit(content_list, issue, warnings)

    report_path = OUTPUT_DIR / f"week_{issue:03d}_audit_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(audit_report)
    logger.info(f"审核报告已保存: {report_path}")

    # Step 5: 渲染 HTML
    logger.info("Step 5/5: 渲染 HTML")
    html = render(content_list, roles, issue, today)

    html_path = OUTPUT_DIR / f"week_{issue:03d}.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML 已保存: {html_path}")

    # 更新历史记录
    save_history(content_list, issue, today)

    # 汇总输出
    logger.info("===== 完成 =====")
    print(f"\n✅ 第 {issue} 期生成完成")
    print(f"   📄 HTML:   {html_path}")
    print(f"   📋 报告:   {report_path}")
    print(f"   🗂  JSON:   {content_json_path}")

    if warnings:
        print("\n⚠️  候选不足提示：")
        for w in warnings:
            print(f"   {w}")

    print("\n👉 下一步：查看审核报告，处理 🔴 项后发布 HTML")


if __name__ == "__main__":
    main()
