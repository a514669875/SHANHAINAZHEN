"""采购 form_data 首次保存与「仅时间表变更」判定（防误触发全套流程文件重生成）。"""
import json

from app.api.procurements import (
    _is_time_records_only_change,
    _procurement_file_sync_should_skip,
    _form_data_gained_nonblank_content,
)


def test_time_records_only_across_repr_json_and_remark():
    """创建时 str(dict)、首次保存 JSON + 多出 remark/空值形态，仍应识别为仅时间表变更。"""
    old = str(
        {
            "content": "工程A",
            "control_price": 100,
            "procurement_project_name": "采购1",
            "_time_records": [{"flow_name": "公告", "date_val": "2024.1.1"}],
            "hetong_jiaodi": "",
        }
    )
    new = json.dumps(
        {
            "content": "工程A",
            "control_price": 100.0,
            "procurement_project_name": "采购1",
            "_time_records": [{"flow_name": "公告", "date_val": "2024.1.2"}],
            "hetong_jiaodi": "",
            "remark": "",
        },
        ensure_ascii=False,
    )
    assert _is_time_records_only_change(old, new, [], None) is True


def test_not_time_only_when_content_changes():
    old = json.dumps(
        {
            "content": "工程A",
            "_time_records": [{"flow_name": "公告", "date_val": "2024.1.1"}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    new = json.dumps(
        {
            "content": "工程B",
            "_time_records": [{"flow_name": "公告", "date_val": "2024.1.2"}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    assert _is_time_records_only_change(old, new, [], None) is False


def test_no_change_not_considered_time_only():
    """时间表与交底均未变，不应走「仅目录」分支。"""
    payload = {
        "content": "工程A",
        "_time_records": [{"flow_name": "公告", "date_val": "2024.1.1"}],
        "hetong_jiaodi": "",
    }
    s = json.dumps(payload, ensure_ascii=False)
    assert _is_time_records_only_change(s, s, [], None) is False


def test_skip_sync_when_form_unchanged():
    """无任何实质变更时应跳过流程文件同步。"""
    s = json.dumps({"content": "A", "_time_records": [{"flow_name": "公告", "date_val": "1"}], "hetong_jiaodi": ""}, ensure_ascii=False)
    assert _procurement_file_sync_should_skip(s, s, [], None) is True


def test_skip_sync_time_records_whitespace_equivalent():
    """时间表仅空格/格式差异，视为未改，应跳过同步。"""
    old = json.dumps(
        {"content": "A", "_time_records": [{"flow_name": "公告", "date_val": "2024.1.1"}], "hetong_jiaodi": ""},
        ensure_ascii=False,
    )
    new = json.dumps(
        {
            "content": "A",
            "_time_records": [{"flow_name": " 公告 ", "date_val": "2024.1.1"}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    assert _procurement_file_sync_should_skip(old, new, [], None) is True


def test_gain_detection_blank_to_filled_triggers_no_skip():
    """第二步等字段从空补填后，不可跳过流程文件同步。"""
    old = json.dumps(
        {
            "content": "工程",
            "gonggao_year": "",
            "gonggao_month": "",
            "gonggao_day": "",
            "_time_records": [{"flow_name": "公告", "date_val": ""}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    new = json.dumps(
        {
            "content": "工程",
            "gonggao_year": "2026",
            "gonggao_month": "3",
            "gonggao_day": "1",
            "_time_records": [{"flow_name": "公告", "date_val": ""}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    assert _procurement_file_sync_should_skip(old, new, [], None) is False


def test_gain_detection_time_table_date_filled():
    """仅流程表某行从空填上日期，也应触发同步（不可跳过）。"""
    old = json.dumps(
        {"content": "A", "_time_records": [{"flow_name": "采购意向公告", "date_val": ""}], "hetong_jiaodi": ""},
        ensure_ascii=False,
    )
    new = json.dumps(
        {"content": "A", "_time_records": [{"flow_name": "采购意向公告", "date_val": "2026.3.1"}], "hetong_jiaodi": ""},
        ensure_ascii=False,
    )
    assert _form_data_gained_nonblank_content(json.loads(old), json.loads(new)) is True
    assert _procurement_file_sync_should_skip(old, new, [], None) is False


def test_time_records_only_with_normalized_compare():
    """非时间表字段一致，时间表仅日期变，仍识别为仅目录更新。"""
    old = json.dumps(
        {"content": "A", "_time_records": [{"flow_name": "公告", "date_val": "2024.1.1"}], "hetong_jiaodi": ""},
        ensure_ascii=False,
    )
    new = json.dumps(
        {
            "content": "A",
            "_time_records": [{"flow_name": "公告", "date_val": "2024.1.2"}],
            "hetong_jiaodi": "",
        },
        ensure_ascii=False,
    )
    assert _is_time_records_only_change(old, new, [], None) is True
