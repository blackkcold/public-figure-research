---
name: public-figure-research
description: 通用公众人物调研并输出结构化 CSV 与报告。用于查粉丝量、品牌合作、待播内容、商业价值，支持多领域（手机/3C、汽车、美妆等）。
version: 1.1.1
license: MIT
author: blackkcold
repository: https://github.com/blackkcold/public-figure-research
---

# 公众人物基础调研 Skill

对公众人物（艺人、企业家、学者、KOL 等）进行系统性基础调研，输出结构化 CSV 数据与标准报告。

> 本 skill 是 `celebrity-research` 的通用化升级版，保留娱乐向 schema，扩展至多领域。

## Agent 适配说明

本 skill 使用**通用 agent 交互模式**，不依赖特定平台：

- **「向用户询问」**：opencode 用 `question` tool，vBuddy 用 `AskUserQuestion`，其他环境用等价物。本 skill 中所有「询问用户」均指此通用交互。
- **「记录任务进度」**：opencode 用 `todowrite`，其他环境用等价任务跟踪机制。
- **路径自定位**：脚本通过 `Path(__file__)` / `dirname $0` 自定位 skill 目录，不硬编码绝对路径。
- **依赖 skills 目录**：默认 `$HOME/.config/opencode/skills`，可用环境变量 `PFR_SKILLS_DIR` 覆盖，或由 agent 探测后写入 config.yaml 的 `skills_dir`。
- **无法确认的目录**：输出目录、依赖 skills 目录等，由 agent 运行时探测并写入 config.yaml 或设置环境变量，不硬编码。

## 功能

- ✅ 查询微博、抖音、小红书、B站四平台粉丝量（通过对应 skill 薄包装）
- ✅ 填写标签/描述、描述、特点三列（形象定位+商业适配场景）
- ✅ 交叉核查品牌合作历史（严格按要求时间范围，排除超范围信息）
- ✅ 交叉核查待播内容（严格按要求时间范围，排除已播出/超范围内容）
- ✅ 警示列：近期舆论口碑风险及行业合作风险
- ✅ 实时写入 CSV（每人物即存，避免上下文溢出）
- ✅ 每次必出标准报告（结果表 + 覆盖统计 + 失败排障 + 文件路径链接）

## ⚠️ 隐私声明（cookie 提取）

本 skill 在**已有平台 skill 查询失败时**，可能通过 `scripts/fetch_cookie.py` 解密本地浏览器 cookie 作为 fallback 数据源。

- **提取范围**：仅目标平台最小 cookie 集合（微博 SCF/SUB/SUBP、抖音 sessionid、小红书 web_session、B站 SESSDATA）
- **浏览器**：Edge / Chrome / Safari（rookiepy 解密，macOS 无需 playwright）
- **用途**：仅作为平台粉丝查询的 fallback，不用于其他任何目的
- **存储**：临时目录 `$TMPDIR/public-figure-research/`，权限 `0600`，有效期 ≤1 小时
- **清理**：任务结束自动移入 `~/.Trash`，绝不上传、不打印、不进日志、不写入任何配置文件
- **同意门禁**：每次触发 cookie 提取前，主 agent 必须用通用「向用户询问」明示并获同意；用户可随时选择"改用已有 skill / 跳过该平台"

## ⚠️ 重要限制：粉丝量查询必须主 Agent 直接执行

**严禁使用子代理（subagent，harness 特有的子任务机制）调用粉丝量查询 skills**。

原因：子代理调用 skill 时会触发用户确认提示，导致调研不完整或流程中断。

正确方式：在主 agent（当前对话）中直接调用 Bash 工具执行 Python 脚本查询粉丝量。

