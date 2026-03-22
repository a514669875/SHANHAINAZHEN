"""Archive service - temp storage, folder creation, ledger generation on archive."""
import json
import re
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.file import File
from app.models.ledger import Ledger
from app.models.supplier import Supplier
from app.config import ARCHIVED_FILE_ROOT
from app.services.procurement_service import (
    create_ledger_record,
    sync_ledgers_on_procurement_update,
    get_next_contract_seq,
    generate_contract_number,
)


def _parse_form_data(form_data: str) -> dict:
    """Parse form_data JSON or Python repr to dict."""
    if not form_data:
        return {}
    try:
        return json.loads(form_data)
    except (json.JSONDecodeError, TypeError):
        try:
            import ast
            return ast.literal_eval(form_data) if form_data else {}
        except Exception:
            return {}

TEMP_PREFIX = "_temp"


def cleanup_empty_temp_dirs() -> None:
    """清理 _temp 下的空目录。归档后定期调用。"""
    temp_root = ARCHIVED_FILE_ROOT / TEMP_PREFIX
    if not temp_root.exists():
        return
    for project_dir in list(temp_root.iterdir()):
        if not project_dir.is_dir():
            continue
        for proc_dir in list(project_dir.iterdir()):
            if proc_dir.is_dir() and not any(proc_dir.iterdir()):
                try:
                    proc_dir.rmdir()
                except OSError:
                    pass
        if project_dir.is_dir() and not any(project_dir.iterdir()):
            try:
                project_dir.rmdir()
            except OSError:
                pass


def get_temp_path(project_id: int, procurement_id: int, filename: str) -> str:
    """Get relative path for temp storage: _temp/{project_id}/{procurement_id}/{filename}."""
    return f"{TEMP_PREFIX}/{project_id}/{procurement_id}/{filename}"


def get_archive_contract_folder(project: Project, proc: Procurement, sibling: Procurement = None) -> str:
    """
    Get archive contract folder name per PRD 3.4.
    - 常规: 合同编号 (e.g. 专机26-01N-材1)
    - 五选二: 工程编号-材X、材X+1 (e.g. 专机26-01N-材3、材4)
    - 补充协议: 合同编号 (e.g. 专机26-01N-材1-补1)
    """
    if sibling:
        a, b = (proc, sibling) if proc.contract_section == "一标段" else (sibling, proc)
        suffix_a = a.contract_number.split("-")[-1] if a.contract_number else ""
        suffix_b = b.contract_number.split("-")[-1] if b.contract_number else ""
        return f"{project.project_id}-{suffix_a}、{suffix_b}"
    return proc.contract_number or ""


