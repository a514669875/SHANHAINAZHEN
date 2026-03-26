"""流程文件同步服务 - 表单保存时更新流程文件，支持手动修改检测与合并。"""
import shutil
import logging
from pathlib import Path
from sqlalchemy.orm import Session
from app.models.process_file_sync_status import ProcessFileSyncStatus
from app.models.procurement import Procurement
from app.models.project import Project
from app.services.procurement_service import get_process_folder_for_procurement
from app.services.word_service import (
    _project_to_dict,
    build_context,
    get_template_path,
    render_docx,
)
from app.services.archive_service import find_dual_sibling

logger = logging.getLogger("shanhai")

SYNCED = "SYNCED"
USER_MODIFIED = "USER_MODIFIED"
OUTDATED_MANUAL_MERGE_REQUIRED = "OUTDATED_MANUAL_MERGE_REQUIRED"
TEMP_VERSIONS_DIR = "temp_versions"
MAX_BACKUPS = 2


def _parse_form_data(form_data: str) -> dict:
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


def get_primary_procurement_id(db: Session, proc: Procurement) -> int:
    """五选二共享同一文件夹，使用一标段 procurement_id 作为 sync_status 的 key。"""
    if proc.procurement_method == "五选二":
        sibling = find_dual_sibling(db, proc)
        if sibling:
            a, b = (proc, sibling) if proc.contract_section == "一标段" else (sibling, proc)
            return a.id
    return proc.id


def ensure_sync_status_records(db: Session, procurement_id: int, filenames: list, folder_path: Path = None) -> None:
    """确保每个流程文件都有 sync_status 记录，缺失则创建为 SYNCED。若提供 folder_path，同时设置 file_mtime_at_sync。"""
    primary_id = procurement_id
    for fn in filenames:
        existing = db.query(ProcessFileSyncStatus).filter(
            ProcessFileSyncStatus.procurement_id == primary_id,
            ProcessFileSyncStatus.filename == fn,
        ).first()
        if not existing:
            db.add(ProcessFileSyncStatus(
                procurement_id=primary_id,
                filename=fn,
                sync_status=SYNCED,
            ))
    db.flush()
    if folder_path and folder_path.exists():
        for fn in filenames:
            fp = folder_path / fn
            if fp.exists():
                row = db.query(ProcessFileSyncStatus).filter(
                    ProcessFileSyncStatus.procurement_id == primary_id,
                    ProcessFileSyncStatus.filename == fn,
                ).first()
                if row:
                    row.file_mtime_at_sync = fp.stat().st_mtime


def sync_process_files_on_form_save(
    db: Session,
    project: Project,
    proc: Procurement,
    step1: dict,
    step2: dict,
    suppliers_data: list,
    time_records: list,
    time_records_only: bool = False,
) -> None:
    """
    表单保存时触发：根据 sync_status 更新流程文件。
    - time_records_only=True：仅更新 目录.docx，其余流程文件禁止生成或替换
    - SYNCED: 用新数据覆盖
    - USER_MODIFIED: 备份到 temp_versions，生成新文件，设为 OUTDATED_MANUAL_MERGE_REQUIRED
    """
    primary_id = get_primary_procurement_id(db, proc)
    process_folder = get_process_folder_for_procurement(project, proc, db)
    if not process_folder.exists():
        logger.warning("流程文件同步跳过：专属文件夹不存在 %s", process_folder)
        return
    if time_records_only:
        # 仅流程时间表变更：只更新 目录.docx
        mulu_path = process_folder / "目录.docx"
        if mulu_path.exists():
            from app.api.procurements import _save_mulu_docx
            title = f"{project.project_id}{project.project_name or ''}{step2.get('content', '')}"
            status_row = db.query(ProcessFileSyncStatus).filter(
                ProcessFileSyncStatus.procurement_id == primary_id,
                ProcessFileSyncStatus.filename == "目录.docx",
            ).first()
            if status_row and status_row.sync_status == USER_MODIFIED:
                _backup_and_regenerate_mulu(process_folder, title, time_records, status_row)
            elif status_row and status_row.sync_status == SYNCED:
                _save_mulu_docx(process_folder, title, time_records)
                _update_file_mtime_after_sync(status_row, process_folder / "目录.docx")
            elif not status_row:
                ensure_sync_status_records(db, primary_id, ["目录.docx"], process_folder)
                _save_mulu_docx(process_folder, title, time_records)
                status_row = db.query(ProcessFileSyncStatus).filter(
                    ProcessFileSyncStatus.procurement_id == primary_id,
                    ProcessFileSyncStatus.filename == "目录.docx",
                ).first()
                if status_row:
                    _update_file_mtime_after_sync(status_row, process_folder / "目录.docx")
        return
    tpl_dir = get_template_path(
        project.funding_type,
        project.project_type,
        proc.procurement_type,
        proc.procurement_method,
    )
    ctx = build_context(
        _project_to_dict(project),
        step1,
        step2,
        suppliers_data,
        winner_idx=1 if (proc.procurement_method == "五选二" and proc.contract_section == "二标段") else 0,
    )
    template_docx_list = list(tpl_dir.glob("*.docx")) if tpl_dir.exists() else []
    if not tpl_dir.exists():
        logger.info("流程文件同步：模板目录不存在 %s，仅处理目录.docx", tpl_dir)
    for tpl_docx in template_docx_list:
        _sync_one_file(db, primary_id, process_folder, tpl_docx.name, tpl_docx, ctx)
    # 目录.docx 由 _save_mulu_docx 生成，需单独处理
    mulu_path = process_folder / "目录.docx"
    if mulu_path.exists():
        from app.api.procurements import _save_mulu_docx
        title = f"{project.project_id}{project.project_name or ''}{step2.get('content', '')}"
        status_row = db.query(ProcessFileSyncStatus).filter(
            ProcessFileSyncStatus.procurement_id == primary_id,
            ProcessFileSyncStatus.filename == "目录.docx",
        ).first()
        if status_row and status_row.sync_status == USER_MODIFIED:
            _backup_and_regenerate_mulu(process_folder, title, time_records, status_row)
        elif status_row and status_row.sync_status == SYNCED:
            _save_mulu_docx(process_folder, title, time_records)
            _update_file_mtime_after_sync(status_row, process_folder / "目录.docx")
        elif not status_row:
            ensure_sync_status_records(db, primary_id, ["目录.docx"], process_folder)
            _save_mulu_docx(process_folder, title, time_records)
            status_row = db.query(ProcessFileSyncStatus).filter(
                ProcessFileSyncStatus.procurement_id == primary_id,
                ProcessFileSyncStatus.filename == "目录.docx",
            ).first()
            if status_row:
                _update_file_mtime_after_sync(status_row, process_folder / "目录.docx")


