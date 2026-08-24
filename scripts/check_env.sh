#!/bin/bash
# public-figure-research 环境诊断脚本
# 用法: bash check_env.sh [skill目录]
# 检测本机依赖是否就绪，输出问题报告，供使用中排查

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✅${NC} $1"; }
warn() { echo -e "${YELLOW}⚠️${NC} $1"; }
err()  { echo -e "${RED}❌${NC} $1"; }

# 目标目录（自定位：脚本所在 skill 根目录，可用参数覆盖）
# 脚本位于 scripts/ 下，向上跳一级到 skill 根目录
SKILL_DIR="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
# 依赖 skills 目录（可用 PFR_SKILLS_DIR 覆盖）
# 默认 opencode 路径，其他 harness 用 PFR_SKILLS_DIR 指定自己的 skills 目录
SKILLS_DIR="${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}"

echo "=========================================="
echo "  public-figure-research 环境诊断报告"
echo "=========================================="
echo ""

# 系统信息
echo "【系统信息】"
echo "  系统: $(sw_vers -productName 2>/dev/null) $(sw_vers -productVersion 2>/dev/null || echo '未知')"
echo "  Python: $(/usr/bin/python3 --version 2>&1 || echo '未找到')"
echo "  uv: $(uv --version 2>/dev/null || echo '未找到')"
echo ""

# 依赖检测
echo "【依赖检测】"
FAILED=()

# 1. pycryptodome（AES 解密）
if /usr/bin/python3 -c "from Crypto.Cipher import AES" 2>/dev/null; then
  ok "pycryptodome（AES 解密）"
else
  err "pycryptodome（AES 解密）"
  FAILED+=("pycryptodome")
fi

# 2. uv（小红书签名环境）
if command -v uv &>/dev/null; then
  ok "uv（Python 环境管理）"
else
  err "uv（Python 环境管理）"
  FAILED+=("uv")
fi

# 3. xhshow（小红书签名，uv 3.10 环境）
if [ -x "$SKILL_DIR/.venv/bin/python" ] && "$SKILL_DIR/.venv/bin/python" -c "import xhshow" 2>/dev/null; then
  ok "xhshow（小红书签名）"
else
  err "xhshow（小红书签名）"
  FAILED+=("xhshow")
fi

# 4. playwright（抖音 fallback）
if /usr/bin/python3 -c "import playwright" 2>/dev/null; then
  ok "playwright（抖音浏览器）"
else
  err "playwright（抖音浏览器）"
  FAILED+=("playwright")
fi

# 5. chromium（playwright 浏览器）
if ls ~/Library/Caches/ms-playwright/chromium-* 2>/dev/null | head -1 >/dev/null; then
  ok "chromium（playwright 浏览器）"
else
  err "chromium（playwright 浏览器）"
  FAILED+=("chromium")
fi

# 6. 依赖 skills
MISSING_SKILLS=()
for s in social-follower-weibo social-follower-douyin social-follower-xiaohongshu social-follower-bilibili; do
  if [ ! -d "$SKILLS_DIR/$s" ]; then
    MISSING_SKILLS+=("$s")
  fi
done
if [ ${#MISSING_SKILLS[@]} -eq 0 ]; then
  ok "依赖 skills（social-follower-*）"
else
  err "依赖 skills（缺少: ${MISSING_SKILLS[*]}）"
  FAILED+=("skills")
  # 提示可自动安装
  if [ -d "$SKILL_DIR/dependencies" ]; then
    echo "    提示: 本 skill 已打包依赖，可运行 bash $SKILL_DIR/install.sh 自动安装"
  fi
fi

echo ""

# 数据源状态检测
echo "【数据源状态】"
NO_SOURCE=()

# 1. justoneapi 是否配置（抖音/小红书主路径）
JUSTONE_OK=0
[ -n "$JUSTONE_API_KEY" ] && JUSTONE_OK=1
[ -n "$JUSTONEAPI_TOKEN" ] && JUSTONE_OK=1
if [ $JUSTONE_OK -eq 0 ] && command -v op &>/dev/null; then
  op read --no-newline "op://保险库/条目/字段" &>/dev/null && JUSTONE_OK=1
fi
if [ $JUSTONE_OK -eq 0 ] && [ -f "${JUSTONE_KEY_FILE:-$HOME/.config/opencode/secrets/justone.key}" ]; then
  JUSTONE_OK=1
fi
if [ $JUSTONE_OK -eq 1 ]; then
  ok "justoneapi（抖音/小红书主路径）"
else
  warn "justoneapi 未配置（抖音/小红书主路径不可用）"
fi

# 2. 浏览器 cookie 可用性（fallback）
for platform in weibo douyin xiaohongshu bilibili; do
  if [ -f "$SKILL_DIR/scripts/fetch_cookie.py" ]; then
    if /usr/bin/python3 "$SKILL_DIR/scripts/fetch_cookie.py" "$platform" --dry-run 2>/dev/null | grep -q "有效"; then
      ok "$platform cookie 可用（fallback）"
    else
      warn "$platform 无 cookie（需浏览器登录）"
      NO_SOURCE+=("$platform")
    fi
  fi
done

echo ""

# 问题报告
echo "【问题报告】"
if [ ${#FAILED[@]} -gt 0 ]; then
  err "检测到 ${#FAILED[@]} 项依赖问题: ${FAILED[*]}"
  echo ""
  echo "  修复建议："
  for f in "${FAILED[@]}"; do
    case "$f" in
      pycryptodome) echo "    - pycryptodome: pip3 install --user pycryptodome" ;;
      uv)       echo "    - uv: curl -LsSf https://astral.sh/uv/install.sh | sh" ;;
      xhshow)   echo "    - xhshow: cd $SKILL_DIR && uv venv --python 3.10 .venv && uv pip install --python .venv/bin/python xhshow requests" ;;
      playwright) echo "    - playwright: pip3 install --user playwright" ;;
      chromium) echo "    - chromium: python3 -m playwright install chromium" ;;
      skills)   echo "    - skills: 安装缺少的 social-follower-* skill" ;;
    esac
  done
  echo ""
  echo "  是否重新安装缺失依赖？"
  echo "  运行: bash $SKILL_DIR/install.sh"
  echo "  （或手动执行上述修复命令）"
  echo ""
  exit 1
fi

# 依赖正常，检查数据源
if [ $JUSTONE_OK -eq 0 ] && [ ${#NO_SOURCE[@]} -gt 0 ]; then
  warn "依赖已就绪，但以下平台无可用数据源: ${NO_SOURCE[*]}"
  echo ""
  echo "  请选择以下任一方式启用数据源："
  echo "  1. 配置 justoneapi key（抖音/小红书主路径）："
  echo "     export JUSTONE_API_KEY=xxx  或  1Password 条目  或  secrets 文件"
  echo "  2. 在浏览器登录对应平台（供 cookie 提取 fallback）："
  echo "     - 微博: 登录 weibo.com"
  echo "     - 抖音: 登录 douyin.com"
  echo "     - 小红书: 登录 xiaohongshu.com"
  echo "     - B站: 登录 bilibili.com"
  echo "     登录后运行: python3 $SKILL_DIR/scripts/fetch_cookie.py <platform>"
  echo ""
  exit 1
fi

ok "所有依赖已就绪，环境正常"
echo ""
echo "  如仍遇到查询问题，可能是平台风控（非依赖问题）："
echo "  - 抖音 verify_check：间隔 8-10 秒，避免频繁访问"
echo "  - 小红书签名失效：算法更新频繁，需更新 xhshow"
echo ""
exit 0
