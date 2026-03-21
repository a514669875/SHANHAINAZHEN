"""File API - upload, list, download (with proxy for distributed)."""
import os
import sys
import subprocess
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pathlib import Path
from app.database import get_db
from app.models.user import User
from app.models.file import File
from app.models.procurement import Procurement
from app.models.project import Project
from app.models.ledger import Ledger
from app.core.auth import get_current_user
from app.services.project_service import is_officer
from app.services.file_proxy_service import proxy_file_from_client
from app.services.archive_service import (
    get_temp_path,
    try_archive_and_create_ledgers,
    find_dual_sibling,
    get_archive_contract_folder,
    count_contract_files_in_temp,
    count_contract_files,
)
from app.services.procurement_service import get_process_folder_for_procurement
from app.services.process_file_sync_service import (
    get_primary_procurement_id,
    ensure_sync_status_records,
    USER_MODIFIED,
    OUTDATED_MANUAL_MERGE_REQUIRED,
    prune_temp_versions_on_confirm,
)
from app.models.process_file_sync_status import ProcessFileSyncStatus
from app.config import ARCHIVED_FILE_ROOT, PROCUREMENT_PROCESS_ROOT
from app.services.emit_event import emit
from app.events_schema import EventType

router = APIRouter(prefix="/api/files", tags=["files"])


def _contract_file_for_ledger(f: File) -> bool:
    """合同文件：布尔字段或历史数据里 file_type 标记。"""
    if getattr(f, "is_contract", False):
        return True
    return (getattr(f, "file_type", None) or "") == "合同文件"


def _can_read_file_content(db: Session, current_user: User, f: File) -> bool:
    """归档/合同文件读取权限：管理员；项目经办人；采购管理员且为智能台账关联的合同（含五选二另一标段、pdf_preview_path 指向）。"""
    if current_user.role == "系统管理员":
        return True
    proc = db.query(Procurement).filter(Procurement.id == f.procurement_id).first()
    if not proc:
        return False
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        return False
    if is_officer(project, current_user.id):
        return True
    if current_user.role == "采购管理员" and _contract_file_for_ledger(f):
        proc_ids = [f.procurement_id]
        if proc.procurement_method == "五选二":
            sibling = find_dual_sibling(db, proc)
            if sibling:
                proc_ids = [proc.id, sibling.id]
        if db.query(Ledger).filter(Ledger.procurement_id.in_(proc_ids)).first():
            return True
        # 台账行与文件可能分属五选二两标段时，归档写入的 pdf_preview_path 仍指向该 file id
        needle = f"/api/files/{f.id}/content"
        if db.query(Ledger).filter(Ledger.pdf_preview_path.isnot(None), Ledger.pdf_preview_path.contains(needle)).first():
            return True
    return False


