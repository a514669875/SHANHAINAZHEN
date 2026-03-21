"""Project (工程项目) API."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger("shanhai")

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import date
from io import BytesIO
import openpyxl
from app.database import get_db
from app.utils.format import format_date_ymd, format_currency_two_decimals
from app.utils.officer import resolve_officer_names
from app.models.user import User
from app.models.project import Project
from app.models.procurement import Procurement
from app.core.auth import get_current_user, get_authenticated_user
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import is_officer, create_project_folders, delete_project_folders, rename_project_folders
from app.services.procurement_service import sync_ledgers_on_project_update
from app.services.emit_event import emit
from app.events_schema import EventType

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_response(db: Session, p: Project) -> ProjectResponse:
    """ORM → API：附带经办人姓名字符串（服务端查库解析）。"""
    r = ProjectResponse.model_validate(p)
    return r.model_copy(
        update={
            "procurement_officer_display": resolve_officer_names(db, p.procurement_officers or ""),
        }
    )


def check_edit_permission(project: Project, current_user: User) -> None:
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无编辑权限")


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    keyword: str = Query("", description="工程编号/名称搜索"),
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0, le=50000, description="0=不分页返回全部，否则分页"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List projects with search；page_size=0 时一次返回全部（清单页滚动浏览）。"""
    q = db.query(Project)
    if keyword:
        q = q.filter(
            (Project.project_id.contains(keyword)) | (Project.project_name.contains(keyword))
        )
    q = q.order_by(Project.create_time.desc())
    if page_size == 0:
        items = q.all()
    else:
        items = q.offset((page - 1) * page_size).limit(page_size).all()
    return [_project_response(db, p) for p in items]


@router.get("/export/excel")
def export_projects_excel(
    ids: str = Query("", description="导出的工程项目ID，逗号分隔；为空时返回错误"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    """导出勾选工程项目。任意已登录用户可导出（不区分角色）。ids 为勾选的工程项目 ID，逗号分隔；未传或为空时返回 400。"""
    if not ids or not ids.strip():
        raise HTTPException(status_code=400, detail="请先勾选要导出的工程项目")
    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="请先勾选要导出的工程项目")
    if not id_list:
        raise HTTPException(status_code=400, detail="请先勾选要导出的工程项目")
    items = db.query(Project).filter(Project.id.in_(id_list)).order_by(Project.create_time.desc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "工程项目清单"
    headers = [
        "序号", "资金类别", "工程类别", "项目编号", "工程编号", "工程名称",
        "项目实施部门", "项目现场管理员", "联系方式", "发包单位", "发包方联系人", "发包方联系方式",
        "总包合同价", "工程工期", "资金来源", "材料（设备）采购经办人", "创建日期"
    ]
    ws.append(headers)
    for i, p in enumerate(items, 1):
        officer_names = resolve_officer_names(db, p.procurement_officers or "")
        total_price_str = format_currency_two_decimals(p.total_contract_price) if p.total_contract_price is not None else ""
        ws.append([
            i, p.funding_type, p.project_type, p.project_number, p.project_id,
            p.project_name, p.department, p.site_manager, p.site_manager_phone,
            p.construction_unit or "",
            getattr(p, "construction_contact_person", None) or "",
            getattr(p, "construction_contact_phone", None) or "",
            total_price_str, p.project_duration or "",
            p.funding_source, officer_names, format_date_ymd(p.create_date)
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=projects.xlsx"}
    )


@router.get("/count")
def count_projects(
    keyword: str = Query(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Project)
    if keyword:
        q = q.filter(
            (Project.project_id.contains(keyword)) | (Project.project_name.contains(keyword))
        )
    return {"total": q.count()}


@router.post("", response_model=ProjectResponse)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create project. 系统管理员可指定任意经办人；采购管理员仅可将本人设为唯一经办人。"""
    if current_user.role != "系统管理员":
        officers = [x.strip() for x in (data.procurement_officers or "").split(",") if x.strip()]
        if officers != [str(current_user.id)]:
            raise HTTPException(
                status_code=403,
                detail="采购管理员仅可将本人设为材料（设备）采购经办人，且只能选择自己",
            )

    project = Project(
        funding_type=data.funding_type,
        project_type=data.project_type,
        project_number=data.project_number,
        project_id=data.project_id,
        project_name=data.project_name,
        department=data.department,
        site_manager=data.site_manager,
        site_manager_phone=data.site_manager_phone,
        construction_unit=data.construction_unit,
        construction_contact_person=getattr(data, "construction_contact_person", None) or "",
        construction_contact_phone=getattr(data, "construction_contact_phone", None) or "",
        total_contract_price=data.total_contract_price,
        project_duration=getattr(data, "project_duration", None),
        funding_source=data.funding_source,
        project_address=data.project_address,
        procurement_officers=data.procurement_officers,
        create_date=date.today(),
    )
    db.add(project)
    db.flush()

    try:
        create_project_folders(project)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(project)
    emit(EventType.PROJECT_CREATED, {"project_id": project.id, "id": project.id})
    return _project_response(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return _project_response(db, project)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_edit_permission(project, current_user)
    old_project_id = project.project_id
    old_project_name = project.project_name
    dump = data.model_dump(exclude_unset=True)
    if current_user.role != "系统管理员" and "procurement_officers" in dump:
        officers = [x.strip() for x in (dump.get("procurement_officers") or "").split(",") if x.strip()]
        if officers != [str(current_user.id)]:
            raise HTTPException(
                status_code=403,
                detail="采购管理员不可将他人设为经办人；经办人仅能为本人，或不修改经办人字段",
            )
    for k, v in dump.items():
        setattr(project, k, v)
    if (old_project_id != project.project_id or old_project_name != project.project_name):
        try:
            rename_project_folders(project, old_project_id, old_project_name)
        except Exception as e:
            logger.exception("工程项目文件夹重命名失败: %s", e)
            raise HTTPException(status_code=500, detail=f"文件夹重命名失败: {str(e)}")
    sync_ledgers_on_project_update(db, project, old_project_id)
    db.commit()
    db.refresh(project)
    emit(EventType.PROJECT_UPDATED, {"project_id": project.id, "id": project.id})
    return _project_response(db, project)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    check_edit_permission(project, current_user)
    proc_count = db.query(Procurement).filter(Procurement.project_id == project.id).count()
    if proc_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"无法删除：该工程项目下仍有 {proc_count} 个采购项目，请先删除全部采购项目后再删除工程。",
        )
    try:
        delete_project_folders(project)
    except Exception as e:
        logger.exception("工程项目文件夹删除失败: %s", e)
    db.delete(project)
    db.commit()
    emit(EventType.PROJECT_DELETED, {"project_id": project_id, "id": project_id})
    return {"message": "ok"}
