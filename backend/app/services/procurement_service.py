"""Procurement service - contract number, ledger, folder creation."""
import shutil
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.ledger import Ledger
from app.models.supplier import Supplier
from app.models.file import File
from app.config import PROCUREMENT_PROCESS_ROOT, ARCHIVED_FILE_ROOT
from pathlib import Path

# 合同编号规则：材料采购 材X，设备采购 设备X，机械租赁 机械X（PRD 8.3）
PROC_TYPE_CODE = {"材料采购": "材", "设备采购": "设备", "机械租赁": "机械"}


def get_next_contract_seq(db: Session, project_id: int, proc_type: str) -> int:
    """Get next contract sequence for project + procurement type."""
    code = PROC_TYPE_CODE.get(proc_type, "材")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return 1
    prefix = f"{project.project_id}-{code}"
    procs = db.query(Procurement).filter(Procurement.project_id == project_id).all()
    max_seq = 0
    for p in procs:
        if p.contract_number and p.contract_number.startswith(prefix):
            try:
                rest = p.contract_number[len(prefix):]
                if rest.isdigit():
                    max_seq = max(max_seq, int(rest))
                elif rest.startswith("-补"):
                    num = rest[2:].split("-")[0]
                    if num.isdigit():
                        max_seq = max(max_seq, int(num))
            except Exception:
                pass
    return max_seq + 1


def generate_contract_number(project: Project, proc_type: str, seq: int, supplement_seq: int = None) -> str:
    """Generate contract number: 专机26-10N-材1 / 专机26-10N-设备1 / 专机26-10N-机械1."""
    code = PROC_TYPE_CODE.get(proc_type, "材")
    base = f"{project.project_id}-{code}{seq}"
    if supplement_seq is not None and supplement_seq > 0:
        return f"{base}-补{supplement_seq}"
    return base


_USE_PROC_CONTROL = object()


def create_ledger_record(
    db: Session,
    project: Project,
    procurement: Procurement,
    supplier_name: str,
    contract_price: float,
    sign_date: str,
    parent_contract_number: str = None,
    control_price_override: object = _USE_PROC_CONTROL,
) -> Ledger:
    """Create ledger record from procurement. 录入时间自动填入计算机系统时间。
    补充协议时传入 control_price_override 为 form_data 的 supplement_control_price（可 None 显示为 /）。"""
    ctrl_price = procurement.control_price if control_price_override is _USE_PROC_CONTROL else control_price_override
    ledger = Ledger(
        project_id=project.id,
        procurement_id=procurement.id,
        group_type=project.project_type,
        procurement_method=procurement.procurement_method,
        department=project.department,
        project_number=project.project_number,
        contract_number=procurement.contract_number,
        project_name=project.project_name,
        procurement_name=procurement.project_name,
        supplier=supplier_name,
        contract_price=contract_price,
        sign_date=sign_date,
        content=procurement.content,
        control_price=ctrl_price,
        funding_source=project.funding_source,
        officer=project.procurement_officers,
        funding_type=project.funding_type,
        parent_contract_number=parent_contract_number or "",
        create_time=datetime.now(),
    )
    db.add(ledger)
    return ledger


PROCUREMENT_ID_FILE = ".procurement_id"


def get_next_draft_seq(db: Session, project_id: int) -> int:
    """获取该项目下暂存采购项目的下一个草稿序号 X，用于 工程编号-草稿X 命名。X 从 1 递增。"""
    count = db.query(Procurement).filter(
        Procurement.project_id == project_id,
        Procurement.is_draft == True,
    ).count()
    return count + 1