```bash
# 在主 agent 中直接执行，不通过子代理
# 依赖 skills 目录：${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}
# 微博
cd "${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}/social-follower-weibo/src" && /usr/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from skill import WeiboFollowerTool
tool = WeiboFollowerTool()
user = tool.search_and_get_user('人物姓名')
print(user.followers_count if user else '未找到')
"

# 抖音
cd "${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}/social-follower-douyin/src" && /usr/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from skill import DouyinFollowerTool
tool = DouyinFollowerTool()
user = tool.search_and_get_user('人物姓名')
print(user.follower_count if user else '未找到')
"

# 小红书
cd "${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}/social-follower-xiaohongshu/src" && /usr/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from skill import XiaohongshuFollowerTool
tool = XiaohongshuFollowerTool()
user = tool.search_and_get_user('人物姓名')
print(user.fans if user else '未找到')
"

# B站
cd "${PFR_SKILLS_DIR:-$HOME/.config/opencode/skills}/social-follower-bilibili/src" && /usr/bin/python3 -c "
import sys; sys.path.insert(0, '.')
from skill import BilibiliFollowerTool
tool = BilibiliFollowerTool()
user = tool.search_and_get_user('人物姓名')
print(user.follower if user else '未找到')
"
```

**四个平台统一使用 `search_and_get_user(人物姓名)` 方法**，返回用户对象，属性名：

| 平台 | 方法 | 粉丝属性 | 示例 |
|------|------|----------|------|
| 微博 | `search_and_get_user` | `.followers_count` | `user.followers_count` → `10260000` |
| 抖音 | `search_and_get_user` | `.follower_count` | `user.follower_count` → `2148000` |
| 小红书 | `search_and_get_user` | `.fans` | `user.fans` → `294000` |
| B站 | `search_and_get_user` | `.follower` 或 `.fans` | `user.follower` → `799000` |

> ⚠️ 旧版 skill 文档曾错误写成 `get_followers()`，该方法不存在，会报 `AttributeError`，已废弃。

## ⚠️ 串行执行，禁止并行调研

**必须串行顺序执行每个公众人物的调研任务**，不可并行。

原因：
- 并行查询会导致 API 或工具触发频率限制
- 子代理调研出问题无法中途沟通，造成 token 浪费
- 主 agent 可实时沟通进度和问题，便于用户反馈

### 正确流程
```
for each_person in [人物列表]:
    1. 创建 todo（当前人物）
    2. 查询4平台粉丝量
    3. 搜索品牌合作历史
    4. 搜索待播内容
    5. 追加写入CSV
    6. 标记todo完成
    7. 向用户简报进度
    8. 继续下一人物
```

## ⚠️ Context 压缩规则

每完成一位人物调研后，必须压缩中间状态：

### 压缩原则
- 每位人物数据独立成段，不与其他人物混杂
- 品牌合作和待播内容只在确认后写入CSV，不在记忆中累积
- 已写入CSV的数据不再重复展示过程
- 向用户报告时仅输出关键数字和不确定项

### 上下文监控
- 每调研3位人物后，主动检查上下文长度
- 如上下文接近50%，暂停并向用户确认是否继续
- 优先保证已确认数据准确性，宁可分段完成

### Step 1: 环境准备

```bash
# 进入 skill 目录（脚本自定位，不硬编码绝对路径）
cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null || cd "$(pwd)"
# 或使用脚本自定位：Path(__file__).resolve().parent.parent
```

### Step 2: 加载依赖 Skills（仅主Agent直接调用）

| 平台 | Skill | 调用方式 |
|------|-------|----------|
| 微博 | `social-follower-weibo` | 主Agent直接执行Python |
| 抖音 | `social-follower-douyin` | 主Agent直接执行Python |
| 小红书 | `social-follower-xiaohongshu` | 主Agent直接执行Python |
| B站 | `social-follower-bilibili` | 主Agent直接执行Python |

**⚠️ 严禁通过子代理调用上述skills**

### Step 3: 数据源策略确认（首次使用，必须执行）

**数据源策略**：justoneapi 优先，未配置则用 fallback。首次安装/首次使用时询问用户选择，确认后写入 config.yaml 的 `data_source`。

