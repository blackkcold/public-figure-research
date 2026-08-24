---
name: social-follower-douyin
description: 获取抖音账号粉丝数据。用于查抖音账号信息。
---

# Douyin Follower Skill

快速获取抖音用户粉丝数据，基于 JustOneAPI。

## 认证

Key 解析链（按优先级）：

| 优先级 | 方式 | 配置方法 |
|--------|------|----------|
| 1 | `JUSTONE_API_KEY` 环境变量 | `export JUSTONE_API_KEY=xxx` 添加到 `~/.zshrc` |
| 2 | 1Password CLI | `op read --no-newline op://保险库/条目/字段` |
| 3 | `~/.config/opencode/secrets/justone.key` | `chmod 600` 密钥文件 |
| 4 | `JUSTONEAPI_TOKEN` 环境变量 | 旧变量名兼容 |

不硬编码，不写进 opencode.json。

### 推荐：1Password CLI

1Password 桌面版启用 CLI 集成后，创建条目（保险库 `Personal`，字段 `credential`）：

```bash
op read --no-newline op://保险库/条目/字段
```

自定义引用路径：`export JUSTONE_OP_REFERENCE="op://保险库/条目/字段"`

### 备选：环境变量

```bash
echo 'export JUSTONE_API_KEY="sk-xxx"' >> ~/.zshrc
```

### 备选：密钥文件

```bash
mkdir -p ~/.config/opencode/secrets
chmod 700 ~/.config/opencode/secrets
echo "sk-xxx" > ~/.config/opencode/secrets/justone.key
chmod 600 ~/.config/opencode/secrets/justone.key
```

## 功能

- ✅ `search_users(keyword)` - 搜索用户
- ✅ `get_user_by_sec_uid(sec_user_id)` - 通过 sec_user_id 获取粉丝数
- ✅ `search_and_get_user(keyword)` - 先搜索后获取

## 安装依赖

```bash
pip install requests
```

## 使用方法

```python
from src.skill import DouyinFollowerTool

tool = DouyinFollowerTool()

user = tool.search_and_get_user('杨迪')
print(f"粉丝数: {user.follower_count}")

user = tool.get_user_by_sec_uid('MS4wLjABAAAA...')
print(f"粉丝数: {user.follower_count}")
```

## 获取 sec_user_id 方法

1. 打开用户抖音主页
2. 点击分享 → 复制链接
3. 链接格式：`https://www.douyin.com/user/MS4wLjABAAAA...`
4. 链接中 `MS4wLjABAAAA...` 部分即为 sec_user_id

## 智能策略

**认证优先**：搜索结果中本人认证账号（蓝V）优先返回。

## 测试结果

| 用户 | 粉丝数 | 认证 | 备注 |
|------|--------|------|------|
| 杨迪 | 1887.6万 | 明星(黄V) | 演员/主持人 |
