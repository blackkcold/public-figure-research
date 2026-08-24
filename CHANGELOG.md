# Changelog

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)（SemVer）。

## [v1.1.1] - 2026-08-24

### 修复

- **Keychain 兜底会话提示**：触发系统弹窗前，主 agent 必须用通用「向用户询问」明示，用户同意后加 `--keychain-consent` 才执行；无 consent 时 keychain 静默跳过，绝不自动弹窗
- **通用性修正**：`question` tool → 通用「向用户询问」，`todowrite` → 「记录任务进度」，`subagent` → 「子代理」，`opencode.json` → 「配置文件」，移除硬编码用户绝对路径
- `fetch_cookie.py` 新增 `--keychain-consent` 门禁参数

## [v1.1.0] - 2026-08-24

### 修复

- **cookie 解密重构**：移除 rookiepy 作为默认解密器，改为三级零弹窗策略
  - 第1级 peanuts 纯数据解密：手写 AES 解密（仅旧版/无保护 profile 有效）
  - 第2级 CDP 拿明文：连接已运行浏览器（`--remote-debugging-port`）
  - 第3级 Keychain 兜底：用 rookiepy 读 Keychain 解密（仅已授权时静默，不自动弹窗）
- **安全 SQL**：host_key + name 双条件过滤，防伪装域名；WAL 友好只读
- **优雅失败**：peanuts/CDP 失败自动降级，Keychain 仅兜底，全部失败打印提示不弹窗

### 新增

- `decrypt_strategy` 配置（config.yaml）：peanuts,cdp,keychain 三级链可配置
- Keychain 兜底带超时防循环

### 依赖变更

- 新增 `pycryptodome`（AES 解密）
- `rookiepy` 降级为 Keychain 兜底依赖（非默认）

## [v1.0.0] - 2026-08-24

### 新增

- 通用公众人物调研 skill（`celebrity-research` 的通用化升级版）
- 微博/B站粉丝查询（crawl4weibo / bilibili-api，无需 justoneapi）
- 小红书 fallback：纯 Python 签名（xhshow）+ 解密 cookie，绕过 justoneapi
- 抖音 fallback：playwright 无头 chromium + 注入 cookie，绕过 verify_check 风控
- 多浏览器 cookie 解密提取（rookiepy，macOS 无需 playwright）
- 标准报告生成器（结果表 + 覆盖统计 + 失败排障 + 文件路径链接）
- 领域池、特例询问、输出目录确认等交互流程
- 隐私声明 + cookie 同意门禁 + 最小化存储 + 用后即删
- 数据源策略：justoneapi 优先，未配置自动降级到 fallback
- 一键部署脚本（install.sh，检测已有依赖不重复安装）
- 环境诊断脚本（check_env.sh，检测依赖 + 数据源状态）
- **无数据源提示**：无 cookie 且无 justoneapi 时，提示用户登录浏览器或配置 key
- **依赖打包**：4 个依赖 skill 打包进 `dependencies/`，install.sh 自动安装

### 通用化

- 脚本自定位（`Path(__file__)` / `dirname $0`），不硬编码绝对路径
- 依赖 skills 目录可用 `PFR_SKILLS_DIR` 环境变量覆盖
- 输出目录参数化（`$PWD/output`），由 agent 探测写入 config
- Agent 适配说明：question/todowrite 等通用交互模式，vBuddy 等环境用等价物

### 安全

- cookie 提取需用户明示同意
- 临时存储权限 `0600`，有效期 ≤1 小时，用后移入 `~/.Trash`
- 绝不上传、不打印、不进日志、不写入配置文件
- 彻底脱敏 justoneapi 引用（1Password 引用路径改为通用占位符）
- 依赖 skill 脱敏：`op://Personal/...` 改为 `op://保险库/条目/字段`
