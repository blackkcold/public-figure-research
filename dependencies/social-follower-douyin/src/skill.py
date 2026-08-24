# -*- coding: utf-8 -*-

import time
import threading
import json
import os
import re
import subprocess
from urllib.parse import urlencode
from typing import List, Optional
import requests
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


class DouyinUser:
    def __init__(self, data: dict):
        self.sec_user_id = data.get("sec_user_id")
        self.nickname = data.get("nickname")
        self.follower_count = data.get("follower_count")
        self.following_count = data.get("following_count")
        self.total_favorited = data.get("total_favorited")
        self.aweme_count = data.get("aweme_count")
        self.verified = data.get("verified", False)
        self.verification_type = data.get("verification_type", 0)
        self.custom_verify = data.get("custom_verify", "")
        self.enterprise_verify_reason = data.get("enterprise_verify_reason", "")
        self.is_star = data.get("is_star", False)

    def __repr__(self):
        return f"<DouyinUser {self.nickname}: {self.follower_count}>"


class DouyinFollowerTool:
    def __init__(self, rate_limit: float = 3.0):
        self._msg_prefix = "[抖音]"
        self._api_key = self._resolve_api_key()
        self._rate_limiter = RateLimiter(min_interval=rate_limit)
        self.base_url = "https://api.justoneapi.com"

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
                        f"{self._msg_prefix} 权限过宽 "
                        f"({oct(st.st_mode & 0o777)}), 建议 chmod 600"
                    )
                return secret_file.read_text(encoding="utf-8").strip() or None
            except Exception:
                pass

        value = os.environ.get("JUSTONEAPI_TOKEN")
        if value and value.strip():
            return value.strip()

        print(f"{self._msg_prefix} JustOneAPI Key 未配置")
        print("  方式一(推荐): 1Password → 创建条目 justone-api-key")
        print("  方式二: export JUSTONE_API_KEY=xxx 添加到 ~/.zshrc")
        print("  方式三: echo xxx > ${JUSTONE_KEY_FILE:-~/.config/opencode/secrets/justone.key} && chmod 600")
        return None

    def _request_json(self, url: str, timeout: int = 60) -> Optional[dict]:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
                data = resp.json()
                code = data.get("code")

                if code == 0:
                    return data

                if code == 302:
                    print(f"{self._msg_prefix} 限流，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(5)
                    continue
                if code == 500:
                    print(f"{self._msg_prefix} 服务器错误，等待后重试 ({attempt + 1}/{max_retries})...")
                    time.sleep(3)
                    continue

                print(f"{self._msg_prefix} 请求失败: code={code}, msg={data.get('message')}")
                return None
            except requests.exceptions.Timeout:
                print(f"{self._msg_prefix} 请求超时，重试 ({attempt + 1}/{max_retries})...")
                time.sleep(2)
                continue
            except json.JSONDecodeError as e:
                print(f"{self._msg_prefix} 响应解析失败: {e}")
                return None
            except Exception as e:
                print(f"{self._msg_prefix} 请求异常: {e}")
                return None

        print(f"{self._msg_prefix} 请求失败: 已达到最大重试次数 ({max_retries})")
        return None

    def _parse_user_info(self, user_info: dict) -> Optional[DouyinUser]:
        if not user_info:
            return None
        nickname = user_info.get("nickname")
        if not nickname:
            return None
        return DouyinUser(
            {
                "sec_user_id": user_info.get("sec_uid"),
                "nickname": nickname,
                "follower_count": user_info.get("follower_count"),
                "following_count": user_info.get("following_count"),
                "total_favorited": user_info.get("total_favorited"),
                "aweme_count": user_info.get("aweme_count"),
                "verified": user_info.get("author_verified", False),
                "verification_type": user_info.get("verification_type", 0),
                "custom_verify": user_info.get("custom_verify", ""),
                "enterprise_verify_reason": user_info.get("enterprise_verify_reason", ""),
                "is_star": user_info.get("is_star", False),
            }
        )

    def _ensure_api_key(self, action: str) -> bool:
        if self._api_key:
            return True
        print(f"{self._msg_prefix} 缺少 JUSTONE_API_KEY / JUSTONEAPI_TOKEN，无法{action}")
        return False

    def _build_url(self, endpoint: str, params: dict) -> str:
        params = {"token": self._api_key, **params}
        return f"{self.base_url}{endpoint}?{urlencode(params)}"

    def _user_label(self, user: DouyinUser) -> str:
        if user.is_star:
            return "明星账号"
        if user.verification_type == 2:
            label = "蓝V认证"
        elif user.verification_type == 1:
            label = "黄V认证"
        elif user.verified:
            label = "认证账号"
        else:
            return "选择结果"
        if user.custom_verify:
            return f"{label}({user.custom_verify})"
        if user.enterprise_verify_reason:
            return f"{label}({user.enterprise_verify_reason})"
        return label

    def search_users(self, keyword: str) -> List[DouyinUser]:
        self._rate_limiter.wait()
        if not self._ensure_api_key("搜索抖音用户"):
            return []

        url = self._build_url(
            "/api/douyin/search-user/v2",
            {"keyword": keyword, "userType": "personal_user"},
        )
        d = self._request_json(url)
        if not d:
            return []

        data = d.get("data", {})
        business_data = data.get("business_data", [])
        users = []
        for item in business_data:
            raw_data = item.get("data", {}).get("raw_data", "{}")
            try:
                raw = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            user_info = raw.get("user_info", {}) if isinstance(raw, dict) else {}
            user = self._parse_user_info(user_info)
            if user:
                users.append(user)
        return users

    def get_user_by_sec_uid(self, sec_user_id: str) -> Optional[DouyinUser]:
        self._rate_limiter.wait()
        if not self._ensure_api_key("获取抖音用户信息"):
            return None

        url = self._build_url("/api/douyin/get-user-detail/v3", {"secUid": sec_user_id})
        d = self._request_json(url)
        if not d:
            return None

        resp_data = d.get("data", {})
        if resp_data.get("status_code") == 0:
            user_data = resp_data.get("user", {})
            if user_data:
                return DouyinUser(
                    {
                        "sec_user_id": sec_user_id,
                        "nickname": user_data.get("nickname"),
                        "follower_count": user_data.get("follower_count"),
                        "following_count": user_data.get("following_count"),
                        "total_favorited": user_data.get("total_favorited"),
                        "aweme_count": user_data.get("aweme_count"),
                        "verified": user_data.get("author_verified", False),
                        "verification_type": user_data.get("verification_type", 0),
                        "custom_verify": user_data.get("custom_verify", ""),
                        "enterprise_verify_reason": user_data.get("enterprise_verify_reason", ""),
                        "is_star": user_data.get("is_star", False),
                    }
                )

        print(f"获取失败: status_code={resp_data.get('status_code')}")
        return None

    def _search_aliases(self, keyword: str) -> list:
        import re

        searchengines = [
            ("DuckDuckGo", "https://html.duckduckgo.com/html/?"),
            ("Bing", "https://www.bing.com/search?"),
        ]

        for name, base_url in searchengines:
            self._rate_limiter.wait()
            try:
                params = {"q": f"{keyword} 抖音 昵称 艺名 别名"}
                resp = requests.get(
                    base_url + urlencode(params),
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                if resp.status_code == 200:
                    text = resp.text
                    aliases = []
                    patterns = [f"{keyword}抖音", f"@{keyword}", f"{keyword}账号"]
                    for pattern in patterns:
                        if pattern in text:
                            idx = text.find(pattern)
                            if idx > 0:
                                chunk = text[max(0, idx - 30) : idx + 60]
                                matches = re.findall(r"@([^<\s,\]]+)", chunk)
                                for m in matches:
                                    if m != keyword and len(m) > 1:
                                        aliases.append(m)
                    if aliases:
                        aliases = list(dict.fromkeys(aliases))[:5]
                        print(f"  [别名-{name}] 发现: {aliases}")
                        return aliases
                    return []
            except Exception:
                print(f"  [别名-{name}] 失败")

        print(f"  [别名] 所有渠道均失败")
        return []

    def _search_best_match(
        self, users: list, keyword: str, exact_match: bool
    ) -> Optional[DouyinUser]:
        keyword_lower = keyword.lower()

        if exact_match:
            # Priority 0: is_star=True (官方明星账号) - highest priority
            for u in users:
                if u.is_star:
                    print(f"✓ {self._user_label(u)}: {u.nickname} ({u.follower_count} 粉丝)")
                    return u

            # Priority 1: Verified accounts with exact nickname match
            for u in users:
                if u.verified:
                    name_lower = (u.nickname or "").lower()
                    if keyword_lower == name_lower:
                        print(f"✓ {self._user_label(u)}精确匹配: {u.nickname} ({u.follower_count} 粉丝)")
                        return u

            # Priority 2: Exact nickname match with significant followers
            for u in users:
                if (u.nickname or "").lower() == keyword_lower:
                    if u.follower_count is not None and u.follower_count >= 10000:
                        print(
                            f"✓ 精确匹配(高粉): {u.nickname} ({u.follower_count} 粉丝)"
                        )
                        return u

            # Priority 3: Trust API's first result as most relevant
            if users and users[0].follower_count is not None:
                first = users[0]
                print(f"✓ API首选: {first.nickname} ({first.follower_count} 粉丝)")
                return first

            print(f"未找到精确匹配用户: {keyword}，选择最佳结果")

        # Score-based selection (used when exact_match=False)
        best_user = None
        best_score = -1
        for u in users:
            if u.follower_count is not None:
                score = (
                    u.follower_count
                    + (200000 if u.verification_type == 2 else 0)
                    + (100000 if u.verification_type == 1 else 0)
                    + (100000 if not u.verification_type and u.verified else 0)
                    + (500000 if u.is_star else 0)
                )
                if score > best_score:
                    best_score = score
                    best_user = u

        if best_user:
            prefix = (
                f"✓ {self._user_label(best_user)}"
            )
            print(f"{prefix}: {best_user.nickname} ({best_user.follower_count} 粉丝)")
            return best_user

        print(f"未找到有效用户: {keyword}")
        return None

    def search_and_get_user(
        self, keyword: str, exact_match: bool = True
    ) -> Optional[DouyinUser]:
        users = self.search_users(keyword)
        if users:
            result = self._search_best_match(users, keyword, exact_match)
            if result:
                return result

        aliases = self._search_aliases(keyword)
        for alias in aliases:
            if alias != keyword:
                users = self.search_users(alias)
                if users:
                    result = self._search_best_match(users, alias, exact_match)
                    if result:
                        print(f"  [别名] 通过别名 '{alias}' 找到用户")
                        return result

        print(f"未找到用户: {keyword}")
        return None


def main():
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m skill <command> [args]")
        print("命令:")
        print("  get <sec_user_id>  获取用户信息")
        print("  search <keyword>   搜索用户")
        return

    cmd = sys.argv[1]
    tool = DouyinFollowerTool(rate_limit=3.0)

    if cmd == "get" and len(sys.argv) >= 3:
        sec_uid = sys.argv[2]
        print(f"获取用户信息: sec_user_id={sec_uid}")
        user = tool.get_user_by_sec_uid(sec_uid)
        if user:
            print(f"  昵称: {user.nickname}")
            print(f"  粉丝数: {user.follower_count}")
            print(f"  关注数: {user.following_count}")
        else:
            print("  获取失败")

    elif cmd == "search" and len(sys.argv) >= 3:
        keyword = sys.argv[2]
        print(f"搜索用户: {keyword}")
        users = tool.search_users(keyword)
        for u in users[:5]:
            print(f"  {u.nickname}: {u.follower_count} 粉丝")


if __name__ == "__main__":
    main()
