# public-figure-research

![Version](https://img.shields.io/badge/version-v1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey)
![GitHub stars](https://img.shields.io/github/stars/blackkcold/public-figure-research)
![GitHub forks](https://img.shields.io/github/forks/blackkcold/public-figure-research)

通用公众人物调研 Skill —— 查询微博/抖音/小红书/B站四平台粉丝量，输出结构化 CSV 与标准报告，支持多领域（手机/3C、汽车、美妆等）。

> 本 skill 是 `celebrity-research` 的通用化升级版，保留娱乐向 schema，扩展至多领域。

## Agent 适配

本 skill 使用**通用 agent 交互模式**，不依赖特定平台：

- **「向用户询问」**：opencode 用 `question` tool，vBuddy 用 `AskUserQuestion`，其他环境用等价物
- **「记录任务进度」**：opencode 用 `todowrite`，其他环境用等价任务跟踪机制
- **路径自定位**：脚本通过 `Path(__file__)` / `dirname $0` 自定位 skill 目录，不硬编码绝对路径
- **依赖 skills 目录**：默认 `$HOME/.config/opencode/skills`，可用环境变量 `PFR_SKILLS_DIR` 覆盖，或由 agent 探测后写入 config.yaml 的 `skills_dir`

## 功能

- ✅ 查询微博、抖音、小红书、B站四平台粉丝量（通过对应 skill 薄包装）
- ✅ 填写标签/描述、描述、特点三列（形象定位+商业适配场景）
- ✅ 交叉核查品牌合作历史（严格按要求时间范围，排除超范围信息）
- ✅ 交叉核查待播内容（严格按要求时间范围，排除已播出/超范围内容）
- ✅ 警示列：近期舆论口碑风险及行业合作风险
- ✅ 实时写入 CSV（每人物即存，避免上下文溢出）
- ✅ 每次必出标准报告（结果表 + 覆盖统计 + 失败排障 + 文件路径链接）
- ✅ **数据源策略**：justoneapi 优先，未配置自动降级到 fallback
- ✅ **环境诊断**：check_env.sh 检测依赖 + 数据源状态，输出问题报告
- ✅ **无数据源提示**：无 cookie 且无 justoneapi 时，提示用户登录浏览器或配置 key
- ✅ **依赖打包**：4 个依赖 skill 已打包进 `dependencies/`，install.sh 自动安装

## 目录结构

```
public-figure-research/
├── SKILL.md              # Skill 主文档（含完整工作流）
├── config.yaml           # 配置中心（领域池、平台映射、数据源策略、cookie 白名单）
├── install.sh            # 一键部署脚本（检测已有依赖，不重复安装）
├── dependencies/         # 打包的依赖 skills（自动安装）
│   ├── social-follower-weibo/
│   ├── social-follower-douyin/
│   ├── social-follower-xiaohongshu/
│   └── social-follower-bilibili/
├── scripts/
│   ├── check_env.sh      # 环境诊断脚本（检测依赖 + 数据源状态）
│   ├── fetch_cookie.py   # 多浏览器 cookie 解密提取（rookiepy，macOS 无需 playwright）
│   ├── query_platform.py  # 平台粉丝查询（小红书纯 Python 签名 + 抖音 playwright 无头）
│   └── gen_report.py      # 标准报告生成器
├── SECURITY.md           # 安全与合规声明
├── CONTRIBUTING.md       # 贡献指南
├── CHANGELOG.md          # 版本变更记录
└── LICENSE               # MIT 协议
```

## 一键部署

```bash
# 方式一：curl 一键部署（自动检测依赖，不重复安装）
curl -fsSL https://raw.githubusercontent.com/blackkcold/public-figure-research/main/install.sh | bash

# 方式二：指定安装目录
curl -fsSL https://raw.githubusercontent.com/blackkcold/public-figure-research/main/install.sh | bash -s -- ~/custom/skills/public-figure-research

# 方式三：手动克隆
git clone https://github.com/blackkcold/public-figure-research.git \
  ~/.config/opencode/skills/public-figure-research
cd ~/.config/opencode/skills/public-figure-research
bash install.sh
```

`install.sh` 会**检测本机已有依赖，不重复安装**：
- 复制 skill 文件到目标目录
- **自动安装依赖 skills**（从 `dependencies/` 复制到 skills 目录）
- 检测并安装 Python 依赖（rookiepy，已装则跳过）
- 检测并创建 uv 3.10 环境（小红书签名，已就绪则跳过）
- 检测并安装 playwright chromium（抖音 fallback，已就绪则跳过）

## 环境诊断

遇到查询问题时，先运行环境诊断，判断是依赖问题还是数据源问题：

```bash
bash ~/.config/opencode/skills/public-figure-research/scripts/check_env.sh
```

诊断脚本会检测：
- **依赖**：rookiepy、uv、xhshow、playwright、chromium、依赖 skills
- **数据源状态**：justoneapi 是否配置、各平台浏览器 cookie 是否可用

- **依赖缺失** → 输出报告后询问用户是否重新安装（`bash install.sh`）
- **数据源缺失** → 提示用户登录浏览器或配置 justoneapi key
- **依赖就绪但查询失败** → 平台风控（抖音 verify_check / 小红书签名失效）

## 数据源策略

**justoneapi 是优先可选项**，未配置时自动降级到 fallback。首次使用会询问用户选择，确认后写入 config.yaml 的 `data_source`：

| 配置 | 说明 |
|------|------|
| `prefer_justoneapi: true` | 优先使用 justoneapi（若已配置） |
| `prefer_justoneapi: false` | 直接用 fallback，不用 justoneapi |
| `ask_on_first_use: true` | 首次使用询问用户选择，确认后写入 config |

## 使用

```bash
# 1. 提取 cookie（需用户同意）
python3 scripts/fetch_cookie.py xiaohongshu
python3 scripts/fetch_cookie.py douyin

# 2. 查询粉丝量（fallback，绕过 justoneapi）
python3 scripts/query_platform.py xiaohongshu 人物姓名   # 小红书：纯 Python 签名
python3 scripts/query_platform.py douyin 人物姓名        # 抖音：playwright 无头

# 3. 清理临时 cookie
python3 scripts/fetch_cookie.py --cleanup
```

## 平台 fallback 链

| 平台 | 主路径 | fallback（绕过 justoneapi） |
|------|--------|------------------------------|
| 微博 | `social-follower-weibo`（crawl4weibo） | 无需 fallback |
| B站 | `social-follower-bilibili`（bilibili-api） | 无需 fallback |
| 小红书 | `social-follower-xiaohongshu`（JustOneAPI） | 纯 Python 签名（xhshow）+ cookie |
| 抖音 | `social-follower-douyin`（JustOneAPI） | playwright 无头 chromium + cookie |

## ⚠️ 安全与合规

本 skill 涉及浏览器 cookie 提取和平台数据访问，存在安全与合规风险。**使用前请务必阅读 [SECURITY.md](SECURITY.md)**。

- **cookie 提取**：仅提取目标平台最小 cookie 集合，需用户明示同意，临时存储 + 用后即删
- **平台风险**：抖音有 verify_check 风控和频率限制，小红书有签名风控
- **法律合规**：自动化数据访问可能违反平台服务条款，使用者需自担风险

## 开源协议

[MIT](LICENSE) © 2026 blackkcold

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。
