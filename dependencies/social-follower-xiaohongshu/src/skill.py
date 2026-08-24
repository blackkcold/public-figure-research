# -*- coding: utf-8 -*-

import time
import threading
from typing import List, Optional
import os
import json
import subprocess
import re
from pathlib import Path


class RateLimiter:
    def __init__(self, min_interval: float = 5.0):
        self.min_interval = min_interval
        self.last_call = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


class XiaohongshuUser:
    def __init__(self, data: dict):
        self.user_id = data.get("user_id")
        self.nickname = data.get("nickname")
        self.red_id = data.get("red_id")
        self.fans = data.get("fans")
        self.verified = data.get("verified", False)
        self.verify_type = data.get("verify_type", 0)
        self.verify_content = data.get("verify_content", "")

    @property
    def verified_label(self) -> str:
        if not self.verified:
            return ""
        TYPE_MAP = {1: "演员", 2: "音乐人", 3: "博主"}
        label = TYPE_MAP.get(self.verify_type)
        if label:
            return f"红V({label})"
        return "红V认证"

    def __repr__(self):
        return f"<XiaohongshuUser {self.nickname}: {self.fans}>"


class XiaohongshuFollowerTool:
    DEFAULT_MIN_FOLLOWERS = 5000

    def __init__(
        self,
        cookie: str = "",
        rate_limit: float = 3.0,
        min_followers: int = DEFAULT_MIN_FOLLOWERS,
        verify_before_search: bool = True,
    ):
        self.cookie = cookie
        self._api_key = self._resolve_api_key()
        self._rate_limiter = RateLimiter(min_interval=rate_limit)
        self._min_followers = min_followers
        self._verify_before_search = verify_before_search

    def _resolve_api_key(self) -> Optional[str]:
        value = os.environ.get("JUSTONE_API_KEY")
        if value and value.strip():
            return value.strip()

        op_ref = os.environ.get(
            "JUSTONE_OP_REFERENCE",
            "op://保险库/条目/字段",
        )
        try:
            result = subprocess.run(
                ["op", "read", "--no-newline", op_ref],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        secret_file = Path(os.environ.get("JUSTONE_KEY_FILE", str(Path.home() / ".config" / "opencode" / "secrets" / "justone.key")))
        if secret_file.exists():
            try:
                st = secret_file.stat()
                if st.st_mode & 0o077:
                    print(
                        f"[小红书] 权限过宽 "
                        f"({oct(st.st_mode & 0o777)}), 建议 chmod 600"
                    )
                return secret_file.read_text(encoding="utf-8").strip() or None
            except Exception:
                pass

        value = os.environ.get("JUSTONEAPI_TOKEN")
        if value and value.strip():
            return value.strip()

        print("[小红书] JustOneAPI Key 未配置")
        print("  方式一(推荐): 1Password → 创建条目 justone-api-key")
        print("  方式二: export JUSTONE_API_KEY=xxx 添加到 ~/.zshrc")
        print("  方式三: echo xxx > ${JUSTONE_KEY_FILE:-~/.config/opencode/secrets/justone.key} && chmod 600")
        return None

    def _verify_xiaohongshu_presence(self, keyword: str) -> bool:
        return True

    def _search_aliases(self, keyword: str) -> list:
        import requests
        from urllib.parse import urlencode
        import re

        try:
            params = {"q": f"{keyword} 小红书 昵称 账号"}
            url = "https://html.duckduckgo.com/html/?" + urlencode(params)
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                text = resp.text
                aliases = []
                patterns = [f"{keyword}小红书", f"{keyword}昵称", f"小红书@{keyword}"]
                for pattern in patterns:
                    if pattern in text:
                        idx = text.find(pattern)
                        if idx > 0:
                            chunk = text[max(0, idx - 30) : idx + 60]
                            matches = re.findall(r"@([^<\s,\]]+)", chunk)
                            for m in matches:
                                if m != keyword and len(m) > 1:
                                    aliases.append(m)
                aliases = list(dict.fromkeys(aliases))[:5]
                if aliases:
                    print(f"  [别名] 发现可能的别名: {aliases}")
                return aliases
        except Exception as e:
            print(f"  [别名] 搜索失败: {e}")
        return []

    def search_users(self, keyword: str) -> List[XiaohongshuUser]:
        self._rate_limiter.wait()
        if not self._api_key:
            print("[小红书] 未配置 JustOneAPI Key，无法搜索")
            return []
        return self._search_via_justoneapi(keyword)

    def _search_via_justoneapi(self, keyword: str) -> List[XiaohongshuUser]:
        """Search users via JustOneAPI V2 endpoint with retry logic.

        API returns users with follower count in sub_title field (e.g., "粉丝 381.2万").
        """
        import requests
        from urllib.parse import urlencode

        max_retries = 3
        for attempt in range(max_retries):
            try:
                params = {"token": self._api_key, "keyword": keyword}
                url = (
                    "https://api.justoneapi.com/api/xiaohongshu/search-user/v2?"
                    + urlencode(params)
                )
                resp = requests.get(url, timeout=60)
                data = resp.json()
                code = data.get("code")

                if code == 0:
                    users_data = data.get("data", {}).get("users", [])
                    users = []
                    for item in users_data:
                        fans = self._parse_followers_from_subtitle(
                            item.get("sub_title", "")
                        )
                        users.append(
                            XiaohongshuUser(
                                {
                                    "user_id": item.get("id"),
                                    "nickname": item.get("name"),
                                    "red_id": item.get("red_id"),
                                    "fans": fans,
                                    "verified": item.get(
                                        "red_official_verified", False
                                    ),
                                    "verify_type": item.get(
                                        "red_official_verify_type", 0
                                    ),
                                    "verify_content": item.get(
                                        "red_official_verify_content", ""
                                    ),
                                }
                            )
                        )
                    return users
                elif code == 302:
                    print(f"限流，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(5)
                    continue
                elif code == 500:
                    print(f"服务器错误，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(3)
                    continue
                else:
                    print(f"搜索失败: code={code}, msg={data.get('message')}")
                    return []
            except requests.exceptions.Timeout:
                print(f"请求超时，重试 ({attempt + 1}/{max_retries})...")
                time.sleep(2)
                continue
            except Exception as e:
                print(f"搜索异常: {e}")
                return []

        print(f"搜索失败: 已达到最大重试次数 ({max_retries})")
        return []

    def _parse_followers_from_subtitle(self, subtitle: str) -> Optional[int]:
        """Parse follower count from sub_title field.

        Format examples:
        - "粉丝 381.2万" -> 3812000
        - "粉丝 2155" -> 2155
        - "粉丝 12" -> 12
        """
        if not subtitle:
            return None
        import re

        match = re.search(r"([\d.]+)万", subtitle)
        if match:
            return int(float(match.group(1)) * 10000)
        match = re.search(r"粉丝\s*(\d+)", subtitle)
        if match:
            return int(match.group(1))
        return None

    def get_user_by_id(self, user_id: str) -> Optional[XiaohongshuUser]:
        self._rate_limiter.wait()
        if self._api_key:
            return self._get_via_justoneapi(user_id)
        return self._get_via_xhs(user_id)

    def search_and_get_user(
        self, keyword: str, exact_match: bool = True
    ) -> Optional[XiaohongshuUser]:
        if self._verify_before_search:
            has_account = self._verify_xiaohongshu_presence(keyword)
            if not has_account:
                print(f"[结论] 未发现 {keyword} 的小红书账号，跳过API搜索")
                return None

        users = self.search_users(keyword)
        result = self._search_best_match_users(users, keyword, exact_match)
        if result:
            return result

        aliases = self._search_aliases(keyword)
        for alias in aliases:
            if alias != keyword:
                users = self.search_users(alias)
                result = self._search_best_match_users(users, alias, exact_match)
                if result:
                    print(f"  [别名] 通过别名 '{alias}' 找到用户")
                    return result

        print(f"未找到用户: {keyword}")
        return None

    def _search_best_match_users(
        self, users: list, keyword: str, exact_match: bool
    ) -> Optional[XiaohongshuUser]:
        if not users:
            return None

        min_fans = self._min_followers
        keyword_lower = keyword.lower()

        if exact_match:
            for u in users:
                if u.verified:
                    nickname_lower = (u.nickname or "").lower()
                    red_id_lower = (u.red_id or "").lower()
                    if (
                        keyword_lower == nickname_lower
                        or keyword_lower == red_id_lower
                        or keyword_lower in (u.nickname or "").lower()
                        or keyword_lower in (u.red_id or "").lower()
                    ):
                        if u.fans is not None and u.fans >= min_fans:
                            print(
                                f"✓ 认证账号优先: {u.nickname} ({u.fans} 粉丝) [{u.verified_label}]"
                            )
                            return u

            for u in users:
                nickname_lower = (u.nickname or "").lower()
                red_id_lower = (u.red_id or "").lower()
                if (
                    keyword_lower == nickname_lower
                    or keyword_lower == red_id_lower
                    or keyword_lower in (u.nickname or "").lower()
                    or keyword_lower in (u.red_id or "").lower()
                ):
                    if u.fans is not None:
                        if u.fans < min_fans:
                            print(f"跳过 {u.nickname} ({u.fans} 粉丝) - 粉丝数低于阈值")
                            continue
                        print(f"✓ 精确匹配: {u.nickname} ({u.fans} 粉丝)")
                        return u
                    result = self.get_user_by_id(u.user_id)
                    if result and result.fans is not None and result.fans >= min_fans:
                        return result
                    if result:
                        print(f"  结果粉丝数 {result.fans} 低于阈值，跳过")

            print(f"未找到精确匹配用户: {keyword}，尝试选择最佳结果")

        best_user = None
        best_score = -1
        for u in users:
            if u.fans is not None and u.fans >= min_fans:
                score = u.fans + (100000 if u.verified else 0)
                if score > best_score:
                    best_score = score
                    best_user = u

        if best_user:
            prefix = f"✓ {best_user.verified_label}" if best_user.verified else "✓ 选择结果"
            print(f"{prefix}: {best_user.nickname} ({best_user.fans} 粉丝)")
            return best_user

        print(f"未找到有效用户: {keyword} (所有结果粉丝数均低于阈值 {min_fans})")
        return None

    def _get_via_justoneapi(self, user_id: str) -> Optional[XiaohongshuUser]:
        import requests

        max_retries = 3
        for attempt in range(max_retries):
            try:
                url = f"https://api.justoneapi.com/api/xiaohongshu/get-user/v3?token={self._api_key}&userId={user_id}"
                resp = requests.get(url, timeout=60)
                data = resp.json()
                code = data.get("code")

                if code == 0:
                    user_data = data.get("data", {})
                    fans = user_data.get("fans")
                    if fans is None:
                        interactions = user_data.get("interactions", [])
                        fans_data = next(
                            (i for i in interactions if i.get("type") == "fans"), {}
                        )
                        fans = fans_data.get("count")
                    return XiaohongshuUser(
                        {
                            "user_id": user_id,
                            "nickname": user_data.get("nickname"),
                            "red_id": user_data.get("red_id"),
                            "fans": fans,
                            "verified": user_data.get("red_official_verified", False),
                            "verify_type": user_data.get("red_official_verify_type", 0),
                            "verify_content": user_data.get("red_official_verify_content", ""),
                        }
                    )
                elif code == 302:
                    print(f"限流，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(5)
                    continue
                elif code == 500:
                    print(f"服务器错误，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(3)
                    continue
                else:
                    print(f"[获取-JustOneAPI] 失败: code={code}, msg={data.get('message')}")
                    return None
            except requests.exceptions.Timeout:
                print(f"请求超时，重试 ({attempt + 1}/{max_retries})...")
                time.sleep(2)
                continue
            except json.JSONDecodeError as e:
                print(f"[获取-JustOneAPI] 响应解析失败: {e}")
                return None
            except Exception as e:
                print(f"[获取-JustOneAPI] 异常: {e}")
                return None

        print(f"获取用户失败: 已达到最大重试次数 ({max_retries})")
        return None


def main():
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m skill <command> [args]")
        print("命令:")
        print("  get <user_id>  获取用户信息")
        return

    cmd = sys.argv[1]
    tool = XiaohongshuFollowerTool(rate_limit=3.0)

    if cmd == "get" and len(sys.argv) >= 3:
        user_id = sys.argv[2]
        print(f"获取用户信息: user_id={user_id}")
        user = tool.get_user_by_id(user_id)
        if user:
            print(f"  昵称: {user.nickname}")
            print(f"  小红书号: {user.red_id}")
            print(f"  粉丝数: {user.fans}")
        else:
            print("  获取失败")


if __name__ == "__main__":
    main()
