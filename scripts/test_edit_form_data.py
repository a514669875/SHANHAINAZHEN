"""测试四步式表单编辑保存 - 全采购类型/方式遍历。
用法：python scripts/test_edit_form_data.py
需先启动后端。脚本通过 API 模拟前端编辑流程。
"""
import os
import sys
import json
import requests

BASE = "http://127.0.0.1:8000"

# 采购类型 x 采购方式（排除需特殊前置的）
COMBOS = [
    ("材料采购", "直接采购"),
    ("材料采购", "单一来源"),
    ("材料采购", "邀请询比"),
    ("材料采购", "五选二"),
    ("设备采购", "直接采购"),
    ("设备采购", "单一来源"),
    ("设备采购", "邀请询比"),
    ("机械租赁", "直接采购"),
]


def login():
    r = requests.post(f"{BASE}/api/auth/login", data={"username": "admin", "password": "admin"})
    if r.status_code != 200:
        raise RuntimeError(f"登录失败: {r.status_code} {r.text}")
    return r.json()["access_token"]


def main():
    print("1. 登录...")
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    print("2. 获取工程与采购列表...")
    r = requests.get(f"{BASE}/api/projects", params={"page": 1, "page_size": 100}, headers=headers)
    if r.status_code != 200:
        print(f"  获取工程失败: {r.status_code}")
        return 1
    projects = r.json()
    if not projects:
        print("  无工程数据，请先创建工程和采购项目")
        return 1
    proj = projects[0]
    proj_id = proj["id"]

    r = requests.get(f"{BASE}/api/procurements", params={"project_id": proj_id, "for_list": True}, headers=headers)
    if r.status_code != 200:
        print(f"  获取采购列表失败: {r.status_code}")
        return 1
    procurements = r.json()
    if not procurements:
        print("  无采购数据，请先创建采购项目")
        return 1

    print(f"  工程: {proj.get('project_id')} {proj.get('project_name')}")
    print(f"  采购数量: {len(procurements)}")

    results = []
    for proc in procurements:
        pid = proc["id"]
        ptype = proc.get("procurement_type", "")
        method = proc.get("procurement_method", "")
        key = f"{ptype}+{method}"

        print(f"\n3. 测试 {key} (id={pid})...")

        # GET 详情
        r = requests.get(f"{BASE}/api/procurements/{pid}", headers=headers)
        if r.status_code != 200:
            results.append((key, "FAIL", f"GET 失败 {r.status_code}"))
            continue
        detail = r.json()
        step2 = detail.get("step2") or {}
        content_before = step2.get("content", "")

        # 构造编辑后的 form_data
        test_suffix = f"_EDIT_{pid}"
        test_content = (content_before or "测试") + test_suffix
        step2_copy = dict(step2)
        step2_copy["content"] = test_content
        step2_copy["_time_records"] = detail.get("time_records", [])

        form_data_str = json.dumps(step2_copy, ensure_ascii=False)

        # PUT 更新
        payload = {
            "project_name": detail.get("procurement_project_name", detail.get("project_name", "")),
            "content": test_content,
            "form_data": form_data_str,
            "suppliers": [{"supplier_name": s.get("supplier_name", ""), "contact_person": s.get("contact_person", ""),
                          "contact_phone": s.get("contact_phone", ""), "business_scope": s.get("business_scope", ""),
                          "tax_rate": s.get("tax_rate", ""), "quoted_price": s.get("quoted_price", 0)}
                         for s in detail.get("suppliers", [])],
        }
        if method == "补充协议":
            payload["supplement_amount"] = detail.get("control_price", 0)
            payload["supplement_content"] = test_content

        r = requests.put(f"{BASE}/api/procurements/{pid}", json=payload, headers=headers)
        if r.status_code != 200:
            results.append((key, "FAIL", f"PUT 失败 {r.status_code} {r.text[:200]}"))
            continue

        # 再次 GET 验证
        r = requests.get(f"{BASE}/api/procurements/{pid}", headers=headers)
        if r.status_code != 200:
            results.append((key, "FAIL", f"GET 验证失败 {r.status_code}"))
            continue
        detail2 = r.json()
        step2_after = detail2.get("step2") or {}
        content_after = step2_after.get("content", "")

        ok = test_suffix in content_after or test_content == content_after
        status = "OK" if ok else "FAIL"
        msg = "content 已更新" if ok else f"content 未包含 {test_suffix!r}, 实际={content_after[:80]!r}"
        results.append((key, status, msg))
        print(f"   {status}: {msg}")

    print("\n=== 汇总 ===")
    for k, s, msg in results:
        print(f"  {k}: {s} - {msg}")
    fails = [r for r in results if r[1] == "FAIL"]
    if fails:
        print(f"\n失败 {len(fails)} 项")
        return 1
    print("\n全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
