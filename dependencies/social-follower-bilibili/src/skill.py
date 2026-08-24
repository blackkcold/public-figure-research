# -*- coding: utf-8 -*-

import time
import threading
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from bilibili_api import sync, Credential
from bilibili_api.search import search_by_type, SearchObjectType, OrderUser
from bilibili_api.user import User
from bilibili_api.exceptions import ResponseCodeException, NetworkException


class RateLimiter:
    def __init__(self, min_interval: float = 3.0):
        self.min_interval = min_interval
        self.last_call = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


class BilibiliUser:
    def __init__(self, data: dict):
        self.mid = data.get("mid")
        self.name = data.get("name")
        self.follower = data.get("follower")
        if self.follower is None:
            self.follower = data.get("fans")
        self.following = data.get("following")
        self.level = data.get("level")
        self.sign = data.get("sign", "")
        self.avatar = data.get("face", data.get("avatar", ""))
        self.official_verify = data.get("official_verify", -1)
        self.official_desc = data.get("official_desc", "")
        self.video_count = data.get("video_count")

    @property
    def fans(self):
        return self.follower

    @property
    def verified_label(self) -> str:
        if self.official_verify == 0:
            label = "个人认证"
        elif self.official_verify == 1:
            label = "机构认证"
        else:
            return ""
        if self.official_desc:
            return f"{label}({self.official_desc})"
        return label

    def __repr__(self):
        label = f" [{self.verified_label}]" if self.verified_label else ""
        return f"<BilibiliUser {self.name}: {self.follower}{label}>"


