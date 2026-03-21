"""Word document generation service."""
from pathlib import Path
import cn2an
from docxtpl import DocxTemplate
from app.config import get_word_templates_dir

# PRD 3.6.2: 材料采购/设备采购 -> 材料（设备）采购；材料租赁 -> 材料租赁（独立模板目录）
PROC_TYPE_MAP = {
    "材料采购": "材料（设备）采购",
    "设备采购": "材料（设备）采购",
    "材料租赁": "材料租赁",
    "机械租赁": "机械租赁",
}

FUNDING_MAP = {"工程类": "工程类", "自有资金": "自有资金"}
PROJECT_MAP = {"集团内项目": "集团内工程", "集团外项目": "集团外工程"}


def _project_to_dict(p) -> dict:
    return {
        "funding_type": p.funding_type,
        "project_type": p.project_type,
        "project_name": p.project_name,
        "project_number": p.project_number,
        "project_id": p.project_id,
        "construction_unit": p.construction_unit,
        "construction_contact_person": getattr(p, "construction_contact_person", None) or "",
        "construction_contact_phone": getattr(p, "construction_contact_phone", None) or "",
        "total_contract_price": p.total_contract_price,
        "project_address": p.project_address,
        "department": p.department,
        "site_manager": p.site_manager,
        "site_manager_phone": p.site_manager_phone,
    }


def get_template_path(funding_type: str, project_type: str, procurement_type: str, procurement_method: str) -> Path:
    """Get template directory path per PRD 3.6.1, UI 3.2.4.1.
    工程类: 资金类别/工程类别/采购类型/采购方式 (四级)
    自有资金: 自有资金/材料（设备）采购或机械租赁/采购方式 (三级，无集团内/外)
    PRD 8.14: 资金类别/工程类别为空时默认工程类/集团内工程，确保模板路径可解析。
    """
    pr_type = PROC_TYPE_MAP.get(procurement_type, procurement_type)
    ft = FUNDING_MAP.get(funding_type or "工程类", funding_type or "工程类")
    base = get_word_templates_dir()
    if ft == "自有资金":
        return base / ft / pr_type / procurement_method
    pt = PROJECT_MAP.get(project_type or "集团内项目", project_type or "集团内工程")
    return base / ft / pt / pr_type / procurement_method


def _join_ymd(y: str, m: str, d: str) -> str:
    """Join year/month/day to date string."""
    parts = [p for p in (y, m, d) if p]
    return f"{y}年{m}月{d}日" if len(parts) == 3 else ""


def _safe_float(v, default: float = 0) -> float:
    """安全转换为 float，避免非数字导致报错。"""
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def num_to_cn(num: float) -> str:
    """阿拉伯数字转人民币大写，使用 cn2an 库。展示至分（元、角、分）。"""
    if num is None:
        return "零元整"
    n = round(float(num), 2)
    if n <= 0:
        return "零元整"
    return cn2an.an2cn(str(n), "rmb")


def _radio_option(selected: str, options: list[str], newline: bool = True) -> str:
    """单选按钮：显示全部选项，选中项[✓]未选中[ ]。newline=True 时分行显示。"""
    sep = "\n " if newline else " "
    return sep.join(f"[✓]{o}" if o == selected else f"[  ]{o}" for o in options)


