#!/bin/bash
# weekly-push 一键安装脚本
# 用法：cd /path/to/weekly-push && ./install.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_TARGET="$HOME/.claude/skills/weekly-push"

echo "📦 weekly-push 安装程序"
echo "项目路径：$PROJECT_DIR"
echo ""

# 1. 检查依赖
echo "🔍 检查依赖..."
if ! command -v uv &>/dev/null; then
  echo "❌ 未找到 uv，请先安装：curl -LsSf https://astral.sh/uv/install.sh | sh"
  exit 1
fi
if ! command -v claude &>/dev/null; then
  echo "❌ 未找到 claude CLI，请先安装 Claude Code"
  exit 1
fi
echo "✅ 依赖检查通过"

# 2. 安装 Python 依赖
echo ""
echo "📥 安装 Python 依赖..."
cd "$PROJECT_DIR"
uv venv --quiet
uv pip install -r requirements.txt --quiet
echo "✅ 依赖安装完成"

# 3. 初始化 .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  echo ""
  echo "⚠️  已创建 .env 文件，请填入 GitHub Token："
  echo "    $PROJECT_DIR/.env"
  echo "    生成地址：https://github.com/settings/tokens（Classic Token，勾选 public_repo）"
else
  echo "✅ .env 已存在，跳过"
fi

# 4. 初始化 history.json
if [ ! -f "$PROJECT_DIR/history.json" ]; then
  echo '{"tools": []}' > "$PROJECT_DIR/history.json"
  echo "✅ 初始化 history.json"
fi

# 5. 安装 Skill 并写入路径
echo ""
echo "🔧 安装 Claude Code Skill..."
mkdir -p "$SKILL_TARGET"
cp "$PROJECT_DIR/skill/SKILL.md" "$SKILL_TARGET/SKILL.md"
# 写入项目路径，供 Skill 运行时读取
echo "$PROJECT_DIR" > "$SKILL_TARGET/.project_path"
echo "✅ Skill 已安装到 $SKILL_TARGET"

echo ""
echo "🎉 安装完成！"
echo ""
echo "下一步："
echo "  1. 在 $PROJECT_DIR/.env 填入 GITHUB_TOKEN"
echo "  2. 在 Claude Code 中运行 /weekly-push"
