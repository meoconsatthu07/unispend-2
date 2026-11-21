"""Biểu đồ Altair và dữ liệu tổng hợp cho giao diện UniSpend 2.0."""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable

import altair as alt

from .storage import BudgetStatus, EXPENSE_CATEGORIES, Transaction
from .utils import compact_money, validate_month

PRIMARY = "#35A879"
GREEN = "#35A879"
RED = "#D94B50"
WARNING = "#E8A45B"
CATEGORY_COLORS = ("#E87A4D", "#8B5CF6", "#38BDF8", "#EC4899", "#F59E0B", "#35A879")
ESSENTIAL_CATEGORIES = ("Ăn uống", "Tiền trọ", "Đi lại")

_VN_MONEY_AXIS_EXPR = (
    "abs(datum.value) >= 1000000 ? format(datum.value / 1000000, '.1f') + ' tr' : "
    "(abs(datum.value) >= 1000 ? format(datum.value / 1000, '.0f') + ' nghìn' : datum.value + ' đ')"
)


def _vnd_short_vi(amount: int) -> str:
    """Định dạng số tiền rút gọn 100% tiếng Việt (VD: 4,50 tr, 326 nghìn, 0 đ)."""
    val = int(amount or 0)
    if abs(val) >= 1_000_000:
        m = val / 1_000_000
        s = f"{m:.2f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{s} tr"
    if abs(val) >= 1_000:
        k = val / 1_000
        s = f"{k:.1f}".rstrip("0").rstrip(".").replace(".", ",")
        return f"{s} nghìn"
    return f"{val:,} đ".replace(",", ".")


def _finish(chart: alt.Chart, title: str, height: int = 260, dark: bool = True) -> alt.Chart:
    bg = "#13201A" if dark else "#FFFFFF"
    label_color = "#9CA3AF" if dark else "#5A7467"
    grid_color = "#182921" if dark else "#EDF5F0"
    tick_color = "#263C31" if dark else "#DCE7DF"
    title_color = "#F3F4F6" if dark else "#1E352B"
    return (
        chart.properties(height=height, title=title, padding={"top": 14, "bottom": 10, "left": 8, "right": 8})
        .configure(background=bg, font="Plus Jakarta Sans, Inter, Segoe UI, sans-serif")
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=label_color,
            titleColor=label_color,
            gridColor=grid_color,
            domain=False,
            tickColor=tick_color,
            titleFontWeight=600,
        )
        .configure_legend(
            title=None,
            labelColor=title_color,
            orient="bottom",
            padding=14,
            symbolSize=100,
            labelFontSize=12,
        )
        .configure_title(anchor="start", color=title_color, fontSize=14, offset=14)
    )


def _category_scale() -> alt.Scale:
    return alt.Scale(domain=list(EXPENSE_CATEGORIES), range=list(CATEGORY_COLORS))


def _monthly_category_rows(
    records: Iterable[Transaction],
    months: list[str],
    categories: tuple[str, ...] = EXPENSE_CATEGORIES,
) -> list[dict]:
    """Chỉ cộng khoản chi trong khoảng đã chọn, giữ cả tháng có tổng bằng 0."""
    totals = {(month, category): 0 for month in months for category in categories}
    for record in records:
        key = (record.date[:7], record.category)
        if record.kind == "expense" and key in totals:
            totals[key] += record.amount
    return [
        {"month": month, "category": category, "amount": totals[month, category]}
        for month in months
        for category in categories
    ]


def _daily_expense_rows(records: Iterable[Transaction], month: str) -> list[dict]:
    """Giữ mọi ngày trong tháng, bao gồm ngày không phát sinh khoản chi."""
    validate_month(month)
    year, month_number = map(int, month.split("-"))
    totals = {
        f"{month}-{day:02d}": 0
        for day in range(1, monthrange(year, month_number)[1] + 1)
    }
    for record in records:
        if record.kind == "expense" and record.date in totals:
            totals[record.date] += record.amount
    return [{"date": day, "amount": amount} for day, amount in totals.items()]


