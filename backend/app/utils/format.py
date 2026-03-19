"""Format utilities - date Y.M.D, numeric display."""


def format_currency_two_decimals(val) -> str:
    """Format number as currency with exactly 2 decimal places (e.g. 100.00)."""
    if val is None:
        return ""
    try:
        n = float(val)
        return f"{n:.2f}"
    except (ValueError, TypeError):
        return str(val) if val is not None else ""


def format_date_ymd(val) -> str:
    """Format date as Y.M.D, e.g. 2026.3.13 (no leading zeros for month/day)."""
    if val is None:
        return ""
    if hasattr(val, "year"):
        return f"{val.year}.{val.month}.{val.day}"
    s = str(val).strip()
    if not s:
        return ""
    parts = s.replace("-", ".").replace("/", ".").split(".")
    if len(parts) >= 3:
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y}.{m}.{d}"
        except (ValueError, IndexError):
            pass
    return s
