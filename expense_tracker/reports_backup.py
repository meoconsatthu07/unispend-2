"""Xuất báo cáo Excel (.xlsx), PDF (.pdf) và Sao lưu / Khôi phục SQLite an toàn."""

from __future__ import annotations

import io
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .storage import BudgetStatus, Transaction, TYPE_LABELS
from .utils import display_date, money


# =============================================================================
# 1. XUẤT BÁO CÁO EXCEL (.XLSX)
# =============================================================================
def export_excel_bytes(
    month: str,
    summary: dict[str, int],
    category_totals: dict[str, int],
    budget_statuses: Iterable[BudgetStatus],
    transactions: Iterable[Transaction],
    extra_metrics: dict[str, str | int] | None = None,
) -> bytes:
    """Tạo file báo cáo Excel (.xlsx) gồm 2 sheet: Tổng quan & Chi tiết giao dịch."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Tong_quan_thang"

    header_fill = PatternFill("solid", fgColor="214C3C")
    mint_fill = PatternFill("solid", fgColor="DCEDE1")
    header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Segoe UI", size=14, bold=True, color="214C3C")
    bold_font = Font(name="Segoe UI", size=10, bold=True, color="243B32")
    normal_font = Font(name="Segoe UI", size=10, color="243B32")
    thin_side = Side(border_style="thin", color="E4ECE6")
    cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)

    ws_summary["A1"] = f"BÁO CÁO TÀI CHÍNH UNISPEND — KỲ {month}"
    ws_summary["A1"].font = title_font
    ws_summary["A2"] = f"Ngày xuất báo cáo: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    ws_summary["A2"].font = normal_font

    ws_summary.append([])
    ws_summary.append(["Chỉ số tổng hợp", "Giá trị (VNĐ / Thông tin)"])
    for col_idx in (1, 2):
        cell = ws_summary.cell(row=4, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    overview_rows = [
        ("Tổng thu nhập", summary.get("income", 0)),
        ("Tổng chi tiêu", summary.get("expense", 0)),
        ("Chênh lệch thu chi", summary.get("balance", 0)),
        ("Tổng số giao dịch", summary.get("count", 0)),
    ]
    if extra_metrics:
        for k, v in extra_metrics.items():
            overview_rows.append((k, v))

    for label, val in overview_rows:
        ws_summary.append([label, val])
        r_idx = ws_summary.max_row
        ws_summary.cell(row=r_idx, column=1).font = bold_font
        c2 = ws_summary.cell(row=r_idx, column=2)
        c2.font = normal_font
        if isinstance(val, int):
            c2.number_format = "#,##0"
        for c in (1, 2):
            ws_summary.cell(row=r_idx, column=c).border = cell_border

    ws_summary.append([])
    ws_summary.append(["Danh mục chi tiêu", "Đã chi (VNĐ)", "Định mức (VNĐ)", "Còn lại (VNĐ)", "Tỷ lệ (%)"])
    cat_header_row = ws_summary.max_row
    for col_idx in range(1, 6):
        cell = ws_summary.cell(row=cat_header_row, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font

    status_map = {s.category: s for s in budget_statuses}
    for cat, spent in category_totals.items():
        st = status_map.get(cat)
        limit_val = st.limit if st else 0
        rem_val = st.remaining if st else 0
        pct_val = round(st.ratio * 100, 1) if st else 0.0
        ws_summary.append([cat, spent, limit_val, rem_val, pct_val])
        r_idx = ws_summary.max_row
        for c in range(1, 6):
            cell = ws_summary.cell(row=r_idx, column=c)
            cell.font = normal_font
            cell.border = cell_border
            if c in (2, 3, 4):
                cell.number_format = "#,##0"

    for col in ws_summary.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_summary.column_dimensions[col_letter].width = max(16, min(42, max_len + 4))

    # Sheet 2: Chi tiết giao dịch
    ws_tx = wb.create_sheet(title="So_giao_dich")
    headers = ["Mã GD", "Ngày (DD/MM/YYYY)", "Loại giao dịch", "Danh mục", "Số tiền (VNĐ)", "Ghi chú"]
    ws_tx.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws_tx.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    for tx in transactions:
        safe_note = tx.note
        if safe_note.lstrip().startswith(("=", "+", "-", "@")):
            safe_note = "'" + safe_note
        ws_tx.append([
            tx.id,
            display_date(tx.date),
            TYPE_LABELS.get(tx.kind, tx.kind),
            tx.category,
            tx.amount,
            safe_note,
        ])
        r_idx = ws_tx.max_row
        for c in range(1, len(headers) + 1):
            cell = ws_tx.cell(row=r_idx, column=c)
            cell.font = normal_font
            cell.border = cell_border
            if c == 5:
                cell.number_format = "#,##0"
            elif c in (1, 2):
                cell.alignment = Alignment(horizontal="center")

    for col in ws_tx.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws_tx.column_dimensions[col_letter].width = max(14, min(48, max_len + 4))

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# =============================================================================
# 2. XUẤT BÁO CÁO PDF (.PDF) HỖ TRỢ TIẾNG VIỆT UNICODE
# =============================================================================
def _find_unicode_ttf() -> Path | None:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/tahoma.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def _ascii_fallback(text: str) -> str:
    import unicodedata
    text = text.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).encode("latin-1", "replace").decode("latin-1")


def export_pdf_bytes(
    month: str,
    summary: dict[str, int],
    category_totals: dict[str, int],
    budget_statuses: Iterable[BudgetStatus],
    transactions: Iterable[Transaction],
    extra_metrics: dict[str, str | int] | None = None,
) -> bytes:
    """Tạo file báo cáo PDF (.pdf) định dạng A4 rõ ràng."""
    from fpdf import FPDF

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_path = _find_unicode_ttf()
    has_unicode = False
    if font_path is not None:
        try:
            pdf.add_font("UniFont", "", str(font_path))
            font_name = "UniFont"
            has_unicode = True
        except Exception:
            font_name = "Helvetica"
    else:
        font_name = "Helvetica"

    def _txt(value: object) -> str:
        s = str(value if value is not None else "")
        return s if has_unicode else _ascii_fallback(s)

    pdf.set_font(font_name, size=16)
    pdf.set_text_color(33, 76, 60)
    pdf.cell(0, 10, _txt(f"BÁO CÁO TÀI CHÍNH UNISPEND — KỲ {month}"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(font_name, size=10)
    pdf.set_text_color(80, 100, 90)
    pdf.cell(0, 6, _txt(f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Đơn vị: VNĐ"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Khối 1: Tổng quan
    pdf.set_font(font_name, size=12)
    pdf.set_text_color(33, 76, 60)
    pdf.cell(0, 8, _txt("1. Tổng hợp thu chi trong kỳ"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(font_name, size=10)
    pdf.set_text_color(36, 59, 50)
    summary_lines = [
        f"• Tổng thu nhập: {money(summary.get('income', 0))}",
        f"• Tổng chi tiêu: {money(summary.get('expense', 0))}",
        f"• Chênh lệch thu chi: {money(summary.get('balance', 0))}",
        f"• Tổng số giao dịch: {summary.get('count', 0)}",
    ]
    if extra_metrics:
        for k, v in extra_metrics.items():
            summary_lines.append(f"• {k}: {v}")
    for line in summary_lines:
        pdf.cell(0, 6, _txt(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Khối 2: Chi tiêu theo danh mục
    pdf.set_font(font_name, size=12)
    pdf.set_text_color(33, 76, 60)
    pdf.cell(0, 8, _txt("2. Chi tiêu theo danh mục & Ngân sách"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(font_name, size=10)
    pdf.set_text_color(36, 59, 50)
    status_map = {s.category: s for s in budget_statuses}
    for cat, spent in category_totals.items():
        st = status_map.get(cat)
        if st:
            line = f"• {cat}: Đã chi {money(spent)} / Định mức {money(st.limit)} ({st.ratio:.1%})"
        else:
            line = f"• {cat}: Đã chi {money(spent)} (Chưa đặt định mức)"
        pdf.cell(0, 6, _txt(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Khối 3: Danh sách giao dịch
    pdf.set_font(font_name, size=12)
    pdf.set_text_color(33, 76, 60)
    tx_list = list(transactions)
    pdf.cell(0, 8, _txt(f"3. Sổ giao dịch chi tiết ({len(tx_list)} giao dịch)"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font(font_name, size=9)
    pdf.set_text_color(36, 59, 50)
    if not tx_list:
        pdf.cell(0, 6, _txt("Chưa có giao dịch trong kỳ đã chọn."), new_x="LMARGIN", new_y="NEXT")
    else:
        for tx in tx_list[:150]:
            row_str = (
                f"#{tx.id} | {display_date(tx.date)} | {TYPE_LABELS.get(tx.kind, tx.kind)} | "
                f"{tx.category} | {money(tx.amount)} | {tx.note[:55]}"
            )
            pdf.cell(0, 5.5, _txt(row_str), new_x="LMARGIN", new_y="NEXT")

    raw_out = pdf.output()
    return bytes(raw_out)


# =============================================================================
# 3. SAO LƯU & KHÔI PHỤC SQLITE AN TOÀN (BACKUP & RESTORE)
# =============================================================================
SQLITE_HEADER = b"SQLite format 3\x00"


def create_sqlite_backup(db_path: str | Path) -> bytes:
    """Sao lưu nóng (hot backup) file SQLite đang hoạt động bằng sqlite3.backup API."""
    source_path = Path(db_path).resolve()
    if not source_path.is_file():
        raise ValueError("Không tìm thấy tệp cơ sở dữ liệu để sao lưu.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        backup_file = Path(tmp_dir) / "backup_snapshot.db"
        src_conn = sqlite3.connect(str(source_path))
        dst_conn = sqlite3.connect(str(backup_file))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()
        return backup_file.read_bytes()


def validate_sqlite_backup(file_bytes: bytes) -> dict[str, int | str | bool]:
    """Kiểm tra tính hợp lệ, toàn vẹn (PRAGMA integrity_check) và bảng dữ liệu của file backup."""
    if not file_bytes or len(file_bytes) < 100 or not file_bytes.startswith(SQLITE_HEADER):
        return {
            "valid": False,
            "transactions_count": 0,
            "budgets_count": 0,
            "message": "Tệp tải lên không phải là cơ sở dữ liệu SQLite3 hợp lệ.",
        }

    with tempfile.TemporaryDirectory() as tmp_dir:
        probe_path = Path(tmp_dir) / "probe.db"
        probe_path.write_bytes(file_bytes)
        conn = sqlite3.connect(str(probe_path))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if str(integrity).lower() != "ok":
                return {
                    "valid": False,
                    "transactions_count": 0,
                    "budgets_count": 0,
                    "message": f"Cơ sở dữ liệu bị lỗi toàn vẹn: {integrity}",
                }
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            if not {"transactions", "budgets"} <= tables:
                return {
                    "valid": False,
                    "transactions_count": 0,
                    "budgets_count": 0,
                    "message": "Tệp SQLite thiếu bảng 'transactions' hoặc 'budgets' của UniSpend.",
                }
            tx_count = int(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
            bg_count = int(conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0])
            return {
                "valid": True,
                "transactions_count": tx_count,
                "budgets_count": bg_count,
                "message": f"Tệp sao lưu hợp lệ ({tx_count} giao dịch, {bg_count} định mức ngân sách).",
            }
        except sqlite3.Error as exc:
            return {
                "valid": False,
                "transactions_count": 0,
                "budgets_count": 0,
                "message": f"Không đọc được cấu trúc SQLite: {exc}",
            }
        finally:
            conn.close()


def restore_sqlite_backup(db_path: str | Path, file_bytes: bytes) -> dict[str, int | str]:
    """Khôi phục SQLite sau khi đã kiểm tra hợp lệ và tạo bản sao an toàn trước khi ghi."""
    check = validate_sqlite_backup(file_bytes)
    if not check["valid"]:
        raise ValueError(str(check["message"]))

    target_path = Path(db_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    safety_copy_path = target_path.with_name(f"{target_path.stem}.pre_restore.bak")
    if target_path.is_file():
        shutil.copy2(target_path, safety_copy_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        src_file = Path(tmp_dir) / "restore_source.db"
        src_file.write_bytes(file_bytes)
        src_conn = sqlite3.connect(str(src_file))
        dst_conn = sqlite3.connect(str(target_path))
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

    return {
        "transactions_count": int(check["transactions_count"]),
        "budgets_count": int(check["budgets_count"]),
        "safety_backup": str(safety_copy_path),
        "message": f"Đã khôi phục thành công {check['transactions_count']} giao dịch và {check['budgets_count']} ngân sách.",
    }