def get_process_folder_for_procurement(project: Project, proc: "Procurement", db: Optional[Session] = None) -> Path:
    """获取采购项目的流程文件专属文件夹路径。草稿使用 草稿X（通过 .procurement_id 定位）。五选二补充协议: 工程编号-采购内容-标段名-补X。"""
    base = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    if proc.is_draft or (proc.contract_number or "") == "草稿":
        folder = _find_draft_folder_for_procurement(project, proc.id)
        return folder if folder else base / f"{project.project_id}-草稿"
    if proc.parent_contract_id and proc.contract_number and "-补" in proc.contract_number:
        content_safe = (proc.content or "").strip() or "补充协议"
        parts = proc.contract_number.split("-补")
        supp_seq = parts[-1].split("-")[0] if len(parts) >= 2 else "1"
        # 五选二补充协议: 工程编号-采购内容-标段名-补X
        if db:
            parent = db.query(Procurement).filter(Procurement.id == proc.parent_contract_id).first()
            if parent and parent.procurement_method == "五选二" and parent.contract_section:
                return base / f"{project.project_id}-{content_safe}-{parent.contract_section}-补{supp_seq}"
        return base / f"{project.project_id}-{content_safe}-补{supp_seq}"
    content = (proc.content or proc.project_name or "").strip()
    folder_name = f"{project.project_id}-{content}" if content else f"{project.project_id}-{proc.project_name}"
    return base / folder_name


def _find_draft_folder_for_procurement(project: Project, procurement_id: int) -> Path | None:
    """根据 procurement_id 查找对应的草稿文件夹（扫描 草稿1、草稿2... 中的 .procurement_id 标记）。"""
    base = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    if not base.exists():
        return None
    target_id = str(procurement_id)
    for p in sorted(base.iterdir()):
        if p.is_dir() and p.name.startswith(f"{project.project_id}-草稿"):
            marker = p / PROCUREMENT_ID_FILE
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == target_id:
                return p
    return None


def create_procurement_folder(project: Project, procurement: Procurement, content: str = "", db: Session = None) -> Path:
    """Create procurement folder: 工程编号-采购内容；暂存时为 工程编号-草稿X（X 从 1 递增）。"""
    base_path = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    if (procurement.is_draft or (procurement.contract_number or "") == "草稿") and db is not None:
        seq = get_next_draft_seq(db, project.id)
        folder_name = f"{project.project_id}-草稿{seq}"
    else:
        folder_name = f"{project.project_id}-{content}" if content else f"{project.project_id}-{procurement.project_name}"
    path = base_path / folder_name
    path.mkdir(parents=True, exist_ok=True)
    if (procurement.is_draft or (procurement.contract_number or "") == "草稿") and db is not None:
        (path / PROCUREMENT_ID_FILE).write_text(str(procurement.id), encoding="utf-8")
    return path


