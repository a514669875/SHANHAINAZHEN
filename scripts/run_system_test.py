"""系统全功能遍历测试 - 检测数据不同步、BUG、缺失功能。"""
import sys
import os
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))
os.chdir(str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Project, Procurement, Supplier, Ledger, File
from app.config import PROCUREMENT_PROCESS_ROOT, ARCHIVED_FILE_ROOT
from app.services.procurement_service import delete_procurement_resources, _find_draft_folder_for_procurement, get_next_draft_seq


def count_files_in_folder(path: Path) -> int:
    if not path.exists():
        return -1
    return sum(1 for _ in path.iterdir())


def test_project_folder_sync(db):
    """检查项目与文件夹同步"""
    issues = []
    for p in db.query(Project).all():
        process_name = f"{p.project_id} {p.project_name}"
        archive_name = f"{p.project_id}材料（设备）合同"
        process_path = PROCUREMENT_PROCESS_ROOT / process_name
        archive_path = ARCHIVED_FILE_ROOT / archive_name
        if not process_path.exists():
            issues.append(f"[P1] 项目 {p.id} 缺少流程文件夹: {process_name}")
        if not archive_path.exists():
            issues.append(f"[P2] 项目 {p.id} 缺少归档文件夹: {archive_name}")
    return issues


def test_procurement_folder_sync(db):
    """检查采购项目与专属文件夹同步"""
    issues = []
    for proc in db.query(Procurement).filter(Procurement.project_id != None).all():
        project = db.query(Project).filter(Project.id == proc.project_id).first()
        if not project:
            continue
        base = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
        if not base.exists():
            continue

        folder_found = False
        if proc.is_draft or (proc.contract_number or "") == "草稿":
            draft_folder = _find_draft_folder_for_procurement(project, proc.id)
            if draft_folder and draft_folder.exists():
                folder_found = True
            elif not proc.parent_contract_id:
                issues.append(f"[PR1] 草稿采购 {proc.id} 未找到专属文件夹 (工程编号-草稿X)")
        elif proc.parent_contract_id and proc.contract_number and "-补" in proc.contract_number:
            content_safe = (proc.content or "").strip() or "补充协议"
            parts = proc.contract_number.split("-补")
            if len(parts) >= 2 and parts[-1].split("-")[0].isdigit():
                supp_seq = parts[-1].split("-")[0]
                folder_name = f"{project.project_id}-{content_safe}-补{supp_seq}"
                if (base / folder_name).exists():
                    folder_found = True
            if not folder_found:
                issues.append(f"[PR2] 补充协议 {proc.id} 未找到专属文件夹")
        elif proc.is_dual_contract:
            content = (proc.content or proc.project_name or "").strip()
            folder_name = f"{project.project_id}-{content}" if content else f"{project.project_id}-{proc.project_name}"
            if (base / folder_name).exists():
                folder_found = True
            if not folder_found:
                issues.append(f"[PR3] 五选二采购 {proc.id} 可能缺少流程文件夹")
        else:
            content = (proc.content or proc.project_name or "").strip()
            folder_name = f"{project.project_id}-{content}" if content else f"{project.project_id}-{proc.project_name}"
            if (base / folder_name).exists():
                folder_found = True
            if not folder_found:
                issues.append(f"[PR4] 采购 {proc.id} ({proc.contract_number}) 未找到专属文件夹: {folder_name}")

    return issues


def test_ledger_consistency(db):
    """检查台账与采购主从关系"""
    issues = []
    for ledger in db.query(Ledger).all():
        if ledger.parent_contract_number:
            parent = db.query(Procurement).filter(
                Procurement.contract_number == ledger.parent_contract_number
            ).first()
            if not parent:
                issues.append(f"[L1] 台账 {ledger.id} 关联主合同 {ledger.parent_contract_number} 不存在")
        if ledger.supplement_contracts:
            for cn in ledger.supplement_contracts.split("\n"):
                cn = cn.strip()
                if not cn:
                    continue
                supp = db.query(Procurement).filter(Procurement.contract_number == cn).first()
                if not supp:
                    issues.append(f"[L2] 台账 {ledger.id} 补充协议 {cn} 已删除但未同步")
    return issues


def test_orphan_files(db):
    """检查孤立的 File 记录"""
    issues = []
    for f in db.query(File).all():
        proc = db.query(Procurement).filter(Procurement.id == f.procurement_id).first()
        if not proc:
            issues.append(f"[F1] 文件 {f.id} 关联的采购 {f.procurement_id} 不存在")
    return issues


def main():
    db = SessionLocal()
    all_issues = []

    try:
        print("=" * 60)
        print("ShanHaiNaZhen 系统全功能遍历测试")
        print("=" * 60)

        all_issues.extend(test_project_folder_sync(db))
        all_issues.extend(test_procurement_folder_sync(db))
        all_issues.extend(test_ledger_consistency(db))
        all_issues.extend(test_orphan_files(db))

        # 统计
        projs = db.query(Project).count()
        procs = db.query(Procurement).count()
        ledgers = db.query(Ledger).count()
        print(f"\n数据统计: 项目={projs}, 采购={procs}, 台账={ledgers}")

        if all_issues:
            print(f"\n发现 {len(all_issues)} 个问题:")
            for i in all_issues:
                print(f"  - {i}")
        else:
            print("\n未发现数据不同步问题。")
        print("=" * 60)
        return all_issues
    finally:
        db.close()


if __name__ == "__main__":
    main()
