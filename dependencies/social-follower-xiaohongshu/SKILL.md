---
name: social-follower-xiaohongshu
description: 获取小红书账号粉丝数据。用于查小红书博主信息。
---

# Xiaohongshu Follower Skill

快速获取小红书用户粉丝数据，基于 JustOneAPI。

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

- ✅ `search_users(keyword)` - 通过关键词搜索用户
- ✅ `get_user_by_id(user_id)` - 通过 user_id 获取粉丝数
- ✅ `search_and_get_user(keyword)` - 搜索并获取用户粉丝数

## 安装依赖

```bash
pip install requests
```

## 使用方法

```python
from src.skill import XiaohongshuFollowerTool

tool = XiaohongshuFollowerTool()

user = tool.search_and_get_user('马頔')
print(f"粉丝数: {user.fans}")
```

## 智能策略

1. **认证优先**：搜索结果中优先返回红标认证账号
2. **阈值过滤**：粉丝数低于 5000 的账号被认为是同名普通用户

## 测试结果

| 用户 | 粉丝数 | 认证 | 备注 |
|------|--------|------|------|
| 杨迪 | 383.6万 | 红V认证 | |
| 马頔 | 15.5万 | 红V认证 | |
| 周杰伦 | 1.2万 | 红V认证 | |
| 赵雷 | 1.1万 | 红V认证 | |
