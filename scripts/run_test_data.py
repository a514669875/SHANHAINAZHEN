#!/usr/bin/env python3
"""
模拟人工前端操作录入测试数据。
按顺序录入：测试项目1（工程类集团内）、测试项目2（工程类集团外）、测试项目3（自有资金）
记录问题但不修改代码。
"""
import json
import os
import requests
import sys
from pathlib import Path

# 避免代理干扰本地请求
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
BASE_URL = "http://127.0.0.1:8000/api"
ISSUES = []


def log_issue(msg: str):
    print(f"[问题] {msg}")
    ISSUES.append(msg)


def login():
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": "admin", "password": "admin123"})
    r.raise_for_status()
    return r.json()["access_token"]


def req(method, url, token, **kwargs):
    headers = {"Authorization": f"Bearer {token}"}
    kwargs.setdefault("proxies", {"http": None, "https": None})
    r = requests.request(method, f"{BASE_URL}{url}", headers=headers, timeout=30, **kwargs)
    if r.status_code >= 400:
        log_issue(f"API {method} {url} 失败: {r.status_code} {r.text[:200]}")
    return r


def parse_date(d: str) -> tuple:
    """2025.6.16 -> (2025, 6, 16) for qianding"""
    if not d or d.strip() == "/":
        return ("", "", "")
    s = d.replace(".", "-").replace(" ", "").strip()
    parts = s.split("-")
    if len(parts) >= 3:
        return (parts[0], parts[1], parts[2])
    return (d, "", "")


def get_or_create_project(token, data: dict):
    # 先查找是否已存在
    r = req("get", f"/projects?keyword={data.get('工程编号','')}&page=1&page_size=5", token)
    if r.status_code == 200:
        for p in r.json():
            if p.get("project_id") == data.get("工程编号"):
                return p
    payload = {
        "funding_type": data.get("资金类别", "工程类"),
        "project_type": data.get("工程类别", "集团内项目"),
        "project_number": data.get("项目编号", ""),
        "project_id": data.get("工程编号", ""),
        "project_name": data.get("工程名称", ""),
        "department": data.get("项目实施部门", ""),
        "site_manager": data.get("项目现场管理员", ""),
        "site_manager_phone": data.get("项目现场管理员联系方式", ""),
        "construction_unit": data.get("建设单位", data.get("发包单位", "")),
        "total_contract_price": float(data.get("总包合同价", 0)),
        "project_duration": data.get("工程工期", ""),
        "funding_source": data.get("资金来源", ""),
        "project_address": data.get("项目地址", ""),
        "procurement_officers": "1",  # admin
    }
    r = req("post", "/projects", token, json=payload)
    if r.status_code == 400 and "已存在" in r.text:
        # 项目已存在，再查一次
        r2 = req("get", f"/projects?keyword={data.get('工程编号','')}&page=1&page_size=5", token)
        if r2.status_code == 200:
            for p in r2.json():
                if p.get("project_id") == data.get("工程编号"):
                    return p
    r.raise_for_status()
    return r.json()


def build_step2(proj, proc_data: dict, sign_date_str: str, method: str):
    y, m, d = parse_date(sign_date_str)
    base = {
        "project_name": proj["project_name"],
        "project_number": proj["project_number"],
        "project_id": proj["project_id"],
        "construction_unit": proj["construction_unit"],
        "total_contract_price": proj["total_contract_price"],
        "project_address": proj["project_address"],
        "department": proj["department"],
        "site_manager": proj["site_manager"],
        "site_manager_phone": proj["site_manager_phone"],
        "procurement_project_name": proc_data.get("采购项目名称", ""),
        "content": proc_data.get("采购内容", ""),
        "control_price": float(proc_data.get("控制价", 0)),
        "procurement_type": "材料采购",
        "procurement_method": method,
        "leibie": "材料物资类",
        "tax_method": "简易计税方法计算" if "简易" in str(proc_data.get("计税方式", "")) else "一般计税方法计算",
        "contract_format": "采用非公司印发的合同标准文本编制" if "非公司" in str(proc_data.get("合同文本格式", "")) else "采用公司印发的合同标准文本编制",
        "use_standard_contract": "是",
        "passed_procurement": "是",
        "reviewed": "是",
        "sign_date": f"{y}-{m.zfill(2)}-{d.zfill(2)}" if y and m and d else sign_date_str,
        "gonggao_year": y, "gonggao_month": m, "gonggao_day": d,
        "yixiang_baoming_jiezhi_year": y, "yixiang_baoming_jiezhi_month": m, "yixiang_baoming_jiezhi_day": d,
        "jiaoyi_fengmian_year": y, "jiaoyi_fengmian_month": m,
        "jiaoyi_wenjian_year": y, "jiaoyi_wenjian_month": m, "jiaoyi_wenjian_day": d,
        "jiaoyi_wenjian_huoqv_jiezhi_year": y, "jiaoyi_wenjian_huoqv_jiezhi_month": m, "jiaoyi_wenjian_huoqv_jiezhi_day": d,
        "xiangying_dijiao_jiezhi_year": y, "xiangying_dijiao_jiezhi_month": m, "xiangying_dijiao_jiezhi_day": d,
        "qianding_year": y, "qianding_month": m, "qianding_day": d,
    }
    if method == "五选二":
        base["kongzhijia_biao1"] = float(proc_data.get("控制价标1（元）", proc_data.get("控制价", 0)))
        base["kongzhijia_biao2"] = float(proc_data.get("控制价标2（元）", proc_data.get("控制价", 0)))
        base["chengjiao_jine1"] = float(proc_data.get("成交金额1（元）", 0))
        base["chengjiao_jine2"] = float(proc_data.get("成交金额2（元）", 0))
    return base


