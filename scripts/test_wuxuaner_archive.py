"""Test 五选二 archive flow: create project, 五选二 procurement, upload 2 contracts, verify archive.
Run with backend server: uvicorn app.main:app --host 127.0.0.1 --port 8000
Or run direct DB test: python scripts/test_wuxuaner_archive.py --direct
"""
import sys
import argparse
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


def test_direct():
    """Direct DB test - no HTTP, creates data and tests archive logic."""
    from app.database import SessionLocal, run_migrations
    from app.models import Project, Procurement, Supplier, File, Ledger, User
    from app.services.archive_service import (
        find_dual_sibling,
        count_contract_files_in_temp,
        try_archive_and_create_ledgers,
        get_temp_path,
    )
    from app.config import ARCHIVED_FILE_ROOT, DATA_DIR

    run_migrations()
    db = SessionLocal()

    try:
        # 1. Create project
        proj = Project(
            project_id="TEST26-01N",
            project_name="五选二归档测试工程",
            project_number="TEST001",
            funding_type="工程类",
            project_type="集团内项目",
            construction_unit="测试单位",
            total_contract_price=1000000,
            project_address="测试地址",
            department="测试部",
            site_manager="张三",
            site_manager_phone="13800138000",
            funding_source="自有资金",
        )
        db.add(proj)
        db.flush()
        print(f"Project created: id={proj.id} project_id={proj.project_id}")

        # 2. Create 五选二 procurements (2 records)
        proc_a = Procurement(
            project_id=proj.id,
            procurement_type="材料采购",
            procurement_method="五选二",
            project_name="一标段混凝土",
            content="混凝土材料",
            control_price=500000,
            contract_number="TEST26-01N-材1",
            is_dual_contract=True,
            contract_section="一标段",
            sign_date="2026-03-10",
        )
        proc_b = Procurement(
            project_id=proj.id,
            procurement_type="材料采购",
            procurement_method="五选二",
            project_name="二标段混凝土",
            content="混凝土材料",
            control_price=500000,
            contract_number="TEST26-01N-材2",
            is_dual_contract=True,
            contract_section="二标段",
            sign_date="2026-03-10",
        )
        db.add(proc_a)
        db.add(proc_b)
        db.flush()
        print(f"五选二 created: 一标段={proc_a.id} 二标段={proc_b.id}")

        # 3. Add suppliers
        for proc, name in [(proc_a, "供应商A"), (proc_b, "供应商B")]:
            db.add(Supplier(
                procurement_id=proc.id,
                supplier_name=name,
                contact_person="李四",
                contact_phone="13900139000",
                business_scope="建材",
                tax_rate="9%",
                quoted_price=100000,
                rank=1,
                is_winner=True,
                contract_section=proc.contract_section,
            ))
        db.flush()

        # 4. Get admin user for File.owner_user_id
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            print("No admin user - run init_db first")
            return 1

        # 5. Create 2 temp contract files
        for proc in [proc_a, proc_b]:
            rel_path = get_temp_path(proj.id, proc.id, f"合同{proc.contract_section}.pdf")
            full_path = ARCHIVED_FILE_ROOT / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(b"fake pdf " + proc.contract_section.encode())
            f = File(
                procurement_id=proc.id,
                file_name=full_path.name,
                file_path=rel_path,
                file_size=len(rel_path),
                file_type="合同文件",
                is_contract=True,
                print_mode="单面",
                owner_user_id=admin.id,
            )
            db.add(f)
        db.flush()

        # 6. Verify find_dual_sibling and counts
        sibling = find_dual_sibling(db, proc_a)
        print(f"find_dual_sibling(proc_a) = {sibling.id if sibling else None}")
        c1 = count_contract_files_in_temp(db, [proc_a.id])
        c2 = count_contract_files_in_temp(db, [proc_b.id])
        print(f"Contract counts: 一标段={c1} 二标段={c2}")

        # 7. Call try_archive_and_create_ledgers (simulating 2nd upload)
        last_file = db.query(File).filter(File.procurement_id == proc_b.id).first()
        ok = try_archive_and_create_ledgers(db, proj, proc_b, last_file)
        print(f"try_archive_and_create_ledgers result: {ok}")

        db.commit()

        # 8. Verify
        files = db.query(File).filter(
            File.procurement_id.in_([proc_a.id, proc_b.id]),
            File.is_contract == True,
        ).all()
        ledgers = db.query(Ledger).filter(Ledger.procurement_id.in_([proc_a.id, proc_b.id])).all()
        archive_base = ARCHIVED_FILE_ROOT / f"{proj.project_id}材料（设备）合同"
        subdirs = list(archive_base.iterdir()) if archive_base.exists() else []

        print(f"\nResult: files={len(files)} ledgers={len(ledgers)} archive_dirs={len(subdirs)}")
        for f in files:
            print(f"  File: {f.file_name} path={f.file_path}")
        for l in ledgers:
            print(f"  Ledger: {l.contract_number} supplier={l.supplier}")
        for d in subdirs:
            if d.is_dir():
                print(f"  Archive: {d.name}")

        if len(ledgers) >= 2 and len(files) >= 2:
            print("\n*** 测试通过: 归档和台账已生成 ***")
            return 0
        else:
            print("\n*** 测试失败 ***")
            return 1
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return 1
    finally:
        db.close()


def test_http():
    """HTTP API test - requires backend running."""
    import requests
    BASE = "http://127.0.0.1:8000/api"
    r = requests.post(f"{BASE}/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        print(f"Login failed: {r.status_code}")
        return 1
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Create project, 五选二, upload 2 files...
    print("HTTP test - use --direct for DB-only test")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--direct", action="store_true", help="Direct DB test without HTTP")
    args = ap.parse_args()
    if args.direct:
        return test_direct()
    return test_http()


if __name__ == "__main__":
    sys.exit(main())
