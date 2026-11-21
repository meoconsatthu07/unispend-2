# -*- coding: utf-8 -*-
"""Tạo và kiểm định bộ dữ liệu thu chi sinh viên UTH sạch (CSV, Excel, SQLite).

Đầu ra mặc định tại: data/clean_dataset/
- thu_chi_sinh_vien_uth_clean.csv        (Chuẩn import vào UniSpend UTH / unispend_3d)
- thu_chi_sinh_vien_unispend2_clean.csv  (Chuẩn danh mục UniSpend 2.0 / expense_tracker)
- thu_chi_sinh_vien_uth_clean.xlsx       (Báo cáo Excel 4 sheet để nộp/trình bày giảng viên)
- unispend2_clean.db                     (SQLite sạch cho UniSpend 2.0 — dùng Khôi phục hoặc --db)
- unispend3d_clean.db                    (SQLite sạch cho UniSpend UTH 3D)
"""

from __future__ import annotations

import csv
import json
import random
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from expense_tracker.reports_backup import validate_sqlite_backup
from expense_tracker.storage import (
    EXPENSE_CATEGORIES as V2_EXPENSE_CATS,
    INCOME_CATEGORIES as V2_INCOME_CATS,
    TOTAL_BUDGET_CATEGORY,
    TYPE_LABELS,
    ExpenseStore,
)
from unispend_3d.csv_import import read_transactions_csv
from unispend_3d.models import (
    EXPENSE_CATEGORIES as UTH_EXPENSE_CATS,
    INCOME_CATEGORIES as UTH_INCOME_CATS,
)

OUTPUT_DIR = BASE_DIR / "data" / "clean_dataset"
AS_OF_DATE = date(2026, 11, 20)
MONTHS = ("2026-06", "2026-07", "2026-08", "2026-09", "2026-10", "2026-11")


@dataclass(frozen=True)
class CleanRecord:
    date: str          # YYYY-MM-DD
    kind: str          # 'income' | 'expense'
    cat_v2: str        # Danh mục UniSpend 2.0
    cat_uth: str       # Danh mục UniSpend UTH (3D)
    amount: int        # VNĐ (số nguyên dương, bội số 1.000)
    note: str          # Ghi chú chi tiết, sạch, tiếng Việt có dấu


def _clamp_day(month_str: str, day: int) -> str:
    year, month = map(int, month_str.split("-"))
    if month == 2:
        max_day = 28
    elif month in (4, 6, 9, 11):
        max_day = 30
    else:
        max_day = 31
    if month_str == AS_OF_DATE.strftime("%Y-%m"):
        max_day = min(max_day, AS_OF_DATE.day)
    safe_day = max(1, min(day, max_day))
    return f"{year:04d}-{month:02d}-{safe_day:02d}"