def category_donut(totals: dict[str, int], dark: bool = False) -> alt.Chart:
    total = sum(totals.values())
    color_lookup = dict(zip(EXPENSE_CATEGORIES, CATEGORY_COLORS))
    rows = []
    domain_labels = []
    range_colors = []
    for category, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
        if amount > 0 and total > 0:
            share = amount / total
            label = f"{category} · {share * 100:.0f}%"
            rows.append({"category": category, "label": label, "amount": amount, "share": share})
            domain_labels.append(label)
            range_colors.append(color_lookup.get(category, PRIMARY))

    title_color = "#F3F4F6" if dark else "#1E352B"
    muted_color = "#9CA3AF" if dark else "#5A7467"

    arc = alt.Chart(alt.Data(values=rows)).mark_arc(
        innerRadius=56,
        outerRadius=88,
        cornerRadius=8,
        padAngle=0.035,
    ).encode(
        theta=alt.Theta("amount:Q", title="Số tiền"),
        color=alt.Color(
            "label:N",
            scale=alt.Scale(domain=domain_labels, range=range_colors),
            legend=alt.Legend(
                orient="right",
                title=None,
                labelColor=title_color,
                labelFontSize=12.5,
                symbolSize=115,
                rowPadding=10,
                labelLimit=170,
                padding=14,
            ),
        ),
        tooltip=[
            alt.Tooltip("category:N", title="Danh mục"),
            alt.Tooltip("amount:Q", title="Số tiền (VNĐ)", format=",.0f"),
            alt.Tooltip("share:Q", title="Tỷ trọng", format=".1%"),
        ],
    )

    center_total = alt.Chart(alt.Data(values=[{"txt": _vnd_short_vi(total)}])).mark_text(
        fontSize=19,
        fontWeight=900,
        color=title_color,
        dy=-7,
    ).encode(text="txt:N")

    center_sub = alt.Chart(alt.Data(values=[{"txt": "Tổng chi tiêu"}])).mark_text(
        fontSize=11,
        fontWeight=600,
        color=muted_color,
        dy=13,
    ).encode(text="txt:N")

    layered = alt.layer(arc, center_total, center_sub)
    return _finish(layered, "Cơ cấu chi tiêu theo danh mục", height=250, dark=dark)