def delete_procurement_resources(db: Session, project: Project, procurement: Procurement) -> None:
    """Delete procurement folders, physical files, ledgers per PRD 4.3."""
    # 1. Delete process folder (采购项目专属文件夹 / 补充协议专属文件夹)
    base_process = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    if procurement.parent_contract_id and procurement.contract_number and "-补" in procurement.contract_number:
        content_safe = (procurement.content or "").strip() or "补充协议"
        parts = procurement.contract_number.split("-补")
        if len(parts) >= 2 and parts[-1].split("-")[0].isdigit():
            supp_seq = int(parts[-1].split("-")[0])
            parent = db.query(Procurement).filter(Procurement.id == procurement.parent_contract_id).first()
            if parent and parent.procurement_method == "五选二" and parent.contract_section:
                folder_name = f"{project.project_id}-{content_safe}-{parent.contract_section}-补{supp_seq}"
            else:
                folder_name = f"{project.project_id}-{content_safe}-补{supp_seq}"
            process_folder = base_process / folder_name
            if process_folder.exists():
                shutil.rmtree(process_folder)
    else:
        # 暂存草稿：工程编号-草稿X（X 从 1 递增），通过 .procurement_id 标记定位（PRD 8.15）
        if procurement.is_draft or (procurement.contract_number or "") == "草稿":
            draft_folder = _find_draft_folder_for_procurement(project, procurement.id)
            if draft_folder and draft_folder.exists():
                shutil.rmtree(draft_folder)
        else:
            content = (procurement.content or procurement.project_name or "").strip()
            folder_name = f"{project.project_id}-{content}" if content else f"{project.project_id}-{procurement.project_name}"
            process_folder = base_process / folder_name
            if process_folder.exists():
                shutil.rmtree(process_folder)

    # 2. Delete physical files from disk
    files = db.query(File).filter(File.procurement_id == procurement.id).all()
    for f in files:
        full_path = ARCHIVED_FILE_ROOT / f.file_path
        if full_path.exists():
            full_path.unlink()

    # 3. Delete archive subfolder if it's only for this procurement (常规/补充协议)
    archive_base = ARCHIVED_FILE_ROOT / f"{project.project_id}材料（设备）合同"
    is_dual = procurement.is_dual_contract or procurement.procurement_method == "五选二"
    if not is_dual and procurement.contract_number:
        archive_sub = archive_base / procurement.contract_number
        if archive_sub.exists():
            shutil.rmtree(archive_sub)
    elif is_dual:
        from app.services.archive_service import find_dual_sibling
        sibling = find_dual_sibling(db, procurement)
        if not sibling:  # Deleting last of pair - remove shared archive folder
            suffix = procurement.contract_number.split("-")[-1] if procurement.contract_number else ""
            for code in ["材", "设备", "机械"]:
                if suffix and suffix.startswith(code) and suffix[len(code):].isdigit():
                    try:
                        num = int(suffix[len(code):])
                        contract_folder = f"{project.project_id}-{suffix}、{code}{num + 1}"
                        archive_sub = archive_base / contract_folder
                        if not archive_sub.exists():
                            contract_folder = f"{project.project_id}-{code}{num - 1}、{suffix}"
                            archive_sub = archive_base / contract_folder
                        if archive_sub.exists():
                            shutil.rmtree(archive_sub)
                    except (ValueError, IndexError):
                        pass
                    break

    # 4. If this is a supplement, remove it from parent ledger's supplement_contracts (PRD 8.11)
    if procurement.parent_contract_id and procurement.contract_number:
        parent_ledger = db.query(Ledger).filter(
            Ledger.procurement_id == procurement.parent_contract_id,
        ).first()
        if parent_ledger and parent_ledger.supplement_contracts:
            lines = [x.strip() for x in parent_ledger.supplement_contracts.split("\n") if x.strip()]
            lines = [x for x in lines if x != procurement.contract_number.strip()]
            parent_ledger.supplement_contracts = "\n".join(lines) if lines else ""

    # 5. Delete ledgers for this procurement
    db.query(Ledger).filter(Ledger.procurement_id == procurement.id).delete()


def sync_ledgers_on_project_update(
    db: Session, project: Project, old_project_id: str | None = None
) -> None:
    """Sync all ledger records for this project when project info changes (PRD 8.9).
    当工程编号变更时，同步更新 Procurement.contract_number 及 Ledger.contract_number。"""
    new_id = project.project_id or ""
    if old_project_id and old_project_id != new_id:
        prefix_old = f"{old_project_id}-"
        prefix_new = f"{new_id}-"
        for p in db.query(Procurement).filter(Procurement.project_id == project.id).all():
            if p.contract_number and p.contract_number.startswith(prefix_old):
                p.contract_number = prefix_new + p.contract_number[len(prefix_old) :]
        for l in db.query(Ledger).filter(Ledger.project_id == project.id).all():
            if l.contract_number and l.contract_number.startswith(prefix_old):
                l.contract_number = prefix_new + l.contract_number[len(prefix_old) :]
            if l.parent_contract_number and l.parent_contract_number.startswith(prefix_old):
                l.parent_contract_number = prefix_new + l.parent_contract_number[len(prefix_old) :]
            if l.supplement_contracts:
                lines = []
                for line in l.supplement_contracts.split("\n"):
                    line = line.strip()
                    if line and line.startswith(prefix_old):
                        line = prefix_new + line[len(prefix_old) :]
                    lines.append(line)
                l.supplement_contracts = "\n".join(lines)
    ledgers = db.query(Ledger).filter(Ledger.project_id == project.id).all()
    for l in ledgers:
        l.group_type = project.project_type
        l.department = project.department
        l.project_number = project.project_number
        l.project_name = project.project_name
        l.funding_source = project.funding_source
        l.officer = project.procurement_officers
        l.funding_type = project.funding_type


