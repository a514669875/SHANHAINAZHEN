"""Ledger API."""
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
import openpyxl
from openpyxl.styles import Alignment
from app.database import get_db
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.models.user import User
from app.models.file import File
from app.core.auth import get_current_user, get_authenticated_user
from app.services.emit_event import emit
from app.events_schema import EventType
from app.utils.officer import resolve_officer_names
from app.utils.format import format_currency_two_decimals
from app.services.procurement_service import sync_ledgers_on_procurement_update, compute_ledger_supplier_derived

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


def _natural_sort_tuple(s: str) -> tuple:
    """
    合同编号等混有数字的字符串，按「自然序」比较，避免字典序下 材10 排在 材2 前面。
    使用 (0, int) / (1, str) 片段元组，避免 Python 3 中 int 与 str 直接比较报错。
    """
    if not s:
        return ()
    parts = re.split(r"(\d+)", s)
    out: list = []
    for p in parts:
        if p == "":
            continue
        if p.isdigit():
            out.append((0, int(p)))
        else:
            out.append((1, p))
    return tuple(out)


def _ledger_sort_key(l: Ledger) -> tuple:
    """台账排序：项目编号 → 材（材料采购与材料租赁共用材X编号）→设备→机械 → 主合同优先 → 补充协议紧跟主合同。"""
    pn = (l.project_number or "").strip()
    cn = (l.contract_number or "").strip()
    parent = (l.parent_contract_number or "").strip()
    base_cn = parent if parent else cn
    # 采购类型优先级：材=1, 设备=2, 机械=3
    if "材" in cn and "材" in base_cn:
        type_order = 1
    elif "设备" in cn or "设备" in base_cn:
        type_order = 2
    elif "机械" in cn or "机械" in base_cn:
        type_order = 3
    else:
        type_order = 4
    is_supp = 1 if parent else 0
    supp_seq = 0
    if "-补" in cn:
        m = re.search(r"-补(\d+)(?:-|$)", cn)
        if m:
            supp_seq = int(m.group(1))
    # base_cn / cn 用自然序，避免 材10 字典序小于 材2
    return (pn, type_order, _natural_sort_tuple(base_cn), is_supp, supp_seq, _natural_sort_tuple(cn))


def _sync_supplement_contracts_display(db: Session, ledger: Ledger) -> str:
    """Return supplement_contracts string with only existing supplements (PRD 8.11)."""
    if not ledger.supplement_contracts:
        return "-"
    valid = []
    for cn in (x.strip() for x in ledger.supplement_contracts.split("\n") if x.strip()):
        supp = db.query(Ledger).filter(
            Ledger.project_id == ledger.project_id,
            Ledger.contract_number == cn,
        ).first()
        if supp:
            valid.append(cn)
    return " ".join(valid) if valid else "-"


ALLOWED_SORT_FIELDS = {"contract_price", "sign_date", "create_time"}


def _apply_ledger_order(q, sort_by: str, sort_order: str):
    """Apply sort to ledger query. contract_price/sign_date/create_time (PRD 8.11)."""
    if sort_by and sort_by in ALLOWED_SORT_FIELDS:
        order_col = getattr(Ledger, sort_by)
        return q.order_by(order_col.desc() if sort_order == "descending" else order_col.asc())
    return q.order_by(Ledger.id.desc())