def build_context(project: dict, step1: dict, step2: dict, suppliers: list, winner_idx: int = 0) -> dict:
    """Build template context from form data. 单选按钮类型字段显示全部选项（123.md 50-58）。"""
    leibie_val = step2.get("leibie", "材料物资类")
    tax_val = step2.get("tax_method", "一般计税方法计算")
    contract_fmt = step2.get("contract_format", "采用非公司印发的合同标准文本编制")
    fanben_val = step2.get("use_standard_contract", "是")
    zhaocai_val = step2.get("passed_procurement", "是")
    shenhe_val = step2.get("reviewed", "是")
    ctx = {
        "gongcheng_or_ziyou": step1.get("funding_type", "工程类"),
        "in_or_out": step1.get("project_type", "集团内项目"),
        "caigou_leixing": step1.get("procurement_type", ""),
        "caigou_fangshi": step1.get("procurement_method", ""),
        "leibie": _radio_option(leibie_val, ["专业分包类", "劳务分包类", "材料物资类", "设备租赁类", "服务类"], newline=True),
        "gong_cheng_ming": step2.get("project_name", ""),
        "xiangmu_bianhao": step2.get("project_number", ""),
        "gongcheng_bianhao": step2.get("project_id", ""),
        "yezhu": step2.get("construction_unit", ""),
        "zongbaojia": step2.get("total_contract_price", 0),
        "xiangmu_dizhi": step2.get("project_address", ""),
        "xiangmubu": step2.get("department", ""),
        "xianchang_guanliren": step2.get("site_manager", ""),
        "xianchang_guanli_dianhua": step2.get("site_manager_phone", ""),
        "caigou_xiangmu_ming": step2.get("procurement_project_name", ""),
        "caigou_neirong": step2.get("content", ""),
        "kongzhijia": step2.get("control_price", 0),
        "caigou_yusuan": round(step2.get("control_price", 0) / 10000) if step2.get("control_price") else 0,
        "jishui_fangshi": _radio_option(tax_val, ["一般计税方法计算", "简易计税方法计算"], newline=True),
        "hetong_wenben_geshi": _radio_option(contract_fmt, ["采用公司印发的合同标准文本编制", "采用非公司印发的合同标准文本编制"], newline=True),
        "hetong_fanben": _radio_option(fanben_val, ["是", "否，但合同已经过法律审核，并有相关证明资料。"], newline=False),
        "zhaocai_chengxu": _radio_option("是" if zhaocai_val == "是" else "否，原因：/", ["是", "否，原因：/"], newline=False),
        "shenhe_jiaodui": _radio_option(shenhe_val, ["是", "否"], newline=False),
        "qianding_shijian": step2.get("sign_date") or _join_ymd(
            step2.get("qianding_year"), step2.get("qianding_month"), step2.get("qianding_day")
        ),
        "gonggao_year": step2.get("gonggao_year", ""),
        "gonggao_month": step2.get("gonggao_month", ""),
        "gonggao_day": step2.get("gonggao_day", ""),
        "yixiang_baoming_jiezhi_year": step2.get("yixiang_baoming_jiezhi_year", ""),
        "yixiang_baoming_jiezhi_month": step2.get("yixiang_baoming_jiezhi_month", ""),
        "yixiang_baoming_jiezhi_day": step2.get("yixiang_baoming_jiezhi_day", ""),
        "jiaoyi_fengmian_year": step2.get("jiaoyi_fengmian_year", ""),
        "jiaoyi_fengmian_month": step2.get("jiaoyi_fengmian_month", ""),
        "jiaoyi_wenjian_year": step2.get("jiaoyi_wenjian_year", ""),
        "jiaoyi_wenjian_month": step2.get("jiaoyi_wenjian_month", ""),
        "jiaoyi_wenjian_day": step2.get("jiaoyi_wenjian_day", ""),
        "jiaoyi_wenjian_huoqv_jiezhi_year": step2.get("jiaoyi_wenjian_huoqv_jiezhi_year", ""),
        "jiaoyi_wenjian_huoqv_jiezhi_month": step2.get("jiaoyi_wenjian_huoqv_jiezhi_month", ""),
        "jiaoyi_wenjian_huoqv_jiezhi_day": step2.get("jiaoyi_wenjian_huoqv_jiezhi_day", ""),
        "xiangying_dijiao_jiezhi_year": step2.get("xiangying_dijiao_jiezhi_year", ""),
        "xiangying_dijiao_jiezhi_month": step2.get("xiangying_dijiao_jiezhi_month", ""),
        "xiangying_dijiao_jiezhi_day": step2.get("xiangying_dijiao_jiezhi_day", ""),
        "biaoduanming1": step2.get("biaoduanming1", ""),
        "biaoduanming2": step2.get("biaoduanming2", ""),
        "kongzhijia_biao1": step2.get("kongzhijia_biao1"),
        "kongzhijia_biao2": step2.get("kongzhijia_biao2"),
    }
    # Suppliers - sort by quoted_price
    sorted_suppliers = sorted(suppliers, key=lambda s: s.get("quoted_price", 0))
    for i in range(3):
        s = sorted_suppliers[i] if i < len(sorted_suppliers) else {}
        ctx[f"gongyingshang{i+1}"] = s.get("supplier_name", "")
        ctx[f"lianxiren{i+1}"] = s.get("contact_person", "")
        ctx[f"lianxi_dianhua{i+1}"] = s.get("contact_phone", "")
        ctx[f"jingying_fanwei{i+1}"] = s.get("business_scope", "")
        ctx[f"shuilv{i+1}"] = s.get("tax_rate", "")
        ctx[f"baojia{i+1}"] = s.get("quoted_price", 0)
    ctx["gongyingshang_count"] = len(suppliers)
    if sorted_suppliers:
        ctx["rank1"] = sorted_suppliers[0].get("supplier_name", "")
        ctx["rank2"] = sorted_suppliers[1].get("supplier_name", "") if len(sorted_suppliers) > 1 else ""
        ctx["rank3"] = sorted_suppliers[-1].get("supplier_name", "") if len(sorted_suppliers) > 2 else ""
        ctx["chengjiao_jine"] = sorted_suppliers[winner_idx].get("quoted_price", 0)
        ctx["chengjiao_jine_daxie"] = num_to_cn(ctx["chengjiao_jine"])
        if step1.get("procurement_method") == "五选二" and len(sorted_suppliers) >= 2:
            # 五选二：成交金额1/2 使用用户输入，不再按报价自动计算
            fallback1 = sorted_suppliers[0].get("quoted_price", 0)
            fallback2 = sorted_suppliers[1].get("quoted_price", 0)
            ctx["chengjiao_jine1"] = _safe_float(step2.get("chengjiao_jine1"), fallback1)
            ctx["chengjiao_jine_daxie1"] = num_to_cn(ctx["chengjiao_jine1"])
            ctx["chengjiao_jine2"] = _safe_float(step2.get("chengjiao_jine2"), fallback2)
            ctx["chengjiao_jine_daxie2"] = num_to_cn(ctx["chengjiao_jine2"])
    return ctx


def render_docx(template_path: Path, context: dict, output_path: Path) -> None:
    """Render docx template with context."""
    if not template_path.exists():
        # Create minimal docx if no template
        from docx import Document
        doc = Document()
        for k, v in context.items():
            doc.add_paragraph(f"{k}: {v}")
        doc.save(output_path)
        return
    tpl = DocxTemplate(str(template_path))
    tpl.render(context)
    tpl.save(str(output_path))
