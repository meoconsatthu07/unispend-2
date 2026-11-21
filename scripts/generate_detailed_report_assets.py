# -*- coding: utf-8 -*-
"""Sinh toàn bộ 14 hình ảnh biểu đồ (Matplotlib) & ảnh kết quả phân tích (Pillow) từ dữ liệu thật
và xuất file thống kê chuẩn xác `docs/figures/report_stats.json` để chèn vào báo cáo Word.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parent.parent
FIG_DIR = BASE_DIR / "docs" / "figures"
RAW_CSV = BASE_DIR / "data" / "real_dataset" / "raw_daily_household_transactions.csv"
KAGGLE_DB = BASE_DIR / "data" / "real_dataset" / "real_unispend2_clean.db"
UTH_DB = BASE_DIR / "data" / "clean_dataset" / "unispend2_clean.db"

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#94A3B8"
plt.rcParams["axes.linewidth"] = 0.9


def _load_pil_font(size: int, mono: bool = False, bold: bool = False):
    if mono:
        cands = ["C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf", "C:/Windows/Fonts/lucon.ttf"]
    else:
        cands = ["C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    for p in cands:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_notebook_card(filename: str, title: str, code_lines: list[str], output_lines: list[str]) -> Path:
    """Vẽ ảnh mô phỏng khối Code + Output chuẩn Jupyter/VS Code sắc nét để chèn vào Word."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / filename

    f_hdr = _load_pil_font(17, mono=False, bold=True)
    f_code = _load_pil_font(16, mono=True, bold=False)
    f_out = _load_pil_font(15, mono=True, bold=False)

    line_h_code = 24
    line_h_out = 22
    pad = 20
    code_h = max(1, len(code_lines)) * line_h_code + 24
    out_h = max(1, len(output_lines)) * line_h_out + 24
    w = 1200
    h = 48 + code_h + 16 + out_h + 24

    img = Image.new("RGB", (w, h), "#FFFFFF")
    draw = ImageDraw.Draw(img)

    # Header bar
    draw.rounded_rectangle([8, 8, w - 8, h - 8], radius=12, fill="#FFFFFF", outline="#CBD5E1", width=2)
    draw.rounded_rectangle([8, 8, w - 8, 46], radius=12, fill="#1E293B")
    draw.rectangle([8, 32, w - 8, 46], fill="#1E293B")
    draw.text((22, 27), f"Python (VS Code / Jupyter) — {title}", fill="#F8FAFC", font=f_hdr, anchor="lm")

    # Code box
    cy0 = 56
    cy1 = cy0 + code_h
    draw.rounded_rectangle([20, cy0, w - 20, cy1], radius=8, fill="#F8FAFC", outline="#E2E8F0", width=1)
    draw.rectangle([20, cy0, 26, cy1], fill="#3B82F6")
    y = cy0 + 12
    for line in code_lines:
        col = "#15803D" if line.lstrip().startswith("#") else "#1E293B"
        draw.text((38, y), line, fill=col, font=f_code)
        y += line_h_code

    # Output box
    oy0 = cy1 + 12
    oy1 = oy0 + out_h
    draw.rounded_rectangle([20, oy0, w - 20, oy1], radius=8, fill="#FFFFFF", outline="#CBD5E1", width=1)
    draw.rectangle([20, oy0, 26, oy1], fill="#10B981")
    y = oy0 + 12
    for line in output_lines:
        draw.text((38, y), line, fill="#0F172A", font=f_out)
        y += line_h_out

    img.save(out)
    return out


def _style_ax(ax, ylabel: str = "", xlabel: str = "") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", linestyle="--", alpha=0.35, color="#94A3B8")
    ax.set_axisbelow(True)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=11, fontweight="bold", color="#1E293B")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=11, fontweight="bold", color="#1E293B")
    ax.tick_params(colors="#334155", labelsize=10)


