---
name: social-follower-bilibili
description: 获取 B 站账号粉丝数据。用于查 B 站 UP 主信息。
---

# Bilibili Follower Skill

快速获取 B站用户粉丝数据和最近视频动态，基于 [bilibili-api-python](https://github.com/Nemo2011/bilibili-api)。

## 认证

SESSDATA 解析链（按优先级）：

| 优先级 | 方式 | 配置方法 |
|--------|------|----------|
| 1 | `BILIBILI_SESSDATA` 环境变量 | `export BILIBILI_SESSDATA=xxx` 添加到 `~/.zshrc` |
| 2 | `~/.config/opencode/secrets/bilibili.sessdata` | `chmod 600` 密钥文件 |
| 3 | `BILIBILI_OP_REFERENCE` 环境变量 | `export BILIBILI_OP_REFERENCE="op://保险库/条目/字段"` |

不硬编码，不写进 opencode.json。

> **注意**: 搜索用户和获取粉丝数无需 SESSDATA。获取最近视频（`get_user_recent_videos`）需要配置 SESSDATA 以避免 412 风控。

### 推荐：环境变量

```bash
echo 'export BILIBILI_SESSDATA="xxx"' >> ~/.zshrc
```

### 备选：密钥文件

```bash
mkdir -p ~/.config/opencode/secrets
chmod 700 ~/.config/opencode/secrets
echo "xxx" > ~/.config/opencode/secrets/bilibili.sessdata
chmod 600 ~/.config/opencode/secrets/bilibili.sessdata
```

### 备选：1Password CLI（需主动设置）

仅当设置 `BILIBILI_OP_REFERENCE` 环境变量后生效，不会无条件调用。

```bash
export BILIBILI_OP_REFERENCE="op://保险库/条目/字段"
```

### 获取 SESSDATA

1. 打开 [bilibili.com](https://www.bilibili.com) 并登录
2. F12 → Application → Cookies → `https://www.bilibili.com`
3. 复制 `SESSDATA` 的值

## 功能

- ✅ `search_users(keyword)` - 搜索用户（返回多个候选用户）
- ✅ `get_user_by_uid(uid)` - 通过 UID 获取粉丝数及详情
- ✅ `get_user_info(uid)` - 获取用户完整原始数据
- ✅ `search_and_get_user(keyword)` - **先搜索后获取**（推荐）
- ✅ `get_user_recent_videos(uid, count=3)` - 获取最近视频动态
- ✅ `search_and_get_recent_videos(keyword, count=3)` - 搜索用户并获取动态

## 安装依赖

```bash
pip install bilibili-api-python httpx
```

## 使用方法

### Python API

```python
from src.skill import BilibiliFollowerTool

tool = BilibiliFollowerTool()

# 搜索并获取用户
user = tool.search_and_get_user('杨迪')
print(f"粉丝数: {user.follower}")

# 获取最近视频
videos, user = tool.search_and_get_recent_videos('杨迪', count=3)
for v in videos:
    print(f"  {v['title']} — {v['play']} plays")
```

### CLI

```bash
# 搜索用户
python3 -m src.skill search 杨迪

# 获取用户详情
python3 -m src.skill get 9847497

# 获取原始用户数据
python3 -m src.skill info 9847497

# 搜索用户并获取最近视频
python3 -m src.skill recent 杨迪 3
```

## 智能策略

**认证优先**：搜索结果中官方认证账号优先返回，显示认证类型和认证描述。

## 测试结果

| 用户 | 粉丝数 | 认证 | 备注 |
|------|--------|------|------|
| 杨迪 | 148.7万 | 个人认证(演员、主持人杨迪) | |