```bash
# 检查 justoneapi 是否已配置（抖音和小红书主路径依赖）
# 密钥路径可配置：环境变量 JUSTONE_KEY_FILE 优先，默认 secrets 目录
KEY_OK=0
[ -n "$JUSTONE_API_KEY" ] && KEY_OK=1
[ -n "$JUSTONEAPI_TOKEN" ] && KEY_OK=1   # 旧变量名兼容
if [ $KEY_OK -eq 0 ] && command -v op &>/dev/null; then
  op read --no-newline "op://保险库/条目/字段" &>/dev/null && KEY_OK=1
fi
if [ $KEY_OK -eq 0 ] && [ -f "${JUSTONE_KEY_FILE:-$HOME/.config/opencode/secrets/justone.key}" ]; then
  KEY_OK=1
fi
```

**决策逻辑**：
- 若 `prefer_justoneapi=true` 且 justoneapi 已配置 → 主路径用 justoneapi
- 若 justoneapi 未配置 → 自动降级到 fallback（小红书纯 Python 签名、抖音 playwright 无头）
- 首次使用询问用户：优先 justoneapi 还是直接用 fallback？确认后写入 config.yaml

### Step 3.5: 数据源可用性检查（每次调研前，必须执行）

**检测每个平台是否有可用数据源**（justoneapi 或浏览器 cookie）：

```bash
# 运行环境诊断，检测数据源状态
bash scripts/check_env.sh
```

**数据源状态判定**：

| 平台 | justoneapi | 浏览器 cookie | 结果 |
|------|-----------|--------------|------|
| 抖音/小红书 | ✅ 已配置 | - | 可用（主路径） |
| 抖音/小红书 | ❌ 未配置 | ✅ 已登录 | 可用（fallback） |
| 抖音/小红书 | ❌ 未配置 | ❌ 未登录 | **无数据源** |
| 微博/B站 | - | ✅ 已登录 | 可用 |
| 微博/B站 | - | ❌ 未登录 | **无数据源** |

**无数据源时，必须提示用户**（不静默失败）：

```
⚠️ 以下平台无可用数据源: [平台列表]
请选择任一方式启用：
1. 配置 justoneapi key（抖音/小红书主路径）：
   export JUSTONE_API_KEY=xxx  或  1Password 条目  或  secrets 文件
2. 在浏览器登录对应平台（供 cookie 提取 fallback）：
   - 微博: 登录 weibo.com
   - 抖音: 登录 douyin.com
   - 小红书: 登录 xiaohongshu.com
   - B站: 登录 bilibili.com
   登录后运行: python3 scripts/fetch_cookie.py <platform>
```

**处理流程**：
1. 检测到无数据源平台 → 向用户展示上述提示
2. 询问用户：配置 justoneapi / 登录浏览器 / 跳过该平台
3. 用户确认后再继续，不静默失败

### Step 3.6: Keychain 兜底会话提示（触发系统弹窗前，必须执行）

当 peanuts/CDP 均无法获取 cookie，需走 **Keychain 兜底**时，主 agent 必须在**触发系统弹窗前**向用户明示：

1. 用**通用「向用户询问」**（opencode 用 `question` tool，vBuddy 用 `AskUserQuestion`，其他环境用等价物）明示：
   ```
   ⚠️ Keychain 兜底将访问浏览器 'Safe Storage' 条目：
      - 首次会触发一次 macOS 系统授权弹窗
      - 点 "Always Allow" 后，本工具将不再弹窗
      - 授权仅绑定当前 Python 解释器，切换解释器可能重新弹窗
   是否允许？
   ```
2. 用户**同意** → 运行 `python3 scripts/fetch_cookie.py <platform> --keychain-consent`
3. 用户**拒绝** → 跳过该平台 / 用 justoneapi / 仅 CDP

> ⚠️ 绝不自动触发 Keychain 弹窗。无 `--keychain-consent` 时 keychain 兜底静默跳过，仅打印引导。

> ⚠️ 每次触发 cookie 提取前，必须用通用「向用户询问」明示"将读取 X 浏览器 Y 平台 cookie，用途 Z"，并提供"改用已有 skill / 跳过该平台"降级选项。用户未同意则跳过。

### Step 4: 领域询问（每次调研前，必须执行）

**领域不固定**。每次调研前需与用户确认：
- 本次调研的**领域**（从 config.yaml 的领域池多选，可追加关联领域）
- 本次调研的**人物名单**
- 是否有**特例与注意事项**（如组合账号拆分、账号混淆标注、特定人物跳过/优先等）