def create_procurement(token, project_id, proj, proc_spec: dict, parent_id=None):
    method = proc_spec["method"]
    step2_data = proc_spec.get("step2", {})
    suppliers = proc_spec.get("suppliers", [])
    time_records = proc_spec.get("time_records", [])
    sign_date = step2_data.get("合同签订时间", "")

    step2 = build_step2(proj, step2_data, sign_date, method)
    step2["project_name"] = proj["project_name"]
    step2["project_number"] = proj["project_number"]
    step2["project_id"] = proj["project_id"]

    payload = {
        "project_id": project_id,
        "step1": {"procurement_type": "材料采购", "procurement_method": method},
        "step2": step2,
        "suppliers": [{"supplier_name": s.get("供应商",""), "contact_person": s.get("联系人",""), "contact_phone": s.get("联系方式",""),
                      "business_scope": s.get("经营范围",""), "tax_rate": str(s.get("税率","")), "quoted_price": float(s.get("含税报价（元）",0) or 0)}
                  for s in suppliers],
        "time_records": [{"flow_name": r["流程"], "date_val": r.get("日期","")} for r in time_records],
    }
    if method in ["单一来源", "直接采购"] and len(suppliers) == 0:
        suppliers = [{"供应商": "", "联系人": "", "联系方式": "", "经营范围": "", "税率": "", "含税报价（元）": 0}]
        log_issue(f"解析到 {method} 供应商为空，使用占位")
    if method == "补充协议":
        payload["parent_contract_id"] = parent_id
        payload["supplement_amount"] = float(step2_data.get("新增金额", 0))
        payload["supplement_content"] = step2_data.get("补充内容", "")
        ctrl = step2_data.get("控制价", "")
        payload["supplement_control_price"] = float(ctrl) if ctrl and str(ctrl).strip() != "/" else None
        payload["suppliers"] = [{"supplier_name": "", "contact_person": "", "contact_phone": "", "business_scope": "", "tax_rate": "", "quoted_price": 0}]
        sign_date = step2_data.get("合同签订时间", "")
        y, m, d = parse_date(sign_date)
        step2["sign_date"] = f"{y}.{int(m) if m else 0}.{int(d) if d else 0}" if y else sign_date
        step2["supplement_control_price"] = payload["supplement_control_price"]
    if method == "五选二":
        payload["section_a_name"] = step2_data.get("一标段名", "一标段")
        payload["section_b_name"] = step2_data.get("二标段名", "二标段")

    r = req("post", "/procurements", token, json=payload)
    if r.status_code >= 400:
        raise Exception(r.text)
    return r.json()