@router.get("")
def list_files(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List files for a procurement. For 五选二, returns files from both 标段."""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    proc_ids = [procurement_id]
    if proc.procurement_method == "五选二":
        sibling = find_dual_sibling(db, proc)
        if sibling:
            proc_ids = [proc.id, sibling.id]
    items = db.query(File).filter(File.procurement_id.in_(proc_ids)).order_by(File.upload_time.desc()).all()
    return items


@router.get("/process-list")
def list_process_files(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List process files (Word) for a procurement - files in procurement专属文件夹，附带 sync_status。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    process_folder = get_process_folder_for_procurement(project, proc, db)
    primary_id = get_primary_procurement_id(db, proc)
    status_rows = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == primary_id,
    ).all()
    status_map = {r.filename: r for r in status_rows}
    temp_dir = process_folder / "temp_versions" if process_folder.exists() else None

    def _has_temp_backup(filename: str) -> bool:
        """OUTDATED_MANUAL_MERGE_REQUIRED 需有 temp_versions 备份才成立，否则视为异常数据。支持 .bak 与 _backup_{ts}.docx 两种格式。"""
        if not temp_dir or not temp_dir.exists():
            return False
        base = filename.rsplit(".", 1)[0] if "." in filename else filename
        ext = filename.rsplit(".", 1)[1] if "." in filename else "docx"
        for p in temp_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith(filename) and p.suffix == ".bak":
                return True
            if p.name.startswith(f"{base}_backup_") and p.suffix == f".{ext}":
                return True
        return False

    result = []
    rows_to_fix = []
    if process_folder.exists():
        for f in process_folder.iterdir():
            if f.is_file() and not f.name.startswith("."):
                size = f.stat().st_size
                current_mtime = f.stat().st_mtime
                row = status_map.get(f.name)
                sync_status = "SYNCED"
                if row:
                    sync_status = row.sync_status
                    # 需人工合并：必须有 temp_versions 备份，否则为异常数据（如新建项目误标），按已同步处理并修正 DB
                    if sync_status == OUTDATED_MANUAL_MERGE_REQUIRED and not _has_temp_backup(f.name):
                        sync_status = "SYNCED"
                        row.sync_status = "SYNCED"
                        row.file_mtime_at_sync = current_mtime
                        rows_to_fix.append(row)
                    # 自动检测：文件 mtime 晚于记录值，视为用户手动修改（容差 2 秒，避免时钟/精度误判）
                    # 必须持久化到 DB，否则表单保存时会按 SYNCED 直接覆盖，导致 temp_versions 未创建
                    elif (
                        sync_status == "SYNCED"
                        and row.file_mtime_at_sync is not None
                        and current_mtime > row.file_mtime_at_sync + 2
                    ):
                        sync_status = "USER_MODIFIED"
                        row.sync_status = USER_MODIFIED
                        rows_to_fix.append(row)
                result.append({
                    "name": f.name,
                    "size": f"{size / 1024:.1f} KB",
                    "sync_status": sync_status,
                })
    if rows_to_fix:
        db.commit()
    return result


@router.post("/process-file-mark-modified")
def mark_process_file_modified(
    procurement_id: int = Query(...),
    filename: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户点击「我已手动修改」：将 sync_status 设为 USER_MODIFIED。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    primary_id = get_primary_procurement_id(db, proc)
    row = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == primary_id,
        ProcessFileSyncStatus.filename == filename,
    ).first()
    if not row:
        db.add(ProcessFileSyncStatus(
            procurement_id=primary_id,
            filename=filename,
            sync_status=USER_MODIFIED,
        ))
    else:
        row.sync_status = USER_MODIFIED
    db.commit()
    emit(EventType.PROCESS_FILE_SYNC_STATUS_CHANGED, {"procurement_id": procurement_id, "project_id": proc.project_id})
    return {"message": "ok"}


@router.post("/process-file-confirm-merge")
def confirm_process_file_merge(
    procurement_id: int = Query(...),
    filename: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户点击「确认更新并完成合并」：状态改为 USER_MODIFIED，temp_versions 仅保留最近 2 个备份。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    primary_id = get_primary_procurement_id(db, proc)
    row = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == primary_id,
        ProcessFileSyncStatus.filename == filename,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="同步状态记录不存在")
    if row.sync_status != OUTDATED_MANUAL_MERGE_REQUIRED:
        raise HTTPException(status_code=400, detail="当前状态不允许确认合并")
    row.sync_status = USER_MODIFIED
    prune_temp_versions_on_confirm(primary_id, filename, db)
    db.commit()
    emit(EventType.PROCESS_FILE_SYNC_STATUS_CHANGED, {"procurement_id": procurement_id, "project_id": proc.project_id})
    return {"message": "ok"}


@router.get("/process-content")
def get_process_file_content(
    procurement_id: int,
    filename: str = Query(..., description="文件名"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """下载流程文件（Word等）供预览/打印。五选二共享同一采购项目专属文件夹；补充协议使用专属文件夹。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    process_folder = get_process_folder_for_procurement(project, proc, db)
    file_path = process_folder / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(file_path, filename=filename)


@router.post("/process-file-open")
def open_process_file_for_edit(
    procurement_id: int = Query(...),
    filename: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """直接打开流程文件（用系统默认应用，如 Word）。需后端与用户同机时有效。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    process_folder = get_process_folder_for_procurement(project, proc, db)
    file_path = process_folder / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    if _open_file_in_default_app(file_path):
        return {"message": "ok"}
    return {"message": "download", "detail": "无法直接打开，请使用下载方式"}


@router.delete("/process-file")
def delete_process_file(
    procurement_id: int,
    filename: str = Query(..., description="文件名"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除流程文件（从采购项目专属文件夹）。五选二共享同一采购项目专属文件夹；补充协议使用专属文件夹。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    process_folder = get_process_folder_for_procurement(project, proc, db)
    file_path = process_folder / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path.unlink()
    return {"message": "ok"}


def _get_process_folder_path(db: Session, procurement_id: int, current_user: User) -> Path:
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    return get_process_folder_for_procurement(project, proc, db)


def _get_archive_folder_path(db: Session, procurement_id: int, current_user: User) -> Path:
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    is_dual = proc.procurement_method == "五选二"
    if is_dual:
        sibling = find_dual_sibling(db, proc)
        contract_folder = get_archive_contract_folder(project, proc, sibling) if sibling else ""
    else:
        contract_folder = proc.contract_number or ""
    archive_base = ARCHIVED_FILE_ROOT / f"{project.project_id}材料（设备）合同"
    return archive_base / contract_folder if contract_folder else archive_base


def _open_folder_in_explorer(folder_path: Path) -> bool:
    """在系统资源管理器中打开文件夹。返回是否成功。"""
    import subprocess
    import sys
    path_str = str(folder_path.resolve())
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", path_str], check=False)
        elif sys.platform == "darwin":
            subprocess.run(["open", path_str], check=False)
        else:
            subprocess.run(["xdg-open", path_str], check=False)
        return True
    except Exception:
        return False


def _open_file_in_default_app(file_path: Path) -> bool:
    """用系统默认应用打开文件（如 Word 打开 docx）。返回是否成功。"""
    path_str = str(file_path.resolve())
    if not file_path.exists() or not file_path.is_file():
        return False
    try:
        if sys.platform == "win32":
            os.startfile(path_str)
        elif sys.platform == "darwin":
            subprocess.run(["open", path_str], check=False)
        else:
            subprocess.run(["xdg-open", path_str], check=False)
        return True
    except Exception:
        return False


@router.get("/process-folder-path")
def get_process_folder_path(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回流程文件专属文件夹的本地路径。"""
    folder = _get_process_folder_path(db, procurement_id, current_user)
    return {"path": str(folder.resolve())}


@router.post("/process-folder-open")
def open_process_folder(
    procurement_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """直接打开流程文件专属文件夹。后端执行 explorer/open 命令；若失败则返回路径供前端复制。"""
    folder = _get_process_folder_path(db, procurement_id, current_user)
    try:
        if _open_folder_in_explorer(folder):
            return {"message": "ok"}
    except Exception:
        pass
    return {"message": "path", "path": str(folder.resolve())}


@router.get("/archive-folder-path")
def get_archive_folder_path(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回归档文件专属文件夹的本地路径。"""
    folder = _get_archive_folder_path(db, procurement_id, current_user)
    return {"path": str(folder.resolve())}


@router.post("/archive-folder-open")
def open_archive_folder(
    procurement_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """直接打开归档文件专属文件夹。后端执行 explorer/open 命令；若失败则返回路径供前端复制。"""
    folder = _get_archive_folder_path(db, procurement_id, current_user)
    try:
        if _open_folder_in_explorer(folder):
            return {"message": "ok"}
    except Exception:
        pass
    return {"message": "path", "path": str(folder.resolve())}


@router.get("/archive-status")
def get_archive_status(
    procurement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get archive progress: required count and uploaded contract count."""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    is_dual = proc.procurement_method == "五选二"
    if is_dual:
        sibling = find_dual_sibling(db, proc)
        proc_ids = [proc.id, sibling.id] if sibling else [proc.id]
        required = 2 if sibling else 1
    else:
        proc_ids = [proc.id]
        required = 1
    uploaded = count_contract_files(db, proc_ids)
    return {"required": required, "uploaded": uploaded, "is_dual": is_dual}


@router.patch("/{file_id}")
def update_file(
    file_id: int,
    print_mode: str = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update file (e.g. print_mode)."""
    f = db.query(File).filter(File.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    proc = db.query(Procurement).filter(Procurement.id == f.procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    if print_mode is not None:
        f.print_mode = print_mode
    db.commit()
    db.refresh(f)
    return f


@router.delete("/{file_id}")
def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete file and physical file. If contract file, unlink ledger pdf_preview_path to avoid duplicate on re-upload."""
    f = db.query(File).filter(File.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    proc = db.query(Procurement).filter(Procurement.id == f.procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")
    if f.is_contract:
        ledger = db.query(Ledger).filter(Ledger.procurement_id == f.procurement_id).first()
        if ledger and ledger.pdf_preview_path:
            ledger.pdf_preview_path = None
    full_path = ARCHIVED_FILE_ROOT / f.file_path
    if full_path.exists():
        full_path.unlink()
    db.delete(f)
    db.commit()
    emit(EventType.FILE_DELETED, {"project_id": project.id, "procurement_id": proc.id, "file_id": f.id})
    return {"message": "ok"}


@router.get("/{file_id}/content")
def get_file_content(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file - proxy from client if distributed, else local."""
    f = db.query(File).filter(File.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="文件不存在")
    if not _can_read_file_content(db, current_user, f):
        raise HTTPException(status_code=403, detail="无权限查看该文件")
    local_path = ARCHIVED_FILE_ROOT / f.file_path
    # 单机/本机开发：文件实际在后端归档目录，但库中仍带 storage_computer_ip，优先读本地避免 8001 路径不一致导致 404→500
    if local_path.is_file():
        return FileResponse(local_path, filename=f.file_name)
    if f.storage_computer_ip:
        owner = db.query(User).filter(User.id == f.owner_user_id).first()
        port = owner.file_service_port if owner and owner.file_service_port else 8001
        resp = proxy_file_from_client(
            f.storage_computer_ip,
            port,
            f.file_path,
            f.file_name,
        )
        return StreamingResponse(resp.iter_content(8192), media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="文件不存在")


def _parse_form_bool(v) -> bool:
    """Form 传参为字符串，需显式解析 true/false。"""
    if v is True or v is False:
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes", "on")
    return bool(v)


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    procurement_id: int = Form(...),
    is_contract: str = Form("false"),
    print_mode: str = Form("单面"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload file. 暂存到 _temp/，勾选合同且台账条件满足时创建归档文件夹并生成台账。"""
    proc = db.query(Procurement).filter(Procurement.id == procurement_id).first()
    if not proc:
        raise HTTPException(status_code=404, detail="采购项目不存在")
    proc_ids = [procurement_id]
    if proc.procurement_method == "五选二":
        sibling = find_dual_sibling(db, proc)
        if sibling:
            proc_ids = [proc.id, sibling.id]
    existing = db.query(File).filter(File.procurement_id.in_(proc_ids), File.file_name == file.filename).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"文件名「{file.filename}」已存在，请重命名后上传")
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if current_user.role != "系统管理员" and not is_officer(project, current_user.id):
        raise HTTPException(status_code=403, detail="无权限")

    # 暂存路径: _temp/{project_id}/{procurement_id}/{filename}
    rel_path = get_temp_path(project.id, procurement_id, file.filename)
    full_path = ARCHIVED_FILE_ROOT / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    full_path.write_bytes(content)

    is_contract_val = _parse_form_bool(is_contract)
    f = File(
        procurement_id=procurement_id,
        file_name=file.filename,
        file_path=rel_path,
        file_size=len(content),
        file_type="合同文件" if is_contract_val else "普通文件",
        is_contract=is_contract_val,
        print_mode=print_mode,
        owner_user_id=current_user.id,
        storage_computer_ip=current_user.computer_ip or "",
        storage_path=str(full_path),
    )
    db.add(f)
    db.flush()

    ledger_created = False
    if is_contract_val:
        ledger_created = try_archive_and_create_ledgers(db, project, proc, f)

    db.commit()
    db.refresh(f)
    emit(EventType.FILE_UPLOADED, {"project_id": project.id, "procurement_id": procurement_id, "file_id": f.id})
    if ledger_created:
        proc_ids = [procurement_id]
        if proc.procurement_method == "五选二":
            sib = find_dual_sibling(db, proc)
            if sib:
                proc_ids = [proc.id, sib.id]
        for pid in proc_ids:
            emit(EventType.LEDGER_CREATED, {"project_id": project.id, "procurement_id": pid})
    return f