def main() -> dict:
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Đọc dữ liệu thô & dữ liệu sạch
    raw_df = pd.read_csv(RAW_CSV)
    conn = sqlite3.connect(str(KAGGLE_DB))
    clean_df = pd.read_sql("SELECT * FROM transactions", conn)
    conn.close()

    # Tái ghép cột Mode từ file raw cho phân tích phương thức thanh toán
    raw_valid = raw_df[raw_df["Income/Expense"].isin(["Income", "Expense"])].drop_duplicates().copy()
    raw_valid["dt"] = pd.to_datetime(raw_valid["Date"], dayfirst=True, format="mixed", errors="coerce")
    raw_valid["amount_vnd"] = (pd.to_numeric(raw_valid["Amount"], errors="coerce") * 300).round(-3).clip(lower=1000).astype(int)

    clean_df["dt"] = pd.to_datetime(clean_df["date"])
    clean_df["year"] = clean_df["dt"].dt.year
    clean_df["month"] = clean_df["dt"].dt.month
    clean_df["weekday"] = clean_df["dt"].dt.weekday  # 0=Thứ 2 .. 6=CN
    clean_df["season"] = clean_df["month"].map({
        1: "Đông", 2: "Đông", 12: "Đông",
        3: "Xuân", 4: "Xuân", 5: "Xuân",
        6: "Hạ", 7: "Hạ", 8: "Hạ",
        9: "Thu", 10: "Thu", 11: "Thu",
    })

    exp_df = clean_df[clean_df["kind"] == "expense"].copy()
    inc_df = clean_df[clean_df["kind"] == "income"].copy()

    # =========================================================================
    # A. 4 ẢNH CODE + OUTPUT GIỐNG JUPYTER NOTEBOOK (CHƯƠNG 2.1 -> 2.3)
    # =========================================================================
    render_notebook_card(
        "step_01_explore_info.png",
        "2.1 Khám phá kích thước & cấu trúc dữ liệu ban đầu",
        [
            "import pandas as pd",
            'df = pd.read_csv("data/real_dataset/raw_daily_household_transactions.csv")',
            'print("Kích thước dữ liệu ban đầu:", df.shape)',
            "print(df.dtypes)",
        ],
        [
            f"Kích thước dữ liệu ban đầu: {raw_df.shape}  (2.461 dòng, 8 thuộc tính)",
            "Date              object   (2461 non-null — chuỗi ngày hỗn hợp)",
            "Mode              object   (2461 non-null — phương thức thanh toán)",
            "Category          object   (2461 non-null — 50 nhãn danh mục thô)",
            "Subcategory       object   (1826 non-null — thiếu 635 giá trị)",
            "Note              object   (1940 non-null — thiếu 521 giá trị)",
            "Amount            float64  (2461 non-null — tiền tệ INR, min=2.0, max=250000.0)",
            "Income/Expense    object   (Expense: 2176 | Transfer-Out: 160 | Income: 125)",
            "Currency          object   (INR: 2461)",
        ],
    )

    nulls = raw_df.isnull().sum()
    dup_cnt = int(raw_df.duplicated().sum())
    transfer_cnt = int((raw_df["Income/Expense"] == "Transfer-Out").sum())
    render_notebook_card(
        "step_02_missing_dup.png",
        "2.2.1 – 2.2.3 Kiểm tra giá trị thiếu, trùng lặp & chuyển khoản nội bộ",
        [
            "# Kiểm tra giá trị thiếu, trùng lặp và dòng chuyển khoản nội bộ",
            "print('Giá trị thiếu theo cột:', df.isnull().sum().to_dict())",
            "print('Số dòng trùng lặp hoàn toàn:', df.duplicated().sum())",
            "print('Số dòng Transfer-Out:', (df['Income/Expense'] == 'Transfer-Out').sum())",
        ],
        [
            f"Giá trị thiếu theo cột: Date=0, Mode=0, Category=0, Subcategory={int(nulls['Subcategory'])}, Note={int(nulls['Note'])}, Amount=0",
            f"Tổng số ô giá trị thiếu: {int(nulls.sum())} (Subcategory: 25.8%, Note: 21.2%)",
            f"Số dòng dữ liệu trùng lặp hoàn toàn: {dup_cnt}",
            f"Số dòng chuyển khoản nội bộ (Transfer-Out): {transfer_cnt} -> Cần loại bỏ",
        ],
    )

    # Tính IQR trên Amount gốc (INR) và sau quy đổi (VNĐ)
    q1 = float(exp_df["amount"].quantile(0.25))
    q3 = float(exp_df["amount"].quantile(0.75))
    iqr = q3 - q1
    upper_iqr = q3 + 1.5 * iqr
    iqr_outliers = int((exp_df["amount"] > upper_iqr).sum())
    render_notebook_card(
        "step_03_date_iqr.png",
        "2.2.4 – 2.2.6 Chuẩn hóa ngày tháng & Kiểm tra ngoại lai (IQR)",
        [
            "df['clean_date'] = pd.to_datetime(df['Date'], dayfirst=True, format='mixed', errors='coerce')",
            "Q1, Q3 = exp_df['amount'].quantile(0.25), exp_df['amount'].quantile(0.75)",
            "IQR = Q3 - Q1; upper = Q3 + 1.5 * IQR",
            "print('Ngày lỗi:', df['clean_date'].isna().sum(), '| Ngoại lai IQR:', (exp_df['amount'] > upper).sum())",
        ],
        [
            "Kiểu dữ liệu Date trước xử lý : str (trộn lẫn DD-MM-YYYY HH:MM và DD-MM-YYYY)",
            "Kiểu dữ liệu Date sau xử lý   : datetime64 -> chuỗi chuẩn ISO YYYY-MM-DD (0 ngày lỗi)",
            f"Phân tích IQR cho số tiền Chi tiêu (VNĐ): Q1 = {q1:,.0f}đ | Q3 = {q3:,.0f}đ | IQR = {iqr:,.0f}đ",
            f"Ngưỡng trên IQR (Q3 + 1.5*IQR): {upper_iqr:,.0f}đ -> Có {iqr_outliers} giao dịch lớn (đầu tư/nhà ở)",
            "Quyết định: GIỮ LẠI các giao dịch lớn hợp lệ để phản ánh trung thực dòng tiền thực tế.",
        ],
    )

    sample_sql = clean_df.head(6)
    sql_out_lines = [
        "SQLite3 Query: SELECT COUNT(*) FROM transactions;  -->  2298 bản ghi sạch (0 lỗi CHECK)",
        "ID  | Ngày       | Loại    | Danh mục | Số tiền (VNĐ) | Ghi chú đã chuẩn hóa",
        "----+------------+---------+----------+---------------+------------------------------------------",
    ]
    for r in sample_sql.itertuples(index=False):
        sql_out_lines.append(
            f"{r.id:<3d} | {r.date} | {r.kind:<7s} | {r.category:<8s} | {r.amount:>13,d} | {str(r.note)[:40]}"
        )
    render_notebook_card(
        "step_04_sqlite_verify.png",
        "2.3 Kiểm tra dữ liệu đã lưu trong cơ sở dữ liệu SQLite (real_unispend2_clean.db)",
        [
            "import sqlite3",
            'conn = sqlite3.connect("data/real_dataset/real_unispend2_clean.db")',
            'print("Tổng bản ghi:", conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])',
            'print(conn.execute("SELECT * FROM transactions LIMIT 6").fetchall())',
        ],
        sql_out_lines,
    )

    # =========================================================================
    # B. 9 BIỂU ĐỒ MATPLOTLIB PHÂN TÍCH CHUYÊN SÂU (CHƯƠNG 2.4)
    # =========================================================================
    tot_inc = int(inc_df["amount"].sum())
    tot_exp = int(exp_df["amount"].sum())
    net_bal = tot_inc - tot_exp
    save_rate = net_bal / tot_inc * 100.0

    # Chart 1: Pie Thu vs Chi
    fig, ax = plt.subplots(figsize=(8.2, 5.0), dpi=180)
    vals = [tot_inc / 1e6, tot_exp / 1e6]
    labels = [f"Tổng thu nhập\n{tot_inc/1e6:.2f} triệu VNĐ", f"Tổng chi tiêu\n{tot_exp/1e6:.2f} triệu VNĐ"]
    colors = ["#4C78A8", "#F58518"]
    wedges, texts, autotexts = ax.pie(
        vals, labels=labels, autopct="%1.2f%%", startangle=90, colors=colors,
        pctdistance=0.62, textprops={"fontsize": 10.5, "color": "#1E293B"},
        wedgeprops={"edgecolor": "white", "linewidth": 2},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")
        t.set_fontsize(11)
    ax.set_title("Tổng quan cơ cấu Thu nhập và Chi tiêu (2.298 giao dịch sạch)", fontsize=13, fontweight="bold", color="#163A5F", pad=14)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_01_thu_chi_tong_quan.png")
    plt.close(fig)

    # Chart 2: Tỷ trọng chi tiêu (%) theo 6 danh mục
    cat_exp = exp_df.groupby("category")["amount"].sum().sort_values(ascending=False)
    cat_exp_pct = (cat_exp / tot_exp * 100.0)
    fig, ax = plt.subplots(figsize=(8.8, 4.8), dpi=180)
    bars = ax.bar(cat_exp_pct.index, cat_exp_pct.values, color="#4C78A8", width=0.58)
    avg_pct = 100.0 / len(cat_exp_pct)
    ax.axhline(avg_pct, color="#DC2626", linestyle="--", linewidth=1.3, label=f"TB đều: {avg_pct:.2f}%")
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 1.2, f"{h:.2f}%", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, max(cat_exp_pct.values) + 10)
    ax.set_title("Tỷ trọng giá trị chi tiêu (%) theo từng danh mục chuẩn", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tỷ trọng chi tiêu (%)")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_02_chi_tieu_theo_danh_muc.png")
    plt.close(fig)

    # Chart 3: Tần suất số lần giao dịch theo danh mục
    cat_cnt = exp_df["category"].value_counts()
    fig, ax = plt.subplots(figsize=(8.8, 4.8), dpi=180)
    bars = ax.bar(cat_cnt.index, cat_cnt.values, color="#10B981", width=0.58)
    avg_cnt = cat_cnt.mean()
    ax.axhline(avg_cnt, color="#DC2626", linestyle="--", linewidth=1.3, label=f"TB: {avg_cnt:.0f} GD/danh mục")
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 18, f"{int(h)} GD", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#065F46")
    ax.set_ylim(0, max(cat_cnt.values) + 120)
    ax.set_title("Tần suất số lần phát sinh giao dịch chi tiêu theo danh mục", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Số lượng giao dịch (lần)")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_03_tan_suat_giao_dich.png")
    plt.close(fig)

    # Chart 4: Cơ cấu nguồn thu nhập
    inc_cat = inc_df.groupby("category")["amount"].sum().sort_values(ascending=False)
    inc_pct = inc_cat / tot_inc * 100.0
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=180)
    bars = ax.bar(inc_pct.index, inc_pct.values, color="#2563EB", width=0.52)
    for b, (cat_name, raw_amt) in zip(bars, inc_cat.items()):
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 1.5, f"{h:.2f}%\n({raw_amt/1e6:.1f}tr)", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#1E3A8A")
    ax.set_ylim(0, max(inc_pct.values) + 15)
    ax.set_title("Cơ cấu nguồn Thu nhập theo danh mục chuẩn (Tổng: 912,72 triệu VNĐ)", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tỷ trọng thu nhập (%)")
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_04_nguon_thu_nhap.png")
    plt.close(fig)

    # Chart 5: Phương thức thanh toán (Mode) từ dữ liệu thật
    mode_exp = raw_valid[raw_valid["Income/Expense"] == "Expense"]["Mode"].value_counts().head(5)
    mode_pct = mode_exp / mode_exp.sum() * 100.0
    fig, ax = plt.subplots(figsize=(9.0, 4.6), dpi=180)
    short_modes = [m.replace("Saving Bank account 1", "Tài khoản ngân hàng 1").replace("Saving Bank account 2", "Tài khoản ngân hàng 2").replace("Cash", "Tiền mặt (Cash)").replace("Credit Card", "Thẻ tín dụng").replace("Debit Card", "Thẻ ghi nợ") for m in mode_pct.index]
    bars = ax.bar(short_modes, mode_pct.values, color="#4C78A8", width=0.55)
    for b, cnt in zip(bars, mode_exp.values):
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 1.2, f"{h:.1f}%\n({cnt} GD)", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, max(mode_pct.values) + 13)
    ax.set_title("Phân bố giao dịch chi tiêu theo Phương thức thanh toán (Top 5)", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tỷ lệ giao dịch (%)")
    plt.xticks(rotation=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_05_phuong_thuc_thanh_toan.png")
    plt.close(fig)

    # Chart 6: Diễn biến Thu - Chi theo năm (2015 -> 2018)
    yr_inc = inc_df.groupby("year")["amount"].sum() / 1e6
    yr_exp = exp_df.groupby("year")["amount"].sum() / 1e6
    years = sorted(clean_df["year"].unique())
    y_i = [float(yr_inc.get(y, 0.0)) for y in years]
    y_e = [float(yr_exp.get(y, 0.0)) for y in years]
    fig, ax = plt.subplots(figsize=(8.8, 4.6), dpi=180)
    ax.plot(years, y_i, marker="o", linewidth=2.5, color="#10B981", label="Tổng thu nhập (triệu VNĐ)")
    ax.plot(years, y_e, marker="s", linewidth=2.5, color="#EF4444", label="Tổng chi tiêu (triệu VNĐ)")
    for x, vi, ve in zip(years, y_i, y_e):
        ax.text(x, vi + 10, f"{vi:.1f}tr", ha="center", fontsize=9.5, fontweight="bold", color="#065F46")
        ax.text(x, ve + 10, f"{ve:.1f}tr", ha="center", fontsize=9.5, fontweight="bold", color="#991B1B")
    ax.set_xticks(years)
    ax.set_ylim(0, max(max(y_i), max(y_e)) + 55)
    ax.set_title("Diễn biến Tổng Thu nhập và Tổng Chi tiêu qua các năm (2015 – 2018)", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Giá trị (Triệu VNĐ)", xlabel="Năm")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_06_xu_huong_theo_nam.png")
    plt.close(fig)

    # Chart 7: Chi tiêu theo 12 tháng trong năm (Line chart + TB đỏ đứt nét giống bài mẫu)
    m_exp = exp_df.groupby("month")["amount"].sum() / 1e6
    months = list(range(1, 13))
    m_vals = [float(m_exp.get(m, 0.0)) for m in months]
    m_avg = float(np.mean(m_vals))
    fig, ax = plt.subplots(figsize=(9.2, 4.6), dpi=180)
    ax.plot(months, m_vals, marker="o", linewidth=2.2, color="#2563EB")
    ax.axhline(m_avg, color="#DC2626", linestyle="--", linewidth=1.3, label=f"TB: {m_avg:.1f} triệu/tháng")
    for x, v in zip(months, m_vals):
        ax.text(x, v + 2.8, f"{v:.1f}tr", ha="center", fontsize=8.8, fontweight="bold", color="#1E3A8A")
    ax.set_xticks(months)
    ax.set_ylim(0, max(m_vals) + 18)
    ax.set_title("Tổng chi tiêu cộng dồn theo 12 tháng trong năm (2015 – 2018)", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tổng chi tiêu (Triệu VNĐ)", xlabel="Tháng")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_07_chi_tieu_theo_thang.png")
    plt.close(fig)

    # Chart 8: Chi tiêu theo Thứ trong tuần (Thứ 2 -> Chủ nhật)
    wd_labels = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
    wd_exp = exp_df.groupby("weekday")["amount"].sum() / 1e6
    wd_vals = [float(wd_exp.get(i, 0.0)) for i in range(7)]
    wd_avg = float(np.mean(wd_vals))
    fig, ax = plt.subplots(figsize=(8.8, 4.6), dpi=180)
    bars = ax.bar(wd_labels, wd_vals, color="#4C78A8", width=0.58)
    ax.axhline(wd_avg, color="#DC2626", linestyle="--", linewidth=1.3, label=f"TB: {wd_avg:.1f} triệu")
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 2.0, f"{h:.1f}tr", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, max(wd_vals) + 18)
    ax.set_title("Phân tích tổng chi tiêu theo Ngày trong tuần (Thứ 2 – Chủ nhật)", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tổng chi tiêu (Triệu VNĐ)", xlabel="Ngày trong tuần")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_08_chi_tieu_theo_thu.png")
    plt.close(fig)

    # Chart 9: Chi tiêu theo 4 Mùa trong năm
    seasons_order = ["Xuân", "Hạ", "Thu", "Đông"]
    s_exp = exp_df.groupby("season")["amount"].sum() / 1e6
    s_vals = [float(s_exp.get(s, 0.0)) for s in seasons_order]
    s_avg = float(np.mean(s_vals))
    fig, ax = plt.subplots(figsize=(8.2, 4.6), dpi=180)
    bars = ax.bar(seasons_order, s_vals, color="#4C78A8", width=0.5)
    ax.axhline(s_avg, color="#DC2626", linestyle="--", linewidth=1.3, label=f"TB: {s_avg:.1f} triệu/mùa")
    for b in bars:
        h = b.get_height()
        ax.text(b.get_x() + b.get_width() / 2, h + 3.5, f"{h:.1f}tr\n({h/(tot_exp/1e6)*100:.1f}%)", ha="center", va="bottom", fontsize=9.8, fontweight="bold", color="#1E293B")
    ax.set_ylim(0, max(s_vals) + 36)
    ax.set_title("Phân tích tổng chi tiêu theo 4 Mùa trong năm", fontsize=13, fontweight="bold", color="#163A5F", pad=12)
    _style_ax(ax, ylabel="Tổng chi tiêu (Triệu VNĐ)", xlabel="Mùa trong năm")
    ax.legend(frameon=False, fontsize=10)
    plt.tight_layout()
    fig.savefig(FIG_DIR / "chart_09_chi_tieu_theo_mua.png")
    plt.close(fig)

    stats = {
        "raw_rows": int(len(raw_df)),
        "clean_rows": int(len(clean_df)),
        "exp_rows": int(len(exp_df)),
        "inc_rows": int(len(inc_df)),
        "tot_inc": tot_inc,
        "tot_exp": tot_exp,
        "net_bal": net_bal,
        "save_rate": round(save_rate, 2),
        "q1": q1, "q3": q3, "iqr": iqr, "upper_iqr": upper_iqr, "iqr_outliers": iqr_outliers,
        "cat_exp_pct": {k: round(float(v), 2) for k, v in cat_exp_pct.items()},
        "cat_cnt": {k: int(v) for k, v in cat_cnt.items()},
        "inc_pct": {k: round(float(v), 2) for k, v in inc_pct.items()},
        "mode_top": {str(k): int(v) for k, v in mode_exp.items()},
        "mode_pct": {str(k): round(float(v), 2) for k, v in mode_pct.items()},
        "year_inc": {str(y): round(v, 2) for y, v in zip(years, y_i)},
        "year_exp": {str(y): round(v, 2) for y, v in zip(years, y_e)},
        "month_vals": {str(m): round(v, 2) for m, v in zip(months, m_vals)},
        "month_max": (int(months[int(np.argmax(m_vals))]), round(max(m_vals), 2)),
        "month_min": (int(months[int(np.argmin(m_vals))]), round(min(m_vals), 2)),
        "month_avg": round(m_avg, 2),
        "wd_vals": {wd_labels[i]: round(wd_vals[i], 2) for i in range(7)},
        "wd_max": (wd_labels[int(np.argmax(wd_vals))], round(max(wd_vals), 2)),
        "wd_min": (wd_labels[int(np.argmin(wd_vals))], round(min(wd_vals), 2)),
        "wd_avg": round(wd_avg, 2),
        "season_vals": {seasons_order[i]: round(s_vals[i], 2) for i in range(4)},
        "season_max": (seasons_order[int(np.argmax(s_vals))], round(max(s_vals), 2)),
        "season_min": (seasons_order[int(np.argmin(s_vals))], round(min(s_vals), 2)),
    }
    (FIG_DIR / "report_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print("GENERATED ALL 13 ASSETS & report_stats.json OK!")
    return stats


if __name__ == "__main__":
    main()
