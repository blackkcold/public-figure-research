#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""public-figure-research cookie 提取脚本。

仅用于在已有平台 skill 查询失败时，作为 fallback 数据源。
通过 rookiepy 解密本地浏览器 cookie（macOS 无需 playwright），
只提取目标平台的最小 cookie 集合，临时存储，用后即删。
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

try:
    import rookiepy
except ImportError:
    print("缺少依赖 rookiepy，请先执行: pip3 install --user rookiepy")
    sys.exit(2)

PLATFORM_COOKIES = {
    "weibo": {"domain": "weibo.com", "keys": ["SCF", "SUB", "SUBP"]},
    "douyin": {"domain": "douyin.com", "keys": ["sessionid", "sessionid_ss", "ttwid", "s_v_web_id", "sid_guard", "uid_tt", "odin_tt", "passport_csrf_token", "d_ticket", "n_mh", "msToken"]},
    "xiaohongshu": {"domain": "xiaohongshu.com", "keys": ["a1", "web_session", "webId", "gid", "sec_poison_id", "websectiga"]},
    "bilibili": {"domain": "bilibili.com", "keys": ["SESSDATA"]},
}

BROWSERS = ["edge", "chrome", "safari"]
MAX_AGE = 3600


def _load_browser(browser, domains):
    try:
        fn = getattr(rookiepy, browser)
        return fn(domains=domains)
    except Exception as e:
        print(f"[{browser}] 解密失败: {type(e).__name__}: {e}")
        return []


def extract(platform, browsers=None):
    browsers = browsers or BROWSERS
    spec = PLATFORM_COOKIES.get(platform)
    if not spec:
        print(f"未知平台: {platform}，可选: {list(PLATFORM_COOKIES.keys())}")
        return {}

    domain = spec["domain"]
    keys = spec["keys"]
    now = time.time()

    for browser in browsers:
        cookies = _load_browser(browser, [domain])
        if not cookies:
            continue
        found = {}
        for c in cookies:
            cdomain = c.get("domain") or ""
            if domain in cdomain and c.get("name") in keys:
                expires = c.get("expires") or 0
                if expires and expires < now:
                    continue
                found[c["name"]] = c.get("value", "")
        if found:
            print(f"[{browser}] 提取到 {platform} 登录态: {sorted(found.keys())}")
            return found
        print(f"[{browser}] 未找到 {platform} 登录态 cookie")

    print(f"所有浏览器均未找到 {platform} 登录态 cookie")
    return {}


def save_cookies(cookies, platform, temp_dir):
    temp_dir = Path(temp_dir).expanduser()
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(temp_dir, 0o700)
    path = temp_dir / f"{platform}_cookies.json"
    payload = {
        "platform": platform,
        "extracted_at": int(time.time()),
        "expires_at": int(time.time()) + MAX_AGE,
        "cookies": cookies,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"已保存到 {path}（权限 0600，有效期 {MAX_AGE}s）")
    return path


def cleanup(temp_dir):
    temp_dir = Path(temp_dir).expanduser()
    if not temp_dir.exists():
        return
    trash = Path.home() / ".Trash"
    trash.mkdir(exist_ok=True)
    dest = trash / f"public-figure-research-{int(time.time())}"
    shutil.move(str(temp_dir), str(dest))
    print(f"已清理临时 cookie 目录 → {dest}")


def main():
    parser = argparse.ArgumentParser(description="提取平台登录 cookie（fallback 用）")
    parser.add_argument("platform", nargs="?", help="平台: weibo/douyin/xiaohongshu/bilibili")
    parser.add_argument("--dry-run", action="store_true", help="仅验证登录态，不落盘")
    parser.add_argument("--browser", action="append", help="指定浏览器（可多次）")
    parser.add_argument("--temp-dir", default=os.environ.get("TMPDIR", "/tmp") + "/public-figure-research")
    parser.add_argument("--cleanup", action="store_true", help="清理临时目录")
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.temp_dir)
        return

    if not args.platform:
        parser.print_help()
        return

    browsers = args.browser or BROWSERS
    cookies = extract(args.platform, browsers)

    if not cookies:
        print("未提取到任何 cookie，无法作为 fallback 数据源")
        sys.exit(1)

    if args.dry_run:
        print(f"[dry-run] {args.platform} 登录态有效，可作 fallback")
        return

    save_cookies(cookies, args.platform, args.temp_dir)


if __name__ == "__main__":
    main()
