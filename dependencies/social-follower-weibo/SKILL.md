---
name: social-follower-weibo
description: 获取微博账号粉丝数据和最近动态。用于查微博用户信息。
---

# Social Follower Weibo Skill

快速获取微博用户粉丝数据和最近动态，基于 `crawl4weibo` 库。

## 功能

- `search_users(keyword)` - 搜索用户（返回多个候选用户）
- `get_user_by_uid(uid)` - 通过 UID 获取用户信息（含认证类型/性别/地区/简介）
- `search_and_get_user(keyword)` - 先搜索后获取（认证账号优先，自动别名查找）
- `get_user_recent_posts(uid, count=2)` - 获取用户最近动态（自动过滤置顶微博）
- `get_user_recent_posts_by_keyword(keyword, count=2)` - 搜索用户并获取动态
- `get_hot_search(count=10)` - 获取微博热搜榜

## 安装依赖

```bash
pip install "crawl4weibo>=0.5.2"
playwright install chromium
```

## 使用方法

```python
from src.skill import WeiboFollowerTool

tool = WeiboFollowerTool()

user = tool.search_and_get_user('辛芷蕾')
print(f"粉丝数: {user.followers_count}")

posts, user = tool.get_user_recent_posts_by_keyword('杨迪', count=3)
for p in posts:
    print(p.created_at, p.text[:50])
```

## 认证类型对照

| verified_type | 含义 | 显示标签 |
|---------------|------|----------|
| 0 + ext=0 | 橙V(个人认证) | 黄V/橙V |
| 0 + ext=1/2 | 金V/红V(个人认证) | 红V/金V |
| 1 | 蓝V(政府) | 蓝V |
| 2 | 蓝V(企业) | 蓝V |
| 3 | 蓝V(媒体) | 蓝V |
| -1 | 普通用户 | — |

## 返回字段

**User**: id, screen_name, gender, location, description, followers_count, following_count, posts_count, verified, verified_reason, avatar_url, cover_image_url

**Post**: id, text, created_at, source, reposts_count, comments_count, attitudes_count, pic_urls, video_url, is_original

## 智能策略

- **认证优先**：搜索结果中认证用户且昵称完全匹配的优先返回
- **别名查找**：通过搜索引擎辅助查找同人不同昵称
- **结果缓存**：相同查询 5 分钟内不重复请求
- **内置反爬**：依赖 crawl4weibo v0.5.2 自带的 432 保护与指数退避

## 测试结果

| 用户 | 粉丝数 | 认证类型 |
|------|--------|----------|
| 杨迪 | 1002.1万 | 橙V |
| 辛芷蕾 | 1356.2万 | 橙V |