def _sync_one_file(db: Session, primary_id: int, folder: Path, filename: str, template_path: Path, ctx: dict) -> None:
    status_row = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == primary_id,
        ProcessFileSyncStatus.filename == filename,
    ).first()
    if not status_row:
        ensure_sync_status_records(db, primary_id, [filename])
        status_row = db.query(ProcessFileSyncStatus).filter(
            ProcessFileSyncStatus.procurement_id == primary_id,
            ProcessFileSyncStatus.filename == filename,
        ).first()
    file_path = folder / filename
    if not file_path.exists():
        return
    if status_row.sync_status == SYNCED:
        render_docx(template_path, ctx, file_path)
        _update_file_mtime_after_sync(status_row, file_path)
    elif status_row.sync_status == USER_MODIFIED:
        _backup_and_regenerate(db, primary_id, folder, filename, template_path, ctx, status_row)


def _update_file_mtime_after_sync(status_row, file_path: Path) -> None:
    """同步后更新记录的 file_mtime_at_sync。"""
    if file_path.exists():
        status_row.file_mtime_at_sync = file_path.stat().st_mtime


def _backup_and_regenerate(
    db: Session, primary_id: int, folder: Path, filename: str,
    template_path: Path, ctx: dict, status_row,
) -> None:
    """USER_MODIFIED 时：备份到 temp_versions，生成新文件，设为 OUTDATED_MANUAL_MERGE_REQUIRED。
    步骤 A: 创建 temp_versions；步骤 B: 移存旧文件为 {原文件名}_backup_{timestamp}.docx；
    步骤 C: 用新数据生成新文件；步骤 D: 状态设为 OUTDATED_MANUAL_MERGE_REQUIRED。"""
    import time
    file_path = folder / filename
    temp_dir = folder / TEMP_VERSIONS_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    base = filename.rsplit(".", 1)[0] if "." in filename else filename
    ext = filename.rsplit(".", 1)[1] if "." in filename else "docx"
    backup_name = f"{base}_backup_{int(time.time())}.{ext}"
    shutil.copy2(file_path, temp_dir / backup_name)
    _prune_backups(temp_dir, base, MAX_BACKUPS, ext)
    render_docx(template_path, ctx, file_path)
    _update_file_mtime_after_sync(status_row, file_path)
    status_row.sync_status = OUTDATED_MANUAL_MERGE_REQUIRED


def _backup_and_regenerate_mulu(folder: Path, title: str, time_records: list, status_row) -> None:
    """目录.docx 的备份与重新生成。"""
    import time
    from app.api.procurements import _save_mulu_docx
    file_path = folder / "目录.docx"
    temp_dir = folder / TEMP_VERSIONS_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    backup_name = f"目录_backup_{int(time.time())}.docx"
    shutil.copy2(file_path, temp_dir / backup_name)
    _prune_backups(temp_dir, "目录", MAX_BACKUPS, "docx")
    _save_mulu_docx(folder, title, time_records)
    _update_file_mtime_after_sync(status_row, file_path)
    status_row.sync_status = OUTDATED_MANUAL_MERGE_REQUIRED


def prune_temp_versions_on_confirm(primary_id: int, filename: str, db: Session) -> None:
    """确认合并后：temp_versions 仅保留最近 2 个备份。"""
    status_row = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == primary_id,
        ProcessFileSyncStatus.filename == filename,
    ).first()
    if not status_row:
        return
    # 需要 folder 路径，从 procurement 反查
    proc = db.query(Procurement).filter(Procurement.id == primary_id).first()
    if not proc:
        return
    project = db.query(Project).filter(Project.id == proc.project_id).first()
    if not project:
        return
    folder = get_process_folder_for_procurement(project, proc, db)
    temp_dir = folder / TEMP_VERSIONS_DIR
    if temp_dir.exists():
        _prune_backups(temp_dir, filename, MAX_BACKUPS)


def _prune_backups(temp_dir: Path, filename_base: str, keep: int, ext: str = "docx") -> None:
    """保留最近 keep 个备份，删除更早的。支持 _backup_{timestamp}.docx 与 .{timestamp}.bak 两种格式。"""
    base_no_ext = filename_base.rsplit(".", 1)[0] if "." in filename_base else filename_base

    def _is_backup(f: Path) -> bool:
        if not f.is_file():
            return False
        return (
            (f.name.startswith(filename_base) and f.suffix == ".bak")
            or (f.name.startswith(f"{base_no_ext}_backup_") and f.suffix == f".{ext}")
        )
    backups = sorted(
        [f for f in temp_dir.iterdir() if _is_backup(f)],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for f in backups[keep:]:
        try:
            f.unlink()
        except OSError:
            pass


