#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""public-figure-research 平台粉丝查询脚本。

绕过 justoneapi 的 fallback 数据源：
- 小红书：纯 Python 签名（xhshow）+ 解密 cookie
- 抖音：playwright 无头 chromium + 注入 cookie + 浏览器内签名

依赖：
- 小红书：Python 3.10+ 环境 + xhshow（uv 创建）
- 抖音：playwright + chromium
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TEMP_DIR = os.environ.get("TMPDIR", "/tmp") + "/public-figure-research"
UV_PYTHON = os.environ.get("PFR_UV_PYTHON", "")  # uv 3.10 环境 python 路径
SKILL_DIR = Path(__file__).resolve().parent.parent  # 脚本所在 skill 目录（自定位）


def _load_cookies(platform):
    path = Path(TEMP_DIR) / f"{platform}_cookies.json"
    if not path.exists():
        print(f"cookie 文件不存在: {path}")
        print(f"请先在浏览器登录该平台，或配置 justoneapi key")
        print(f"   - 浏览器登录: 登录 {platform}.com 后运行 fetch_cookie.py {platform}")
        print(f"   - justoneapi: export JUSTONE_API_KEY=xxx")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["cookies"]


def _ensure_uv_env():
    """确保 uv 3.10 环境存在且装有 xhshow。"""
    if UV_PYTHON and Path(UV_PYTHON).exists():
        return UV_PYTHON
    venv = SKILL_DIR / ".venv"
    py = venv / "bin" / "python"
    if not py.exists():
        print("创建 uv 3.10 环境（小红书签名需要）...")
        subprocess.run(["uv", "venv", "--python", "3.10", str(venv)], check=True)
        subprocess.run(
            ["uv", "pip", "install", "--python", str(py), "xhshow", "requests"],
            check=True,
        )
    return str(py)


def query_xiaohongshu(keyword):
    """小红书粉丝查询：纯 Python 签名 + cookie。"""
    cookies = _load_cookies("xiaohongshu")
    if not cookies:
        return None
    py = _ensure_uv_env()
    script = f"""
import json, requests, time
from xhshow import Xhshow
cookies = {json.dumps(cookies, ensure_ascii=False)}
client = Xhshow()
uri = 'https://edith.xiaohongshu.com/api/sns/web/v1/search/usersearch'
payload = {{
    'search_user_request': {{
        'keyword': '{keyword}',
        'search_id': client.get_search_id(),
        'page': 1,
        'page_size': 10,
        'biz_type': 'web_search_user',
        'request_id': f'{{int(round(time.time()))}}-{{int(round(time.time()*1000))}}',
    }}
}}
headers = client.sign_headers_post(uri=uri, cookies=cookies, payload=payload, x_rap=True)
headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
headers['Referer'] = 'https://www.xiaohongshu.com/'
headers['Origin'] = 'https://www.xiaohongshu.com'
headers['Content-Type'] = 'application/json'
r = requests.post(uri, json=payload, headers=headers, cookies=cookies, timeout=15)
data = r.json()
users = data.get('data', {{}}).get('users', [])
for u in users:
    print(f"{{u.get('nickname')}}|{{u.get('fans')}}|{{u.get('profession')}}")
"""
    result = subprocess.run([py, "-c", script], capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"小红书查询失败: {result.stderr[:200]}")
        return None
    lines = [l for l in result.stdout.strip().splitlines() if "|" in l]
    if not lines:
        return None
    # 返回第一个（认证优先）
    nickname, fans, profession = lines[0].split("|", 2)
    return {"nickname": nickname, "fans": fans, "profession": profession}


def query_douyin(keyword):
    """抖音粉丝查询：playwright 无头 chromium + 注入 cookie + 浏览器内签名。"""
    cookies = _load_cookies("douyin")
    if not cookies:
        return None
    script = f"""
import json
from playwright.sync_api import sync_playwright
cookies = {json.dumps(cookies, ensure_ascii=False)}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
    context = browser.new_context(
        viewport={{'width': 1920, 'height': 1080}},
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        locale='zh-CN',
    )
    context.add_cookies([
        {{'name': k, 'value': v, 'domain': '.douyin.com', 'path': '/'}}
        for k, v in cookies.items()
    ])
    page = context.new_page()
    captured = []
    def on_response(response):
        if '/aweme/v1/web/discover/search' in response.url:
            try:
                body = response.json()
                if body.get('user_list') is not None:
                    captured.append(body)
            except: pass
    page.on('response', on_response)
    from urllib.parse import quote
    page.goto(f'https://www.douyin.com/search/{{quote("{keyword}")}}?type=user', wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(8000)
    for c in captured:
        for u in c.get('user_list', []):
            info = u.get('user_info', {{}})
            print(f"{{info.get('nickname')}}|{{info.get('follower_count')}}|{{info.get('custom_verify')}}")
    browser.close()
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"抖音查询失败: {result.stderr[:200]}")
        return None
    lines = [l for l in result.stdout.strip().splitlines() if "|" in l]
    if not lines:
        return None
    nickname, followers, verify = lines[0].split("|", 2)
    return {"nickname": nickname, "followers": followers, "verify": verify}


def main():
    parser = argparse.ArgumentParser(description="平台粉丝查询（绕过 justoneapi）")
    parser.add_argument("platform", help="平台: xiaohongshu/douyin")
    parser.add_argument("keyword", help="搜索关键词")
    args = parser.parse_args()

    if args.platform == "xiaohongshu":
        result = query_xiaohongshu(args.keyword)
        if result:
            print(f"小红书: {result['nickname']} | 粉丝 {result['fans']} | {result['profession']}")
        else:
            print("小红书: 未找到")
    elif args.platform == "douyin":
        result = query_douyin(args.keyword)
        if result:
            print(f"抖音: {result['nickname']} | 粉丝 {result['followers']} | {result['verify']}")
        else:
            print("抖音: 未找到")
    else:
        print(f"未知平台: {args.platform}")


if __name__ == "__main__":
    main()