def load_test_file(path: Path) -> dict:
    """简单解析 md 中的表格数据"""
    text = path.read_text(encoding="utf-8")
    data = {"project": {}, "procurements": []}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("| 字段名 |") or line.startswith("| 字段名|"):
            i += 1
            while i < len(lines) and lines[i].startswith("|"):
                row = lines[i]
                parts = [p.strip() for p in row.split("|") if p.strip()]
                if len(parts) >= 2 and "---" not in row:
                    k, v = parts[0], parts[1]
                    if not data["project"] and k in ["资金类别","工程类别","项目编号"]:
                        data["project"][k] = v
                    if k in ["资金类别","工程类别","项目编号","工程编号","工程名称","项目实施部门","项目现场管理员",
                             "项目现场管理员联系方式","建设单位","总包合同价","工程工期","资金来源","项目地址"]:
                        data["project"][k] = v
                i += 1
            continue
        if "### 1." in line and "采购" in line:
            proc = {"method": "", "step2": {}, "suppliers": [], "time_records": []}
            if "邀请询比" in line: proc["method"] = "邀请询比"
            elif "单一来源" in line: proc["method"] = "单一来源"
            elif "直接采购" in line: proc["method"] = "直接采购"
            elif "五选二" in line: proc["method"] = "五选二"
            elif "补充协议" in line: proc["method"] = "补充协议"
            i += 1
            while i < len(lines) and not (lines[i].startswith("### 1.") and "采购" in lines[i]):
                # 补充协议采购方式表含 选择主合同
                if proc["method"] == "补充协议" and ("| 字段 |" in lines[i] or "| 字段|" in lines[i]):
                    i += 1
                    while i < len(lines) and lines[i].startswith("|") and "---" not in lines[i]:
                        row = lines[i]
                        parts = [p.strip() for p in row.split("|") if p.strip()]
                        if len(parts) >= 2:
                            k, v = parts[0], parts[1]
                            if k in ["选择主合同","主合同为五选二项目","标段"]:
                                proc["step2"][k] = v
                        i += 1
                    continue
                ln = lines[i]
                if "| 字段" in ln or "| 字段名" in ln:
                    i += 1
                    while i < len(lines) and lines[i].startswith("|") and "---" not in lines[i]:
                        row = lines[i]
                        parts = [p.strip() for p in row.split("|") if p.strip()]
                        if len(parts) >= 2:
                            k, v = parts[0], parts[1]
                            proc["step2"][k] = v
                        i += 1
                    continue
                # 供应商表头含 供应商 列，排除含 "流程" 的流程时间表（流程表有"流程"列）
                if "供应商" in ln and "|" in ln and "流程" not in ln and "供应商推荐表" not in ln:
                    i += 1
                    while i < len(lines) and lines[i].startswith("|"):
                        row = lines[i]
                        if "---" in row:
                            i += 1
                            continue
                        parts = [p.strip() for p in row.split("|") if p.strip()]
                        if len(parts) < 7:
                            i += 1
                            break  # 流程时间表等，停止供应商解析
                        if parts[0].isdigit():
                            try:
                                q = float(parts[6].replace(",", "")) if parts[6] else 0
                            except (ValueError, TypeError):
                                q = 0
                            proc["suppliers"].append({"供应商": parts[1], "联系人": parts[2], "联系方式": parts[3],
                                                      "经营范围": parts[4], "税率": parts[5], "含税报价（元）": q})
                        i += 1
                    continue
                if "| 序号 | 流程 |" in ln or "| 序号|流程|" in ln:
                    i += 1
                    while i < len(lines) and lines[i].startswith("|") and "---" not in lines[i]:
                        row = lines[i]
                        parts = [p.strip() for p in row.split("|") if p.strip()]
                        if len(parts) >= 3 and parts[0].isdigit():
                            proc["time_records"].append({"流程": parts[1], "日期": parts[2]})
                        i += 1
                    continue
                i += 1
            if proc["method"]:
                data["procurements"].append(proc)
            continue
        i += 1
    return data


def run_project(token, name: str, md_path: Path):
    print(f"\n=== 录入 {name} ===")
    raw = load_test_file(md_path)
    proj_data = raw["project"]
    if not proj_data.get("工程编号"):
        log_issue(f"{name}: 无法解析工程项目数据")
        return
    proj = get_or_create_project(token, proj_data)
    print(f"  工程项目已创建: id={proj['id']} {proj['project_id']} {proj['project_name']}")
    pid = proj["id"]

    contract_to_id = {}
    for idx, proc in enumerate(raw["procurements"]):
        method = proc["method"]
        parent_id = None
        if method == "补充协议":
            parent_cn = proc["step2"].get("选择主合同", "")
            parent_id = contract_to_id.get(parent_cn)
            if not parent_id:
                log_issue(f"{name} 补充协议: 未找到主合同 {parent_cn}，contract_to_id={contract_to_id}")
                continue
        try:
            if len(proc.get("suppliers", [])) != (5 if method == "五选二" else 3 if method == "邀请询比" else 1) and method != "补充协议":
                log_issue(f"{name} {method}: 解析到 {len(proc.get('suppliers',[]))} 家供应商，期望 {'5' if method=='五选二' else '3' if method=='邀请询比' else '1'} 家")
            res = create_procurement(token, pid, proj, proc, parent_id)
            ids = res.get("procurement_ids") or [res.get("procurement_id")]
            if ids:
                for iid in ids:
                    r2 = req("get", f"/procurements/{iid}", token)
                    if r2.status_code == 200:
                        cn = r2.json().get("contract_number", "")
                        if cn:
                            contract_to_id[cn] = iid
            print(f"  采购项目已创建: {method} -> {ids}")
        except Exception as e:
            log_issue(f"{name} {method} 创建失败: {e}")


def main():
    root = Path(__file__).resolve().parent.parent
    test_dir = root / "测试数据"
    if not test_dir.exists():
        log_issue("测试数据目录不存在")
        return
    try:
        token = login()
        print("登录成功")
    except Exception as e:
        log_issue(f"登录失败: {e}，请确保后端已启动 (uvicorn app.main:app --port 8000)")
        return
    for name, fname in [
        ("测试项目1（工程类集团内）", "测试项目1（工程类集团内）.md"),
        ("测试项目2（工程类集团外）", "测试项目2（工程类集团外）.md"),
        ("测试项目3（自有资金）", "测试项目3（自有资金）.md"),
    ]:
        path = test_dir / fname
        if path.exists():
            run_project(token, name, path)
        else:
            log_issue(f"文件不存在: {path}")
    print("\n" + "=" * 50)
    print(f"共记录 {len(ISSUES)} 个问题")
    for i, iss in enumerate(ISSUES, 1):
        print(f"  {i}. {iss}")


if __name__ == "__main__":
    main()
