"""Procurement API."""
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger("shanhai")
from sqlalchemy.orm import Session
from datetime import date
from app.database import get_db
from app.config import ARCHIVED_FILE_ROOT
from app.models.user import User
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.models.ledger import Ledger
from app.core.auth import get_current_user
from app.schemas.procurement import ProcurementCreate, ProcurementUpdate
from app.services.project_service import is_officer
from app.services.archive_service import get_archive_contract_folder
from app.services.procurement_service import (
    get_next_contract_seq,
    generate_contract_number,
    create_procurement_folder,
    delete_procurement_resources,
    rename_procurement_folders,
    sync_ledgers_on_procurement_update,
)
from app.services.process_file_sync_service import ensure_sync_status_records, get_primary_procurement_id, sync_process_files_on_form_save
from app.services.word_service import get_template_path, build_context, render_docx
from app.services.emit_event import emit
from app.events_schema import EventType
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn


def _save_mulu_docx(folder_path, title: str, time_records: list) -> None:
    """生成目录.docx，标题宋体四号居中。"""
    doc = Document()
    p = doc.add_paragraph()
    run = p.add_run(title)
    run.font.name = "SimSun"
    run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")
    run.font.size = Pt(14)  # 四号
    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    for tr in time_records:
        doc.add_paragraph(f"{tr.get('flow_name', '')}: {tr.get('date_val', '')}")
    doc.save(folder_path / "目录.docx")


router = APIRouter(prefix="/api/procurements", tags=["procurements"])


def check_permission(project: Project, current_user: User):
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无编辑权限")


def _is_dual_second(p: Procurement) -> bool:
    """是否为五选二二标段（含旧数据兼容：procurement_method=五选二 且 contract_section=二标段）."""
    if p.procurement_method == "五选二" and p.contract_section == "二标段":
        return True
    return False


def _is_dual_first(p: Procurement) -> bool:
    """是否为五选二一标段."""
    if p.procurement_method == "五选二" and p.contract_section == "一标段":
        return True
    return False


def _parse_form_data(form_data: str) -> dict:
    """Parse form_data JSON or repr to dict."""
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


def _is_time_records_only_change(
    old_form_data: str,
    new_form_data: str | None,
    old_suppliers: list,
    new_suppliers: list | None,
) -> bool:
    """判断是否仅流程时间表（_time_records）变更。若仅变更则只更新目录.docx。"""
    if not new_form_data:
        return False
    old_fd = _parse_form_data(old_form_data)
    new_fd = _parse_form_data(new_form_data)
    if not isinstance(old_fd, dict) or not isinstance(new_fd, dict):
        return False
    old_without = {k: v for k, v in old_fd.items() if k != "_time_records"}
    new_without = {k: v for k, v in new_fd.items() if k != "_time_records"}
    if old_without != new_without:
        return False
    old_tr = old_fd.get("_time_records", [])
    new_tr = new_fd.get("_time_records", [])
    if old_tr == new_tr:
        return False
    # 供应商未变更（new_suppliers 在 dump 中时需比较；不在 dump 则视为未变更）
    if new_suppliers is not None:
        def _norm_orm(s):
            return (getattr(s, "supplier_name", None), getattr(s, "quoted_price", None))
        def _norm_dict(s):
            return (s.get("supplier_name"), s.get("quoted_price"))
        old_norm = [_norm_orm(s) for s in old_suppliers]
        new_norm = [_norm_dict(s) for s in new_suppliers]
        if old_norm != new_norm:
            return False
    return True


def _find_dual_sibling(db: Session, proc: Procurement) -> Procurement | None:
    """Find the sibling procurement for 五选二 pair (二标段)."""
    if proc.procurement_method != "五选二":
        return None
    other = db.query(Procurement).filter(
        Procurement.project_id == proc.project_id,
        Procurement.procurement_method == "五选二",
        Procurement.id != proc.id,
    ).first()
    return other


def _parse_supplement_seq(contract_number: str | None) -> int | None:
    """Parse supplement sequence from contract_number like 'xxx-补1' -> 1."""
    if not contract_number or "-补" not in contract_number:
        return None
    try:
        return int(contract_number.split("-补")[-1])
    except (ValueError, IndexError):
        return None


def _validate_quoted_price_vs_control(
    suppliers_data: list,
    control_price: float | None,
    method: str = "",
) -> None:
    """Validate all suppliers' quoted_price <= control price. 五选二：所有供应商都≤控制价."""
    if control_price is not None and control_price > 0:
        for i, s in enumerate(suppliers_data):
            qp = s.get("quoted_price") or 0
            if qp > control_price:
                name = s.get("supplier_name") or f"第{i + 1}家"
                raise HTTPException(
                    status_code=400,
                    detail=f"供应商「{name}」含税报价（{qp} 元）大于控制价（{control_price} 元），请调整。",
                )


def _validate_supplement_sign_dates(
    db: Session,
    parent_id: int,
    new_sign_date: str,
    *,
    exclude_proc_id: int | None = None,
    new_seq: int | None = None,
) -> None:
    """Validate supplement sign dates are in order: 补1 <= 补2 <= 补3..."""
    supplements = db.query(Procurement).filter(
        Procurement.parent_contract_id == parent_id,
        Procurement.procurement_method == "补充协议",
        Procurement.contract_number != "草稿",
    ).all()
    items = []
    for p in supplements:
        if p.id == exclude_proc_id:
            seq = _parse_supplement_seq(p.contract_number or "") or 0
            items.append((seq, new_sign_date))
        else:
            seq = _parse_supplement_seq(p.contract_number or "")
            if seq is not None:
                items.append((seq, p.sign_date or ""))
    if new_seq is not None:
        items.append((new_seq, new_sign_date))
    items.sort(key=lambda x: x[0])
    for i in range(1, len(items)):
        prev_date, curr_date = items[i - 1][1], items[i][1]
        if prev_date and curr_date and prev_date > curr_date:
            raise HTTPException(
                status_code=400,
                detail=f"同一主合同下，补充协议签订时间须按顺序递增：第{i}份（{prev_date}）应早于第{i + 1}份（{curr_date}），请调整。",
            )


