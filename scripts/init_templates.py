"""Create Word template directory structure per PRD 3.6.1."""
import shutil
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.config import WORD_TEMPLATES_DIR

FUNDING_TYPES = ["工程类", "自有资金"]
PROJECT_TYPES = ["集团内工程", "集团外工程"]
PROCUREMENT_TYPES = ["材料（设备）采购", "材料租赁", "机械租赁"]
PROCUREMENT_METHODS = ["单一来源", "邀请询比", "直接采购", "五选二", "补充协议"]


def main():
    # 清理自有资金下错误的集团内/外工程目录（PRD 3.6.1）
    ziyou_base = WORD_TEMPLATES_DIR / "自有资金"
    for wrong in ["集团内工程", "集团外工程"]:
        wrong_path = ziyou_base / wrong
        if wrong_path.exists():
            shutil.rmtree(wrong_path)
            print(f"Removed (incorrect): {wrong_path.relative_to(WORD_TEMPLATES_DIR)}")

    for ft in FUNDING_TYPES:
        if ft == "自有资金":
            # PRD 3.6.1: 自有资金无集团内/外区分，直接为 自有资金/采购类型/采购方式
            for prt in PROCUREMENT_TYPES:
                for pm in PROCUREMENT_METHODS:
                    path = WORD_TEMPLATES_DIR / ft / prt / pm
                    path.mkdir(parents=True, exist_ok=True)
                    print(f"Created: {path.relative_to(WORD_TEMPLATES_DIR)}")
        else:
            # 工程类: 四级 资金类别/工程类别/采购类型/采购方式
            for pt in PROJECT_TYPES:
                for prt in PROCUREMENT_TYPES:
                    for pm in PROCUREMENT_METHODS:
                        path = WORD_TEMPLATES_DIR / ft / pt / prt / pm
                        path.mkdir(parents=True, exist_ok=True)
                        print(f"Created: {path.relative_to(WORD_TEMPLATES_DIR)}")
    print("Template directory structure created.")


if __name__ == "__main__":
    main()
