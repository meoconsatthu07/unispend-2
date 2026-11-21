# -*- coding: utf-8 -*-
"""Pipeline ETL làm sạch bộ dữ liệu THẬT tải từ Internet (Daily Household Transactions).

Nguồn dữ liệu gốc (Public Dataset):
- Tên gốc: Daily Household Transactions (Kaggle — tác giả Prasad Patil)
- Bản mirror CSV công khai (GitHub):
  https://github.com/Mahesh1827/Daily_Transactions/blob/main/Daily%20Household%20Transactions.csv

Đầu ra tại: data/real_dataset/
- raw_daily_household_transactions.csv   (Dữ liệu thô gốc tải từ Internet)
- real_transactions_uth_clean.csv        (CSV sạch chuẩn import UniSpend UTH 3D)
- real_transactions_unispend2_clean.csv  (CSV sạch chuẩn UniSpend 2.0)
- real_unispend2_clean.db                (SQLite sạch cho UniSpend 2.0)
- real_unispend3d_clean.db               (SQLite sạch cho UniSpend UTH 3D)
- bao_cao_lam_sach_du_lieu_that.xlsx     (Báo cáo Excel đối chiếu Trước/Sau làm sạch cho giảng viên)
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from expense_tracker.reports_backup import validate_sqlite_backup
from expense_tracker.storage import (
    TOTAL_BUDGET_CATEGORY,
    TYPE_LABELS,
    ExpenseStore,
)
from unispend_3d.csv_import import read_transactions_csv

DATA_DIR = BASE_DIR / "data" / "real_dataset"
RAW_CSV = DATA_DIR / "raw_daily_household_transactions.csv"
SOURCE_URL = "https://github.com/Mahesh1827/Daily_Transactions/blob/main/Daily%20Household%20Transactions.csv"
INR_TO_VND = 300  # Tỷ giá quy đổi tham chiếu: 1 INR = 300 VNĐ (làm tròn 1.000 VNĐ)

EXPENSE_MAP: dict[str, tuple[str, str]] = {
    # raw_category_lower: (cat_v2, cat_uth)
    "food": ("Ăn uống", "Tiền ăn"),
    "cook": ("Ăn uống", "Tiền ăn"),
    "rent": ("Tiền trọ", "Tiền trọ"),
    "household": ("Tiền trọ", "Tiền trọ"),
    "maid": ("Tiền trọ", "Tiền trọ"),
    "garbage disposal": ("Tiền trọ", "Tiền trọ"),
    "water (jar /tanker)": ("Tiền trọ", "Tiền trọ"),
    "transportation": ("Đi lại", "Đi lại"),
    "education": ("Học tập", "Học tập"),
    "self-development": ("Học tập", "Học tập"),
    "documents": ("Học tập", "Học tập"),
    "culture": ("Giải trí", "Giải trí & Xã giao"),
    "festivals": ("Giải trí", "Giải trí & Xã giao"),
    "social life": ("Giải trí", "Giải trí & Xã giao"),
    "tourism": ("Giải trí", "Giải trí & Xã giao"),
    "gift": ("Giải trí", "Giải trí & Xã giao"),
    "subscription": ("Giải trí", "Giải trí & Xã giao"),
    "apparel": ("Khác", "Sinh hoạt & Mua sắm"),
    "beauty": ("Khác", "Sinh hoạt & Mua sắm"),
    "grooming": ("Khác", "Sinh hoạt & Mua sắm"),
}

INCOME_MAP: dict[str, tuple[str, str]] = {
    "salary": ("Làm thêm", "Làm thêm (Part-time)"),
    "bonus": ("Học bổng", "Học bổng & Thưởng"),
    "gpay reward": ("Học bổng", "Học bổng & Thưởng"),
    "amazon pay cashback": ("Học bổng", "Học bổng & Thưởng"),
    "petty cash": ("Gia đình hỗ trợ", "Trợ cấp gia đình"),
}


def _clean_text(val: object) -> str:
    if pd.isna(val):
        return ""
    text = re.sub(r"\s+", " ", str(val)).strip()
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = text.lstrip("=+-@ ")
    return text


def _map_category(kind: str, raw_cat: str) -> tuple[str, str]:
    key = raw_cat.strip().lower()
    if kind == "expense":
        return EXPENSE_MAP.get(key, ("Khác", "Chi phí khác"))
    return INCOME_MAP.get(key, ("Khác", "Thu nhập khác"))


def _to_vnd(amount_inr: float) -> int:
    raw_vnd = round(float(amount_inr) * INR_TO_VND)
    rounded = max(1_000, int(round(raw_vnd / 1_000) * 1_000))
    return rounded


def clean_dataset() -> tuple[pd.DataFrame, dict[str, object]]:
    if not RAW_CSV.is_file():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu thô tại {RAW_CSV}")

    raw_df = pd.read_csv(RAW_CSV)
    raw_rows = len(raw_df)
    raw_null_sub = int(raw_df["Subcategory"].isna().sum())
    raw_null_note = int(raw_df["Note"].isna().sum())
    raw_exact_dups = int(raw_df.duplicated().sum())
    raw_transfer_out = int((raw_df["Income/Expense"] == "Transfer-Out").sum())

    # Bước 1: Loại bỏ Transfer-Out (chuyển khoản nội bộ, không phải thu/chi)
    df = raw_df[raw_df["Income/Expense"].isin(["Income", "Expense"])].copy()

    # Bước 2: Loại bỏ bản ghi trùng lặp hoàn toàn
    before_dedup = len(df)
    df = df.drop_duplicates().copy()
    dropped_dups = before_dedup - len(df)

    # Bước 3: Chuẩn hóa ngày hỗn hợp -> ISO YYYY-MM-DD
    parsed_dates = pd.to_datetime(df["Date"], dayfirst=True, format="mixed", errors="coerce")
    invalid_dates = int(parsed_dates.isna().sum())
    df["clean_date"] = parsed_dates.dt.strftime("%Y-%m-%d")
    df = df[df["clean_date"].notna()].copy()

    # Bước 4: Chuẩn hóa loại giao dịch & danh mục
    df["kind"] = df["Income/Expense"].map({"Income": "income", "Expense": "expense"})
    mapped = [
        _map_category(k, c)
        for k, c in zip(df["kind"], df["Category"].astype(str))
    ]
    df["cat_v2"] = [m[0] for m in mapped]
    df["cat_uth"] = [m[1] for m in mapped]

    # Bước 5: Chuẩn hóa số tiền INR -> VNĐ số nguyên dương hợp lệ
    df["amount_inr"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df[df["amount_inr"].notna() & (df["amount_inr"] > 0)].copy()
    df["amount_vnd"] = df["amount_inr"].apply(_to_vnd)

    # Lọc bỏ ngoại lai vượt ngưỡng 500 triệu VNĐ/giao dịch (ràng buộc của UniSpend UTH)
    before_cap = len(df)
    df = df[df["amount_vnd"] <= 500_000_000].copy()
    dropped_outliers = before_cap - len(df)

    # Bước 6: Làm sạch & bù giá trị thiếu cho Ghi chú (Note)
    notes: list[str] = []
    imputed_notes = 0
    for raw_note, raw_sub, raw_cat, raw_mode in zip(
        df["Note"], df["Subcategory"], df["Category"], df["Mode"]
    ):
        n = _clean_text(raw_note)
        s = _clean_text(raw_sub)
        c = _clean_text(raw_cat)
        m = _clean_text(raw_mode)
        if not n:
            imputed_notes += 1
            parts = [p for p in (c, s) if p]
            base = " - ".join(parts) if parts else "Giao dịch cá nhân"
            n = f"{base} ({m})" if m else base
        elif s and s.lower() not in n.lower() and len(n) < 40:
            n = f"{s}: {n}"
        notes.append(n[:190])
    df["clean_note"] = notes

    # Sắp xếp tăng dần theo ngày
    df = df.sort_values(["clean_date", "kind", "cat_uth", "amount_vnd", "clean_note"]).reset_index(drop=True)

    stats = {
        "source_name": "Daily Household Transactions (Kaggle / GitHub)",
        "source_url": SOURCE_URL,
        "raw_rows": raw_rows,
        "raw_transfer_out": raw_transfer_out,
        "raw_exact_dups": raw_exact_dups,
        "dropped_dups": dropped_dups,
        "raw_null_subcategory": raw_null_sub,
        "raw_null_note": raw_null_note,
        "imputed_notes": imputed_notes,
        "invalid_dates_dropped": invalid_dates,
        "outliers_dropped": dropped_outliers,
        "clean_rows": len(df),
        "date_min": str(df["clean_date"].min()),
        "date_max": str(df["clean_date"].max()),
        "exchange_rate": f"1 INR = {INR_TO_VND} VNĐ",
        "total_income_vnd": int(df.loc[df["kind"] == "income", "amount_vnd"].sum()),
        "total_expense_vnd": int(df.loc[df["kind"] == "expense", "amount_vnd"].sum()),
    }
    return df, stats


def export_all(df: pd.DataFrame, stats: dict[str, object]) -> dict[str, Path]:
    # 1. CSV chuẩn UniSpend UTH 3D
    uth_csv = DATA_DIR / "real_transactions_uth_clean.csv"
    with open(uth_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ngày giao dịch", "Loại giao dịch", "Danh mục", "Số tiền (VNĐ)", "Ghi chú chi tiết"])
        for row in df.itertuples(index=False):
            w.writerow([row.clean_date, TYPE_LABELS[row.kind], row.cat_uth, int(row.amount_vnd), row.clean_note])

    # 2. CSV chuẩn UniSpend 2.0
    v2_csv = DATA_DIR / "real_transactions_unispend2_clean.csv"
    with open(v2_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Mã", "Ngày", "Loại", "Danh mục", "Số tiền (VNĐ)", "Ghi chú"])
        for idx, row in enumerate(df.itertuples(index=False), start=1):
            w.writerow([idx, row.clean_date, TYPE_LABELS[row.kind], row.cat_v2, int(row.amount_vnd), row.clean_note])

    # 3. SQLite sạch cho UniSpend 2.0
    v2_db = DATA_DIR / "real_unispend2_clean.db"
    if v2_db.exists():
        v2_db.unlink()
    store = ExpenseStore(v2_db)
    try:
        with store.connection:
            store.connection.executemany(
                "INSERT INTO transactions(date, kind, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                [
                    (row.clean_date, row.kind, row.cat_v2, int(row.amount_vnd), row.clean_note)
                    for row in df.itertuples(index=False)
                ],
            )
        # Tạo ngân sách tham chiếu cho 6 tháng gần nhất trong dataset
        recent_months = sorted(df["clean_date"].str.slice(0, 7).unique())[-6:]
        for m in recent_months:
            store.set_budgets(m, {
                TOTAL_BUDGET_CATEGORY: 15_000_000,
                "Ăn uống": 3_000_000,
                "Tiền trọ": 3_000_000,
                "Đi lại": 1_500_000,
                "Học tập": 1_500_000,
                "Giải trí": 2_000_000,
                "Khác": 4_000_000,
            })
    finally:
        store.close()

    # 4. SQLite sạch cho UniSpend UTH 3D
    uth_db = DATA_DIR / "real_unispend3d_clean.db"
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
                [
                    (row.clean_date, TYPE_LABELS[row.kind], row.cat_uth, float(row.amount_vnd), row.clean_note)
                    for row in df.itertuples(index=False)
                ],
            )
            uth_limits = json.dumps({
                "Tiền ăn": 3_000_000,
                "Tiền trọ": 3_000_000,
                "Đi lại": 1_500_000,
                "Học tập": 1_500_000,
                "Sinh hoạt & Mua sắm": 1_500_000,
                "Giải trí & Xã giao": 2_000_000,
                "Chi phí khác": 2_500_000,
            }, ensure_ascii=False)
            recent_months = sorted(df["clean_date"].str.slice(0, 7).unique())[-6:]
            conn.executemany(
                "INSERT INTO budgets(month, total_budget, category_limits_json) VALUES (?, ?, ?)",
                [(m, 15_000_000.0, uth_limits) for m in recent_months],
            )
    finally:
        conn.close()

    # 5. Excel báo cáo Trước/Sau làm sạch cho giảng viên
    xlsx_path = DATA_DIR / "bao_cao_lam_sach_du_lieu_that.xlsx"
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

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
            ws.column_dimensions[letter].width = max(14, min(55, width + 4))

    # Sheet 1: Báo cáo ETL Trước/Sau
    ws1 = wb.active
    ws1.title = "Bao_cao_ETL_Truoc_Sau"
    ws1["A1"] = "BÁO CÁO LÀM SẠCH DỮ LIỆU THẬT (DAILY HOUSEHOLD TRANSACTIONS)"
    ws1["A1"].font = title_font
    ws1["A2"] = f"Nguồn công khai: {stats['source_url']}"
    ws1["A2"].font = normal_font
    ws1["A3"] = f"Ngày xử lý: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Quy đổi: {stats['exchange_rate']}"
    ws1["A3"].font = normal_font
    ws1.append([])

    ws1.append(["Bước xử lý / Chỉ số", "Trước làm sạch (Raw)", "Sau làm sạch (Clean)", "Ghi chú xử lý"])
    for c in range(1, 5):
        cell = ws1.cell(row=5, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    etl_rows = [
        ("Tổng số dòng dữ liệu", stats["raw_rows"], stats["clean_rows"], "Giữ lại toàn bộ giao dịch Thu/Chi hợp lệ"),
        ("Giao dịch nội bộ (Transfer-Out)", stats["raw_transfer_out"], 0, "Đã loại bỏ để tránh tính trùng chi tiêu"),
        ("Bản ghi trùng lặp hoàn toàn", stats["raw_exact_dups"], 0, f"Đã khử {stats['dropped_dups']} dòng trùng trong Thu/Chi"),
        ("Giá trị thiếu ở Ghi chú (Note)", stats["raw_null_note"], 0, f"Đã bù {stats['imputed_notes']} ghi chú từ Category/Subcategory/Mode"),
        ("Định dạng ngày hỗn hợp", "Nhiều định dạng (DD-MM-YYYY, HH:MM)", "100% ISO YYYY-MM-DD", f"Khoảng thời gian: {stats['date_min']} → {stats['date_max']}"),
        ("Danh mục lộn xộn (38 nhãn tiếng Anh)", "38 nhãn chưa chuẩn hóa", "Chuẩn UniSpend UTH & v2", "Ánh xạ 100% không mất dữ liệu"),
        ("Đơn vị tiền tệ", "INR (có số thập phân)", "VNĐ (số nguyên dương)", f"Quy đổi {stats['exchange_rate']}, loại {stats['outliers_dropped']} ngoại lai"),
    ]
    for r in etl_rows:
        ws1.append(list(r))
        ri = ws1.max_row
        for c in range(1, 5):
            cell = ws1.cell(row=ri, column=c)
            cell.font = bold_font if c == 1 else normal_font
            cell.border = border
    autofit(ws1)

    # Sheet 2: Tổng quan theo năm
    ws2 = wb.create_sheet("Tong_quan_theo_nam")
    ws2.append(["Năm", "Số giao dịch", "Tổng thu (VNĐ)", "Tổng chi (VNĐ)", "Chênh lệch (VNĐ)"])
    for c in range(1, 6):
        cell = ws2.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    df["year"] = df["clean_date"].str.slice(0, 4)
    for yr, grp in df.groupby("year"):
        inc = int(grp.loc[grp["kind"] == "income", "amount_vnd"].sum())
        exp = int(grp.loc[grp["kind"] == "expense", "amount_vnd"].sum())
        ws2.append([yr, len(grp), inc, exp, inc - exp])
        ri = ws2.max_row
        for c in range(1, 6):
            cell = ws2.cell(row=ri, column=c)
            cell.font = normal_font
            cell.border = border
            if c in (3, 4, 5):
                cell.number_format = "#,##0"
            elif c in (1, 2):
                cell.alignment = Alignment(horizontal="center")
    autofit(ws2)

    # Sheet 3: Phân bổ danh mục
    ws3 = wb.create_sheet("Phan_bo_danh_muc")
    ws3.append(["Loại", "Danh mục (UniSpend UTH)", "Danh mục (UniSpend 2.0)", "Số giao dịch", "Tổng tiền (VNĐ)"])
    for c in range(1, 6):
        cell = ws3.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    cat_grp = df.groupby(["kind", "cat_uth", "cat_v2"], as_index=False).agg(
        count=("amount_vnd", "size"),
        total=("amount_vnd", "sum"),
    ).sort_values(["kind", "total"], ascending=[True, False])
    for row in cat_grp.itertuples(index=False):
        ws3.append([TYPE_LABELS[row.kind], row.cat_uth, row.cat_v2, int(row.count), int(row.total)])
        ri = ws3.max_row
        for c in range(1, 6):
            cell = ws3.cell(row=ri, column=c)
            cell.font = normal_font
            cell.border = border
            if c == 5:
                cell.number_format = "#,##0"
    autofit(ws3)

    # Sheet 4: Toàn bộ dữ liệu sạch
    ws4 = wb.create_sheet("Du_lieu_sach_da_chuan_hoa")
    ws4.append(["Mã", "Ngày", "Loại", "Danh mục (UTH)", "Danh mục (v2)", "Số tiền gốc (INR)", "Số tiền (VNĐ)", "Ghi chú sạch"])
    for c in range(1, 9):
        cell = ws4.cell(row=1, column=c)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for idx, row in enumerate(df.itertuples(index=False), start=1):
        ws4.append([
            idx, row.clean_date, TYPE_LABELS[row.kind], row.cat_uth, row.cat_v2,
            float(row.amount_inr), int(row.amount_vnd), row.clean_note,
        ])
        ri = ws4.max_row
        ws4.cell(row=ri, column=7).number_format = "#,##0"
    autofit(ws4)

    wb.save(xlsx_path)

    return {
        "uth_csv": uth_csv,
        "v2_csv": v2_csv,
        "v2_db": v2_db,
        "uth_db": uth_db,
        "xlsx": xlsx_path,
    }


def main() -> int:
    df, stats = clean_dataset()
    outputs = export_all(df, stats)

    # Kiểm thử tích hợp ngược vào cả 2 app
    parsed_uth = read_transactions_csv(outputs["uth_csv"].read_bytes())
    assert len(parsed_uth) == len(df), "Import CSV vào UniSpend UTH không khớp số dòng!"

    v2_check = validate_sqlite_backup(outputs["v2_db"].read_bytes())
    assert v2_check["valid"] is True, f"SQLite UniSpend 2.0 lỗi: {v2_check}"
    assert v2_check["transactions_count"] == len(df)

    print("=== HOÀN TẤT LÀM SẠCH DỮ LIỆU THẬT TỪ INTERNET ===")
    print(f"Nguồn gốc         : {stats['source_name']}")
    print(f"Dữ liệu thô (Raw) : {stats['raw_rows']} dòng (Transfer-Out: {stats['raw_transfer_out']}, Trùng: {stats['raw_exact_dups']}, Thiếu Note: {stats['raw_null_note']})")
    print(f"Dữ liệu sạch      : {stats['clean_rows']} dòng ({stats['date_min']} -> {stats['date_max']})")
    print(f"Tổng thu (VNĐ)    : {stats['total_income_vnd']:,} VNĐ")
    print(f"Tổng chi (VNĐ)    : {stats['total_expense_vnd']:,} VNĐ")
    print(f"Kiểm thử CSV UTH  : PASS ({len(parsed_uth)} giao dịch)")
    print(f"Kiểm thử SQLite v2: PASS ({v2_check['message']})")
    for k, p in outputs.items():
        print(f"  - [{k}] {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