def _parse_form_data(form_data: str) -> dict:
    """Parse form_data JSON or Python repr to dict."""
    if not form_data:
        return {}
    try:
        import json
        return json.loads(form_data)
    except (json.JSONDecodeError, TypeError):
        try:
            import ast
            return ast.literal_eval(form_data) if form_data else {}
        except Exception:
            return {}


def _suppliers_sorted_by_price(suppliers: list) -> list:
    """按报价升序排序，None 视为极大值，确保编辑后排名变化时取对供应商。"""
    return sorted(
        suppliers,
        key=lambda s: (float(s.quoted_price) if s.quoted_price is not None and s.quoted_price != "" else float("inf")),
    )


def sync_ledgers_on_procurement_update(db: Session, procurement: Procurement) -> None:
    """Sync all ledger records for this procurement when procurement info changes (PRD 8.9).
    五选二：一标段取排序第1名+成交金额1，二标段取排序第2名+成交金额2；其他方式取排序第1名+报价。"""
    project = db.query(Project).filter(Project.id == procurement.project_id).first()
    if not project:
        return
    suppliers = db.query(Supplier).filter(Supplier.procurement_id == procurement.id).all()
    sorted_suppliers = _suppliers_sorted_by_price(suppliers)
    supplier_name = ""
    contract_price = 0.0
    if procurement.procurement_method == "补充协议":
        contract_price = float(procurement.control_price or 0)
        if procurement.parent_contract_id:
            parent_suppliers = db.query(Supplier).filter(
                Supplier.procurement_id == procurement.parent_contract_id
            ).all()
            parent = db.query(Procurement).filter(Procurement.id == procurement.parent_contract_id).first()
            if parent_suppliers and parent:
                psorted = _suppliers_sorted_by_price(parent_suppliers)
                rank_idx = 1 if parent.procurement_method == "五选二" and parent.contract_section == "二标段" else 0
                if rank_idx < len(psorted):
                    supplier_name = psorted[rank_idx].supplier_name or ""
            if not supplier_name and suppliers:
                supplier_name = suppliers[0].supplier_name or ""
    elif procurement.procurement_method == "五选二":
        fd = _parse_form_data(procurement.form_data or "")
        if procurement.contract_section == "一标段":
            rank_idx = 0
            cp = fd.get("chengjiao_jine1")
        else:
            rank_idx = 1
            cp = fd.get("chengjiao_jine2")
        if rank_idx < len(sorted_suppliers):
            supplier_name = sorted_suppliers[rank_idx].supplier_name or ""
        if cp is None or cp == "":
            contract_price = float(sorted_suppliers[rank_idx].quoted_price) if rank_idx < len(sorted_suppliers) and sorted_suppliers[rank_idx].quoted_price is not None else 0.0
        else:
            contract_price = float(cp)
    else:
        if sorted_suppliers:
            supplier_name = sorted_suppliers[0].supplier_name or ""
            qp = sorted_suppliers[0].quoted_price
            contract_price = float(qp) if qp is not None and qp != "" else 0.0
    # 补充协议控制价用 form_data.supplement_control_price，非新增金额；其他用 proc.control_price；null 显示为 "/"
    if procurement.procurement_method == "补充协议":
        fd = _parse_form_data(procurement.form_data or "")
        supp_ctrl = fd.get("supplement_control_price")
        ledger_control_price = float(supp_ctrl) if supp_ctrl is not None and supp_ctrl != "" else None
    else:
        ledger_control_price = procurement.control_price
    ledgers = db.query(Ledger).filter(Ledger.procurement_id == procurement.id).all()
    for l in ledgers:
        l.procurement_method = procurement.procurement_method
        l.procurement_name = procurement.project_name
        l.content = procurement.content
        l.control_price = ledger_control_price
        l.supplier = supplier_name
        l.contract_price = contract_price
        l.sign_date = procurement.sign_date or ""


