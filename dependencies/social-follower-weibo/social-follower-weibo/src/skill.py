# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import time
import logging
from typing import List, Optional

from crawl4weibo import WeiboClient
from crawl4weibo.models import User, Post

logger = logging.getLogger("weibo-skill")

VERIFIED_TYPE_MAP: dict[int, str] = {
    -1: "普通用户",
    200: "初级达人",
    220: "中级达人",
    400: "已故V用户",
    0: "橙V(个人认证)",
    1: "蓝V(政府)",
    2: "蓝V(企业)",
    3: "蓝V(媒体)",
    4: "蓝V(校园)",
    5: "蓝V(网站)",
    6: "蓝V(应用)",
    7: "蓝V(团体/机构)",
    8: "待审企业",
    10: "微博女郎",
}


def _verify_label(user: User) -> str:
    raw = user.raw_data or {}
    vt = raw.get("verified_type", -1)
    base = VERIFIED_TYPE_MAP.get(vt, f"未知({vt})")

    if vt == 0:
        vte = raw.get("verified_type_ext", 0)
        if vte in (1, 2):
            base = "金V/红V(个人认证)"
    return base


def _is_pinned(post: Post) -> bool:
    mark = (post.raw_data or {}).get("mark", "") or ""
    return "followtopweibo" in mark


def _format_fans(n) -> str:
    if n is None:
        return "未知"
    if isinstance(n, str):
        if "亿" in n or "万" in n:
            return n
        n = int(n)
    if n >= 100_000_000:
        return f"{n / 100_000_000:.1f}亿"
    if n >= 10_000:
        return f"{n / 10_000:.1f}万"
    return str(n)