def build_clean_records() -> list[CleanRecord]:
    """Sinh dữ liệu thu chi 6 tháng thực tế của sinh viên UTH (deterministic seed=2026)."""
    rng = random.Random(2026)
    records: list[CleanRecord] = []

    food_pool = [
        ("Cơm trưa căn tin cơ sở 1 UTH", (35_000, 45_000)),
        ("Đi chợ mua thực phẩm nấu ăn tuần", (180_000, 260_000)),
        ("Mua đồ ăn sáng và cà phê trước giờ học", (35_000, 55_000)),
        ("Mua thực phẩm và sữa tại Bách Hóa Xanh", (140_000, 230_000)),
        ("Ăn tối cơm tấm cùng bạn cùng phòng", (45_000, 65_000)),
        ("Mua trái cây và rau củ tại chợ Bà Chiểu", (85_000, 140_000)),
        ("Ăn bún bò Huế gần ký túc xá", (40_000, 55_000)),
        ("Mua mì gói, trứng và đồ khô dự trữ", (95_000, 150_000)),
        ("Cơm văn phòng buổi trưa sau ca học", (40_000, 50_000)),
        ("Mua đồ ăn nhẹ học khuya ôn kiểm tra", (45_000, 75_000)),
        ("Đi siêu thị Co.opmart mua đồ nấu ăn cuối tuần", (170_000, 250_000)),
    ]

    transport_pool = [
        ("Đổ xăng xe máy đi học", (65_000, 85_000)),
        ("Vé xe buýt tháng sinh viên", (112_000, 112_000)),
        ("Gửi xe tại trường và đổ xăng", (70_000, 95_000)),
        ("Đặt xe công nghệ đi học trời mưa", (45_000, 75_000)),
        ("Thay nhớt và bơm lốp xe máy định kỳ", (120_000, 150_000)),
    ]

    study_pool = [
        ("In ấn slide bài giảng và tài liệu ôn tập", (45_000, 85_000)),
        ("Mua giáo trình chuyên ngành tại thư viện UTH", (120_000, 210_000)),
        ("Mua vở ghi chép, bút và dụng cụ học tập", (55_000, 95_000)),
        ("Đóng tiền in báo cáo đồ án nhóm", (60_000, 110_000)),
        ("Đăng ký khóa học trực tuyến bổ trợ lập trình", (150_000, 220_000)),
    ]

    fun_pool = [
        ("Xem phim cuối tuần cùng nhóm bạn", (95_000, 145_000)),
        ("Cà phê thảo luận bài tập và giao lưu CLB", (55_000, 90_000)),
        ("Góp quỹ sinh nhật bạn cùng lớp", (100_000, 150_000)),
        ("Đi ăn vặt và trà sữa sau tuần thi", (65_000, 110_000)),
    ]

    shopping_pool = [
        ("Mua dầu gội, sữa tắm và bàn chải cá nhân", (110_000, 175_000)),
        ("Mua nước giặt và đồ dùng vệ sinh phòng trọ", (95_000, 145_000)),
        ("Cắt tóc nam/nữ gần khu trọ", (60_000, 90_000)),
        ("Mua áo sơ mi đồng phục thực hành", (180_000, 240_000)),
    ]

    other_pool = [
        ("Mua thuốc cảm và vitamin C tại nhà thuốc", (55_000, 95_000)),
        ("Nạp tiền điện thoại gói data sinh viên", (70_000, 90_000)),
        ("Đóng quỹ lớp và hoạt động đoàn khoa", (50_000, 80_000)),
    ]

    def pick_amount(low: int, high: int) -> int:
        if low == high:
            return low
        steps = (high - low) // 5_000
        return low + rng.randint(0, steps) * 5_000

    for idx, month in enumerate(MONTHS):
        is_current_partial = month == AS_OF_DATE.strftime("%Y-%m")
        max_d = AS_OF_DATE.day if is_current_partial else 28

        # 1. Thu nhập cố định & làm thêm
        records.append(CleanRecord(
            date=_clamp_day(month, 1),
            kind="income",
            cat_v2="Gia đình hỗ trợ",
            cat_uth="Trợ cấp gia đình",
            amount=4_500_000,
            note=f"Gia đình chuyển sinh hoạt phí tháng {month[5:]}",
        ))

        part_time_salary = [1_650_000, 1_800_000, 1_950_000, 1_750_000, 2_050_000, 1_850_000][idx]
        records.append(CleanRecord(
            date=_clamp_day(month, 10),
            kind="income",
            cat_v2="Làm thêm",
            cat_uth="Làm thêm (Part-time)",
            amount=part_time_salary,
            note=f"Lương gia sư Toán - Tin học tháng {month[5:]}",
        ))

        # Học bổng đầu học kỳ (tháng 09/2026)
        if month == "2026-09":
            records.append(CleanRecord(
                date=_clamp_day(month, 15),
                kind="income",
                cat_v2="Học bổng",
                cat_uth="Học bổng & Thưởng",
                amount=2_500_000,
                note="Học bổng khuyến khích học tập loại Giỏi tại UTH",
            ))

        # Thu nhập phụ (tháng 07 & tháng 10)
        if month == "2026-07":
            records.append(CleanRecord(
                date=_clamp_day(month, 18),
                kind="income",
                cat_v2="Khác",
                cat_uth="Thu nhập khác",
                amount=280_000,
                note="Bán lại giáo trình cũ cho sinh viên khóa dưới",
            ))
        elif month == "2026-10":
            records.append(CleanRecord(
                date=_clamp_day(month, 22),
                kind="income",
                cat_v2="Khác",
                cat_uth="Thu nhập khác",
                amount=350_000,
                note="Hỗ trợ hoàn thành bài tập nhóm thiết kế slide",
            ))

        # 2. Chi tiêu cố định: Tiền trọ + điện nước
        rent_amount = [2_200_000, 2_250_000, 2_280_000, 2_240_000, 2_260_000, 2_250_000][idx]
        records.append(CleanRecord(
            date=_clamp_day(month, 2),
            kind="expense",
            cat_v2="Tiền trọ",
            cat_uth="Tiền trọ",
            amount=rent_amount,
            note=f"Tiền thuê phòng trọ, điện nước và wifi tháng {month[5:]}",
        ))

        # 3. Chi tiêu ăn uống (9-11 lần/tháng, tháng hiện tại 7 lần)
        food_days = [2, 4, 6, 8, 11, 13, 15, 17, 19, 22, 26]
        if is_current_partial:
            food_days = [d for d in food_days if d <= max_d]
        for f_idx, d in enumerate(food_days):
            note_base, (lo, hi) = food_pool[(idx * 3 + f_idx) % len(food_pool)]
            records.append(CleanRecord(
                date=_clamp_day(month, d),
                kind="expense",
                cat_v2="Ăn uống",
                cat_uth="Tiền ăn",
                amount=pick_amount(lo, hi),
                note=f"{note_base} (đợt {f_idx + 1}/{len(food_days)})" if f_idx >= 8 else note_base,
            ))

        # 4. Đi lại (3-4 lần/tháng)
        transport_days = [3, 9, 16, 24]
        if is_current_partial:
            transport_days = [d for d in transport_days if d <= max_d]
        for t_idx, d in enumerate(transport_days):
            if t_idx == 0:
                note_base, (lo, hi) = transport_pool[1]  # Vé xe buýt tháng
            else:
                note_base, (lo, hi) = transport_pool[(idx + t_idx) % len(transport_pool)]
                if note_base == transport_pool[1][0]:
                    note_base, (lo, hi) = transport_pool[0]
            records.append(CleanRecord(
                date=_clamp_day(month, d),
                kind="expense",
                cat_v2="Đi lại",
                cat_uth="Đi lại",
                amount=pick_amount(lo, hi),
                note=note_base,
            ))

        # 5. Học tập (2-3 lần/tháng)
        study_days = [5, 14, 21] if month in ("2026-09", "2026-10") else [6, 17]
        study_days = [d for d in study_days if d <= max_d]
        for s_idx, d in enumerate(study_days):
            note_base, (lo, hi) = study_pool[(idx * 2 + s_idx) % len(study_pool)]
            records.append(CleanRecord(
                date=_clamp_day(month, d),
                kind="expense",
                cat_v2="Học tập",
                cat_uth="Học tập",
                amount=pick_amount(lo, hi),
                note=note_base,
            ))

        # 6. Giải trí (2 lần/tháng)
        fun_days = [12, 23] if not is_current_partial else [12, 18]
        for fn_idx, d in enumerate(fun_days):
            note_base, (lo, hi) = fun_pool[(idx + fn_idx) % len(fun_pool)]
            records.append(CleanRecord(
                date=_clamp_day(month, d),
                kind="expense",
                cat_v2="Giải trí",
                cat_uth="Giải trí & Xã giao",
                amount=pick_amount(lo, hi),
                note=note_base,
            ))

        # 7. Sinh hoạt & Mua sắm (1-2 lần/tháng)
        shop_days = [7, 20] if not is_current_partial else [7]
        for sh_idx, d in enumerate(shop_days):
            note_base, (lo, hi) = shopping_pool[(idx + sh_idx) % len(shopping_pool)]
            records.append(CleanRecord(
                date=_clamp_day(month, d),
                kind="expense",
                cat_v2="Khác",
                cat_uth="Sinh hoạt & Mua sắm",
                amount=pick_amount(lo, hi),
                note=note_base,
            ))

        # 8. Chi phí khác (1 lần/tháng)
        other_day = 15 if is_current_partial else 25
        note_base, (lo, hi) = other_pool[idx % len(other_pool)]
        records.append(CleanRecord(
            date=_clamp_day(month, other_day),
            kind="expense",
            cat_v2="Khác",
            cat_uth="Chi phí khác",
            amount=pick_amount(lo, hi),
            note=note_base,
        ))

    # Sắp xếp tăng dần theo ngày để ID và sổ giao dịch mạch lạc
    records.sort(key=lambda r: (r.date, 0 if r.kind == "income" else 1, r.cat_uth, r.amount, r.note))
    return records