### Step 5: 输出目录确认（首次运行，必须执行）

- 默认输出到 agent 对话工作目录 `$PWD/output/`
- **首次运行**需询问用户确认，并检测历史输出目录（若存在）：
  - 沿用旧目录，还是使用新目录？
  - 确认后写入 config.yaml 的 `output_dir`
- 输出目录不硬编码，由 agent 探测并写入 config.yaml

### Step 6: Todo列表（串行执行）

每开始一位人物前，先创建todo（通用任务跟踪：opencode 用 `todowrite`，其他 harness 用等价机制）：
```
记录任务: 人物=XXX, status=in_progress
```

完成后标记：
```
记录任务: 人物=XXX, status=completed
```

向用户简报：
```
[XXX完成] 微博:1026万 抖音:79万 小红书:27.9万 B站:79.9万 | 品牌:好太太 | 待播:3部
不确定项: 小红书账号官方性待确认
```

### Step 7: 时间基准

> ⚠️ 以下为示例。每次调研由主 Agent 记录当前日期为**时刻基准**，自动推算近 6 个月 / 未来 3 个月。

- **时刻基准**: {当前日期}
- **近6个月品牌合作**: {当前日期-6个月} ~ {当前日期}
- **未来3个月待播**: {当前日期+1天} ~ {当前日期+3个月}

### Step 8: 每人处理流程（串行执行）

```
1. 记录任务（当前人物）
2. 主Agent直接调用4平台skill查粉丝量
3. 网络搜索品牌合作历史（交叉核查多个来源）
4. 网络搜索待播内容（交叉核查多个来源）
5. 追加写入CSV文件
6. 标记任务完成
7. 向用户简报进度（含不确定项）
8. 继续下一人物
```

### Step 9: CSV字段规范

| 字段 | 说明 | 示例 |
|------|------|------|
| 人物 | 姓名 | 罗永浩 |
| 标签/描述 | 短标签，2-4个关键词，用空格分隔 | 理想主义者 创业者 流量担当 |
| 描述 | 一句话描述人物形象定位（30-50字）偏重公众认知与形象定位 | 中国初代网红、理想主义创业者代表，以敢说敢当、真诚敢言的个人魅力持续影响公众舆论与消费市场。 |
| 特点 | 具体特质+商业适配场景（40-60字）偏重个人运营特点、社媒形象、商业场景 | 理想主义，真诚敢言、表达力强、流量号召力持久，兼具话题制造能力与深度内容影响力，适合精英对话与品质消费叙事。 |
| 微博粉丝 | 单位：万，例：1026.2万 | 363.1万 |
| 抖音粉丝 | 单位：万，含账号标记混淆情况 | 214.8万 |
| 小红书粉丝 | 单位：万，未找到填"未找到" | 29.4万 |
| B站粉丝 | 单位：万，含账号标记混淆情况 | 91.9万 |
| 近6个月品牌合作 | 品牌名-代言身份（2026年 x 月），无填"无" | 瑞幸-超大杯推荐官（2026年 3 月 23 日官宣） |
| 待播内容1 | 内容名 类型 上映/播出时间（2026年 4 月 x 日） | 《罗永浩的十字路口》播客 持续更新 |
| 主演/嘉宾1 | 主要演员/嘉宾 | 罗永浩/每期嘉宾（崔健/孟京辉/杨笠等） |
| 待播内容2 | 同上 | 未检索到已官宣的影视/综艺 |
| 主演/嘉宾2 | 同上 | - |
| 待播内容3 | 同上 | - |
| 主演/嘉宾3 | 同上 | - |
| 警示 | 近期舆论口碑风险及行业合作风险 | 无明显风险 / 需关注：XXX |

#### 标签/描述、描述、特点、警示 四列填写规范

| 列 | 填写要点 |
|---|----------|
| **标签/描述** | 短标签，2-4个关键词，用空格分隔。例："冷面松弛感 反套路男主" |
| **描述** | 偏重**形象定位**。一句话描述人物的公众形象、角色定位、代表性身份。（30-50字） |
| **特点** | 偏重**个人运营特点和商业场景**。结合作品风格、社媒形象，总结特质并点明适配的商业合作方向。（参考：当前调研领域）。（40-60字） |
| **警示** | 近期舆论口碑风险及行业合作风险。无填"无明显风险"，有风险需标注具体内容。 |