@router.get("")
def list_ledger(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0, le=50000, description="0=不分页返回全部"),
    sort_by: str = Query("", description="排序字段：contract_price/sign_date/create_time"),
    sort_order: str = Query("ascending", description="ascending/descending"),
    funding_type: str = Query("", description="筛选资金类别：工程类/自有资金"),
    group_type: str = Query("", description="筛选集团内/外项目"),
    procurement_method: str = Query("", description="筛选采购方式"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Ledger)
    if keyword:
        q = q.filter(
            Ledger.contract_number.contains(keyword)
            | Ledger.supplier.contains(keyword)
            | Ledger.project_name.contains(keyword)
        )
    if funding_type:
        q = q.filter(Ledger.funding_type == funding_type)
    if group_type:
        q = q.filter(Ledger.group_type == group_type)
    if procurement_method:
        q = q.filter(Ledger.procurement_method == procurement_method)
    total = q.count()
    if sort_by and sort_by in ALLOWED_SORT_FIELDS:
        q = _apply_ledger_order(q, sort_by, sort_order)
        if page_size == 0:
            items = q.all()
        else:
            items = q.offset((page - 1) * page_size).limit(page_size).all()
    else:
        # 默认排序：项目编号 → 材→设备→机械 → 主合同优先 → 补充协议紧跟主合同
        all_items = q.all()
        all_items.sort(key=_ledger_sort_key)
        if page_size == 0:
            items = all_items
        else:
            start = (page - 1) * page_size
            items = all_items[start : start + page_size]
    # Build response with officer names and file preview
    result = []
    for l in items:
        officer_names = resolve_officer_names(db, l.officer or "")
        first_file = db.query(File).filter(File.procurement_id == l.procurement_id, File.is_contract == True).first()
        parent_preview = None
        if l.parent_contract_number:
            parent_ledger = db.query(Ledger).filter(
                Ledger.project_id == l.project_id,
                Ledger.contract_number == l.parent_contract_number.strip(),
            ).first()
            if parent_ledger:
                pf = db.query(File).filter(
                    File.procurement_id == parent_ledger.procurement_id,
                    File.is_contract == True,
                ).first()
                if pf:
                    parent_preview = f"/api/files/{pf.id}/content"
        supplement_list = []
        if l.supplement_contracts:
            for cn in (x.strip() for x in l.supplement_contracts.split("\n") if x.strip()):
                supp_ledger = db.query(Ledger).filter(
                    Ledger.project_id == l.project_id,
                    Ledger.contract_number == cn,
                ).first()
                if not supp_ledger:
                    continue
                url = None
                sf = db.query(File).filter(
                    File.procurement_id == supp_ledger.procurement_id,
                    File.is_contract == True,
                ).first()
                if sf:
                    url = f"/api/files/{sf.id}/content"
                supplement_list.append({"cn": cn, "url": url})
        proc_row = db.query(Procurement).filter(Procurement.id == l.procurement_id).first()
        if proc_row:
            derived = compute_ledger_supplier_derived(db, proc_row)
            scp = (derived["supplier_contact_person"] or "").strip() or "-"
            scph = (derived["supplier_contact_phone"] or "").strip() or "-"
            opart = derived["other_participants"] or "/"
        else:
            scp, scph, opart = "-", "-", "/"
        proc_type_str = (proc_row.procurement_type or "") if proc_row else ""
        result.append({
            "id": l.id,
            "project_id": l.project_id,
            "procurement_id": l.procurement_id,
            "seq": None,
            "group_type": l.group_type,
            "procurement_type": proc_type_str,
            "procurement_method": l.procurement_method,
            "department": l.department,
            "project_number": l.project_number,
            "contract_number": l.contract_number,
            "project_name": l.project_name,
            "procurement_name": l.procurement_name,
            "supplier": l.supplier,
            "supplier_contact_person": scp,
            "supplier_contact_phone": scph,
            "contract_price": l.contract_price,
            "sign_date": l.sign_date,
            "content": l.content,
            "other_participants": opart,
            "control_price": l.control_price,
            "funding_source": l.funding_source,
            "officer": officer_names,
            "funding_type": l.funding_type,
            "file_preview_url": f"/api/files/{first_file.id}/content" if first_file else None,
            "parent_contract_number": l.parent_contract_number,
            "parent_contract_preview_url": parent_preview,
            "supplement_contracts": "\n".join(x["cn"] for x in supplement_list) if supplement_list else "-",
            "supplement_contracts_list": supplement_list,
            "create_time": l.create_time.strftime("%Y-%m-%d") if l.create_time else "",
        })
    return {"items": result, "total": total}