def validate_records(records: list[CleanRecord]) -> dict[str, object]:
    """Kiểm định 6 tiêu chuẩn dữ liệu sạch (Data Quality Assurance)."""
    assert len(records) >= 120, "Bộ dữ liệu cần đủ lớn cho phân tích 6 tháng."

    seen_keys: set[tuple[str, str, str, int, str]] = set()
    null_count = 0
    dup_count = 0
    future_count = 0
    invalid_cat_count = 0
    invalid_amount_count = 0
    formula_risk_count = 0

    for r in records:
        if not all([r.date, r.kind, r.cat_v2, r.cat_uth, r.note.strip()]):
            null_count += 1
        d = date.fromisoformat(r.date)
        if d > AS_OF_DATE:
            future_count += 1
        if r.kind == "income":
            if r.cat_v2 not in V2_INCOME_CATS or r.cat_uth not in UTH_INCOME_CATS:
                invalid_cat_count += 1
        elif r.kind == "expense":
            if r.cat_v2 not in V2_EXPENSE_CATS or r.cat_uth not in UTH_EXPENSE_CATS:
                invalid_cat_count += 1
        else:
            invalid_cat_count += 1

        if not isinstance(r.amount, int) or r.amount <= 0 or r.amount % 1_000 != 0:
            invalid_amount_count += 1
        if r.note.lstrip().startswith(("=", "+", "-", "@")):
            formula_risk_count += 1

        key = (r.date, r.kind, r.cat_uth, r.amount, r.note)
        if key in seen_keys:
            dup_count += 1
        seen_keys.add(key)

    assert null_count == 0, f"Có {null_count} dòng thiếu giá trị!"
    assert dup_count == 0, f"Có {dup_count} dòng trùng lặp!"
    assert future_count == 0, f"Có {future_count} dòng ngày tương lai!"
    assert invalid_cat_count == 0, f"Có {invalid_cat_count} dòng sai danh mục!"
    assert invalid_amount_count == 0, f"Có {invalid_amount_count} dòng sai định dạng tiền!"
    assert formula_risk_count == 0, f"Có {formula_risk_count} dòng chứa ký tự công thức!"

    total_income = sum(r.amount for r in records if r.kind == "income")
    total_expense = sum(r.amount for r in records if r.kind == "expense")
    return {
        "total_rows": len(records),
        "months": list(MONTHS),
        "date_min": records[0].date,
        "date_max": records[-1].date,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_balance": total_income - total_expense,
        "savings_rate_pct": round((total_income - total_expense) / total_income * 100, 2),
        "null_count": null_count,
        "duplicate_count": dup_count,
        "future_date_count": future_count,
        "invalid_category_count": invalid_cat_count,
        "invalid_amount_count": invalid_amount_count,
        "formula_risk_count": formula_risk_count,
    }


