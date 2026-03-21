"""台账列表默认排序：合同编号自然序（材2 在 材10 前）。"""
from app.api.ledger import _natural_sort_tuple


def test_natural_sort_tuple_orders_numeric_suffix():
    keys = ["H-2023-21-材10", "H-2023-21-材2", "H-2023-21-材1"]
    assert sorted(keys, key=_natural_sort_tuple) == [
        "H-2023-21-材1",
        "H-2023-21-材2",
        "H-2023-21-材10",
    ]


def test_natural_sort_tuple_vs_lexicographic():
    """字典序会把 材10 放在 材2 前；自然序为 材2 < 材10。"""
    assert _natural_sort_tuple("X-材2") < _natural_sort_tuple("X-材10")
    assert "X-材10" < "X-材2"  # 纯字符串字典序（错误顺序）
