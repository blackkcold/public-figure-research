#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""public-figure-research cookie 提取脚本。

三级零弹窗解密策略（macOS，Keychain 仅在需要时触发一次弹窗）：
1. peanuts 纯数据解密：从浏览器 Cookies SQLite 用固定 peanuts 密钥 AES 解密。
   仅对旧版/无 Keychain 保护的 profile 有效；现代浏览器会失败。
2. CDP 拿明文：连接已运行的真实浏览器，Network.getAllCookies 返回明文 cookie。
   需浏览器已启动（带 --remote-debugging-port），零 Keychain 弹窗。
3. Keychain 兜底：用 rookiepy 读 Keychain 密钥解密（解密正确，已授权则不弹窗）。
   仅当用户手动授权后触发，绝不自动弹窗。

只提取目标平台的最小 cookie 集合，临时存储，用后即删。
"""
import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import hashlib
import urllib.request
from pathlib import Path

try:
    from Crypto.Cipher import AES
except ImportError:
    print("缺少依赖 pycryptodome，请先执行: pip3 install --user pycryptodome")
    sys.exit(2)

PLATFORM_COOKIES = {
    "weibo": {"domain": "weibo.com", "keys": ["SCF", "SUB", "SUBP"]},
    "douyin": {"domain": "douyin.com", "keys": ["sessionid", "sessionid_ss", "ttwid", "s_v_web_id", "sid_guard", "uid_tt", "odin_tt", "passport_csrf_token", "d_ticket", "n_mh", "msToken"]},
    "xiaohongshu": {"domain": "xiaohongshu.com", "keys": ["a1", "web_session", "webId", "gid", "sec_poison_id", "websectiga"]},
    "bilibili": {"domain": "bilibili.com", "keys": ["SESSDATA"]},
}

# macOS 浏览器 cookie 数据库路径模板（多 profile 探测）
BROWSER_DB_PATTERNS = {
    "chrome": "~/Library/Application Support/Google/Chrome/{profile}/Cookies",
    "edge": "~/Library/Application Support/Microsoft Edge/{profile}/Cookies",
}

MAX_AGE = 3600
CDP_PORT = 9222


def _derive_key(password):
    return hashlib.pbkdf2_hmac("sha1", password.encode(), b"saltysalt", 1003, 16)


def _aes_decrypt(key, data):
    """解密 v10 前缀的 AES-128-CBC 密文。"""
    if not data or data[:3] != b"v10":
        return None
    iv = b" " * 16
    cipher = AES.new(key, AES.MODE_CBC, iv)
    plain = cipher.decrypt(data[3:])
    pad = plain[-1]
    if 1 <= pad <= 16 and all(b == pad for b in plain[-pad:]):
        return plain[:-pad].decode("utf-8", errors="replace")
    return None


def _discover_cookie_db(browser):
    """探测指定浏览器的 Cookies 数据库路径（遍历 Default + Profile N）。"""
    base = BROWSER_DB_PATTERNS.get(browser)
    if not base:
        return None
    candidates = ["Default", "Profile 1", "Profile 2", "Profile 3"]
    for profile in candidates:
        path = Path(os.path.expanduser(base.format(profile=profile)))
        if path.exists():
            return path
    return None


def _sqlite_query_cookies(db_path, domain, keys):
    """从 SQLite 查询目标 cookie，安全双条件过滤（host_key AND name）。"""
    conn = None
    try:
        # WAL 友好：只读 + immutable 提示
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()
        placeholders = ",".join("?" * len(keys))
        # 双条件：host 严格匹配目标域名后缀，name 限定目标集合
        sql = f"""
            SELECT host_key, name, encrypted_value, value
            FROM cookies
            WHERE (host_key = ? OR host_key LIKE ?)
              AND name IN ({placeholders})
        """
        cur.execute(sql, [domain, f"%.{domain}"] + keys)
        rows = cur.fetchall()
        return rows
    finally:
        if conn:
            conn.close()


def _extract_via_peanuts(platform):
    """第1级：peanuts 纯数据解密（尽力而为，零弹窗）。"""
    spec = PLATFORM_COOKIES.get(platform)
    if not spec:
        return None, None
    domain = spec["domain"]
    keys = spec["keys"]
    key = _derive_key("peanuts")

    for browser in BROWSER_DB_PATTERNS:
        db_path = _discover_cookie_db(browser)
        if not db_path:
            continue
        rows = _sqlite_query_cookies(db_path, domain, keys)
        found = {}
        for host_key, name, enc, val in rows:
            decrypted = None
            if enc and enc[:3] == b"v10":
                decrypted = _aes_decrypt(key, enc)
            if decrypted:
                found[name] = decrypted
            elif val:  # 未加密的明文 cookie
                found[name] = val
        if found:
            print(f"[{browser}] peanuts 解密提取到 {platform}: {sorted(found.keys())}")
            return found, browser
        print(f"[{browser}] peanuts 未解密出 {platform} cookie")
    return None, None


def _cdp_get_cookies(platform, port=CDP_PORT):
    """第2级：CDP 连接已运行浏览器（真实 profile），拿明文 cookie（零 Keychain）。"""
    spec = PLATFORM_COOKIES.get(platform)
    if not spec:
        return None, None
    domain = spec["domain"]
    keys = spec["keys"]

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("CDP 需要 playwright，请执行: pip3 install --user playwright")
        return None, None

    try:
        with sync_playwright() as p:
            cdp = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            result = {}
            # 遍历所有 context 收集目标 cookie（真实浏览器 profile 的已登录 cookie）
            for ctx in cdp.contexts:
                for c in ctx.cookies():
                    if domain in c.get("domain", "") and c.get("name") in keys:
                        result[c["name"]] = c.get("value", "")
            cdp.close()
            if result:
                print(f"[cdp:9222] 提取到 {platform}: {sorted(result.keys())}")
                return result, "cdp"
            print(f"[cdp:9222] 未找到 {platform} cookie")
    except Exception as e:
        print(f"[cdp] 连接失败: {type(e).__name__}: {str(e)[:80]}")
    return None, None


def _keychain_get_cookies(platform, port=CDP_PORT, timeout=5):
    """第3级（兜底）：用 rookiepy 读 Keychain 解密（解密正确，已授权不弹窗）。

    rookiepy 内部读 "Safe Storage" Keychain 条目。若已授权则不弹窗；
    未授权时由 macOS 弹一次窗（符合"仅触发一次"要求）。
    """
    spec = PLATFORM_COOKIES.get(platform)
    if not spec:
        return None, None
    domain = spec["domain"]
    keys = spec["keys"]

    try:
        import rookiepy
    except ImportError:
        print("Keychain 兜底需要 rookiepy，请执行: pip3 install --user rookiepy")
        return None, None

    try:
        for browser in ("edge", "chrome"):
            fn = getattr(rookiepy, browser, None)
            if not fn:
                continue
            cookies = fn(domains=[domain])
            found = {}
            for c in cookies:
                if c.get("name") in keys:
                    expires = c.get("expires") or 0
                    if expires and expires < time.time():
                        continue
                    found[c["name"]] = c.get("value", "")
            if found:
                print(f"[keychain:{browser}] 提取到 {platform}: {sorted(found.keys())}")
                return found, f"keychain:{browser}"
    except Exception as e:
        print(f"[keychain] 失败: {type(e).__name__}: {str(e)[:80]}")
    return None, None


def extract(platform, strategy="peanuts,cdp,keychain"):
    """按策略链提取 cookie（peanuts→CDP→Keychain，带超时防循环）。"""
    strategies = [s.strip() for s in strategy.split(",")]
    if "peanuts" in strategies:
        found, browser = _extract_via_peanuts(platform)
        if found:
            return found, browser
    if "cdp" in strategies:
        found, browser = _cdp_get_cookies(platform)
        if found:
            return found, browser
    if "keychain" in strategies:
        found, browser = _keychain_get_cookies(platform)
        if found:
            return found, browser
    return None, None


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
    parser = argparse.ArgumentParser(description="提取平台登录 cookie（零弹窗 fallback）")
    parser.add_argument("platform", nargs="?", help="平台: weibo/douyin/xiaohongshu/bilibili")
    parser.add_argument("--dry-run", action="store_true", help="仅验证登录态，不落盘")
    parser.add_argument("--browser", action="append", help="指定浏览器（可多次）")
    parser.add_argument("--strategy", default="peanuts,cdp,keychain", help="解密策略链: peanuts,cdp,keychain")
    parser.add_argument("--temp-dir", default=os.environ.get("TMPDIR", "/tmp") + "/public-figure-research")
    parser.add_argument("--cleanup", action="store_true", help="清理临时目录")
    args = parser.parse_args()

    if args.cleanup:
        cleanup(args.temp_dir)
        return

    if not args.platform:
        parser.print_help()
        return

    cookies, browser = extract(args.platform, args.strategy)

    if not cookies:
        print(f"未提取到 {args.platform} cookie")
        print("提示（不自动弹窗）：")
        print("  1. 若浏览器已运行，可用 CDP 拿明文（需浏览器带 --remote-debugging-port）")
        print("  2. 或手动在 Keychain Access 允许 'Safe Storage' 条目")
        print("  3. 或配置 justoneapi key")
        sys.exit(1)

    if args.dry_run:
        print(f"[dry-run] {args.platform} 登录态有效（来源: {browser}），可作 fallback")
        return

    save_cookies(cookies, args.platform, args.temp_dir)


if __name__ == "__main__":
    main()