def rename_procurement_folders(
    project: Project,
    procurement: Procurement,
    old_content: str,
    old_project_name: str,
    old_contract_number: str,
    db: Optional[Session] = None,
) -> None:
    """Rename procurement folders when content/project_name/contract_number changes."""
    base_process = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    base_archive = ARCHIVED_FILE_ROOT / f"{project.project_id}材料（设备）合同"
    new_content = (procurement.content or procurement.project_name or "").strip()
    # 五选二：流程文件夹为 工程编号-采购内容，内容变更时需重命名
    if procurement.is_dual_contract or (procurement.procurement_method == "五选二" and procurement.contract_section):
        old_folder = base_process / (f"{project.project_id}-{old_content}" if old_content else f"{project.project_id}-{old_project_name}")
        new_folder = base_process / (f"{project.project_id}-{new_content}" if new_content else f"{project.project_id}-{procurement.project_name}")
        if old_folder.exists() and old_folder != new_folder:
            new_folder.parent.mkdir(parents=True, exist_ok=True)
            old_folder.rename(new_folder)
        return
    # Process folder (常规/补充协议)
    if not procurement.is_dual_contract:
        # 草稿完成：old 工程编号-草稿X -> new 工程编号-内容 或 工程编号-内容-补X（PRD 8.15）
        if (old_contract_number or "") == "草稿" and procurement.contract_number:
            old_folder = _find_draft_folder_for_procurement(project, procurement.id)
            if old_folder and old_folder.exists():
                if procurement.parent_contract_id and "-补" in procurement.contract_number:
                    content_safe = (procurement.content or "").strip() or "补充协议"
                    parts = procurement.contract_number.split("-补")
                    supp_seq = parts[-1].split("-")[0] if len(parts) >= 2 else "1"
                    if db:
                        parent = db.query(Procurement).filter(Procurement.id == procurement.parent_contract_id).first()
                        if parent and parent.procurement_method == "五选二" and parent.contract_section:
                            new_folder = base_process / f"{project.project_id}-{content_safe}-{parent.contract_section}-补{supp_seq}"
                        else:
                            new_folder = base_process / f"{project.project_id}-{content_safe}-补{supp_seq}"
                    else:
                        new_folder = base_process / f"{project.project_id}-{content_safe}-补{supp_seq}"
                else:
                    new_content = (procurement.content or procurement.project_name or "").strip()
                    new_folder = base_process / (f"{project.project_id}-{new_content}" if new_content else f"{project.project_id}-{procurement.project_name}")
                if old_folder != new_folder:
                    new_folder.parent.mkdir(parents=True, exist_ok=True)
                    old_folder.rename(new_folder)
            return  # 草稿完成时 archive 子文件夹在归档时创建，此处无需处理
        else:
            old_folder = base_process / (f"{project.project_id}-{old_content}" if old_content else f"{project.project_id}-{old_project_name}")
            new_content = (procurement.content or procurement.project_name or "").strip()
            new_folder = base_process / (f"{project.project_id}-{new_content}" if new_content else f"{project.project_id}-{procurement.project_name}")
        if old_folder.exists() and old_folder != new_folder:
            new_folder.parent.mkdir(parents=True, exist_ok=True)
            old_folder.rename(new_folder)
    # Archive subfolder (常规/补充协议)
    if not procurement.is_dual_contract and old_contract_number and procurement.contract_number:
        old_archive_sub = base_archive / old_contract_number
        new_archive_sub = base_archive / procurement.contract_number
        if old_archive_sub.exists() and old_archive_sub != new_archive_sub:
            old_archive_sub.rename(new_archive_sub)
