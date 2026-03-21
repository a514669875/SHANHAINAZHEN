"""接口冒烟测试：健康检查、登录、工程 CRUD 规则、台账列表、导出参数校验。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.procurement import Procurement
from app.models.project import Project
from app.services.procurement_service import (
    generate_contract_number,
    get_next_contract_seq,
)


def test_root(client: TestClient):
    r = client.get("/")
    assert r.status_code == 200
    assert "version" in r.json()


def test_health(client: TestClient):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_stats_no_auth_ok(client: TestClient):
    """首页统计接口当前无鉴权。"""
    r = client.get("/api/stats")
    assert r.status_code == 200
    data = r.json()
    assert "projects" in data
    assert "procurements" in data
    assert "ledgers" in data


def test_login_invalid(client: TestClient):
    r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_me_no_auth_returns_null(client: TestClient):
    """未登录时返回 200 + null，便于前端探测会话且不产生误导性 401。"""
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json() is None


def test_me_with_admin(client: TestClient, admin_headers: dict):
    r = client.get("/api/auth/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_projects_list_empty_then_create(client: TestClient, admin_headers: dict):
    r = client.get("/api/projects", headers=admin_headers)
    assert r.status_code == 200
    assert r.json() == []

    me = client.get("/api/auth/me", headers=admin_headers).json()
    oid = str(me["id"])
    payload = {
        "funding_type": "工程类",
        "project_type": "集团内项目",
        "project_number": "PY-001",
        "project_id": "TEST-PY-API",
        "project_name": "接口测试工程",
        "department": "测试部",
        "site_manager": "测",
        "site_manager_phone": "13800000000",
        "construction_unit": "测试单位",
        "total_contract_price": 1000.0,
        "funding_source": "企业自筹",
        "project_address": "测试地址",
        "procurement_officers": oid,
    }
    r2 = client.post("/api/projects", json=payload, headers=admin_headers)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["project_id"] == "TEST-PY-API"

    r3 = client.get("/api/projects", headers=admin_headers)
    assert r3.status_code == 200
    assert len(r3.json()) == 1


def test_delete_project_blocked_when_has_procurement(
    client: TestClient, admin_headers: dict, db_session
):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    oid = str(me["id"])
    payload = {
        "funding_type": "工程类",
        "project_type": "集团内项目",
        "project_number": "PY-DEL",
        "project_id": "TEST-DEL-BLOCK",
        "project_name": "删除拦截测试",
        "department": "测试部",
        "site_manager": "测",
        "site_manager_phone": "1",
        "construction_unit": "测",
        "total_contract_price": 1.0,
        "funding_source": "自筹",
        "project_address": "测",
        "procurement_officers": oid,
    }
    r = client.post("/api/projects", json=payload, headers=admin_headers)
    assert r.status_code == 200
    pid = r.json()["id"]

    db_session.add(
        Procurement(
            project_id=pid,
            procurement_type="材料采购",
            procurement_method="直接采购",
            project_name="子项",
            content="子项",
            control_price=1.0,
            contract_number="T-CON",
            form_data="{}",
        )
    )
    db_session.commit()

    r2 = client.delete(f"/api/projects/{pid}", headers=admin_headers)
    assert r2.status_code == 400
    assert "无法删除" in (r2.json().get("detail") or "")


def test_delete_empty_project_ok(client: TestClient, admin_headers: dict):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    oid = str(me["id"])
    payload = {
        "funding_type": "自有资金",
        "project_type": "",
        "project_number": "PY-DEL2",
        "project_id": "TEST-DEL-OK",
        "project_name": "可删工程",
        "department": "测试部",
        "site_manager": "测",
        "site_manager_phone": "1",
        "construction_unit": "自有",
        "total_contract_price": 1.0,
        "funding_source": "自有资金",
        "project_address": "测",
        "procurement_officers": oid,
    }
    r = client.post("/api/projects", json=payload, headers=admin_headers)
    assert r.status_code == 200
    pid = r.json()["id"]
    r2 = client.delete(f"/api/projects/{pid}", headers=admin_headers)
    assert r2.status_code == 200


def test_projects_export_requires_ids(client: TestClient, admin_headers: dict):
    r = client.get("/api/projects/export/excel", headers=admin_headers)
    assert r.status_code == 400


def test_material_lease_shares_cai_contract_sequence(
    client: TestClient, admin_headers: dict, db_session
):
    """材料租赁与材料采购共用 材X 序号池（PRD 确认）。"""
    me = client.get("/api/auth/me", headers=admin_headers).json()
    oid = str(me["id"])
    payload = {
        "funding_type": "工程类",
        "project_type": "集团内项目",
        "project_number": "PY-ML",
        "project_id": "TEST-SEQ-ML",
        "project_name": "材号共用测试工程",
        "department": "测试部",
        "site_manager": "测",
        "site_manager_phone": "1",
        "construction_unit": "测",
        "total_contract_price": 1.0,
        "funding_source": "自筹",
        "project_address": "测",
        "procurement_officers": oid,
    }
    r = client.post("/api/projects", json=payload, headers=admin_headers)
    assert r.status_code == 200
    pid = r.json()["id"]
    proj = db_session.query(Project).filter(Project.id == pid).first()
    db_session.add(
        Procurement(
            project_id=pid,
            procurement_type="材料采购",
            procurement_method="直接采购",
            project_name="m1",
            content="c1",
            control_price=1.0,
            contract_number=f"{proj.project_id}-材1",
            form_data="{}",
        )
    )
    db_session.commit()
    assert get_next_contract_seq(db_session, pid, "材料租赁") == 2
    assert get_next_contract_seq(db_session, pid, "材料采购") == 2
    assert generate_contract_number(proj, "材料租赁", 2) == f"{proj.project_id}-材2"


def test_ledger_list_authenticated(client: TestClient, admin_headers: dict):
    r = client.get("/api/ledger", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data and "total" in data
    assert isinstance(data["items"], list)