def monthly_income_expense(rows: list[dict], dark: bool = False) -> alt.Chart:
    values = [
        {"month": row["month"], "kind": label, "amount": row[key]}
        for row in rows
        for key, label in (("income", "Thu nhập"), ("expense", "Chi tiêu"))
    ]
    chart = alt.Chart(alt.Data(values=values)).mark_bar(
        cornerRadiusTopLeft=5,
        cornerRadiusTopRight=5,
    ).encode(
        x=alt.X(
            "month:N",
            title="Tháng",
            sort=[row["month"] for row in rows],
            axis=alt.Axis(labelAngle=0),
        ),
        xOffset=alt.XOffset("kind:N", sort=["Thu nhập", "Chi tiêu"]),
        y=alt.Y("amount:Q", title="Số tiền", axis=alt.Axis(labelExpr=_VN_MONEY_AXIS_EXPR)),
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(domain=["Thu nhập", "Chi tiêu"], range=[GREEN, RED]),
        ),
        tooltip=[
            alt.Tooltip("month:N", title="Tháng"),
            alt.Tooltip("kind:N", title="Loại giao dịch"),
            alt.Tooltip("amount:Q", title="Số tiền (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, "So sánh thu nhập và chi tiêu", dark=dark)


def monthly_categories(records: Iterable[Transaction], months: list[str], dark: bool = False) -> alt.Chart:
    chart = alt.Chart(alt.Data(values=_monthly_category_rows(records, months))).mark_bar(
        cornerRadiusTopLeft=4,
        cornerRadiusTopRight=4,
    ).encode(
        x=alt.X("month:N", title="Tháng", sort=months, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("amount:Q", title="Chi tiêu", axis=alt.Axis(labelExpr=_VN_MONEY_AXIS_EXPR)),
        color=alt.Color("category:N", scale=_category_scale()),
        tooltip=[
            alt.Tooltip("month:N", title="Tháng"),
            alt.Tooltip("category:N", title="Danh mục"),
            alt.Tooltip("amount:Q", title="Chi tiêu (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, "So sánh 6 tháng theo danh mục", dark=dark)


def essential_trend(records: Iterable[Transaction], months: list[str], dark: bool = False) -> alt.Chart:
    rows = _monthly_category_rows(records, months, ESSENTIAL_CATEGORIES)
    chart = alt.Chart(alt.Data(values=rows)).mark_line(
        strokeWidth=3,
        point=alt.OverlayMarkDef(size=70, filled=True),
    ).encode(
        x=alt.X("month:N", title="Tháng", sort=months, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("amount:Q", title="Số tiền", axis=alt.Axis(labelExpr=_VN_MONEY_AXIS_EXPR)),
        color=alt.Color(
            "category:N",
            scale=alt.Scale(
                domain=list(ESSENTIAL_CATEGORIES),
                range=list(CATEGORY_COLORS[:3]),
            ),
        ),
        tooltip=[
            alt.Tooltip("month:N", title="Tháng"),
            alt.Tooltip("category:N", title="Khoản thiết yếu"),
            alt.Tooltip("amount:Q", title="Số tiền (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, "Biến động tiền ăn, tiền trọ và đi lại", 280, dark=dark)


def daily_expenses(records: Iterable[Transaction], month: str, dark: bool = False) -> alt.Chart:
    line_col = "#69C39B" if dark else PRIMARY
    stop_low = "#192821" if dark else "#F5F8F5"
    stop_high = "#2DAA79" if dark else "#69C39B"
    chart = alt.Chart(alt.Data(values=_daily_expense_rows(records, month))).mark_area(
        line={"color": line_col, "strokeWidth": 2.5},
        color=alt.Gradient(
            gradient="linear",
            x1=1,
            x2=1,
            y1=1,
            y2=0,
            stops=[
                alt.GradientStop(color=stop_low, offset=0),
                alt.GradientStop(color=stop_high, offset=1),
            ],
        ),
        point=alt.OverlayMarkDef(color=line_col, size=36),
    ).encode(
        x=alt.X(
            "date:O",
            title="Ngày trong tháng",
            axis=alt.Axis(labelAngle=0, labelExpr="substring(datum.label, 8, 10)"),
        ),
        y=alt.Y("amount:Q", title="Chi tiêu", axis=alt.Axis(labelExpr=_VN_MONEY_AXIS_EXPR)),
        tooltip=[
            alt.Tooltip("date:N", title="Ngày"),
            alt.Tooltip("amount:Q", title="Tổng chi (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, f"Chi tiêu từng ngày · {month}", 270, dark=dark)


def budget_comparison(statuses: Iterable[BudgetStatus], dark: bool = False) -> alt.Chart:
    statuses = list(statuses)
    rows = [
        {"category": status.category, "kind": label, "amount": amount}
        for status in statuses
        for label, amount in (("Đã chi thực tế", status.spent), ("Định mức", status.limit))
    ]
    limit_col = "#9BB8A8" if dark else "#8CA89B"
    chart = alt.Chart(alt.Data(values=rows)).mark_bar(cornerRadiusEnd=5).encode(
        y=alt.Y("category:N", title=None, sort=[status.category for status in statuses]),
        yOffset=alt.YOffset("kind:N", sort=["Đã chi thực tế", "Định mức"]),
        x=alt.X("amount:Q", title="Số tiền (VNĐ)"),
        color=alt.Color(
            "kind:N",
            scale=alt.Scale(
                domain=["Đã chi thực tế", "Định mức"],
                range=[RED, limit_col],
            ),
        ),
        tooltip=[
            alt.Tooltip("category:N", title="Danh mục"),
            alt.Tooltip("kind:N", title="Loại"),
            alt.Tooltip("amount:Q", title="Số tiền (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, "Tiến độ ngân sách: Thực tế và định mức", max(240, len(statuses) * 55), dark=dark)


def financial_trend(rows: list[dict], dark: bool = False) -> alt.Chart:
    """Biểu đồ xu hướng tài chính (Thu nhập, Chi tiêu và Chênh lệch thu chi qua các tháng)."""
    values = []
    for row in rows:
        inc = int(row.get("income", 0))
        exp = int(row.get("expense", 0))
        net = inc - exp
        values.extend([
            {"month": row["month"], "metric": "Thu nhập", "amount": inc},
            {"month": row["month"], "metric": "Chi tiêu", "amount": exp},
            {"month": row["month"], "metric": "Chênh lệch thu chi", "amount": net},
        ])
    net_col = "#69C39B" if dark else PRIMARY
    chart = alt.Chart(alt.Data(values=values)).mark_line(
        strokeWidth=3,
        point=alt.OverlayMarkDef(size=75, filled=True),
    ).encode(
        x=alt.X(
            "month:N",
            title="Tháng",
            sort=[row["month"] for row in rows],
            axis=alt.Axis(labelAngle=0),
        ),
        y=alt.Y("amount:Q", title="Số tiền", axis=alt.Axis(labelExpr=_VN_MONEY_AXIS_EXPR)),
        color=alt.Color(
            "metric:N",
            scale=alt.Scale(
                domain=["Thu nhập", "Chi tiêu", "Chênh lệch thu chi"],
                range=[GREEN, RED, net_col],
            ),
        ),
        tooltip=[
            alt.Tooltip("month:N", title="Tháng"),
            alt.Tooltip("metric:N", title="Chỉ số"),
            alt.Tooltip("amount:Q", title="Số tiền (VNĐ)", format=",.0f"),
        ],
    )
    return _finish(chart, "Xu hướng tài chính & chênh lệch thu chi", 280, dark=dark)
