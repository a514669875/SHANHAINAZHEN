"""Project service - folder creation logic per PRD 3.1.3."""
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import PROCUREMENT_PROCESS_ROOT, ARCHIVED_FILE_ROOT
from app.models.project import Project


def delete_project_folders(project: Project) -> None:
    """Delete project folders and contents per PRD 4.3."""
    process_folder_name = f"{project.project_id} {project.project_name}"
    process_path = PROCUREMENT_PROCESS_ROOT / process_folder_name
    archive_folder_name = f"{project.project_id}材料（设备）合同"
    archive_path = ARCHIVED_FILE_ROOT / archive_folder_name
    if process_path.exists():
        shutil.rmtree(process_path)
    if archive_path.exists():
        shutil.rmtree(archive_path)


def is_officer(project: Project, user_id: int) -> bool:
    """Check if user is in procurement_officers list."""
    if not project.procurement_officers:
        return False
    officers = [x.strip() for x in project.procurement_officers.split(",") if x.strip()]
    return str(user_id) in officers


def rename_project_folders(project: Project, old_project_id: str, old_project_name: str) -> None:
    """Rename project folders when project_id or project_name changes."""
    old_process = PROCUREMENT_PROCESS_ROOT / f"{old_project_id} {old_project_name}"
    old_archive = ARCHIVED_FILE_ROOT / f"{old_project_id}材料（设备）合同"
    new_process = PROCUREMENT_PROCESS_ROOT / f"{project.project_id} {project.project_name}"
    new_archive = ARCHIVED_FILE_ROOT / f"{project.project_id}材料（设备）合同"
    if old_process.exists() and old_process != new_process:
        old_process.rename(new_process)
    if old_archive.exists() and old_archive != new_archive:
        old_archive.rename(new_archive)


def create_project_folders(project: Project) -> tuple[Path, Path]:
    """
    Create project folders per PRD 3.1.3.
    Returns (process_folder_path, archive_folder_path).
    """
    # 工程项目专属文件夹: 工程编号 + 空格 + 工程名称
    process_folder_name = f"{project.project_id} {project.project_name}"
    process_path = PROCUREMENT_PROCESS_ROOT / process_folder_name

    # 工程项目归档专属文件夹: 工程编号 + 材料（设备）合同
    archive_folder_name = f"{project.project_id}材料（设备）合同"
    archive_path = ARCHIVED_FILE_ROOT / archive_folder_name

    # Check for duplicate names (global constraint)
    if process_path.exists():
        raise ValueError(f"工程项目专属文件夹已存在: {process_folder_name}")
    if archive_path.exists():
        raise ValueError(f"工程项目归档专属文件夹已存在: {archive_folder_name}")

    process_path.mkdir(parents=True, exist_ok=True)
    archive_path.mkdir(parents=True, exist_ok=True)

    return process_path, archive_path