#### 警示列填写规范

**风险类型**：

| 风险类型 | 填写内容 | 示例 |
|----------|----------|------|
| 近期舆论口碑风险 | 近期（以需求提出时间为准）是否有负面舆论、争议事件、公众批评 | 2026年 3 月与杨笠对话引发粉丝争议，部分用户号召退货 |
| 行业合作排他 | 是否已与竞品品牌有深度合作，可能存在排他风险 | 曾代言XXX品牌（竞品），需确认排他期是否届满 |
| 品牌调性冲突 | 个人形象/言论与品牌调性是否存在潜在冲突 | 言论激进，可能不适合高端商务品牌 |

**搜索关键词**：
```
"{人物名}" 争议 2025 OR 2026
"{人物名}" 负面 2025 OR 2026
"{人物名}" 品牌 代言
"{人物名}" 商业排他
```

### Step 10: 组合账号处理规则

- **双人/多人组合**：如查不到组合账号，分别查询各人账号
- **合并写入**：两者粉丝量均在同一行"小红书粉丝"格内，用"/"分隔，如"土豆:34.8万/吕严:54.8万"

### Step 11: 数据不确定处理

- 平台返回"未找到"：如实填写，注明平台限制
- 同名混淆：在字段值内标注"（疑似同名）"
- 非官方账号：在字段值内标注"（非官方）"
- 账号不确定：在字段值内标注"（账号待确认）"

### Step 12: 搜索关键词策略

**品牌合作搜索**：
```
"{人物名}" 代言 2025 OR 2026
"{人物名}" 品牌大使 2025 OR 2026
"{人物名}" 商业合作 2025 OR 2026
```

**待播内容搜索**：
```
"{人物名}" 待播 2026
"{人物名}" 新剧 2026
"{人物名}" 综艺 2026
"{人物名}" 电影 2026
"{人物名}" 演唱会 2026
```

**交叉核查要求**：
- 至少查阅2个不同来源确认同一信息
- 品牌合作需确认具体品牌、身份、时间
- 待播内容需确认上映/播出时间和共同主演

### Step 13: 输出文件路径

```
{output_dir}/公众人物调研_{人数}人_{日期}.csv
```

注：文件名需包含人数和调研日期（格式：YYYYMMDD）。`output_dir` 默认 `$PWD/output/`，首次运行确认后写入 config.yaml。

### Step 14: 生成标准报告

每次调研完成后，必须生成标准报告：

```bash
# 在 skill 目录下执行（脚本自定位）
cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null || cd "$(pwd)"
/usr/bin/python3 scripts/gen_report.py "{output_dir}/公众人物调研_{人数}人_{日期}.csv" --output-dir "{output_dir}"
```

报告包含：结果表 + 平台覆盖统计 + 失败排障 + 文件路径链接。

## CSV编码要求

- 使用UTF-8 with BOM编码（确保Excel正确显示中文）
- 每人物处理后立即append写入文件

## 数据源优先级

1. **粉丝量**: skill工具实时查询（主路径）
2. **纯 Python 签名 + cookie fallback**: 小红书（xhshow 签名）、抖音（playwright 无头 chromium）
3. **品牌合作**: 品牌官方微博、人物工作室公告、门户网站娱乐版
4. **待播内容**: 豆瓣、猫眼、微博剧集超话、人物工作室公告

## 数据源策略：justoneapi 优先，fallback 兜底

**justoneapi 是优先可选项**，未配置时自动降级到 fallback。策略由 config.yaml 的 `data_source` 控制：

| 配置 | 说明 |
|------|------|
| `prefer_justoneapi: true` | 优先使用 justoneapi（若已配置） |
| `prefer_justoneapi: false` | 直接用 fallback，不用 justoneapi |
| `ask_on_first_use: true` | 首次使用询问用户选择，确认后写入 config |