def find_dual_sibling(db: Session, proc: Procurement) -> Procurement | None:
    """Find the sibling procurement for 五选二 pair.

    优先规则：
    1) 反向标段 + 合同号序号相邻（材X/设备X/机械X 的 X±1）
    2) 反向标段 + 创建时间最接近
    3) 任意候选 + 创建时间最接近（历史脏数据兜底）
    """
    if proc.procurement_method != "五选二":
        return None

    candidates = db.query(Procurement).filter(
        Procurement.project_id == proc.project_id,
        Procurement.procurement_method == "五选二",
        Procurement.id != proc.id,
    ).all()
    if not candidates:
        return None

    def _closest_by_create_time(rows: list[Procurement]) -> Procurement | None:
        if not rows:
            return None
        p_ct = getattr(proc, "create_time", None)
        if p_ct is None:
            return min(rows, key=lambda x: abs((x.id or 0) - (proc.id or 0)))
        scored = []
        for r in rows:
            r_ct = getattr(r, "create_time", None)
            if r_ct is None:
                score = float("inf")
            else:
                try:
                    score = abs((r_ct - p_ct).total_seconds())
                except Exception:
                    score = float("inf")
            scored.append((score, abs((r.id or 0) - (proc.id or 0)), r))
        scored.sort(key=lambda t: (t[0], t[1]))
        return scored[0][2]

    def _contract_seq_info(contract_number: str | None) -> tuple[str, int] | None:
        if not contract_number:
            return None
        m = re.match(r"^(.*?-)(材|设备|机械)(\d+)$", str(contract_number).strip())
        if not m:
            return None
        stem = f"{m.group(1)}{m.group(2)}"
        return stem, int(m.group(3))

    opposite_section = None
    if proc.contract_section == "一标段":
        opposite_section = "二标段"
    elif proc.contract_section == "二标段":
        opposite_section = "一标段"

    section_candidates = candidates
    if opposite_section:
        sec_filtered = [c for c in candidates if (c.contract_section or "") == opposite_section]
        if sec_filtered:
            section_candidates = sec_filtered

    proc_seq = _contract_seq_info(getattr(proc, "contract_number", None))
    if proc_seq and opposite_section:
        stem, n = proc_seq
        expect_n = n + 1 if proc.contract_section == "一标段" else n - 1
        for c in section_candidates:
            ci = _contract_seq_info(getattr(c, "contract_number", None))
            if ci and ci[0] == stem and ci[1] == expect_n:
                return c

    return _closest_by_create_time(section_candidates) or _closest_by_create_time(candidates)


def _parse_main_contract_seq(contract_number: str | None) -> int | None:
    if not contract_number:
        return None
    m = re.match(r"^.*-(材|设备|机械)(\d+)$", str(contract_number).strip())
    if not m:
        return None
    try:
        return int(m.group(2))
    except (TypeError, ValueError):
        return None


def _ensure_main_contract_number(db: Session, project: Project, proc: Procurement) -> None:
    """主合同编号在首次归档时分配；避免创建采购时抢号。"""
    if (proc.contract_number or "").strip():
        return
    seq = get_next_contract_seq(db, project.id, proc.procurement_type)
    while True:
        cn = generate_contract_number(project, proc.procurement_type, seq)
        exists = db.query(Procurement).filter(
            Procurement.project_id == project.id,
            Procurement.contract_number == cn,
            Procurement.id != proc.id,
        ).first()
        if not exists:
            proc.contract_number = cn
            return
        seq += 1


def _ensure_dual_contract_numbers(db: Session, project: Project, proc: Procurement, sibling: Procurement) -> None:
    """五选二在归档时一次性分配连号（按一标段/二标段）。"""
    first, second = (proc, sibling) if proc.contract_section == "一标段" else (sibling, proc)
    first_has = bool((first.contract_number or "").strip())
    second_has = bool((second.contract_number or "").strip())
    if first_has and second_has:
        return
    if not first_has and not second_has:
        seq = get_next_contract_seq(db, project.id, first.procurement_type)
        first.contract_number = generate_contract_number(project, first.procurement_type, seq)
        second.contract_number = generate_contract_number(project, second.procurement_type, seq + 1)
        return
    if first_has and not second_has:
        s = _parse_main_contract_seq(first.contract_number)
        if s is not None:
            second.contract_number = generate_contract_number(project, second.procurement_type, s + 1)
            return
        _ensure_main_contract_number(db, project, second)
        return
    if second_has and not first_has:
        s = _parse_main_contract_seq(second.contract_number)
        if s is not None and s > 1:
            first.contract_number = generate_contract_number(project, first.procurement_type, s - 1)
            return
        _ensure_main_contract_number(db, project, first)


