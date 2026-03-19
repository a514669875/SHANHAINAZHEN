"""Ledger API."""
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
import openpyxl
from app.database import get_db
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.procurement import Procurement
from app.models.supplier import Supplier
from app.models.user import User
from app.models.file import File
from app.core.auth import get_current_user
from app.services.emit_event import emit
from app.events_schema import EventType
from app.utils.officer import resolve_officer_names
from app.utils.format import format_currency_two_decimals

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


def _ledger_sort_key(l: Ledger) -> tuple:
    """台账排序：项目编号 → 材→设备→机械 → 主合同优先 → 补充协议紧跟主合同。"""
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
    return (pn, type_order, base_cn, is_supp, supp_seq)


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
    page_size: int = Query(20, ge=1, le=100),
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
        items = q.offset((page - 1) * page_size).limit(page_size).all()
    else:
        # 默认排序：项目编号 → 材→设备→机械 → 主合同优先 → 补充协议紧跟主合同
        all_items = q.all()
        all_items.sort(key=_ledger_sort_key)
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
        result.append({
            "id": l.id,
            "project_id": l.project_id,
            "procurement_id": l.procurement_id,
            "seq": None,
            "group_type": l.group_type,
            "procurement_method": l.procurement_method,
            "department": l.department,
            "project_number": l.project_number,
            "contract_number": l.contract_number,
            "project_name": l.project_name,
            "procurement_name": l.procurement_name,
            "supplier": l.supplier,
            "contract_price": l.contract_price,
            "sign_date": l.sign_date,
            "content": l.content,
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
    current_user: User = Depends(get_current_user),
):
    """导出选中台账。ids 为勾选的台账 ID，逗号分隔；未传或为空时返回 400。"""
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
        "序号", "资金类别", "集团内/外项目", "采购方式", "项目实施部门", "项目编号", "合同编号",
        "工程名称", "采购项目名称", "供应商", "合同价（元）", "签订日期", "采购内容",
        "采购控制价（元）", "资金来源", "经办人", "所属主合同", "补充协议", "录入时间"
    ]
    ws.append(headers)
    for i, l in enumerate(items, 1):
        supp_str = _sync_supplement_contracts_display(db, l)
        from app.utils.format import format_date_ymd
        create_time_str = format_date_ymd(l.create_time) if l.create_time else ""
        sign_date_str = format_date_ymd(l.sign_date) if l.sign_date else ""
        officer_names = resolve_officer_names(db, l.officer or "")
        contract_price_str = format_currency_two_decimals(l.contract_price) if l.contract_price is not None else "/"
        control_price_str = format_currency_two_decimals(l.control_price) if l.control_price is not None else "/"
        ws.append([
            i, l.funding_type or "-", l.group_type, l.procurement_method, l.department, l.project_number,
            l.contract_number, l.project_name, l.procurement_name, l.supplier,
            contract_price_str, sign_date_str, l.content,
            control_price_str, l.funding_source,
            officer_names, l.parent_contract_number or "-", supp_str, create_time_str,
        ])
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
            contract_price=contract_price,
            sign_date=sign_date,
            content=content,
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
    db.commit()
    for pj_id, pc_id in created_pairs:
        emit(EventType.LEDGER_CREATED, {"project_id": pj_id, "procurement_id": pc_id})
    return {"message": "ok", "created": created}
