"""流程文件同步服务 - 表单保存时更新流程文件，支持手动修改检测与合并。

与 PRD §8.21 对应关系摘要：
- 8.21.1 / 8.21.5：SYNCED、USER_MODIFIED、OUTDATED… 及 file_mtime_at_sync
- 8.21.2：列表接口 mtime 自动检测；本模块将「检测 + 是否写库」集中实现
- 8.21.3：sync_process_files_on_form_save
"""
import shutil
import logging
import time
from datetime import datetime
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

# ---- PRD 8.21.2 列表 mtime 检测参数（误报防护与人工修改识别的平衡）----
MTIME_DRIFT_TOLERANCE_SEC = 2.0
# 采购项目创建后、或同步表记录新建后一段时间内：mtime 漂移一律只刷新基线（须先于「超大漂移」判断，否则异常小的 stored 会误判）
POST_CREATE_MTIME_RECONCILE_WINDOW_SEC = 72 * 3600
# 仅用于「老项目」：漂移极大且已超出上述窗口时，仍判为需关注（防时钟错乱等）
MAX_MTIME_DRIFT_BEFORE_FORCE_USER_MODIFIED_SEC = 7 * 86400
# 小于此值的 stored 视为无效基线（脏数据/未正确写入），按缺失处理
MIN_VALID_MTIME_SYNC_EPOCH = 946684800.0  # 2000-01-01 起算的常见 st_mtime


def _naive_datetime(dt):
    if dt is None:
        return None
    try:
        if getattr(dt, "tzinfo", None) is not None:
            return dt.replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _in_mtime_baseline_reconcile_window(proc: Procurement, row: ProcessFileSyncStatus) -> bool:
    """新建后短期内：杀毒/索引等导致的 mtime 变化只刷新基线（PRD 8.21.2 实现补充）。"""
    now = datetime.utcnow()
    ct = _naive_datetime(getattr(proc, "create_time", None))
    if ct is not None:
        try:
            if (now - ct).total_seconds() <= POST_CREATE_MTIME_RECONCILE_WINDOW_SEC:
                return True
        except Exception:
            pass
    ca = _naive_datetime(getattr(row, "created_at", None))
    if ca is not None:
        try:
            if (now - ca).total_seconds() <= POST_CREATE_MTIME_RECONCILE_WINDOW_SEC:
                return True
        except Exception:
            pass
    return False


def apply_process_list_mtime_detection_to_row(
    proc: Procurement,
    row: ProcessFileSyncStatus,
    current_mtime: float,
    has_outdated_merge_backup: bool,
) -> str:
    """
    PRD 8.21.2 / 8.21.6：GET process-list 时对单条 sync 记录与磁盘文件做 mtime 探测。
    可能修改 row.sync_status、row.file_mtime_at_sync；调用方负责 db.commit。

    返回前端展示的 sync_status 字符串（与 DB 中常量一致）。
    """
    st = row.sync_status or SYNCED

    if st == OUTDATED_MANUAL_MERGE_REQUIRED:
        if not has_outdated_merge_backup:
            row.sync_status = SYNCED
            row.file_mtime_at_sync = current_mtime
            return SYNCED
        return OUTDATED_MANUAL_MERGE_REQUIRED

    if st == USER_MODIFIED:
        return USER_MODIFIED

    if st != SYNCED:
        return st

    stored = row.file_mtime_at_sync
    if (
        stored is None
        or not isinstance(stored, (int, float))
        or stored != stored  # NaN
        or stored < MIN_VALID_MTIME_SYNC_EPOCH
    ):
        row.file_mtime_at_sync = current_mtime
        return SYNCED

    if current_mtime <= stored + MTIME_DRIFT_TOLERANCE_SEC:
        return SYNCED

    drift = current_mtime - stored

    # 必须先于「超大漂移」：新建后 stored 异常会导致 drift 极大，否则会被误判为 USER_MODIFIED
    if _in_mtime_baseline_reconcile_window(proc, row):
        row.file_mtime_at_sync = current_mtime
        return SYNCED

    if drift > MAX_MTIME_DRIFT_BEFORE_FORCE_USER_MODIFIED_SEC:
        row.sync_status = USER_MODIFIED
        return USER_MODIFIED

    row.sync_status = USER_MODIFIED
    return USER_MODIFIED


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


def snap_sync_status_mtimes_from_disk(db: Session, procurement_id: int, folder_path: Path | None) -> None:
    """
    在 db.commit() 之后调用：再次从磁盘读取各流程文件 mtime 写回 DB。
    避免生成后短时间内杀软/索引改写文件导致「记录偏旧」，首次 GET process-list 误判 USER_MODIFIED。
    """
    if folder_path is None or not folder_path.exists() or not folder_path.is_dir():
        return
    time.sleep(0.12)
    rows = db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == procurement_id,
    ).all()
    for row in rows:
        fp = folder_path / row.filename
        if fp.is_file():
            row.file_mtime_at_sync = fp.stat().st_mtime
    db.commit()


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
        # 两轮写入 mtime：生成刚结束时有进程可能仍在落盘，首轮与次轮间隔可减少「记录偏旧」
        for _pass in (1, 2):
            for fn in filenames:
                fp = folder_path / fn
                if fp.exists():
                    row = db.query(ProcessFileSyncStatus).filter(
                        ProcessFileSyncStatus.procurement_id == primary_id,
                        ProcessFileSyncStatus.filename == fn,
                    ).first()
                    if row:
                        row.file_mtime_at_sync = fp.stat().st_mtime
            if _pass == 1:
                time.sleep(0.15)


def reset_sync_status_records_for_new_procurement(db: Session, procurement_id: int) -> None:
    """新建采购项目前清空同 procurement_id 的历史状态，避免旧库残留导致新项目误显示 USER_MODIFIED。"""
    db.query(ProcessFileSyncStatus).filter(
        ProcessFileSyncStatus.procurement_id == procurement_id,
    ).delete(synchronize_session=False)


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