def write_csv_files(records: list[CleanRecord]) -> tuple[Path, Path]:
    uth_csv = OUTPUT_DIR / "thu_chi_sinh_vien_uth_clean.csv"
    with open(uth_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Ngày giao dịch", "Loại giao dịch", "Danh mục", "Số tiền (VNĐ)", "Ghi chú chi tiết"])
        for r in records:
            writer.writerow([r.date, TYPE_LABELS[r.kind], r.cat_uth, r.amount, r.note])

    v2_csv = OUTPUT_DIR / "thu_chi_sinh_vien_unispend2_clean.csv"
    with open(v2_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Mã", "Ngày", "Loại", "Danh mục", "Số tiền (VNĐ)", "Ghi chú"])
        for idx, r in enumerate(records, start=1):
            writer.writerow([idx, r.date, TYPE_LABELS[r.kind], r.cat_v2, r.amount, r.note])

    return uth_csv, v2_csv


def write_sqlite_files(records: list[CleanRecord]) -> tuple[Path, Path]:
    # 1. UniSpend 2.0 (expense_tracker)
    v2_db = OUTPUT_DIR / "unispend2_clean.db"
    if v2_db.exists():
        v2_db.unlink()
    store = ExpenseStore(v2_db)
    try:
        for r in records:
            store.add_transaction(r.date, r.kind, r.cat_v2, r.amount, r.note)
        v2_budgets = {
            TOTAL_BUDGET_CATEGORY: 4_800_000,
            "Ăn uống": 1_700_000,
            "Tiền trọ": 2_350_000,
            "Đi lại": 350_000,
            "Học tập": 400_000,
            "Giải trí": 350_000,
            "Khác": 350_000,
        }
        for month in MONTHS:
            store.set_budgets(month, v2_budgets)
    finally:
        store.close()

    # 2. UniSpend UTH 3D (unispend_3d)
    uth_db = OUTPUT_DIR / "unispend3d_clean.db"
    if uth_db.exists():
        uth_db.unlink()
    conn = sqlite3.connect(str(uth_db))
    try:
        with conn:
            conn.executescript("""
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    tx_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    amount REAL NOT NULL,
                    note TEXT
                );
                CREATE TABLE budgets (
                    month TEXT PRIMARY KEY,
                    total_budget REAL NOT NULL,
                    category_limits_json TEXT NOT NULL
                );
            """)
            conn.executemany(
                "INSERT INTO transactions(date, tx_type, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                [(r.date, TYPE_LABELS[r.kind], r.cat_uth, float(r.amount), r.note) for r in records],
            )
            uth_limits = {
                "Tiền ăn": 1_700_000,
                "Tiền trọ": 2_350_000,
                "Đi lại": 350_000,
                "Học tập": 400_000,
                "Sinh hoạt & Mua sắm": 300_000,
                "Giải trí & Xã giao": 350_000,
                "Chi phí khác": 200_000,
            }
            limits_json = json.dumps(uth_limits, ensure_ascii=False)
            conn.executemany(
                "INSERT INTO budgets(month, total_budget, category_limits_json) VALUES (?, ?, ?)",
                [(month, 4_800_000.0, limits_json) for month in MONTHS],
            )
    finally:
        conn.close()

    return v2_db, uth_db


def write_excel_report(records: list[CleanRecord], qa: dict[str, object]) -> Path:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    xlsx_path = OUTPUT_DIR / "thu_chi_sinh_vien_uth_clean.xlsx"
    wb = Workbook()

    header_fill = PatternFill("solid", fgColor="1E4D3B")
    sub_fill = PatternFill("solid", fgColor="E6F2EC")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Segoe UI", size=14, bold=True, color="1E4D3B")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="1F2D27")
    normal_font = Font(name="Segoe UI", size=10, color="1F2D27")
    thin = Side(border_style="thin", color="D5E2DA")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def autofit(ws):
        for col in ws.columns:
            letter = get_column_letter(col[0].column)
            width = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[letter].width = max(14, min(52, width + 4))

    # Sheet 1: Tổng quan 6 tháng
    ws1 = wb.active
    ws1.title = "Tong_quan_6_thang"
    ws1["A1"] = "BỘ DỮ LIỆU SẠCH THU CHI SINH VIÊN UTH (06/2026 - 11/2026)"
    ws1["A1"].font = title_font
    ws1["A2"] = f"Ngày tạo: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Tổng số bản ghi: {qa['total_rows']} | Đơn vị: VNĐ"
    ws1["A2"].font = normal_font
    ws1.append([])

    headers1 = ["Tháng", "Số giao dịch", "Tổng thu nhập (VNĐ)", "Tổng chi tiêu (VNĐ)", "Chênh lệch (VNĐ)", "Tỷ lệ tiết kiệm (%)"]
    ws1.append(headers1)
    for c in range(1, 7):
        cell = ws1.cell(row=4, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    monthly = defaultdict(lambda: {"count": 0, "income": 0, "expense": 0})
    for r in records:
        m = r.date[:7]
        monthly[m]["count"] += 1
        monthly[m][r.kind] += r.amount

    for m in MONTHS:
        st = monthly[m]
        bal = st["income"] - st["expense"]
        rate = round(bal / st["income"] * 100, 1) if st["income"] else 0.0
        ws1.append([m, st["count"], st["income"], st["expense"], bal, rate])
        row_idx = ws1.max_row
        for c in range(1, 7):
            cell = ws1.cell(row=row_idx, column=c)
            cell.font = normal_font
            cell.border = border
            if c in (3, 4, 5):
                cell.number_format = "#,##0"
            elif c in (1, 2):
                cell.alignment = Alignment(horizontal="center")

    ws1.append([
        "TỔNG CỘNG",
        qa["total_rows"],
        qa["total_income"],
        qa["total_expense"],
        qa["net_balance"],
        qa["savings_rate_pct"],
    ])
    tot_row = ws1.max_row
    for c in range(1, 7):
        cell = ws1.cell(row=tot_row, column=c)
        cell.fill = sub_fill
        cell.font = bold_font
        cell.border = border
        if c in (3, 4, 5):
            cell.number_format = "#,##0"
        elif c in (1, 2):
            cell.alignment = Alignment(horizontal="center")
    autofit(ws1)

    # Sheet 2: Phân bổ danh mục
    ws2 = wb.create_sheet("Phan_bo_danh_muc")
    ws2.append(["Loại giao dịch", "Danh mục (UniSpend UTH)", "Danh mục (UniSpend 2.0)", "Số giao dịch", "Tổng tiền (VNĐ)", "Tỷ trọng trong loại (%)"])
    for c in range(1, 7):
        cell = ws2.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    cat_stats = defaultdict(lambda: {"count": 0, "amount": 0})
    for r in records:
        cat_stats[(r.kind, r.cat_uth, r.cat_v2)]["count"] += 1
        cat_stats[(r.kind, r.cat_uth, r.cat_v2)]["amount"] += r.amount

    for (kind, cat_uth, cat_v2), st in sorted(cat_stats.items(), key=lambda x: (x[0][0], -x[1]["amount"])):
        denom = qa["total_income"] if kind == "income" else qa["total_expense"]
        pct = round(st["amount"] / denom * 100, 2) if denom else 0.0
        ws2.append([TYPE_LABELS[kind], cat_uth, cat_v2, st["count"], st["amount"], pct])
        row_idx = ws2.max_row
        for c in range(1, 7):
            cell = ws2.cell(row=row_idx, column=c)
            cell.font = normal_font
            cell.border = border
            if c == 5:
                cell.number_format = "#,##0"
            elif c in (1, 4):
                cell.alignment = Alignment(horizontal="center")
    autofit(ws2)

    # Sheet 3: Dữ liệu giao dịch sạch
    ws3 = wb.create_sheet("Du_lieu_giao_dich_sach")
    ws3.append(["Mã GD", "Ngày giao dịch", "Loại giao dịch", "Danh mục (UTH)", "Danh mục (v2)", "Số tiền (VNĐ)", "Ghi chú chi tiết"])
    for c in range(1, 8):
        cell = ws3.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for idx, r in enumerate(records, start=1):
        ws3.append([idx, r.date, TYPE_LABELS[r.kind], r.cat_uth, r.cat_v2, r.amount, r.note])
        row_idx = ws3.max_row
        for c in range(1, 8):
            cell = ws3.cell(row=row_idx, column=c)
            cell.font = normal_font
            cell.border = border
            if c == 6:
                cell.number_format = "#,##0"
            elif c in (1, 2, 3):
                cell.alignment = Alignment(horizontal="center")
    autofit(ws3)

    # Sheet 4: Tiêu chuẩn làm sạch & Kiểm định chất lượng
    ws4 = wb.create_sheet("Tieu_chuan_lam_sach")
    ws4.append(["Tiêu chí kiểm định", "Mô tả chuẩn dữ liệu sạch", "Kết quả đo", "Trạng thái"])
    for c in range(1, 5):
        cell = ws4.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    qa_rows = [
        ("Tính đầy đủ (Completeness)", "Không có giá trị NULL, rỗng ở ngày, loại, danh mục, số tiền, ghi chú", f"{qa['null_count']} lỗi / {qa['total_rows']} dòng", "ĐẠT 100%"),
        ("Tính duy nhất (Uniqueness)", "Không có bản ghi giao dịch bị trùng lặp hoàn toàn", f"{qa['duplicate_count']} dòng trùng", "ĐẠT 100%"),
        ("Tính hợp lệ ngày (Timeliness)", "Định dạng chuẩn ISO YYYY-MM-DD, không có ngày tương lai hoặc năm sai lệch", f"{qa['date_min']} → {qa['date_max']} ({qa['future_date_count']} lỗi)", "ĐẠT 100%"),
        ("Tính hợp lệ danh mục (Validity)", "100% khớp tập danh mục chuẩn của UniSpend UTH và UniSpend 2.0", f"{qa['invalid_category_count']} lỗi danh mục", "ĐẠT 100%"),
        ("Chuẩn hóa tiền tệ (Accuracy)", "Số nguyên dương VNĐ, bội số 1.000đ, không ký tự lạ/số âm/ngoại lai bất thường", f"{qa['invalid_amount_count']} lỗi số tiền", "ĐẠT 100%"),
        ("An toàn bảng tính (Security)", "Không chứa ký tự kích hoạt công thức Excel (=, +, -, @) ở đầu ghi chú", f"{qa['formula_risk_count']} rủi ro", "ĐẠT 100%"),
    ]
    for row in qa_rows:
        ws4.append(list(row))
        row_idx = ws4.max_row
        for c in range(1, 5):
            cell = ws4.cell(row=row_idx, column=c)
            cell.font = bold_font if c == 4 else normal_font
            cell.border = border
            if c == 4:
                cell.fill = sub_fill
                cell.alignment = Alignment(horizontal="center")
    autofit(ws4)

    wb.save(xlsx_path)
    return xlsx_path


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = build_clean_records()
    qa = validate_records(records)

    uth_csv, v2_csv = write_csv_files(records)
    v2_db, uth_db = write_sqlite_files(records)
    xlsx_path = write_excel_report(records, qa)

    # Kiểm thử tích hợp ngược vào chính parser & validator của 2 ứng dụng
    parsed_uth = read_transactions_csv(uth_csv.read_bytes())
    assert len(parsed_uth) == len(records), "Import CSV vào UniSpend UTH không khớp số dòng!"

    v2_check = validate_sqlite_backup(v2_db.read_bytes())
    assert v2_check["valid"] is True, f"SQLite UniSpend 2.0 không hợp lệ: {v2_check}"
    assert v2_check["transactions_count"] == len(records)

    print("=== HOÀN TẤT TẠO & KIỂM ĐỊNH BỘ DỮ LIỆU SẠCH ===")
    print(f"Tổng số giao dịch : {qa['total_rows']}")
    print(f"Khoảng thời gian  : {qa['date_min']} -> {qa['date_max']} (6 tháng)")
    print(f"Tổng thu nhập     : {qa['total_income']:,} VNĐ")
    print(f"Tổng chi tiêu     : {qa['total_expense']:,} VNĐ")
    print(f"Chênh lệch ròng   : {qa['net_balance']:,} VNĐ ({qa['savings_rate_pct']}%)")
    print(f"Kiểm thử CSV UTH  : PASS ({len(parsed_uth)} giao dịch đọc thành công)")
    print(f"Kiểm thử SQLite v2: PASS ({v2_check['message']})")
    print("Các tệp đã xuất:")
    for p in (uth_csv, v2_csv, xlsx_path, v2_db, uth_db):
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