class WeiboFollowerTool:
    def __init__(self, cache_ttl: int = 300):
        self._cache: dict = {}
        self._cache_ttl = cache_ttl
        self._client_init()

    def _client_init(self):
        cookie_path = os.path.expanduser("~/.crawl4weibo/weibo_storage_state.json")
        try:
            self._client = WeiboClient(
                login_cookies=True,
                cookie_storage_path=cookie_path,
            )
        except Exception as e:
            logger.error("初始化微博客户端失败: %s", e)
            raise

    def _cache_get(self, key: str) -> tuple | None:
        entry = self._cache.get(key)
        if entry and time.time() - entry[0] < self._cache_ttl:
            return entry[1]
        if entry:
            del self._cache[key]
        return None

    def _cache_set(self, key: str, value):
        self._cache[key] = (time.time(), value)

    def _user_summary(self, user: User) -> str:
        verified_tag = _verify_label(user)
        reason = f" [{user.verified_reason}]" if user.verified_reason else ""
        return f"{user.screen_name} ({_format_fans(user.followers_count)} 粉丝){reason} [{verified_tag}]"

    def get_hot_search(self, count: int = 10) -> list:
        cache_key = f"hot_{count}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            url = "https://m.weibo.cn/api/container/getIndex"
            params = {
                "containerid": "106003type=25&t=3&disable_hot=1&filter_type=realtimehot",
                "luicode": "10000011",
                "lfid": "231583",
            }
            resp = self._client.session.get(url, params=params, timeout=30)
            data = resp.json()
            if data.get("ok") == 1:
                cards = data.get("data", {}).get("cards", [])
                if cards:
                    items = cards[0].get("card_group", [])[:count]
                    self._cache_set(cache_key, items)
                    return items
            return []
        except Exception as e:
            logger.error("获取热搜失败: %s", e)
            return []

    def search_users(self, keyword: str, page: int = 1) -> List[User]:
        cache_key = f"search_{keyword}_{page}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            users = self._client.search_users(keyword, page=page)
            self._cache_set(cache_key, users)
            return users
        except Exception as e:
            logger.error("搜索用户失败: %s", e)
            return []

    def get_user_by_uid(self, uid: str) -> Optional[User]:
        cache_key = f"uid_{uid}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            user = self._client.get_user_by_uid(uid)
            self._cache_set(cache_key, user)
            return user
        except Exception as e:
            logger.error("获取用户信息失败: %s", e)
            return None

    def get_user_by_keyword(self, keyword: str) -> List[User]:
        return self.search_users(keyword)

    def _search_aliases(self, keyword: str) -> list:
        import re
        import requests
        from urllib.parse import urlencode

        try:
            params = {"q": f"{keyword} 微博 昵称 艺名 别名"}
            url = "https://html.duckduckgo.com/html/?" + urlencode(params)
            resp = requests.get(
                url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                return []
            text = resp.text
            aliases = []
            for pattern in [f"{keyword}昵称", f"{keyword}微博名", f"@{keyword}"]:
                if pattern not in text:
                    continue
                idx = text.find(pattern)
                chunk = text[max(0, idx - 20): idx + 50]
                matches = re.findall(r"@([^<\s]+)", chunk)
                for m in matches:
                    if m != keyword and len(m) > 1:
                        aliases.append(m)
            if aliases:
                logger.info("[别名] 发现可能的别名: %s", aliases[:5])
            return aliases[:5]
        except Exception as e:
            logger.debug("[别名] 搜索失败: %s", e)
        return []

    def get_user_recent_posts(
        self, uid: str, count: int = 2, skip_pinned: bool = True
    ) -> List[Post]:
        cache_key = f"posts_{uid}_{count}_{skip_pinned}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        try:
            posts = self._client.get_user_posts(str(uid), page=1)
            if skip_pinned:
                posts = [p for p in posts if not _is_pinned(p)]
            result = posts[:count]
            self._cache_set(cache_key, result)
            return result
        except Exception as e:
            logger.error("获取用户动态失败: %s", e)
            return []

    def _search_best_match(
        self, users: list, keyword: str, exact_match: bool
    ) -> Optional[User]:
        keyword_lower = keyword.lower()

        if exact_match:
            for u in users:
                if u.verified and (u.screen_name or "").lower() == keyword_lower:
                    logger.info("✓ 认证账号优先: %s", self._user_summary(u))
                    return u

            for u in users:
                if keyword in (u.screen_name or ""):
                    logger.info("✓ 精确匹配: %s", self._user_summary(u))
                    return u

            logger.info("未找到精确匹配用户: %s，选择最佳结果", keyword)

        best_user = None
        best_score = -1
        for u in users:
            if u.followers_count is not None:
                score = u.followers_count + (100_000 if u.verified else 0)
                if score > best_score:
                    best_score = score
                    best_user = u

        if best_user:
            logger.info("✓ %s: %s",
                        "认证账号" if best_user.verified else "选择结果",
                        self._user_summary(best_user))
            return best_user

        logger.info("未找到有效用户: %s", keyword)
        return None

    def search_and_get_user(
        self, keyword: str, exact_match: bool = True
    ) -> Optional[User]:
        users = self.search_users(keyword)
        if users:
            result = self._search_best_match(users, keyword, exact_match)
            if result:
                return result

        aliases = self._search_aliases(keyword)
        for alias in aliases:
            if alias == keyword:
                continue
            users = self.search_users(alias)
            if not users:
                continue
            result = self._search_best_match(users, alias, exact_match)
            if result:
                logger.info("  [别名] 通过别名 '%s' 找到用户", alias)
                return result

        logger.info("未找到用户: %s", keyword)
        return None

    def get_user_recent_posts_by_keyword(
        self, keyword: str, count: int = 2, skip_pinned: bool = True
    ) -> tuple[Optional[List[Post]], Optional[User]]:
        user = self.search_and_get_user(keyword)
        if not user:
            return None, None
        posts = self.get_user_recent_posts(str(user.id), count, skip_pinned)
        return posts, user


def main():
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m skill <command> [args]")
        print("命令:")
        print("  hot [n]                获取热搜榜（默认10条）")
        print("  search_users <keyword>  搜索用户")
        print("  get_user <uid>          获取用户信息")
        print("  get_posts <uid> [n]    获取用户动态（默认2条）")
        print("  recent <keyword> [n]    搜索用户并获取动态")
        return

    cmd = sys.argv[1]
    tool = WeiboFollowerTool()

    if cmd == "hot":
        count = int(sys.argv[2]) if len(sys.argv) >= 3 else 10
        print(f"获取热搜榜 (前{count}条):")
        items = tool.get_hot_search(count)
        for i, item in enumerate(items, 1):
            desc = item.get("desc", "")
            num_extr = item.get("num_extr", "")
            print(f"  {i}. {desc}")
            if num_extr:
                print(f"     热度: {num_extr}")
        if not items:
            print("  获取失败")
        return

    if cmd == "search_users" and len(sys.argv) >= 3:
        keyword = sys.argv[2]
        print(f"搜索用户: {keyword}")
        users = tool.search_users(keyword)
        for u in users:
            label = _verify_label(u)
            print(f"  UID: {u.id}, 昵称: {u.screen_name}, "
                  f"粉丝: {_format_fans(u.followers_count)}, "
                  f"认证: {label}, 地区: {u.location or '-'}")

    elif cmd == "get_user" and len(sys.argv) >= 3:
        uid = sys.argv[2]
        print(f"获取用户信息: UID={uid}")
        user = tool.get_user_by_uid(uid)
        if user:
            label = _verify_label(user)
            print(f"  昵称: {user.screen_name}")
            print(f"  粉丝数: {_format_fans(user.followers_count)} ({user.followers_count})")
            print(f"  关注数: {user.following_count}")
            print(f"  微博数: {user.posts_count}")
            print(f"  认证: {label}")
            if user.verified_reason:
                print(f"  认证原因: {user.verified_reason}")
            if user.gender:
                gender_map = {"m": "男", "f": "女", "n": "未知"}
                print(f"  性别: {gender_map.get(user.gender, user.gender)}")
            if user.location:
                print(f"  地区: {user.location}")
            if user.description:
                print(f"  简介: {user.description[:80]}...")
        else:
            print("  获取失败")

    elif cmd == "get_posts" and len(sys.argv) >= 3:
        uid = sys.argv[2]
        count = int(sys.argv[3]) if len(sys.argv) >= 4 else 2
        print(f"获取用户动态: UID={uid}, 数量={count}")
        posts = tool.get_user_recent_posts(uid, count)
        for i, p in enumerate(posts, 1):
            print(f"\n--- 动态 {i} ---")
            print(f"  ID: {p.id}")
            print(f"  时间: {p.created_at}")
            print(f"  来源: {p.source}")
            print(f"  转发: {p.reposts_count}, 评论: {p.comments_count}, "
                  f"点赞: {p.attitudes_count}")
            if p.pic_urls:
                print(f"  图片: {len(p.pic_urls)}张")
            if p.video_url:
                print(f"  视频: {p.video_url[:60]}...")
            if not p.is_original:
                print(f"  类型: 转发微博")
            text = p.text[:100] + "..." if len(p.text) > 100 else p.text
            print(f"  内容: {text}")

    elif cmd == "recent" and len(sys.argv) >= 3:
        keyword = sys.argv[2]
        count = int(sys.argv[3]) if len(sys.argv) >= 4 else 2
        print(f"搜索用户并获取动态: {keyword}, 数量={count}")
        posts, user = tool.get_user_recent_posts_by_keyword(keyword, count)
        if not user:
            print("  未找到用户")
            return
        label = _verify_label(user)
        print(f"\n用户: {user.screen_name} (UID: {user.id}) [{label}]")
        print(f"粉丝: {_format_fans(user.followers_count)}")

        if posts:
            print(f"\n最近动态 (共 {len(posts)} 条):")
            for i, p in enumerate(posts, 1):
                print(f"\n--- 动态 {i} ---")
                print(f"  时间: {p.created_at}")
                print(f"  来源: {p.source}")
                print(f"  转发: {p.reposts_count}, 评论: {p.comments_count}, "
                      f"点赞: {p.attitudes_count}")
                if p.pic_urls:
                    print(f"  图片: {len(p.pic_urls)}张")
                if p.video_url:
                    print(f"  视频: {p.video_url[:60]}...")
                text = p.text[:100] + "..." if len(p.text) > 100 else p.text
                print(f"  内容: {text}")
        else:
            print("  无动态")


if __name__ == "__main__":
    main()