def _ensure_supplement_contract_number(db: Session, proc: Procurement) -> None:
    """补充协议编号在归档时分配：主合同号-补X（按已有补充协议号递增，不回收）。"""
    if (proc.contract_number or "").strip():
        return
    if not proc.parent_contract_id:
        return
    parent = db.query(Procurement).filter(Procurement.id == proc.parent_contract_id).first()
    if not parent or not (parent.contract_number or "").strip():
        return
    base = f"{parent.contract_number}-补"
    rows = db.query(Procurement).filter(
        Procurement.parent_contract_id == proc.parent_contract_id,
        Procurement.id != proc.id,
        Procurement.contract_number.isnot(None),
        Procurement.contract_number.like(f"{base}%"),
    ).all()
    max_seq = 0
    for r in rows:
        cn = (r.contract_number or "").strip()
        if not cn.startswith(base):
            continue
        tail = cn[len(base):]
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    proc.contract_number = f"{base}{max_seq + 1}"


def count_contract_files_in_temp(db: Session, procurement_ids: list[int]) -> int:
    """Count contract files in _temp for given procurements."""
    return db.query(File).filter(
        File.procurement_id.in_(procurement_ids),
        File.is_contract == True,
        File.file_path.like(f"{TEMP_PREFIX}/%"),
    ).count()


def count_contract_files(db: Session, procurement_ids: list[int]) -> int:
    """Count all contract files for given procurements (temp or archived)."""
    return db.query(File).filter(
        File.procurement_id.in_(procurement_ids),
        File.is_contract == True,
    ).count()


