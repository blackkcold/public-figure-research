#!/bin/bash
# public-figure-research 一键部署脚本
# 用法: bash install.sh [目标目录]
# 默认安装到 ~/.config/opencode/skills/public-figure-research
# 检测本机已有依赖，不重复安装

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[install]${NC} $1"; }
warn() { echo -e "${YELLOW}[warn]${NC} $1"; }
err()  { echo -e "${RED}[error]${NC} $1"; }

# 源目录（脚本所在 skill 目录，含 dependencies/）
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
# 目标目录（可用参数覆盖，默认与源目录相同）
SKILL_DIR="${1:-$SRC_DIR}"
# 依赖 skills 目录（可用 PFR_SKILLS_DIR 覆盖，默认 opencode 路径）
SKILLS_DIR="${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}"

log "📦 安装 public-figure-research 到 $SKILL_DIR"

# 1. 复制 skill 文件
mkdir -p "$SKILL_DIR/scripts"
cp "$SRC_DIR/SKILL.md" "$SRC_DIR/config.yaml" "$SKILL_DIR/"
cp "$SRC_DIR"/scripts/*.py "$SRC_DIR/scripts/check_env.sh" "$SKILL_DIR/scripts/"
log "✅ skill 文件已复制"

# 2. 检查并安装依赖 skills（从 dependencies/ 自动安装）
log "🔍 检查依赖 skills..."
MISSING=()
for s in social-follower-weibo social-follower-douyin social-follower-xiaohongshu social-follower-bilibili; do
  if [ ! -d "$SKILLS_DIR/$s" ]; then
    MISSING+=("$s")
  fi
done
if [ ${#MISSING[@]} -gt 0 ]; then
  warn "缺少依赖 skills: ${MISSING[*]}"
  # 尝试从 dependencies/ 自动安装（源目录）
  for s in "${MISSING[@]}"; do
    if [ -d "$SRC_DIR/dependencies/$s" ]; then
      cp -r "$SRC_DIR/dependencies/$s" "$SKILLS_DIR/"
      log "✅ 已自动安装依赖 skill: $s"
    else
      warn "⚠️ $s 无打包版本，需从作者处获取或自行实现"
    fi
  done
  # 复查
  STILL_MISSING=()
  for s in "${MISSING[@]}"; do
    [ ! -d "$SKILLS_DIR/$s" ] && STILL_MISSING+=("$s")
  done
  if [ ${#STILL_MISSING[@]} -gt 0 ]; then
    warn "仍缺少: ${STILL_MISSING[*]}（对应平台无法查询）"
  fi
else
  log "✅ 依赖 skills 已就绪"
fi

# 3. 检测并安装 Python 依赖（rookiepy）
log "🔍 检测 rookiepy..."
if /usr/bin/python3 -c "import rookiepy" 2>/dev/null; then
  log "✅ rookiepy 已安装，跳过"
else
  log "🔧 安装 rookiepy..."
  pip3 install --user rookiepy 2>/dev/null || warn "rookiepy 安装失败，请手动执行: pip3 install --user rookiepy"
fi

# 4. 检测并创建 uv 3.10 环境（小红书签名需要）
log "🔍 检测 uv 环境..."
if command -v uv &>/dev/null; then
  if [ -x "$SKILL_DIR/.venv/bin/python" ] && "$SKILL_DIR/.venv/bin/python" -c "import xhshow" 2>/dev/null; then
    log "✅ xhshow 环境已就绪，跳过"
  else
    log "🔧 创建 uv 3.10 环境（小红书签名需要）..."
    cd "$SKILL_DIR"
    if [ ! -d ".venv" ]; then
      uv venv --python 3.10 .venv
    fi
    uv pip install --python .venv/bin/python xhshow requests 2>/dev/null || warn "xhshow 安装失败，请手动执行: uv pip install --python .venv/bin/python xhshow requests"
  fi
else
  warn "未找到 uv，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# 5. 检测并安装 playwright chromium（抖音 fallback 需要）
log "🔍 检测 playwright..."
if /usr/bin/python3 -c "import playwright" 2>/dev/null; then
  if ls ~/Library/Caches/ms-playwright/chromium-* 2>/dev/null | head -1 >/dev/null; then
    log "✅ playwright chromium 已就绪，跳过"
  else
    log "🔧 安装 playwright chromium..."
    /usr/bin/python3 -m playwright install chromium 2>/dev/null || warn "playwright chromium 安装失败，请手动执行: python3 -m playwright install chromium"
  fi
else
  warn "未找到 playwright，请先安装: pip3 install --user playwright && python3 -m playwright install chromium"
fi

log "✅ 部署完成！"
echo ""
echo "  下一步："
echo "  1. 首次使用会询问数据源策略（justoneapi 优先 or fallback）"
echo "  2. 查询粉丝量："
echo "     python3 $SKILL_DIR/scripts/query_platform.py xiaohongshu 人物姓名"
echo "     python3 $SKILL_DIR/scripts/query_platform.py douyin 人物姓名"
echo ""
echo "  遇到问题？运行环境诊断："
echo "     bash $SKILL_DIR/scripts/check_env.sh"
echo ""
echo "  ⚠️ 注意：本 skill 涉及 cookie 提取，请阅读 SECURITY.md 了解安全与合规声明"
