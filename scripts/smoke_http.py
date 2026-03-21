#!/usr/bin/env python3
"""
对已启动的后端做 HTTP 冒烟检查（不替代 pytest）。

用法（先启动 uvicorn）:
  python scripts/smoke_http.py
  set SHANHAI_API_BASE=http://127.0.0.1:8000 && python scripts/smoke_http.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get("SHANHAI_API_BASE", "http://127.0.0.1:8000").rstrip("/")
    checks = [
        ("GET", f"{base}/api/health", None, 200),
        ("GET", f"{base}/api/stats", None, 200),
    ]
    for method, url, body, expect in checks:
        req = urllib.request.Request(url, method=method)
        if body is not None:
            req.data = json.dumps(body).encode("utf-8")
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                code = resp.status
        except urllib.error.HTTPError as e:
            print(f"FAIL {method} {url} -> HTTP {e.code}")
            return 1
        except urllib.error.URLError as e:
            print(f"FAIL {method} {url} -> {e.reason}")
            print("  请先启动后端: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return 2
        if code != expect:
            print(f"FAIL {method} {url} expected {expect} got {code}")
            return 1
        print(f"OK   {method} {url}")

    # 登录（默认管理员，与 init_db 一致）
    login_url = f"{base}/api/auth/login"
    data = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
    req = urllib.request.Request(
        login_url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                print(f"FAIL POST {login_url} -> {resp.status}")
                return 1
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"FAIL POST {login_url} -> HTTP {e.code} (数据库是否已 init_db？)")
        return 1
    except urllib.error.URLError as e:
        print(f"FAIL POST {login_url} -> {e.reason}")
        return 2

    token = payload.get("access_token")
    if not token:
        print("FAIL login response missing access_token")
        return 1
    print(f"OK   POST {login_url}")

    me_url = f"{base}/api/auth/me"
    req = urllib.request.Request(
        me_url, headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        if resp.status != 200:
            print(f"FAIL GET {me_url} -> {resp.status}")
            return 1
    print(f"OK   GET {me_url}")
    print("Smoke passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
