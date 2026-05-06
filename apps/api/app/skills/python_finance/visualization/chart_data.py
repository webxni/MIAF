from __future__ import annotations


def line_chart(title: str, rows: list[dict], x: str, y: str) -> dict:
    return {"type": "line", "title": title, "xKey": x, "yKey": y, "data": rows}


def bar_chart(title: str, rows: list[dict], x: str, y: str) -> dict:
    return {"type": "bar", "title": title, "xKey": x, "yKey": y, "data": rows}


def pie_chart(title: str, rows: list[dict], label: str, value: str) -> dict:
    return {"type": "pie", "title": title, "labelKey": label, "valueKey": value, "data": rows}


def multi_line_chart(title: str, rows: list[dict], x: str, series: list[str]) -> dict:
    return {"type": "multi_line", "title": title, "xKey": x, "series": series, "data": rows}


def generate_chart(
    chart_type: str,
    title: str,
    rows: list[dict],
    x_key: str = "period",
    y_key: str = "value",
    series: list[str] | None = None,
    label_key: str = "label",
    value_key: str = "value",
) -> dict:
    if chart_type == "line":
        return line_chart(title, rows, x_key, y_key)
    if chart_type == "bar":
        return bar_chart(title, rows, x_key, y_key)
    if chart_type == "pie":
        return pie_chart(title, rows, label_key, value_key)
    if chart_type == "multi_line":
        return multi_line_chart(title, rows, x_key, series or [y_key])
    raise ValueError(f"Unknown chart type: {chart_type}")