class BilibiliFollowerTool:
    def __init__(self, rate_limit: float = 3.0):
        self._msg_prefix = "[B站]"
        self._credential = self._resolve_credential()
        self._rate_limiter = RateLimiter(min_interval=rate_limit)

    def _resolve_credential(self) -> Credential:
        sessdata = os.environ.get("BILIBILI_SESSDATA")
        if sessdata and sessdata.strip():
            return Credential(sessdata=sessdata.strip())

        op_ref = os.environ.get("BILIBILI_OP_REFERENCE")
        if op_ref:
            try:
                result = subprocess.run(
                    ["op", "read", "--no-newline", op_ref],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return Credential(sessdata=result.stdout.strip())
            except (FileNotFoundError, subprocess.TimeoutExpired):
                print(f"{self._msg_prefix} 1Password CLI 不可用，跳过")

        secret_file = Path(os.environ.get("BILIBILI_SESSDATA_FILE", str(Path.home() / ".config" / "opencode" / "secrets" / "bilibili.sessdata")))
        if secret_file.exists():
            try:
                st = secret_file.stat()
                if st.st_mode & 0o077:
                    print(
                        f"{self._msg_prefix} 权限过宽 "
                        f"({oct(st.st_mode & 0o777)}), 建议 chmod 600"
                    )
                value = secret_file.read_text(encoding="utf-8").strip()
                if value:
                    return Credential(sessdata=value)
            except Exception:
                pass

        print(f"{self._msg_prefix} B站 SESSDATA 未配置（公开API仍可用，但部分功能受限）")
        print("  方式一(推荐): export BILIBILI_SESSDATA=xxx 添加到 ~/.zshrc")
        print(f"  方式二: echo xxx > {secret_file} && chmod 600")
        return Credential()

    def _ensure_credential(self, action: str) -> bool:
        if self._credential and self._credential.sessdata:
            return True
        print(f"{self._msg_prefix} 缺少 BILIBILI_SESSDATA，无法{action}")
        return False

    def _call_api(self, api_func, *args, **kwargs):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._rate_limiter.wait()
                return sync(api_func(*args, **kwargs))
            except ResponseCodeException as e:
                if e.code in (-503, -412, -509):
                    wait_time = 5 * (attempt + 1)
                    print(
                        f"{self._msg_prefix} 限流(HTTP {e.code})，"
                        f"等待{wait_time}s后重试 ({attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue
                print(f"{self._msg_prefix} API 错误: code={e.code}")
                return None
            except NetworkException as e:
                wait_time = 2 ** (attempt + 1)
                print(
                    f"{self._msg_prefix} 网络错误，"
                    f"等待{wait_time}s后重试 ({attempt + 1}/{max_retries})..."
                )
                time.sleep(wait_time)
                continue
            except Exception as e:
                print(f"{self._msg_prefix} 请求异常: {e}")
                return None

        print(f"{self._msg_prefix} 请求失败: 已达最大重试次数 ({max_retries})")
        return None

    def search_users(self, keyword: str) -> List[BilibiliUser]:
        result = self._call_api(
            search_by_type,
            keyword,
            search_type=SearchObjectType.USER,
            order_type=OrderUser.FANS,
        )
        if not result:
            return []

        users = []
        for item in result.get("result", []):
            if item.get("type") != "bili_user":
                continue
            verify_info = item.get("verify_info", "")
            official_verify = -1
            official_desc = ""
            if verify_info:
                official_desc = verify_info
                official_verify = 0

            users.append(
                BilibiliUser({
                    "mid": item.get("mid"),
                    "name": item.get("uname"),
                    "follower": item.get("fans"),
                    "following": None,
                    "level": None,
                    "sign": item.get("usign", ""),
                    "avatar": item.get("upic", ""),
                    "official_verify": official_verify,
                    "official_desc": official_desc,
                    "video_count": item.get("videos"),
                })
            )
        return users

    def get_user_by_uid(self, uid: str) -> Optional[BilibiliUser]:
        mid = int(uid)
        user_api = User(mid, credential=self._credential)

        rel = self._call_api(user_api.get_relation_info)
        if not rel:
            return None

        info = self._call_api(user_api.get_user_info)
        if not info:
            return None

        official_data = info.get("official", {})
        official_verify = official_data.get("type", -1)
        official_desc = official_data.get("title", "")

        return BilibiliUser({
            "mid": mid,
            "name": info.get("name"),
            "follower": rel.get("follower"),
            "following": rel.get("following"),
            "level": info.get("level"),
            "sign": info.get("sign", ""),
            "avatar": info.get("face", ""),
            "official_verify": official_verify,
            "official_desc": official_desc,
        })

    def get_user_info(self, uid: str) -> Optional[dict]:
        mid = int(uid)
        user_api = User(mid, credential=self._credential)
        info = self._call_api(user_api.get_user_info)
        if not info:
            return None

        rel = self._call_api(user_api.get_relation_info)
        follower = rel.get("follower") if rel else None
        following = rel.get("following") if rel else None
        official_data = info.get("official", {})

        return {
            "mid": mid,
            "name": info.get("name"),
            "fans": follower,
            "following": following,
            "level": info.get("level"),
            "sign": info.get("sign", ""),
            "avatar": info.get("face", ""),
            "sex": info.get("sex", ""),
            "birthday": info.get("birthday", ""),
            "official_type": official_data.get("type", -1),
            "official_title": official_data.get("title", ""),
            "official_desc": official_data.get("desc", ""),
        }

    def _search_best_match(
        self, users: list, keyword: str, exact_match: bool
    ) -> Optional[BilibiliUser]:
        keyword_lower = keyword.lower()

        if exact_match:
            for u in users:
                if u.official_verify == 0:
                    name_lower = (u.name or "").lower()
                    if keyword_lower == name_lower or keyword in (u.name or ""):
                        label_detail = (
                            f" [{u.verified_label}]" if u.verified_label else ""
                        )
                        print(f"✓ 认证账号优先: {u.name} ({u.follower} 粉丝){label_detail}")
                        return u

            for u in users:
                if keyword in (u.name or ""):
                    if u.follower is not None:
                        print(f"✓ 精确匹配: {u.name} ({u.follower} 粉丝)")
                        return u

            print(f"未找到精确匹配用户: {keyword}，选择最佳结果")

        best_user = None
        best_score = -1
        for u in users:
            if u.follower is not None:
                score = u.follower + (200000 if u.official_verify == 0 else 0)
                if score > best_score:
                    best_score = score
                    best_user = u

        if best_user:
            prefix = "✓ 认证账号" if best_user.official_verify == 0 else "✓ 选择结果"
            label_detail = (
                f" [{best_user.verified_label}]" if best_user.verified_label else ""
            )
            print(f"{prefix}: {best_user.name} ({best_user.follower} 粉丝){label_detail}")
            return best_user

        print(f"未找到有效用户: {keyword}")
        return None

    def search_and_get_user(
        self, keyword: str, exact_match: bool = True
    ) -> Optional[BilibiliUser]:
        users = self.search_users(keyword)
        if users:
            result = self._search_best_match(users, keyword, exact_match)
            if result:
                if result.level is None and result.mid:
                    full = self.get_user_by_uid(str(result.mid))
                    if full:
                        return full
                return result

        print(f"未找到用户: {keyword}")
        return None

    def get_user_recent_videos(
        self, uid: str, count: int = 3
    ) -> Optional[List[dict]]:
        if not self._ensure_credential("获取最近视频"):
            return None

        mid = int(uid)
        user_api = User(mid, credential=self._credential)
        result = self._call_api(user_api.get_videos, pn=1, ps=count)
        if not result:
            return None

        vlist = result.get("list", {}).get("vlist", [])
        if not vlist:
            return []

        videos = []
        for v in vlist[:count]:
            videos.append({
                "bvid": v.get("bvid"),
                "title": v.get("title"),
                "play": v.get("play"),
                "video_review": v.get("video_review"),
                "favorites": v.get("favorites"),
                "like": v.get("like", 0),
                "created": v.get("created"),
                "duration": v.get("length"),
                "pic": v.get("pic"),
                "description": v.get("description", ""),
            })
        return videos

    def search_and_get_recent_videos(
        self, keyword: str, count: int = 3
    ) -> Tuple[Optional[List[dict]], Optional[BilibiliUser]]:
        user = self.search_and_get_user(keyword)
        if not user:
            return None, None
        videos = self.get_user_recent_videos(str(user.mid), count)
        return videos, user


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="B站用户粉丝数据查询工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="命令")

    search_parser = subparsers.add_parser("search", help="搜索用户")
    search_parser.add_argument("keyword", help="搜索关键词")

    get_parser = subparsers.add_parser("get", help="获取用户详情")
    get_parser.add_argument("uid", help="用户UID")

    info_parser = subparsers.add_parser("info", help="获取原始用户详情数据")
    info_parser.add_argument("uid", help="用户UID")

    recent_parser = subparsers.add_parser("recent", help="搜索用户并获取最近视频")
    recent_parser.add_argument("keyword", help="搜索关键词")
    recent_parser.add_argument(
        "count", nargs="?", type=int, default=3, help="视频数量 (默认3)"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    tool = BilibiliFollowerTool(rate_limit=3.0)

    if args.command == "search":
        print(f"搜索用户: {args.keyword}")
        users = tool.search_users(args.keyword)
        if users:
            for u in users[:10]:
                label = f" [{u.verified_label}]" if u.verified_label else ""
                print(f"  UID: {u.mid}, 昵称: {u.name}, 粉丝: {u.follower}{label}")
            if len(users) > 10:
                print(f"  ... 共 {len(users)} 个结果")
        else:
            print("  未找到结果")

    elif args.command == "get":
        print(f"获取用户详情: UID={args.uid}")
        user = tool.get_user_by_uid(args.uid)
        if user:
            print(f"  昵称: {user.name}")
            print(f"  粉丝数: {user.follower}")
            print(f"  关注数: {user.following}")
            print(f"  等级: {user.level}")
            print(f"  签名: {user.sign}")
            if user.verified_label:
                print(f"  认证: {user.verified_label}")
        else:
            print("  获取失败")

    elif args.command == "info":
        print(f"获取用户详情数据: UID={args.uid}")
        info = tool.get_user_info(args.uid)
        if info:
            for k, v in info.items():
                print(f"  {k}: {v}")
        else:
            print("  获取失败")

    elif args.command == "recent":
        print(f"搜索用户并获取最近视频: {args.keyword}")
        videos, user = tool.search_and_get_recent_videos(args.keyword, args.count)
        if not user:
            print("  未找到用户")
            return
        print(f"\n用户: {user.name} (UID: {user.mid})")
        print(f"粉丝: {user.follower}")
        if user.verified_label:
            print(f"认证: {user.verified_label}")
        if videos:
            print(f"\n最近视频 (共 {len(videos)} 条):")
            for i, v in enumerate(videos, 1):
                print(f"\n--- 视频 {i} ---")
                print(f"  BV号: {v['bvid']}")
                print(f"  标题: {v['title']}")
                print(f"  播放: {v['play']}")
                print(f"  弹幕: {v['video_review']}")
                print(f"  收藏: {v['favorites']}")
                print(f"  时长: {v['duration']}s")
        else:
            print("  无最近视频数据（需要配置 BILIBILI_SESSDATA）")


if __name__ == "__main__":
    main()