def try_archive_and_create_ledgers(
    db: Session,
    project: Project,
    proc: Procurement,
    current_file: File,
) -> bool:
    """
    When is_contract, check if 台账生成条件满足. If so:
    1. Create archive folder
    2. Move all temp files for this procurement(s) to archive folder
    3. Update File records
    4. Create ledger(s)
    Returns True if archive was performed.
    """
    is_dual = proc.procurement_method == "五选二"
    if is_dual:
        sibling = find_dual_sibling(db, proc)
        if not sibling:
            return False
        proc_ids = [proc.id, sibling.id]
        required = 2
        # 五选二需一标段、二标段各至少1份合同
        count_per_proc = [
            count_contract_files_in_temp(db, [pid]) for pid in proc_ids
        ]
        if any(c < 1 for c in count_per_proc):
            return False
    else:
        proc_ids = [proc.id]
        required = 1

    count = count_contract_files_in_temp(db, proc_ids)
    if count < required:
        return False

    # 合同编号在归档成功时分配（非创建采购时）
    if is_dual and sibling:
        _ensure_dual_contract_numbers(db, project, proc, sibling)
    elif proc.procurement_method == "补充协议":
        _ensure_supplement_contract_number(db, proc)
    else:
        _ensure_main_contract_number(db, project, proc)
    if is_dual and sibling:
        a, b = (proc, sibling) if proc.contract_section == "一标段" else (sibling, proc)
        if not (a.contract_number or "").strip() or not (b.contract_number or "").strip():
            return False
    else:
        if not (proc.contract_number or "").strip():
            return False

    # Build archive folder path
    archive_base = f"{project.project_id}材料（设备）合同"
    if is_dual and sibling:
        contract_folder = get_archive_contract_folder(project, proc, sibling)
    else:
        contract_folder = proc.contract_number or ""

    archive_rel = f"{archive_base}/{contract_folder}"
    archive_full = ARCHIVED_FILE_ROOT / archive_rel
    archive_full.mkdir(parents=True, exist_ok=True)

    # Move all temp files for these procurements to archive
    temp_files = db.query(File).filter(
        File.procurement_id.in_(proc_ids),
        File.file_path.like(f"{TEMP_PREFIX}/%"),
    ).all()

    for f in temp_files:
        src = ARCHIVED_FILE_ROOT / f.file_path
        if src.exists():
            dst = archive_full / f.file_name
            dst.write_bytes(src.read_bytes())
            src.unlink()
        # Update file_path to final archive path
        f.file_path = f"{archive_rel}/{f.file_name}"

    # Create ledgers and set pdf_preview_path (一标段先、二标段后)
    if is_dual and sibling:
        p_first, p_second = (proc, sibling) if proc.contract_section == "一标段" else (sibling, proc)
        fd = _parse_form_data(p_first.form_data or "")
        cj1 = fd.get("chengjiao_jine1")
        cj2 = fd.get("chengjiao_jine2")
        for p, sect, cp_val in [(p_first, "一标段", cj1), (p_second, "二标段", cj2)]:
            existing = db.query(Ledger).filter(Ledger.procurement_id == p.id).first()
            if existing:
                pass
            else:
                supps = db.query(Supplier).filter(Supplier.procurement_id == p.id).all()
                sorted_supps = sorted(
                    supps,
                    key=lambda s: (float(s.quoted_price) if s.quoted_price is not None and s.quoted_price != "" else float("inf")),
                )
                rank_idx = 0 if sect == "一标段" else 1
                if rank_idx < len(sorted_supps):
                    winner = sorted_supps[rank_idx]
                    cp = cp_val
                    if cp is None or cp == "":
                        cp = winner.quoted_price or 0
                    else:
                        cp = float(cp)
                    create_ledger_record(db, project, p, winner.supplier_name, cp, p.sign_date or "")
        db.flush()
        for p in [proc, sibling]:
            f_for_proc = next((x for x in temp_files if x.procurement_id == p.id and x.is_contract), None)
            if f_for_proc:
                ledger = db.query(Ledger).filter(Ledger.procurement_id == p.id).first()
                if ledger:
                    ledger.pdf_preview_path = f"/api/files/{f_for_proc.id}/content"
    else:
        existing = db.query(Ledger).filter(Ledger.procurement_id == proc.id).first()
        if not existing:
            winner = db.query(Supplier).filter(Supplier.procurement_id == proc.id).order_by(Supplier.rank).first()
            if winner:
                parent_num = None
                if proc.parent_contract_id:
                    parent = db.query(Procurement).filter(Procurement.id == proc.parent_contract_id).first()
                    parent_num = parent.contract_number if parent else None
                # 补充协议合同价=新增金额；控制价用 form_data.supplement_control_price（非新增金额）
                if proc.procurement_method == "补充协议":
                    contract_price = float(proc.control_price or 0)
                    fd = _parse_form_data(proc.form_data or "")
                    supp_ctrl = fd.get("supplement_control_price")
                    supp_ctrl_val = float(supp_ctrl) if supp_ctrl is not None and supp_ctrl != "" else None
                    create_ledger_record(db, project, proc, winner.supplier_name or "", contract_price, proc.sign_date or "", parent_num, control_price_override=supp_ctrl_val)
                else:
                    qp = winner.quoted_price
                    contract_price = float(qp) if qp is not None and qp != "" else 0.0
                    create_ledger_record(db, project, proc, winner.supplier_name or "", contract_price, proc.sign_date or "", parent_num)
                if proc.parent_contract_id and parent_num:
                    parent_ledger = db.query(Ledger).filter(Ledger.procurement_id == proc.parent_contract_id).first()
                    if parent_ledger:
                        existing_supp = (parent_ledger.supplement_contracts or "").strip()
                        parent_ledger.supplement_contracts = f"{existing_supp}\n{proc.contract_number}".strip() if existing_supp else proc.contract_number
        f_for_proc = next((x for x in temp_files if x.procurement_id == proc.id and x.is_contract), None)
        if f_for_proc:
            ledger = db.query(Ledger).filter(Ledger.procurement_id == proc.id).first()
            if ledger:
                ledger.pdf_preview_path = f"/api/files/{f_for_proc.id}/content"

    # 填充台账联系人、其余参与方等派生字段（与采购供应商同步）
    for pid in proc_ids:
        pobj = db.query(Procurement).filter(Procurement.id == pid).first()
        if pobj:
            sync_ledgers_on_procurement_update(db, pobj)

    # 归档后清理 _temp 空目录
    try:
        cleanup_empty_temp_dirs()
    except Exception:
        pass

    return True