**决策流程**：
1. 首次使用询问用户：优先 justoneapi 还是直接用 fallback？
2. 若选 justoneapi 且已配置 → 主路径用 justoneapi
3. 若 justoneapi 未配置 → 自动降级到 fallback（无需用户干预）

## fallback 链（绕过 justoneapi）

当 justoneapi 未配置、查询失败，或用户要求不用 justoneapi 时，使用 `query_platform.py`：

```bash
# 1. 先向用户明示并获同意（通用「向用户询问」）
# 2. 提取 cookie（dry-run 验证登录态）
cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null || cd "$(pwd)"
/usr/bin/python3 scripts/fetch_cookie.py <platform> --dry-run

# 3. 确认登录态有效后，正式提取（落盘临时目录）
/usr/bin/python3 scripts/fetch_cookie.py <platform>

# 4. 查询粉丝量（绕过 justoneapi）
/usr/bin/python3 scripts/query_platform.py xiaohongshu 人物姓名   # 小红书：纯 Python 签名
/usr/bin/python3 scripts/query_platform.py douyin 人物姓名        # 抖音：playwright 无头

# 5. 任务结束后清理
/usr/bin/python3 scripts/fetch_cookie.py --cleanup
```

### 各平台 fallback 实现

| 平台 | 方案 | 依赖 | 说明 |
|------|------|------|------|
| 小红书 | 纯 Python 签名（xhshow）+ cookie | Python 3.10+（uv 创建 .venv） | 本地生成 x-s/x-s-common 签名，无需 playwright |
| 抖音 | playwright 无头 chromium + cookie | playwright + chromium | 浏览器内执行签名，绕过 verify_check |

### ⚠️ 抖音风控注意事项

- 抖音有严格的频率限制，**连续搜索会触发 verify_check 验证码拦截**
- 每次查询间隔建议 **8-10 秒**，避免频繁访问导致 cookie 被封
- 若返回空结果或页面标题为空，说明已触发风控，**立即停止**并等待冷却
- playwright 无头 chromium 是独立环境（非用户浏览器），不会进入"启动非常用浏览器"的失败循环

> ⚠️ 每次触发 cookie 提取前，必须用通用「向用户询问」明示"将读取 X 浏览器 Y 平台 cookie，用途 Z"，并提供"改用已有 skill / 跳过该平台"降级选项。用户未同意则跳过。

## 使用问题排查

遇到查询失败时，**先诊断环境，再判断是依赖问题还是平台风控**。

### Step 1: 运行环境诊断

```bash
cd "$(dirname "$(readlink -f "$0")")" 2>/dev/null || cd "$(pwd)"
bash scripts/check_env.sh
```

诊断脚本会检测：rookiepy、uv、xhshow、playwright、chromium、依赖 skills，输出问题报告。

### Step 2: 判断问题类型

| 诊断结果 | 问题类型 | 处理方式 |
|----------|----------|----------|
| 依赖缺失/异常 | 本地依赖问题 | 输出报告后**询问用户是否重新安装** |
| 依赖全部就绪 | 平台风控/签名问题 | 见下方平台排查 |

### Step 3: 依赖问题处理

若 `check_env.sh` 报告依赖缺失：

1. 向用户展示问题报告（哪些依赖缺失、修复建议）
2. **用通用「向用户询问」确认是否重新安装**
3. 用户同意 → 运行 `bash install.sh`（自动检测并安装缺失依赖，不重复安装）
4. 用户拒绝 → 记录问题，跳过受影响平台

### Step 4: 平台风控排查

若依赖全部就绪但仍查询失败：

| 平台 | 可能原因 | 处理 |
|------|----------|------|
| 抖音 | verify_check 风控 | 间隔 8-10 秒，避免频繁访问；若持续风控，等待冷却 |
| 小红书 | 签名失效（算法更新） | 更新 xhshow：`uv pip install --python .venv/bin/python -U xhshow` |
| 微博/B站 | 频率限制 | 降低查询频率 |

> ⚠️ 若多次查询失败且非依赖问题，**不要反复重试**（可能触发平台封禁）。停止并向用户报告，等待冷却或改用其他数据源。
