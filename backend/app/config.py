"""Application configuration."""
import json
import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent


def get_static_dist_dir() -> Path | None:
    """生产模式：前端构建目录（含 index.html）。未找到则返回 None，根路径仍返回 JSON API 提示。

    优先级：
    1. 环境变量 SHANHAI_STATIC_DIST（绝对或相对路径，相对 cwd）
    2. backend/web/dist（便于「仅拷贝 backend+dist」单目录分发）
    3. 仓库 frontend/dist（开发机 npm build 后直接 uvicorn）
    """
    candidates: list[Path] = []
    env = os.getenv("SHANHAI_STATIC_DIST", "").strip()
    if env:
        candidates.append(Path(env))
    candidates.append(BASE_DIR / "web" / "dist")
    candidates.append(REPO_ROOT / "frontend" / "dist")
    for p in candidates:
        try:
            resolved = p.resolve()
        except OSError:
            continue
        if resolved.is_dir() and (resolved / "index.html").is_file():
            return resolved
    return None


DATABASE_DIR = BASE_DIR / "database"
# 测试或独立部署时可设置环境变量 SHANHAI_DATABASE_PATH 指向其它 SQLite 文件
if os.getenv("SHANHAI_DATABASE_PATH"):
    DATABASE_PATH = Path(os.environ["SHANHAI_DATABASE_PATH"])
else:
    DATABASE_PATH = DATABASE_DIR / "shanhai.db"
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"

# Default template dir (used when no config override)
_DEFAULT_WORD_TEMPLATES_DIR = BASE_DIR / "word_templates"


def get_word_templates_dir() -> Path:
    """获取 Word 模板根目录。优先从 config.json 读取，其次环境变量，最后默认路径。"""
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, encoding="utf-8") as f:
                d = json.load(f)
                p = d.get("word_templates_dir")
                if p and str(p).strip():
                    return Path(p)
    except Exception:
        pass
    env_path = os.getenv("WORD_TEMPLATES_DIR")
    if env_path and str(env_path).strip():
        return Path(env_path)
    return _DEFAULT_WORD_TEMPLATES_DIR


def set_word_templates_dir(path: str) -> None:
    """保存模板路径到 config.json。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["word_templates_dir"] = path.strip() if path else ""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# 兼容旧代码直接引用
WORD_TEMPLATES_DIR = get_word_templates_dir()

# 流程/归档根目录：默认均在运行后端的 backend/data 下（集中存储）
PROCUREMENT_PROCESS_ROOT = Path(os.getenv("PROCUREMENT_PROCESS_ROOT", str(DATA_DIR / "procurement_process")))
ARCHIVED_FILE_ROOT = Path(os.getenv("ARCHIVED_FILE_ROOT", str(DATA_DIR / "archived_file")))

# Ensure directories exist
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
get_word_templates_dir().mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCUREMENT_PROCESS_ROOT.mkdir(parents=True, exist_ok=True)
ARCHIVED_FILE_ROOT.mkdir(parents=True, exist_ok=True)

# Security
SECRET_KEY = os.getenv("SECRET_KEY", "shanhai-nazhen-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# API
API_V1_PREFIX = "/api"

# Client agent (for distributed file storage)
CLIENT_API_KEY = os.getenv("CLIENT_API_KEY", "your-secret-api-key")