@router.get("/export/excel")
def export_ledger(
    ids: str = Query("", description="导出的台账ID，逗号分隔；为空时返回错误"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """导出选中台账。任意已登录用户可导出（不区分角色）。ids 为勾选的台账 ID，逗号分隔；未传或为空时返回 400。"""
    if not ids or not ids.strip():
        raise HTTPException(status_code=400, detail="请先勾选要导出的台账项")
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="请先勾选要导出的台账项")
    if not id_list:
        raise HTTPException(status_code=400, detail="请先勾选要导出的台账项")
    items = db.query(Ledger).filter(Ledger.id.in_(id_list)).order_by(Ledger.id.desc()).all()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "智能台账"
    headers = [
        "序号", "资金类别", "集团内/外项目", "采购类型", "采购方式", "项目实施部门", "项目编号", "合同编号",
        "工程名称", "采购项目名称", "供应商", "供应商联系人", "供应商联系方式", "合同价（元）", "签订日期", "采购内容",
        "其余参与方", "采购控制价（元）", "资金来源", "经办人", "所属主合同", "补充协议", "录入时间"
    ]
    ws.append(headers)
    wrap_align = Alignment(wrap_text=True, vertical="top")
    for i, l in enumerate(items, 1):
        supp_str = _sync_supplement_contracts_display(db, l)
        from app.utils.format import format_date_ymd
        create_time_str = format_date_ymd(l.create_time) if l.create_time else ""
        sign_date_str = format_date_ymd(l.sign_date) if l.sign_date else ""
        officer_names = resolve_officer_names(db, l.officer or "")
        contract_price_str = format_currency_two_decimals(l.contract_price) if l.contract_price is not None else "/"
        control_price_str = format_currency_two_decimals(l.control_price) if l.control_price is not None else "/"
        proc_row = db.query(Procurement).filter(Procurement.id == l.procurement_id).first()
        if proc_row:
            derived = compute_ledger_supplier_derived(db, proc_row)
            ex_scp = (derived["supplier_contact_person"] or "").strip() or "-"
            ex_scp2 = (derived["supplier_contact_phone"] or "").strip() or "-"
            other_str = derived["other_participants"] or "/"
        else:
            ex_scp, ex_scp2, other_str = "-", "-", "/"
        proc_type_excel = (proc_row.procurement_type or "") if proc_row else ""
        row = [
            i, l.funding_type or "-", l.group_type, proc_type_excel, l.procurement_method, l.department, l.project_number,
            l.contract_number, l.project_name, l.procurement_name, l.supplier,
            ex_scp,
            ex_scp2,
            contract_price_str, sign_date_str, l.content,
            other_str,
            control_price_str, l.funding_source,
            officer_names, l.parent_contract_number or "-", supp_str, create_time_str,
        ]
        ws.append(row)
        r = ws.max_row
        for c in (12, 13, 17):  # 供应商联系人、供应商联系方式、其余参与方
            ws.cell(row=r, column=c).alignment = wrap_align
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ledger.xlsx"}
    )


# Excel import column mapping (export headers)
IMPORT_HEADERS = [
    "序号", "集团内/外项目", "采购方式", "项目实施部门", "项目编号", "合同编号",
    "工程名称", "采购项目名称", "供应商", "合同价（元）", "签订日期", "采购内容",
    "采购控制价（元）", "资金来源", "经办人", "资金类别", "所属主合同", "补充协议"
]


def _fill(val) -> str:
    """Fill missing with '/'."""
    if val is None or (isinstance(val, str) and not val.strip()):
        return "/"
    return str(val).strip() if val else "/"


