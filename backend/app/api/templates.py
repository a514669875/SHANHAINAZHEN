"""Word template management API."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, Body
from pathlib import Path
from pydantic import BaseModel
from app.config import get_word_templates_dir, set_word_templates_dir
from app.core.auth import get_current_admin
from app.models.user import User

router = APIRouter(prefix="/api/templates", tags=["templates"])

# PRD 3.6.1: 资金类别 × 工程类别 × 采购类型 × 采购方式
FUNDING_TYPES = ["工程类", "自有资金"]
PROJECT_TYPES = ["集团内工程", "集团外工程"]
PROCUREMENT_TYPES = ["材料（设备）采购", "材料租赁", "机械租赁"]
PROCUREMENT_METHODS = ["单一来源", "邀请询比", "直接采购", "五选二", "补充协议"]


def ensure_template_dirs():
    """Create template directory structure per PRD 3.6.1."""
    base = get_word_templates_dir()
    for ft in FUNDING_TYPES:
        if ft == "自有资金":
            for prt in PROCUREMENT_TYPES:
                for pm in PROCUREMENT_METHODS:
                    (base / ft / prt / pm).mkdir(parents=True, exist_ok=True)
        else:
            for pt in PROJECT_TYPES:
                for prt in PROCUREMENT_TYPES:
                    for pm in PROCUREMENT_METHODS:
                        (base / ft / pt / prt / pm).mkdir(parents=True, exist_ok=True)


class TemplateConfigBody(BaseModel):
    word_templates_dir: str = ""


@router.get("/config")
def get_template_config(current_user: User = Depends(get_current_admin)):
    """获取模板路径配置。"""
    return {"word_templates_dir": str(get_word_templates_dir())}


@router.put("/config")
def update_template_config(
    body: TemplateConfigBody = Body(...),
    current_user: User = Depends(get_current_admin),
):
    """更新模板路径配置。路径需存在且可访问。"""
    path_str = (body.word_templates_dir or "").strip()
    if path_str:
        p = Path(path_str)
        if not p.exists():
            raise HTTPException(status_code=400, detail="路径不存在")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail="路径必须是目录")
    set_word_templates_dir(path_str)
    from app.services.emit_event import emit
    from app.events_schema import EventType
    emit(EventType.CONFIG_CHANGED, {"key": "word_templates_dir", "value": path_str})
    emit(EventType.TEMPLATE_UPDATED, {})
    return {"message": "ok", "word_templates_dir": str(get_word_templates_dir())}


@router.get("/structure")
def get_template_structure(current_user: User = Depends(get_current_admin)):
    """Get template directory structure per PRD 3.6.1."""
    base = get_word_templates_dir()
    ensure_template_dirs()
    result = []
    for ft in FUNDING_TYPES:
        if ft == "自有资金":
            for prt in PROCUREMENT_TYPES:
                for pm in PROCUREMENT_METHODS:
                    path = base / ft / prt / pm
                    files = list(path.glob("*.docx")) if path.exists() else []
                    result.append({"path": f"{ft}/{prt}/{pm}", "files": [f.name for f in files]})
        else:
            for pt in PROJECT_TYPES:
                for prt in PROCUREMENT_TYPES:
                    for pm in PROCUREMENT_METHODS:
                        path = base / ft / pt / prt / pm
                        files = list(path.glob("*.docx")) if path.exists() else []
                        result.append({"path": f"{ft}/{pt}/{prt}/{pm}", "files": [f.name for f in files]})
    return result


@router.post("/upload")
async def upload_template(
    file: UploadFile,
    funding_type: str = Form(...),
    project_type: str = Form(""),
    procurement_type: str = Form(...),
    procurement_method: str = Form(...),
    current_user: User = Depends(get_current_admin),
):
    """Upload Word template (admin only). 自有资金时 project_type 忽略。"""
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files allowed")
    ensure_template_dirs()
    base = get_word_templates_dir()
    if funding_type == "自有资金":
        target_dir = base / funding_type / procurement_type / procurement_method
    else:
        target_dir = base / funding_type / (project_type or "集团内工程") / procurement_type / procurement_method
    target_path = target_dir / file.filename
    content = await file.read()
    target_path.write_bytes(content)
    return {"message": "ok", "path": str(target_path.relative_to(base))}


@router.get("/path")
def get_template_path_api(
    funding_type: str,
    project_type: str,
    procurement_type: str,
    procurement_method: str,
    current_user: User = Depends(get_current_admin),
):
    """Get template directory path for a combination. 自有资金时 project_type 忽略。"""
    base = get_word_templates_dir()
    if funding_type == "自有资金":
        path = base / funding_type / procurement_type / procurement_method
    else:
        path = base / funding_type / (project_type or "集团内工程") / procurement_type / procurement_method
    return {"path": str(path), "exists": path.exists()}
