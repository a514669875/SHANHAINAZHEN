"""测试数据种子脚本 - 用于遍历测试 ShanHaiNaZhen 采购系统全功能。"""
import sys
from pathlib import Path
from datetime import date

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.models.user import User
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.services.project_service import create_project_folders
from app.services.procurement_service import (
    create_procurement_folder,
    generate_contract_number,
    get_next_contract_seq,
)


def seed():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            raise RuntimeError("请先运行 init_db.py 创建管理员用户")

        officer_ids = str(admin.id)

        # --- 工程项目 1: 工程类 + 集团内项目 ---
        p1 = Project(
            funding_type="工程类",
            project_type="集团内项目",
            project_number="XM2024-001",
            project_id="专机26-10N",
            project_name="办公楼改造工程",
            department="工程部",
            site_manager="张三",
            site_manager_phone="13800138000",
            construction_unit="某建设公司",
            total_contract_price=5000000,
            project_duration="180天",
            funding_source="企业自筹",
            project_address="北京市朝阳区",
            procurement_officers=officer_ids,
            create_date=date.today(),
        )
        db.add(p1)
        db.flush()
        try:
            create_project_folders(p1)
        except ValueError as e:
            print(f"  项目1文件夹可能已存在: {e}")
        db.commit()
        db.refresh(p1)

        # --- 工程项目 2: 自有资金 ---
        p2 = Project(
            funding_type="自有资金",
            project_type="",
            project_number="XM2024-002",
            project_id="专机26-11N",
            project_name="设备采购项目",
            department="设备部",
            site_manager="李四",
            site_manager_phone="13900139000",
            construction_unit="自有",
            total_contract_price=800000,
            funding_source="自有资金",
            project_address="上海市",
            procurement_officers=officer_ids,
            create_date=date.today(),
        )
        db.add(p2)
        db.flush()
        try:
            create_project_folders(p2)
        except ValueError as e:
            print(f"  项目2文件夹可能已存在: {e}")
        db.commit()
        db.refresh(p2)

        # --- 采购 1: 邀请询比 (已完成) ---
        seq1 = get_next_contract_seq(db, p1.id, "材料采购")
        proc1 = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="邀请询比",
            project_name="混凝土采购",
            content="C30混凝土",
            control_price=100000,
            budget=10,
            contract_number=generate_contract_number(p1, "材料采购", seq1),
            sign_date="2024-03-01",
            is_draft=False,
            form_data="{}",
        )
        db.add(proc1)
        db.flush()
        for i, (name, price) in enumerate([("供应商A", 95000), ("供应商B", 98000), ("供应商C", 102000)], 1):
            db.add(Supplier(procurement_id=proc1.id, supplier_name=name, quoted_price=price, rank=i, is_winner=(i == 1)))
        try:
            create_procurement_folder(p1, proc1, "C30混凝土")
        except Exception:
            pass
        db.commit()
        db.refresh(proc1)

        # --- 采购 2: 单一来源 (已完成) ---
        seq2 = get_next_contract_seq(db, p1.id, "材料采购")
        proc2 = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="单一来源",
            project_name="特种钢材",
            content="特种钢材采购",
            control_price=50000,
            contract_number=generate_contract_number(p1, "材料采购", seq2),
            sign_date="2024-03-05",
            is_draft=False,
            form_data="{}",
        )
        db.add(proc2)
        db.flush()
        db.add(Supplier(procurement_id=proc2.id, supplier_name="独家供应商", quoted_price=48000, rank=1, is_winner=True))
        try:
            create_procurement_folder(p1, proc2, "特种钢材采购")
        except Exception:
            pass
        db.commit()
        db.refresh(proc2)

        # --- 采购 3: 直接采购 (草稿) ---
        proc3 = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="直接采购",
            project_name="草稿",
            content="草稿",
            control_price=30000,
            contract_number="草稿",
            is_draft=True,
            form_data="{}",
        )
        db.add(proc3)
        db.flush()
        db.add(Supplier(procurement_id=proc3.id, supplier_name="", quoted_price=0, rank=1, is_winner=True))
        try:
            create_procurement_folder(p1, proc3, "草稿", db=db)
        except Exception:
            pass
        db.commit()
        db.refresh(proc3)

        # --- 采购 4 & 5: 五选二 (一标段+二标段) ---
        seq4 = get_next_contract_seq(db, p1.id, "材料采购")
        proc4a = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="五选二",
            project_name="混凝土供应（大标）",
            content="五选二混凝土",
            control_price=200000,
            is_dual_contract=True,
            contract_section="一标段",
            contract_number=generate_contract_number(p1, "材料采购", seq4),
            sign_date="2024-03-10",
            form_data="{}",
        )
        proc4b = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="五选二",
            project_name="混凝土供应（小标）",
            content="五选二混凝土",
            control_price=200000,
            is_dual_contract=True,
            contract_section="二标段",
            contract_number=generate_contract_number(p1, "材料采购", seq4 + 1),
            sign_date="2024-03-10",
            form_data="{}",
        )
        db.add(proc4a)
        db.add(proc4b)
        db.flush()
        db.add(Supplier(procurement_id=proc4a.id, supplier_name="五选二供应商1", quoted_price=95000, rank=1, is_winner=True, contract_section="一标段"))
        db.add(Supplier(procurement_id=proc4b.id, supplier_name="五选二供应商2", quoted_price=98000, rank=1, is_winner=True, contract_section="二标段"))
        try:
            create_procurement_folder(p1, proc4a, "五选二混凝土")
        except Exception:
            pass
        db.commit()
        db.refresh(proc4a)
        db.refresh(proc4b)

        # --- 采购 6: 补充协议 (已完成, 主合同=proc1) ---
        proc6 = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="补充协议",
            parent_contract_id=proc1.id,
            project_name="混凝土采购",
            content="补充混凝土量",
            control_price=20000,
            contract_number=f"{proc1.contract_number}-补1",
            sign_date="2024-03-15",
            form_data="{}",
        )
        db.add(proc6)
        db.flush()
        db.add(Supplier(procurement_id=proc6.id, supplier_name="供应商A", quoted_price=115000, rank=1, is_winner=True))
        try:
            from app.config import PROCUREMENT_PROCESS_ROOT
            content_safe = "补充混凝土量"
            folder_name = f"{p1.project_id}-{content_safe}-补1"
            folder_path = PROCUREMENT_PROCESS_ROOT / f"{p1.project_id} {p1.project_name}" / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        db.commit()
        db.refresh(proc6)

        # --- 采购 7: 补充协议草稿 ---
        proc7 = Procurement(
            project_id=p1.id,
            procurement_type="材料采购",
            procurement_method="补充协议",
            parent_contract_id=proc1.id,
            project_name="混凝土采购",
            content="补充协议草稿内容",
            control_price=10000,
            contract_number="草稿",
            is_draft=True,
            form_data="{}",
        )
        db.add(proc7)
        db.flush()
        db.add(Supplier(procurement_id=proc7.id, supplier_name="供应商A", quoted_price=125000, rank=1, is_winner=True))
        try:
            create_procurement_folder(p1, proc7, "草稿", db=db)
        except Exception:
            pass
        db.commit()
        db.refresh(proc7)

        print("=" * 50)
        print("测试数据创建成功")
        print("=" * 50)
        print(f"  工程项目1 (工程类/集团内): id={p1.id}, project_id={p1.project_id}")
        print(f"  工程项目2 (自有资金): id={p2.id}, project_id={p2.project_id}")
        print(f"  采购项目:")
        print(f"    - 邀请询比(完成): id={proc1.id}, 合同号={proc1.contract_number}")
        print(f"    - 单一来源(完成): id={proc2.id}, 合同号={proc2.contract_number}")
        print(f"    - 直接采购(草稿): id={proc3.id}")
        print(f"    - 五选二: 一标段={proc4a.id}, 二标段={proc4b.id}")
        print(f"    - 补充协议(完成): id={proc6.id}, 合同号={proc6.contract_number}")
        print(f"    - 补充协议(草稿): id={proc7.id}")
        print("=" * 50)
    finally:
        db.close()


if __name__ == "__main__":
    seed()