@router.post("/import/excel")
async def import_ledger_excel(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import ledger from Excel. Auto-match columns, fill missing with '/', create project/procurement if needed."""
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="请上传 Excel 文件 (.xlsx)")
    content = await file.read()
    wb = openpyxl.load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    if not ws:
        raise HTTPException(status_code=400, detail="Excel 文件为空")
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel 无数据行")
    headers = [str(h).strip() if h else "" for h in rows[0]]
    col_map = {}
    for i, h in enumerate(IMPORT_HEADERS):
        for j, rh in enumerate(headers):
            if rh and (h == rh or h in rh):
                col_map[i] = j
                break
    created = 0
    created_pairs = []
    sync_procurement_ids = set()
    for row in rows[1:]:
        if not any(row):
            continue
        def get(i):
            j = col_map.get(i, i)
            return row[j] if j < len(row) else None
        group_type = _fill(get(1))
        procurement_method = _fill(get(2))
        department = _fill(get(3))
        project_number = _fill(get(4))
        contract_number = _fill(get(5))
        project_name = _fill(get(6))
        procurement_name = _fill(get(7))
        supplier = _fill(get(8))
        try:
            contract_price = float(get(9)) if get(9) is not None else 0.0
        except (TypeError, ValueError):
            contract_price = 0.0
        sign_date = _fill(get(10))
        content = _fill(get(11))
        try:
            control_price = float(get(12)) if get(12) is not None else 0.0
        except (TypeError, ValueError):
            control_price = 0.0
        funding_source = _fill(get(13))
        officer = _fill(get(14))
        funding_type = _fill(get(15))
        parent_contract_number = _fill(get(16))
        supplement_contracts = _fill(get(17))
        if contract_number == "/" or project_number == "/":
            continue
        project = db.query(Project).filter(Project.project_number == project_number).first()
        if not project:
            project = db.query(Project).filter(Project.project_id == project_number).first()
        if not project:
            project_id_str = project_number[:20] if len(project_number) > 20 else project_number
            project = Project(
                project_number=project_number,
                project_id=project_id_str,
                project_name=project_name if project_name != "/" else project_number,
                department=department if department != "/" else "",
                funding_source=funding_source if funding_source != "/" else "",
                funding_type=funding_type if funding_type != "/" else "工程类",
                project_type=group_type if group_type != "/" else "集团内项目",
                procurement_officers="",
            )
            db.add(project)
            db.flush()
        procurement = db.query(Procurement).filter(
            Procurement.project_id == project.id,
            Procurement.contract_number == contract_number,
        ).first()
        if not procurement:
            procurement = Procurement(
                project_id=project.id,
                procurement_type="材料采购",
                procurement_method=procurement_method if procurement_method != "/" else "直接采购",
                project_name=procurement_name if procurement_name != "/" else project_name,
                content=content if content != "/" else "",
                control_price=control_price,
                contract_number=contract_number,
                sign_date=sign_date if sign_date != "/" else "",
            )
            db.add(procurement)
            db.flush()
            db.add(Supplier(
                procurement_id=procurement.id,
                supplier_name=supplier if supplier != "/" else "",
                quoted_price=contract_price,
                rank=1,
                is_winner=True,
            ))
        ledger = Ledger(
            project_id=project.id,
            procurement_id=procurement.id,
            group_type=group_type,
            procurement_method=procurement_method,
            department=department,
            project_number=project_number,
            contract_number=contract_number,
            project_name=project_name,
            procurement_name=procurement_name,
            supplier=supplier,
            supplier_contact_person="",
            supplier_contact_phone="",
            contract_price=contract_price,
            sign_date=sign_date,
            content=content,
            other_participants="/",
            control_price=control_price,
            funding_source=funding_source,
            officer=officer,
            funding_type=funding_type,
            parent_contract_number=parent_contract_number,
            supplement_contracts=supplement_contracts,
            create_time=datetime.now(),
        )
        db.add(ledger)
        created += 1
        created_pairs.append((project.id, procurement.id))
        sync_procurement_ids.add(procurement.id)
    for pid in sync_procurement_ids:
        pobj = db.query(Procurement).filter(Procurement.id == pid).first()
        if pobj:
            sync_ledgers_on_procurement_update(db, pobj)
    db.commit()
    for pj_id, pc_id in created_pairs:
        emit(EventType.LEDGER_CREATED, {"project_id": pj_id, "procurement_id": pc_id})
    return {"message": "ok", "created": created}