@router.get("/parent-contract-options")
def get_parent_contract_options(
    project_id: int = Query(...),
    procurement_type: str = Query(...),
    is_dual_contract: bool = Query(False, description="主合同为五选二项目"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """补充协议主合同候选：同采购类型、非补充协议、合同编号已存在于台账。五选二时仅返回五选二产生的合同且已入台账。"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    # 台账中存在的合同编号
    rows = db.query(Ledger.contract_number).filter(
        Ledger.project_id == project_id,
        Ledger.contract_number.isnot(None),
        Ledger.contract_number != "",
    ).distinct().all()
    ledger_cns = {r[0] for r in rows if r[0]}
    if not ledger_cns:
        return []
    q = db.query(Procurement).filter(
        Procurement.project_id == project_id,
        Procurement.procurement_type == procurement_type,
        Procurement.contract_number.isnot(None),
        Procurement.contract_number != "",
        Procurement.contract_number != "草稿",
        Procurement.procurement_method != "补充协议",
        Procurement.contract_number.in_(ledger_cns),
    )
    if is_dual_contract:
        q = q.filter(Procurement.procurement_method == "五选二")
    else:
        q = q.filter(Procurement.procurement_method != "五选二")
    items = q.order_by(Procurement.create_time.desc()).all()
    result = []
    for p in items:
        supp_count = db.query(Procurement).filter(
            Procurement.parent_contract_id == p.id,
        ).count()
        result.append({
            "id": p.id,
            "contract_number": p.contract_number,
            "project_name": p.project_name or "",
            "content": p.content or "",
            "contract_section": p.contract_section or "",
            "supplement_count": supp_count,
        })
    return result


@router.get("")
def list_procurements(
    project_id: int = Query(...),
    for_list: bool = Query(True, description="True=采购清单只显示1条五选二; False=归档用显示合并组"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List procurements for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    items = db.query(Procurement).filter(Procurement.project_id == project_id).order_by(Procurement.create_time.desc()).all()
    result = []
    for p in items:
        sibling = None
        if _is_dual_second(p):
            if for_list:
                continue
            continue
        if _is_dual_first(p):
            sibling = _find_dual_sibling(db, p)

        suppliers = db.query(Supplier).filter(Supplier.procurement_id == p.id).order_by(Supplier.rank).all()
        # 按报价升序取第一名作为中选人（供应商/合同价随报价排名变更）
        sorted_by_price = sorted(
            suppliers,
            key=lambda s: (float(s.quoted_price) if s.quoted_price is not None and s.quoted_price != "" else float("inf")),
        )
        winner = sorted_by_price[0] if sorted_by_price else None
        remark = ""  # 备注栏不显示任何关联内容（PRD 8.8）

        # 补充协议合同价=新增金额；控制价用 form_data.supplement_control_price（非新增金额）
        if p.procurement_method == "补充协议":
            _contract_price = p.control_price or 0
            _control_price = None
            if p.form_data:
                try:
                    import json
                    try:
                        fd = json.loads(p.form_data)
                    except (json.JSONDecodeError, TypeError):
                        import ast
                        fd = ast.literal_eval(p.form_data) if p.form_data else {}
                    if isinstance(fd, dict):
                        sc = fd.get("supplement_control_price")
                        _control_price = float(sc) if sc is not None and sc != "" else None
                except Exception:
                    pass
        else:
            _contract_price = winner.quoted_price if winner else 0
            _control_price = p.control_price

        _supplier = winner.supplier_name if winner else ""
        _contract_price_display = None  # 五选二时用分行显示

        # 五选二：供应商、合同价分行显示；一标段=排序第1名+成交金额1，二标段=排序第2名+成交金额2
        if p.procurement_method == "五选二" and sibling:
            sorted_a = sorted(suppliers, key=lambda s: (float(s.quoted_price) if s.quoted_price is not None and s.quoted_price != "" else float("inf")))
            supp_b = db.query(Supplier).filter(Supplier.procurement_id == sibling.id).all()
            sorted_b = sorted(supp_b, key=lambda s: (float(s.quoted_price) if s.quoted_price is not None and s.quoted_price != "" else float("inf")))
            winner_a = sorted_a[0] if len(sorted_a) > 0 else None
            winner_b = sorted_b[1] if len(sorted_b) > 1 else (sorted_b[0] if sorted_b else None)
            supp_a_name = winner_a.supplier_name if winner_a else ""
            supp_b_name = winner_b.supplier_name if winner_b else ""
            _supplier = f"{supp_a_name}\n{supp_b_name}".strip() or ""
            # 从 form_data 取成交金额1、成交金额2
            cj1, cj2 = None, None
            if p.form_data:
                try:
                    import json
                    try:
                        fd = json.loads(p.form_data)
                    except (json.JSONDecodeError, TypeError):
                        import ast
                        fd = ast.literal_eval(p.form_data) if p.form_data else {}
                    if isinstance(fd, dict):
                        cj1 = fd.get("chengjiao_jine1")
                        cj2 = fd.get("chengjiao_jine2")
                except Exception:
                    pass
            if cj1 is None and winner_a:
                cj1 = winner_a.quoted_price
            if cj2 is None and winner_b:
                cj2 = winner_b.quoted_price
            c1 = (cj1 if cj1 is not None else 0) or 0
            c2 = (cj2 if cj2 is not None else 0) or 0
            _contract_price_display = f"{c1:,.2f}\n{c2:,.2f}"
            _contract_price = c1  # 保留首值供排序等

        item = {
            "id": p.id,
            "project_id": p.project_id,
            "procurement_type": p.procurement_type,
            "procurement_method": p.procurement_method,
            "project_name": p.project_name,
            "content": p.content,
            "control_price": _control_price,
            "contract_number": p.contract_number,
            "supplier": _supplier,
            "contract_price": _contract_price,
            "sign_date": p.sign_date,
            "remark": remark,
        }
        if _contract_price_display is not None:
            item["contract_price_display"] = _contract_price_display
        if not for_list and p.procurement_method == "五选二" and sibling:
            item["is_dual"] = True
            item["dual_ids"] = [p.id, sibling.id]
            cn_a = p.contract_number or ""
            cn_b = sibling.contract_number or ""
            item["contract_number"] = f"{cn_a}、{cn_b}" if cn_a and cn_b else (cn_a or cn_b)
        result.append(item)
    return result


@router.get("/{procurement_id}")
def get_procurement(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get procurement detail for overview (read-only)."""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    suppliers = db.query(Supplier).filter(Supplier.procurement_id == procurement_id).order_by(Supplier.rank).all()
    # 五选二：保留一标段全部5家供应商供编辑；二标段中选单位在构建返回时标记 is_winner
    winner_b_name = None
    if proc.procurement_method == "五选二":
        sibling = _find_dual_sibling(db, proc)
        if sibling:
            winner_b = db.query(Supplier).filter(
                Supplier.procurement_id == sibling.id,
                Supplier.is_winner == True,
            ).first()
            winner_b_name = winner_b.supplier_name if winner_b else None
    step2 = {}
    time_records = []
    if proc.form_data:
        try:
            import ast
            import json
            try:
                data = json.loads(proc.form_data)
            except (json.JSONDecodeError, TypeError):
                data = ast.literal_eval(proc.form_data)
            if isinstance(data, dict):
                step2 = {k: v for k, v in data.items() if k != "_time_records"}
                time_records = data.get("_time_records", [])
        except Exception:
            pass
    # 工程项目信息从 Project 取（暂存载入时正确回填）；采购项目名称/内容若为草稿占位则返回空
    _proj_name = project.project_name or ""
    _proj_number = project.project_number or ""
    _proj_id = project.project_id or ""
    _construction = project.construction_unit or ""
    _total_price = project.total_contract_price or 0
    _proj_address = project.project_address or ""
    _department = project.department or ""
    _site_manager = project.site_manager or ""
    _site_manager_phone = project.site_manager_phone or ""
    _proc_name = proc.project_name if (proc.project_name or "") != "草稿" else ""
    _content = proc.content if (proc.content or "") != "草稿" else ""
    return {
        "id": proc.id,
        "project_id": proc.project_id,
        "procurement_type": proc.procurement_type,
        "procurement_method": proc.procurement_method,
        "project_name": _proj_name,
        "project_number": _proj_number,
        "project_id_display": _proj_id,
        "construction_unit": _construction,
        "total_contract_price": _total_price,
        "project_address": _proj_address,
        "department": _department,
        "site_manager": _site_manager,
        "site_manager_phone": _site_manager_phone,
        "procurement_project_name": _proc_name,
        "content": _content,
        "control_price": proc.control_price,
        "contract_number": proc.contract_number,
        "sign_date": proc.sign_date,
        "contract_section": proc.contract_section,
        "parent_contract_id": proc.parent_contract_id,
        "step2": step2,
        "suppliers": [
            {
                "supplier_name": s.supplier_name,
                "contact_person": s.contact_person,
                "contact_phone": s.contact_phone,
                "business_scope": s.business_scope or "",
                "tax_rate": s.tax_rate or "",
                "quoted_price": (proc.control_price or 0) if proc.procurement_method == "补充协议" else (s.quoted_price or 0),
                "is_winner": s.is_winner or (winner_b_name is not None and s.supplier_name == winner_b_name),
                "contract_section": s.contract_section or "",
            }
            for s in suppliers
        ],
        "time_records": time_records,
    }


@router.post("")
def create_procurement(
    data: ProcurementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create procurement with full flow."""
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_permission(project, current_user)

    step1 = data.step1.model_dump()
    step2 = data.step2.model_dump()
    step2["project_name"] = project.project_name
    step2["project_number"] = project.project_number
    step2["project_id"] = project.project_id
    step2["construction_unit"] = project.construction_unit
    step2["total_contract_price"] = project.total_contract_price
    step2["project_address"] = project.project_address
    step2["department"] = project.department
    step2["site_manager"] = project.site_manager
    step2["site_manager_phone"] = project.site_manager_phone

    suppliers_data = [s.model_dump() for s in data.suppliers]
    method = step1["procurement_method"]
    is_draft = getattr(data, "is_draft", False) or False

    # 暂存：仅支持常规采购，放松校验
    if is_draft:
        if method == "五选二":
            raise HTTPException(status_code=400, detail="暂存不支持五选二")
        if method == "补充协议" and not data.parent_contract_id:
            raise HTTPException(status_code=400, detail="补充协议暂存需先选择主合同")
        if not suppliers_data:
            suppliers_data = [{"supplier_name": "", "contact_person": "", "contact_phone": "", "business_scope": "", "tax_rate": "", "quoted_price": 0}]
        if method == "邀请询比" and len(suppliers_data) < 3:
            while len(suppliers_data) < 3:
                suppliers_data.append({"supplier_name": "", "contact_person": "", "contact_phone": "", "business_scope": "", "tax_rate": "", "quoted_price": 0})
        if method == "补充协议" and len(suppliers_data) < 1:
            suppliers_data = [{"supplier_name": "", "contact_person": "", "contact_phone": "", "business_scope": "", "tax_rate": "", "quoted_price": 0}]
    else:
        # Validate supplier count
        if method in ["邀请询比"] and len(suppliers_data) < 3:
            raise HTTPException(status_code=400, detail="邀请询比需至少3家供应商")
        if method == "五选二" and len(suppliers_data) < 5:
            raise HTTPException(status_code=400, detail="五选二需至少5家供应商")
        if method in ["单一来源", "直接采购", "补充协议"] and len(suppliers_data) != 1:
            raise HTTPException(status_code=400, detail="该采购方式需1家供应商")

    # Sort suppliers by price
    sorted_suppliers = sorted(suppliers_data, key=lambda s: s.get("quoted_price", 0))

    if not is_draft and method != "补充协议":
        ctrl = step2.get("control_price")
        _validate_quoted_price_vs_control(
            suppliers_data,
            float(ctrl) if ctrl is not None and ctrl != "" else None,
            method,
        )

    if method == "五选二" and not is_draft:
        # Create two procurements
        seq = get_next_contract_seq(db, project.id, step1["procurement_type"])
        form_data_str = str({**step2, "_time_records": [{"flow_name": r.get("flow_name", ""), "date_val": r.get("date_val", "")} for r in data.time_records]})
        proc_a = Procurement(
            project_id=project.id,
            procurement_type=step1["procurement_type"],
            procurement_method=method,
            project_name=data.section_a_name or step2["procurement_project_name"],
            content=step2["content"],
            control_price=step2["control_price"],
            budget=round(step2["control_price"] / 10000),
            form_data=form_data_str,
            is_dual_contract=True,
            contract_section="一标段",
            contract_number=generate_contract_number(project, step1["procurement_type"], seq),
            sign_date=step2.get("sign_date", ""),
        )
        proc_b = Procurement(
            project_id=project.id,
            procurement_type=step1["procurement_type"],
            procurement_method=method,
            project_name=data.section_b_name or step2["procurement_project_name"],
            content=step2["content"],
            control_price=step2["control_price"],
            budget=round(step2["control_price"] / 10000),
            form_data=form_data_str,
            is_dual_contract=True,
            contract_section="二标段",
            contract_number=generate_contract_number(project, step1["procurement_type"], seq + 1),
            sign_date=step2.get("sign_date", ""),
        )
        db.add(proc_a)
        db.add(proc_b)
        db.flush()

        # 五选二：一标段、二标段各存全部5家供应商，便于编辑时完整回显；一标段中选 rank1，二标段中选 rank2
        s1, s2 = sorted_suppliers[0], sorted_suppliers[1]
        for proc, winner_s, section in [(proc_a, s1, "一标段"), (proc_b, s2, "二标段")]:
            for i, s in enumerate(sorted_suppliers, 1):
                is_win = s == winner_s
                db.add(Supplier(
                    procurement_id=proc.id,
                    supplier_name=s["supplier_name"],
                    contact_person=s["contact_person"],
                    contact_phone=s["contact_phone"],
                    business_scope=s["business_scope"],
                    tax_rate=s["tax_rate"],
                    quoted_price=s["quoted_price"],
                    rank=i,
                    is_winner=is_win,
                    contract_section=section,
                ))
            # 台账在归档时生成，不在此创建

        # 五选二：创建采购项目专属文件夹（不分标段）并生成 Word 流程文件
        try:
            folder = create_procurement_folder(project, proc_a, step2.get("content") or step2.get("procurement_project_name") or "")
            from app.services.word_service import _project_to_dict, build_context, get_template_path, render_docx
            ctx = build_context(
                _project_to_dict(project),
                {"funding_type": project.funding_type, "project_type": project.project_type, **step1},
                step2, suppliers_data, 0,
            )
            tpl_dir = get_template_path(project.funding_type, project.project_type, step1["procurement_type"], method)
            filenames = [d.name for d in tpl_dir.glob("*.docx")]
            for docx in tpl_dir.glob("*.docx"):
                render_docx(docx, ctx, folder / docx.name)
            title = f"{project.project_id}{project.project_name or ''}{step2.get('content', '')}"
            _save_mulu_docx(folder, title, data.time_records)
            ensure_sync_status_records(db, proc_a.id, filenames + ["目录.docx"], folder)
        except Exception as e:
            logger.exception("五选二流程文件生成失败: %s", e)
            raise HTTPException(status_code=500, detail=f"流程文件生成失败: {str(e)}")

        db.commit()
        for pid in [proc_a.id, proc_b.id]:
            emit(EventType.PROCUREMENT_CREATED, {"project_id": project.id, "procurement_id": pid})
        return {"message": "ok", "procurement_ids": [proc_a.id, proc_b.id]}

    elif method == "补充协议" and is_draft:
        parent = db.query(Procurement).filter(Procurement.id == data.parent_contract_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="主合同不存在")
        supplement_content = data.supplement_content or step2.get("content", "")
        form_data_str = str({**step2, "_time_records": [{"flow_name": r.get("flow_name", ""), "date_val": r.get("date_val", "")} for r in data.time_records]})
        proc = Procurement(
            project_id=project.id,
            procurement_type=step1["procurement_type"],
            procurement_method=method,
            parent_contract_id=data.parent_contract_id,
            project_name=parent.project_name or step2.get("procurement_project_name", ""),
            content=supplement_content or "",
            control_price=data.supplement_amount or 0,
            budget=0,
            form_data=form_data_str,
            contract_number="草稿",
            sign_date=step2.get("sign_date", ""),
            is_draft=True,
        )
        db.add(proc)
        db.flush()
        s = sorted_suppliers[0] if sorted_suppliers else {"supplier_name": "", "contact_person": "", "contact_phone": "", "business_scope": "", "tax_rate": "", "quoted_price": 0}
        parent_winner = db.query(Supplier).filter(Supplier.procurement_id == data.parent_contract_id).order_by(Supplier.rank).first()
        total_price = (parent_winner.quoted_price or 0) + (data.supplement_amount or 0)
        db.add(Supplier(
            procurement_id=proc.id,
            supplier_name=parent_winner.supplier_name if parent_winner else s.get("supplier_name", ""),
            contact_person=s.get("contact_person", ""),
            contact_phone=s.get("contact_phone", ""),
            business_scope=s.get("business_scope", ""),
            tax_rate=s.get("tax_rate", ""),
            quoted_price=total_price,
            rank=1,
            is_winner=True,
        ))
        # 补充协议暂存：创建专属文件夹（工程编号-草稿X）并生成全套流程文件（PRD 8.14/8.15）
        try:
            from app.services.word_service import _project_to_dict, build_context, get_template_path, render_docx
            folder_path = create_procurement_folder(project, proc, "草稿", db=db)
            supp_control = getattr(data, "supplement_control_price", None) or data.supplement_amount or 0
            step2_supp = {**step2, "content": supplement_content, "control_price": supp_control, "project_name": parent.project_name or step2.get("procurement_project_name", "")}
            supp_suppliers = [{"supplier_name": parent_winner.supplier_name if parent_winner else s.get("supplier_name", ""), "contact_person": s.get("contact_person", ""), "contact_phone": s.get("contact_phone", ""), "business_scope": s.get("business_scope", ""), "tax_rate": s.get("tax_rate", ""), "quoted_price": total_price}]
            ctx = build_context(_project_to_dict(project), {"funding_type": project.funding_type, "project_type": project.project_type, **step1}, step2_supp, supp_suppliers, 0)
            tpl_dir = get_template_path(project.funding_type, project.project_type, step1["procurement_type"], method)
            filenames = [d.name for d in tpl_dir.glob("*.docx")]
            for docx in tpl_dir.glob("*.docx"):
                render_docx(docx, ctx, folder_path / docx.name)
            parent_contracts = db.query(Procurement).filter(
                Procurement.project_id == project.id,
                Procurement.parent_contract_id == data.parent_contract_id,
            ).all()
            supp_seq = len(parent_contracts)
            title = f"{project.project_id}{project.project_name or ''}{supplement_content or '补充协议'}补充协议{supp_seq}"
            _save_mulu_docx(folder_path, title, data.time_records)
            ensure_sync_status_records(db, proc.id, filenames + ["目录.docx"], folder_path)
        except Exception as e:
            logger.exception("补充协议暂存流程文件生成失败: %s", e)
            raise HTTPException(status_code=500, detail=f"流程文件生成失败: {str(e)}")
        db.commit()
        db.refresh(proc)
        emit(EventType.PROCUREMENT_CREATED, {"project_id": project.id, "procurement_id": proc.id})
        return {"message": "ok", "procurement_id": proc.id}

    elif method == "补充协议" and not is_draft:
        parent = db.query(Procurement).filter(Procurement.id == data.parent_contract_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="主合同不存在")
        parent_winner = db.query(Supplier).filter(Supplier.procurement_id == data.parent_contract_id).order_by(Supplier.rank).first()
        original_price = parent_winner.quoted_price or 0 if parent_winner else 0
        supplement_amount = data.supplement_amount or 0
        supplement_content = data.supplement_content or step2.get("content", "")
        total_price = original_price + supplement_amount
        supp_ctrl = getattr(data, "supplement_control_price", None) or step2.get("supplement_control_price")
        if supp_ctrl is not None and supp_ctrl != "" and str(supp_ctrl).strip() != "/":
            try:
                ctrl_val = float(supp_ctrl)
                if ctrl_val > 0 and supplement_amount > ctrl_val:
                    raise HTTPException(
                        status_code=400,
                        detail=f"补充协议新增金额（{supplement_amount} 元）大于控制价（{ctrl_val} 元），请调整。",
                    )
            except (ValueError, TypeError):
                pass
        # 补充协议编号: 主合同编号-补Y
        parent_contracts = db.query(Procurement).filter(
            Procurement.project_id == project.id,
            Procurement.parent_contract_id == data.parent_contract_id,
        ).all()
        supp_seq = len(parent_contracts) + 1
        contract_num = f"{parent.contract_number}-补{supp_seq}"
        sign_date_val = step2.get("sign_date", "") or ""
        _validate_supplement_sign_dates(db, data.parent_contract_id, sign_date_val, new_seq=supp_seq)
        form_data_str = str({**step2, "_time_records": [{"flow_name": r.get("flow_name", ""), "date_val": r.get("date_val", "")} for r in data.time_records]})
        proc = Procurement(
            project_id=project.id,
            procurement_type=step1["procurement_type"],
            procurement_method=method,
            parent_contract_id=data.parent_contract_id,
            project_name=parent.project_name or step2["procurement_project_name"],
            content=supplement_content,
            control_price=supplement_amount,
            budget=round(total_price / 10000),
            form_data=form_data_str,
            contract_number=contract_num,
            sign_date=sign_date_val,
        )
        db.add(proc)
        db.flush()
        s = sorted_suppliers[0]
        db.add(Supplier(
            procurement_id=proc.id,
            supplier_name=parent_winner.supplier_name if parent_winner else s["supplier_name"],
            contact_person=s["contact_person"],
            contact_phone=s["contact_phone"],
            business_scope=s.get("business_scope", ""),
            tax_rate=s.get("tax_rate", ""),
            quoted_price=total_price,
            rank=1,
            is_winner=True,
        ))
        # 补充协议专属文件夹：常规 工程编号-采购内容-补X；五选二 工程编号-采购内容-标段名-补X（123.md）
        try:
            from app.config import PROCUREMENT_PROCESS_ROOT
            from app.services.word_service import _project_to_dict, build_context, get_template_path, render_docx
            content_safe = (supplement_content or parent.content or "").strip() or "补充协议"
            if parent.procurement_method == "五选二" and parent.contract_section:
                folder_name = f"{project.project_id}-{content_safe}-{parent.contract_section}-补{supp_seq}"
            else:
                folder_name = f"{project.project_id}-{content_safe}-补{supp_seq}"
            folder_path = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}" / folder_name
            folder_path.mkdir(parents=True, exist_ok=True)
            supp_control = getattr(data, "supplement_control_price", None) or supplement_amount
            step2_supp = {**step2, "content": supplement_content, "control_price": supp_control, "project_name": parent.project_name or step2.get("procurement_project_name", "")}
            supp_suppliers = [{"supplier_name": parent_winner.supplier_name if parent_winner else s["supplier_name"], "contact_person": s["contact_person"], "contact_phone": s["contact_phone"], "business_scope": s.get("business_scope", ""), "tax_rate": s.get("tax_rate", ""), "quoted_price": total_price}]
            ctx = build_context(_project_to_dict(project), {"funding_type": project.funding_type, "project_type": project.project_type, **step1}, step2_supp, supp_suppliers, 0)
            tpl_dir = get_template_path(project.funding_type, project.project_type, step1["procurement_type"], method)
            filenames = [d.name for d in tpl_dir.glob("*.docx")]
            for docx in tpl_dir.glob("*.docx"):
                render_docx(docx, ctx, folder_path / docx.name)
            title = f"{project.project_id}{project.project_name or ''}{supplement_content or '补充协议'}补充协议{supp_seq}"
            _save_mulu_docx(folder_path, title, data.time_records)
            ensure_sync_status_records(db, proc.id, filenames + ["目录.docx"], folder_path)
        except Exception as e:
            logger.exception("补充协议流程文件生成失败: %s", e)
            raise HTTPException(status_code=500, detail=f"流程文件生成失败: {str(e)}")
        db.commit()
        emit(EventType.PROCUREMENT_CREATED, {"project_id": project.id, "procurement_id": proc.id})
        return {"message": "ok", "procurement_id": proc.id}

    else:
        # Single procurement (含暂存)
        if not is_draft:
            seq = get_next_contract_seq(db, project.id, step1["procurement_type"])
            contract_num = generate_contract_number(project, step1["procurement_type"], seq)
        else:
            contract_num = "草稿"
        form_data_str = str({**step2, "_time_records": [{"flow_name": r.get("flow_name", ""), "date_val": r.get("date_val", "")} for r in data.time_records]})
        proc = Procurement(
            project_id=project.id,
            procurement_type=step1["procurement_type"],
            procurement_method=method,
            project_name=step2.get("procurement_project_name", "") or "",
            content=step2.get("content", "") or "",
            control_price=step2.get("control_price", 0) or 0,
            budget=round((step2.get("control_price", 0) or 0) / 10000),
            form_data=form_data_str,
            contract_number=contract_num,
            sign_date=step2.get("sign_date", ""),
            is_draft=is_draft,
        )
        db.add(proc)
        db.flush()
        winner = sorted_suppliers[0]
        for i, s in enumerate(sorted_suppliers, 1):
            db.add(Supplier(
                procurement_id=proc.id,
                supplier_name=s["supplier_name"],
                contact_person=s["contact_person"],
                contact_phone=s["contact_phone"],
                business_scope=s["business_scope"],
                tax_rate=s["tax_rate"],
                quoted_price=s["quoted_price"],
                rank=i,
                is_winner=(i == 1),
            ))
        # 台账在归档时生成，不在此创建

        # Create folder and generate Word (仅采购项目专属文件夹，不创建归档文件夹)
        try:
            folder = create_procurement_folder(project, proc, step2.get("content") or step2.get("procurement_project_name") or "草稿", db=db)
            from app.services.word_service import _project_to_dict, build_context, get_template_path, render_docx
            ctx = build_context(
                _project_to_dict(project),
                {"funding_type": project.funding_type, "project_type": project.project_type, **step1},
                step2, suppliers_data, 0
            )
            tpl_dir = get_template_path(project.funding_type, project.project_type, step1["procurement_type"], method)
            filenames = [d.name for d in tpl_dir.glob("*.docx")]
            for docx in tpl_dir.glob("*.docx"):
                render_docx(docx, ctx, folder / docx.name)
            title = f"{project.project_id}{project.project_name or ''}{step2.get('content', '')}"
            _save_mulu_docx(folder, title, data.time_records)
            ensure_sync_status_records(db, proc.id, filenames + ["目录.docx"], folder)
        except Exception as e:
            logger.exception("采购项目流程文件生成失败: %s", e)
            raise HTTPException(status_code=500, detail=f"流程文件生成失败: {str(e)}")

        db.commit()
        db.refresh(proc)
        emit(EventType.PROCUREMENT_CREATED, {"project_id": project.id, "procurement_id": proc.id})
        return {"message": "ok", "procurement_id": proc.id}


@router.put("/{procurement_id}")
def update_procurement(
    procurement_id: int,
    data: ProcurementUpdate,
    draft_only: bool = Query(False, description="仅暂存更新，不完成草稿"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update procurement. 草稿完成时生成合同编号。draft_only=True 时仅更新表单不完成。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_permission(project, current_user)
    old_content = proc.content or ""
    old_project_name = proc.project_name or ""
    old_contract_number = proc.contract_number or ""
    dump = data.model_dump(exclude_unset=True)
    if draft_only and proc.is_draft:
        for k, v in dump.items():
            if k == "form_data":
                proc.form_data = v
            elif k == "project_name":
                proc.project_name = v
            elif k == "content":
                proc.content = v
            elif k == "supplement_amount" and v is not None:
                proc.control_price = v
            elif k == "supplement_content" and v is not None:
                proc.content = v
        if "suppliers" in dump and dump["suppliers"] is not None:
            db.query(Supplier).filter(Supplier.procurement_id == proc.id).delete()
            supp_amount = dump.get("supplement_amount") or 0
            total_price = 0
            if proc.parent_contract_id:
                parent_winner = db.query(Supplier).filter(
                    Supplier.procurement_id == proc.parent_contract_id
                ).order_by(Supplier.rank).first()
                total_price = (parent_winner.quoted_price or 0) + supp_amount if parent_winner else supp_amount
            _draft_supp = dump["suppliers"]
            _draft_sorted = sorted(_draft_supp, key=lambda s: float(s.get("quoted_price") or 0) if s.get("quoted_price") not in (None, "") else float("inf"))
            for i, s in enumerate(_draft_sorted, 1):
                qp = total_price if proc.parent_contract_id and i == 1 else s.get("quoted_price", 0)
                db.add(Supplier(
                    procurement_id=proc.id,
                    supplier_name=s.get("supplier_name", ""),
                    contact_person=s.get("contact_person", ""),
                    contact_phone=s.get("contact_phone", ""),
                    business_scope=s.get("business_scope", ""),
                    tax_rate=s.get("tax_rate", ""),
                    quoted_price=qp,
                    rank=i,
                    is_winner=(i == 1),
                ))
        # 暂存编辑：草稿文件夹保持 工程编号-草稿X，直到完成才重命名（PRD 8.15）
        db.commit()
        db.refresh(proc)
        emit(EventType.PROCUREMENT_UPDATED, {"project_id": project.id, "procurement_id": proc.id})
        return proc
    # 流程时间表单独更新：仅 _time_records 变更时只更新 目录.docx
    old_form_data = proc.form_data
    old_suppliers = list(db.query(Supplier).filter(Supplier.procurement_id == proc.id).order_by(Supplier.rank).all())

    if proc.is_draft and dump.get("form_data") and not draft_only:
        if proc.contract_number == "草稿":
            if proc.procurement_method == "补充协议" and proc.parent_contract_id:
                parent = db.query(Procurement).filter(Procurement.id == proc.parent_contract_id).first()
                if parent:
                    parent_contracts = db.query(Procurement).filter(
                        Procurement.project_id == proc.project_id,
                        Procurement.parent_contract_id == proc.parent_contract_id,
                    ).all()
                    proc.contract_number = f"{parent.contract_number}-补{len(parent_contracts)}"
            else:
                seq = get_next_contract_seq(db, project.id, proc.procurement_type)
                proc.contract_number = generate_contract_number(project, proc.procurement_type, seq)
        proc.is_draft = False
    for k, v in dump.items():
        if k == "form_data":
            proc.form_data = v
            # 五选二：同步更新兄弟标段的 form_data，避免编辑后打开仍为旧数据
            if proc.procurement_method == "五选二" and v:
                sibling = _find_dual_sibling(db, proc)
                if sibling:
                    sibling.form_data = v
            # 从 form_data 同步 sign_date、control_price 到 proc；五选二时同步到兄弟标段
            if v:
                try:
                    import json
                    try:
                        fd = json.loads(v)
                    except (json.JSONDecodeError, TypeError):
                        import ast
                        fd = ast.literal_eval(v)
                    if isinstance(fd, dict):
                        sign_val = fd.get("sign_date")
                        if sign_val is not None:
                            proc.sign_date = sign_val if isinstance(sign_val, str) else str(sign_val or "")
                            if proc.procurement_method == "五选二":
                                sib = _find_dual_sibling(db, proc)
                                if sib:
                                    sib.sign_date = proc.sign_date
                        if proc.procurement_method != "补充协议" and "control_price" in fd:
                            ctrl_val = fd.get("control_price")
                            proc.control_price = float(ctrl_val) if ctrl_val is not None and ctrl_val != "" else None
                            if proc.procurement_method == "五选二":
                                sib = _find_dual_sibling(db, proc)
                                if sib:
                                    sib.control_price = proc.control_price
                except Exception:
                    pass
        elif k == "control_price" and proc.procurement_method != "补充协议":
            proc.control_price = float(v) if v is not None and v != "" else None
            if proc.procurement_method == "五选二":
                sib = _find_dual_sibling(db, proc)
                if sib:
                    sib.control_price = proc.control_price
        elif k == "suppliers" and v is not None:
            # 供应商数量需满足最低要求：邀请询比≥3，五选二≥5，其他=1
            min_supp = 5 if proc.procurement_method == "五选二" else (3 if proc.procurement_method == "邀请询比" else 1)
            if len(v) < min_supp:
                raise HTTPException(status_code=400, detail=f"{proc.procurement_method}需至少{min_supp}家供应商")
            if proc.procurement_method != "补充协议":
                fd = {}
                if proc.form_data:
                    try:
                        import json
                        try:
                            fd = json.loads(proc.form_data)
                        except (json.JSONDecodeError, TypeError):
                            import ast
                            fd = ast.literal_eval(proc.form_data) if proc.form_data else {}
                    except Exception:
                        pass
                ctrl = fd.get("control_price") if isinstance(fd, dict) else None
                if dump.get("form_data"):
                    try:
                        import json
                        try:
                            fd2 = json.loads(dump["form_data"])
                        except (json.JSONDecodeError, TypeError):
                            import ast
                            fd2 = ast.literal_eval(dump["form_data"])
                        if isinstance(fd2, dict):
                            ctrl = fd2.get("control_price", ctrl)
                    except Exception:
                        pass
                ctrl_f = float(ctrl) if ctrl is not None and ctrl != "" else None
                _validate_quoted_price_vs_control(v, ctrl_f, proc.procurement_method)
            db.query(Supplier).filter(Supplier.procurement_id == proc.id).delete()
            supp_amount = dump.get("supplement_amount") or 0
            total_price = 0
            if proc.parent_contract_id:
                parent_winner = db.query(Supplier).filter(
                    Supplier.procurement_id == proc.parent_contract_id
                ).order_by(Supplier.rank).first()
                total_price = (parent_winner.quoted_price or 0) + supp_amount if parent_winner else supp_amount
            # 询比/单源/五选二：按报价升序排序，中标列随供应商变更同步
            def _qp_key(s):
                q = s.get("quoted_price")
                if q is None or q == "" or (isinstance(q, str) and str(q).strip() == ""):
                    return float("inf")
                try:
                    return float(q)
                except (ValueError, TypeError):
                    return float("inf")
            sorted_v = sorted(v, key=_qp_key)
            sect = "一标段" if proc.procurement_method == "五选二" and proc.contract_section == "一标段" else None
            for i, s in enumerate(sorted_v, 1):
                qp = total_price if proc.parent_contract_id and i == 1 else s.get("quoted_price", 0)
                is_win = (i == 1) if proc.procurement_method != "五选二" else (i == 1 and sect == "一标段") or (i == 2 and sect != "一标段")
                sup = Supplier(
                    procurement_id=proc.id,
                    supplier_name=s.get("supplier_name", ""),
                    contact_person=s.get("contact_person", ""),
                    contact_phone=s.get("contact_phone", ""),
                    business_scope=s.get("business_scope", ""),
                    tax_rate=s.get("tax_rate", ""),
                    quoted_price=qp,
                    rank=i,
                    is_winner=is_win,
                )
                if sect:
                    sup.contract_section = sect
                db.add(sup)
            # 五选二：同步更新兄弟标段供应商（5家相同，一标段中选第1家、二标段中选第2家）
            if proc.procurement_method == "五选二" and len(sorted_v) >= 2:
                sibling = _find_dual_sibling(db, proc)
                if sibling:
                    db.query(Supplier).filter(Supplier.procurement_id == sibling.id).delete()
                    win_idx = 2 if sibling.contract_section == "二标段" else 1
                    sib_sect = sibling.contract_section or "二标段"
                    for i, s in enumerate(sorted_v, 1):
                        db.add(Supplier(
                            procurement_id=sibling.id,
                            supplier_name=s.get("supplier_name", ""),
                            contact_person=s.get("contact_person", ""),
                            contact_phone=s.get("contact_phone", ""),
                            business_scope=s.get("business_scope", ""),
                            tax_rate=s.get("tax_rate", ""),
                            quoted_price=s.get("quoted_price", 0),
                            rank=i,
                            is_winner=(i == win_idx),
                            contract_section=sib_sect,
                        ))
        elif k not in ("supplement_amount", "supplement_content"):
            setattr(proc, k, v)
    if "supplement_amount" in dump and dump["supplement_amount"] is not None:
        proc.control_price = dump["supplement_amount"]
    if "supplement_content" in dump and dump["supplement_content"] is not None:
        proc.content = dump["supplement_content"]
    if proc.procurement_method == "补充协议" and proc.parent_contract_id:
        supp_amt = proc.control_price or 0
        fd = {}
        if proc.form_data:
            try:
                import json
                try:
                    fd = json.loads(proc.form_data)
                except (json.JSONDecodeError, TypeError):
                    import ast
                    fd = ast.literal_eval(proc.form_data) if proc.form_data else {}
            except Exception:
                pass
        supp_ctrl = fd.get("supplement_control_price") if isinstance(fd, dict) else None
        if dump.get("form_data"):
            try:
                import json
                try:
                    fd2 = json.loads(dump["form_data"])
                except (json.JSONDecodeError, TypeError):
                    import ast
                    fd2 = ast.literal_eval(dump["form_data"])
                if isinstance(fd2, dict) and "supplement_control_price" in fd2:
                    supp_ctrl = fd2.get("supplement_control_price", supp_ctrl)
            except Exception:
                pass
        if supp_ctrl is not None and supp_ctrl != "" and str(supp_ctrl).strip() != "/":
            try:
                ctrl_val = float(supp_ctrl)
                if ctrl_val > 0 and supp_amt > ctrl_val:
                    raise HTTPException(
                        status_code=400,
                        detail=f"补充协议新增金额（{supp_amt} 元）大于控制价（{ctrl_val} 元），请调整。",
                    )
            except (ValueError, TypeError):
                pass
        _validate_supplement_sign_dates(db, proc.parent_contract_id, proc.sign_date or "", exclude_proc_id=proc.id)
    try:
        rename_procurement_folders(project, proc, old_content, old_project_name, old_contract_number, db)
    except Exception as e:
        logger.exception("采购项目文件夹重命名失败: %s", e)
        raise HTTPException(status_code=500, detail=f"文件夹重命名失败: {str(e)}")
    # 必须 flush 使新供应商写入 DB，否则 sync 查询不到，导致台账供应商/合同价空白
    db.flush()
    sync_ledgers_on_procurement_update(db, proc)
    if proc.procurement_method == "五选二":
        sibling = _find_dual_sibling(db, proc)
        if sibling:
            sync_ledgers_on_procurement_update(db, sibling)
    # 表单保存时触发流程文件同步（非草稿、非暂存）
    if not draft_only and not proc.is_draft:
        try:
            fd = {}
            if proc.form_data:
                try:
                    import json
                    fd = json.loads(proc.form_data)
                except (json.JSONDecodeError, TypeError):
                    import ast
                    fd = ast.literal_eval(proc.form_data) if proc.form_data else {}
            step1 = {
                "funding_type": project.funding_type or "工程类",
                "project_type": project.project_type or "集团内项目",
                "procurement_type": proc.procurement_type,
                "procurement_method": proc.procurement_method,
            }
            step2 = fd if isinstance(fd, dict) else {}
            if isinstance(step2, dict):
                step2.setdefault("project_name", project.project_name or "")
                step2.setdefault("project_number", project.project_number or "")
                step2.setdefault("project_id", project.project_id or "")
                step2.setdefault("construction_unit", project.construction_unit or "")
                step2.setdefault("total_contract_price", project.total_contract_price or 0)
                step2.setdefault("project_address", project.project_address or "")
                step2.setdefault("department", project.department or "")
                step2.setdefault("site_manager", project.site_manager or "")
                step2.setdefault("site_manager_phone", project.site_manager_phone or "")
            time_records = (step2.get("_time_records", []) or []) if isinstance(step2, dict) else []
            suppliers_data = [
                {"supplier_name": s.supplier_name, "contact_person": s.contact_person, "contact_phone": s.contact_phone,
                 "business_scope": s.business_scope or "", "tax_rate": s.tax_rate or "", "quoted_price": s.quoted_price or 0}
                for s in db.query(Supplier).filter(Supplier.procurement_id == proc.id).order_by(Supplier.rank).all()
            ]
            new_suppliers = dump.get("suppliers") if "suppliers" in dump else None
            time_records_only = _is_time_records_only_change(
                old_form_data, proc.form_data, old_suppliers, new_suppliers
            )
            sync_process_files_on_form_save(
                db, project, proc, step1, step2, suppliers_data, time_records,
                time_records_only=time_records_only,
            )
        except Exception as e:
            logger.exception("流程文件同步失败 procurement_id=%s: %s", proc.id, e)
    db.commit()
    db.refresh(proc)
    emit(EventType.PROCUREMENT_UPDATED, {"project_id": project.id, "procurement_id": proc.id})
    return proc


@router.delete("/{procurement_id}")
def delete_procurement(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete procurement and sync folders, files, ledgers per PRD 4.3. For 五选二, deletes both 标段."""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_permission(project, current_user)
    to_delete = [proc]
    is_dual = proc.is_dual_contract or proc.procurement_method == "五选二"
    if is_dual:
        sibling = _find_dual_sibling(db, proc)
        if sibling:
            to_delete.append(sibling)
    # 五选二：在删除 DB 记录前先删除归档专属文件夹（PRD 8.13）
    if len(to_delete) == 2 and is_dual:
        folder_name = get_archive_contract_folder(project, to_delete[0], to_delete[1])
        if folder_name:
            archive_base = ARCHIVED_FILE_ROOT / f"{project.project_id}材料（设备）合同"
            archive_path = archive_base / folder_name
            if archive_path.exists():
                try:
                    shutil.rmtree(archive_path)
                except Exception as e:
                    logger.warning("五选二归档文件夹删除失败: %s", e)
    warnings = []
    for p in to_delete:
        try:
            delete_procurement_resources(db, project, p)
        except Exception as e:
            logger.exception("删除采购项目资源失败 procurement_id=%s: %s", p.id, e)
            warnings.append(f"采购项目 {p.id} 关联文件夹/文件删除失败: {str(e)}")
        db.delete(p)
    db.commit()
    for p in to_delete:
        emit(EventType.PROCUREMENT_DELETED, {"project_id": project.id, "procurement_id": p.id})
    res = {"message": "ok"}
    if warnings:
        res["warnings"] = warnings
    return res
