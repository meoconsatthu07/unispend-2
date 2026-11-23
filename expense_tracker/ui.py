"""Giao diện UniSpend 2.0 — Mobile-First Dark-Green Personal Finance Calendar (MONii Inspired).

Kiến trúc 4 Tab chính + 2 Màn hình phụ điều hướng qua Bottom Navigation cố định & URL query_params:
- ?tab=lich    : Trang chủ Lịch Tài Chính (Header 1 hàng + Hero Card Khả dụng tháng & Mascot UniBean
                 + Hộp CHI/THU + Lưới lịch 7 cột bấm chọn ngày trực tiếp + Chi tiết ngày & Quick Add + 2 FAB Camera/Mic)
- ?tab=hoadon  : Hóa Đơn & Đăng Ký (Segmented Control Hóa đơn định kỳ | Sổ ghi nợ + 2 thẻ Chưa/Đã thanh toán
                 + Danh sách hóa đơn / Empty State Mascot '?' + Nút '+ Thêm Hóa Đơn')
- ?tab=thongke : Thống Kê Chi Tiêu (Lưới KPI 2x2 + Donut & Mascot ôm ví + Xuất Excel/PDF + TB mỗi ngày / Chi nhiều nhất
                 + 8 hạng mục tỷ trọng + Cảnh báo ngân sách + 3 khoản thiết yếu + Biểu đồ xu hướng)
- ?tab=canhan  : Cá Nhân & Tiện Ích (Tìm kiếm giao dịch + Trợ lý AI Chat + Cổng đấu nối API Gemini/OpenAI/Tesseract
                 + Thiết lập ngân sách + Sao lưu/Khôi phục SQLite)
- ?tab=ocr     : Quét Hóa Đơn AI 9 bước (Tesseract OCR 5.x + OpenCV + Gemini Vision/JSON 12 trường)
- ?tab=voice   : Nhập Chi Tiêu Bằng Giọng Nói Tiếng Việt (Bottom-Sheet Modal + AI STT + NLP)
"""

from __future__ import annotations

from calendar import monthcalendar, monthrange
import csv
from datetime import date, timedelta
import hashlib
from html import escape
import io
import os
from pathlib import Path
import sqlite3
from typing import Any

import pandas as pd
import streamlit as st

from . import charts
from .accounts import (
    AccountInfo,
    accounts_dir_for,
    create_account,
    delete_account,
    import_db_as_account,
    list_accounts,
    load_active_account,
    rename_account,
    save_active_account,
)
from .ai_data_cleaner import (
    clean_raw_text,
    clean_tabular_file,
    rows_to_clean_csv_bytes,
)
from .ai_service import (
    answer_financial_question,
    build_financial_analysis,
    check_api_status,
    generate_ai_deep_financial_review,
    parse_vietnamese_voice_expense,
    save_ai_api_config,
    test_all_ai_pipelines,
    transcribe_audio_bytes,
)
from .extensions_db import ExtensionsStore, resolve_extensions_db_path
from .lucide_icons import (
    category_lucide_box,
    lucide_box,
    lucide_svg,
    mini_sparkline_svg,
)
from .mascot import mascot_calendar_svg, mascot_logo_svg, mascot_question_svg, mascot_wallet_svg
from .ocr_pipeline import (
    ALLOWED_GEMINI_CATEGORIES,
    GeminiReceiptSchema,
    analyze_ocr_text_with_gemini,
    analyze_receipt_image_with_gemini,
    check_tesseract_status,
    clear_ocr_and_gemini_cache,
    enhance_receipt_image_color,
    map_gemini_category_to_storage,
    run_tesseract_ocr,
    test_gemini_connection,
    validate_receipt_image,
)
from .reports_backup import (
    create_sqlite_backup,
    export_excel_bytes,
    export_pdf_bytes,
    restore_sqlite_backup,
    validate_sqlite_backup,
)
from .storage import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    MAX_AMOUNT,
    TOTAL_BUDGET_CATEGORY,
    TYPE_LABELS,
    ExpenseStore,
)
from .styles import inject_mobile_styles, minify_html, render_html
from .utils import compact_money, display_date, money, shift_month, validate_month


CATEGORY_META = {
    "Ăn uống": (lucide_svg("utensils", 18, "#E87A4D"), "Tiền ăn", "#E87A4D", "Ăn uống hằng ngày, thực phẩm và đồ uống"),
    "Tiền trọ": (lucide_svg("home", 18, "#8B5CF6"), "Tiền trọ", "#8B5CF6", "Tiền phòng, điện nước và sinh hoạt"),
    "Đi lại": (lucide_svg("car", 18, "#38BDF8"), "Đi lại", "#38BDF8", "Xăng xe, vé xe buýt và di chuyển"),
    "Học tập": (lucide_svg("graduation-cap", 18, "#14B8A6"), "Học tập", "#14B8A6", "Học phí, giáo trình và tài liệu"),
    "Giải trí": (lucide_svg("gamepad-2", 18, "#F59E0B"), "Giải trí", "#F59E0B", "Xem phim, thể thao và hoạt động xã hội"),
    "Khác": (lucide_svg("package", 18, "#94A3B8"), "Khác", "#94A3B8", "Chi phí phát sinh khác"),
}

EIGHT_DISPLAY_CATEGORIES: tuple[tuple[str, str, str, str], ...] = (
    ("Ăn uống", lucide_svg("utensils", 18, "#E87A4D"), "#E87A4D", "rgba(232, 122, 77, 0.16)"),
    ("Nhà cửa", lucide_svg("home", 18, "#8B5CF6"), "#8B5CF6", "rgba(139, 92, 246, 0.16)"),
    ("Di chuyển", lucide_svg("car", 18, "#38BDF8"), "#38BDF8", "rgba(56, 189, 248, 0.16)"),
    ("Mua sắm", lucide_svg("shopping-bag", 18, "#EC4899"), "#EC4899", "rgba(236, 72, 153, 0.16)"),
    ("Giải trí", lucide_svg("gamepad-2", 18, "#F59E0B"), "#F59E0B", "rgba(245, 158, 11, 0.16)"),
    ("Học tập", lucide_svg("graduation-cap", 18, "#14B8A6"), "#14B8A6", "rgba(20, 184, 166, 0.16)"),
    ("Sức khỏe", lucide_svg("heart-pulse", 18, "#34D399"), "#34D399", "rgba(52, 211, 153, 0.16)"),
    ("Khác", lucide_svg("package", 18, "#94A3B8"), "#94A3B8", "rgba(148, 163, 184, 0.16)"),
)

SHOPPING_KEYWORDS = ("mua sắm", "quần áo", "giày", "áo", "váy", "mỹ phẩm", "shopee", "lazada", "siêu thị", "đồ dùng", "bột giặt")
HEALTH_KEYWORDS = ("thuốc", "khám", "bệnh viện", "y tế", "sức khỏe", "nha khoa", "gym", "vitamin", "bảo hiểm")
WEEKDAY_LABELS = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")
WEEKDAY_FULL_VN = ("Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật")

SAMPLE_RECEIPT_TEXT = """SIÊU THỊ MINI UNIMART - CN BÌNH THẠNH
SĐT: 0901234567 - Mã HĐ: HD20261119
Ngày in: 19/11/2026 18:00
Ngày mua: 11/11/2026 12:35
--------------------------------
Nước suối Aquafina 1 x 8.000 = 8.000
Bánh mì sandwich 1 x 15.000 = 15.000
Sữa tươi Meiji 1 x 20.000 = 20.000
Tạm tính: 43.000
VAT (0%): 0
Tổng cộng: 43.000 đ
Phương thức: Ví điện tử MoMo"""


def _html_md(raw_html: str) -> None:
    """Render HTML đã minify 1 dòng an toàn tuyệt đối (không bao giờ lộ raw HTML/SVG)."""
    render_html(raw_html)


def _category_label(category: str) -> str:
    _, title, *_ = CATEGORY_META.get(category, ("", category))
    return title


def _notice(message: str) -> None:
    st.session_state["notice"] = message
    st.rerun()


def _status_text(status) -> tuple[str, str, str]:
    if status.exceeded:
        return "danger", "Vượt ngân sách", f"Vượt định mức {money(-status.remaining)}"
    if status.near_limit:
        return "warning", "Sắp chạm ngưỡng", f"Đã dùng {status.ratio:.1%} định mức"
    return "safe", "Trong định mức", f"Còn có thể chi {money(status.remaining)}"


def _compute_eight_category_breakdown(records: list[Any]) -> dict[str, int]:
    """Tổng hợp 8 hạng mục hiển thị từ các giao dịch chi tiêu SQLite thật."""
    buckets = {name: 0 for name, *_ in EIGHT_DISPLAY_CATEGORIES}
    for r in records:
        if r.kind != "expense":
            continue
        if r.category == "Ăn uống":
            buckets["Ăn uống"] += r.amount
        elif r.category == "Tiền trọ":
            buckets["Nhà cửa"] += r.amount
        elif r.category == "Đi lại":
            buckets["Di chuyển"] += r.amount
        elif r.category == "Giải trí":
            buckets["Giải trí"] += r.amount
        elif r.category == "Học tập":
            buckets["Học tập"] += r.amount
        else:
            note_lower = (r.note or "").casefold()
            if any(kw in note_lower for kw in HEALTH_KEYWORDS):
                buckets["Sức khỏe"] += r.amount
            elif any(kw in note_lower for kw in SHOPPING_KEYWORDS):
                buckets["Mua sắm"] += r.amount
            else:
                buckets["Khác"] += r.amount
    return buckets


def _compute_safe_daily_allowance(month: str, summary: dict[str, int], budgets: dict[str, Any]) -> tuple[int, int, float, str]:
    """Tính toán 'Có thể chi hôm nay' & 'Chi tiêu an toàn / ngày' từ dữ liệu SQLite thật."""
    year, month_num = map(int, month.split("-"))
    days_in_month = monthrange(year, month_num)[1]
    today = date.today()
    if today.strftime("%Y-%m") == month:
        remaining_days = max(1, days_in_month - today.day + 1)
    else:
        remaining_days = days_in_month

    total_budget = budgets.get(TOTAL_BUDGET_CATEGORY)
    cap_amount = total_budget.limit if total_budget else (summary["income"] if summary["income"] > 0 else 6_500_000)
    remaining_pool = max(0, cap_amount - summary["expense"])
    daily_safe = round(remaining_pool / remaining_days) if remaining_pool > 0 else 0
    used_pct = min(100.0, (summary["expense"] / cap_amount * 100.0)) if cap_amount > 0 else 0.0
    status_label = "Trong giới hạn" if summary["expense"] <= cap_amount else "Vượt định mức"
    return daily_safe, cap_amount, used_pct, status_label


def _sync_query_params(store: ExpenseStore, ext_store: ExtensionsStore) -> str:
    """Đồng bộ st.query_params (?tab=..., ?month=..., ?day=..., ?theme=..., ?bmode=...) với session_state."""
    qp = st.query_params

    # 1. Xử lý đổi giao diện Light/Dark qua query param
    if qp.get("theme") == "toggle":
        curr_mode = ext_store.get_theme_mode()
        ext_store.set_theme_mode("light" if curr_mode == "dark" else "dark")
        try:
            del qp["theme"]
        except Exception:
            pass

    # 2. Xử lý chọn tháng qua query param (?month=YYYY-MM)
    q_month = qp.get("month")
    if q_month:
        try:
            valid_m = validate_month(str(q_month).strip())
            st.session_state["pending_month"] = valid_m
        except ValueError:
            pass
        try:
            del qp["month"]
        except Exception:
            pass

    # 3. Xử lý chọn ngày trực tiếp từ lưới lịch (?day=YYYY-MM-DD)
    q_day = qp.get("day")
    if q_day:
        s_day = str(q_day).strip()
        try:
            date.fromisoformat(s_day)
            st.session_state["selected_calendar_date"] = s_day
            st.session_state["pending_month"] = s_day[:7]
        except ValueError:
            pass

    # 4. Xử lý chế độ Tab Hóa đơn (?bmode=recurring|debt|gallery)
    q_bmode = qp.get("bmode")
    if q_bmode in ("recurring", "debt", "gallery"):
        st.session_state["bills_submode"] = q_bmode

    # 4b. Xử lý câu nói gửi về từ nút Nhấn giữ để ghi âm (?spoken=...)
    q_spoken = str(qp.get("spoken") or "").strip()
    if q_spoken:
        st.session_state["voice_transcript_input"] = q_spoken
        try:
            st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense(q_spoken, use_ai=True)
        except ValueError:
            pass
        try:
            del qp["spoken"]
        except Exception:
            pass

    # 5. Xử lý Tab đang mở (?tab=lich|hoadon|thongke|canhan|ocr|voice|cleaner|dbview)
    valid_tabs = {"lich", "hoadon", "thongke", "canhan", "ocr", "voice", "cleaner", "dbview"}
    q_tab = str(qp.get("tab") or "").strip().lower()
    if q_tab in valid_tabs:
        st.session_state["active_mobile_tab"] = q_tab
        studio_map = {
            "lich": "none",
            "hoadon": "bills",
            "thongke": "stats",
            "canhan": "backup",
            "ocr": "ocr",
            "voice": "voice",
            "cleaner": "cleaner",
            "dbview": "dbview",
        }
        st.session_state["active_studio_panel"] = studio_map[q_tab]

    st.session_state.setdefault("active_mobile_tab", "lich")
    st.session_state.setdefault("active_studio_panel", "none")

    # Đồng bộ ngược nếu người dùng bấm nút Streamlit studio_panel
    panel = st.session_state.get("active_studio_panel", "none")
    panel_to_tab = {
        "none": st.session_state.get("active_mobile_tab", "lich")
        if st.session_state.get("active_mobile_tab") in ("lich", "hoadon", "thongke")
        else "lich",
        "ocr": "ocr",
        "voice": "voice",
        "cleaner": "cleaner",
        "dbview": "dbview",
        "assistant": "canhan",
        "backup": "canhan",
        "bills": "hoadon",
        "stats": "thongke",
    }
    active_tab = panel_to_tab.get(panel, "lich")
    st.session_state["active_mobile_tab"] = active_tab
    return active_tab


def _resolve_base_data_dir(db_path: str | Path) -> Path:
    resolved = Path(db_path).resolve()
    project_data = (Path(__file__).resolve().parent.parent / "data").resolve()
    try:
        resolved.relative_to(project_data)
        return project_data
    except ValueError:
        return resolved.parent


def _activate_account(base_data_dir: Path, target_db: Path, message: str | None = None) -> None:
    resolved = str(target_db.resolve())
    save_active_account(base_data_dir, resolved)
    st.session_state[f"active_account_db:{base_data_dir}"] = resolved
    st.session_state["account_just_switched"] = True
    for param_key in ("day", "month"):
        try:
            if param_key in st.query_params:
                del st.query_params[param_key]
        except Exception:
            pass
    if message:
        _notice(message)
    else:
        st.rerun()


def _on_account_select(base_data_dir: Path, widget_key: str) -> None:
    chosen = st.session_state.get(widget_key)
    if not chosen:
        return
    resolved = str(Path(chosen).resolve())
    save_active_account(base_data_dir, resolved)
    st.session_state[f"active_account_db:{base_data_dir}"] = resolved
    st.session_state["account_just_switched"] = True
    for param_key in ("day", "month"):
        try:
            if param_key in st.query_params:
                del st.query_params[param_key]
        except Exception:
            pass
    st.session_state["notice"] = f"Đã chuyển sang tài khoản: {Path(resolved).name}"


def _render_account_manager(
    db_path: str | Path,
    base_data_dir: Path,
    store: ExpenseStore,
    ext_store: ExtensionsStore,
) -> None:
    """Quản lý đa tài khoản: mỗi file SQLite (.db) là một tài khoản riêng có thể chỉnh sửa."""
    active_path = Path(db_path).resolve()
    accounts_dir = accounts_dir_for(base_data_dir)
    accounts = list_accounts(base_data_dir, extra_paths=(active_path,))
    current_acc = next((a for a in accounts if a.path == active_path), None)
    curr_label = current_acc.display_name if current_acc else active_path.stem

    with st.container(border=True):
        _html_md(
            f'<div class="section-heading" style="margin-top:0;">'
            f'{lucide_svg("users", 17, "#34D399")}'
            f'<span>Tài khoản dữ liệu (Mỗi file .db = 1 tài khoản riêng)</span></div>'
        )
        st.caption(f"Đang mở: **{curr_label}** · File: `{active_path.name}` ({current_acc.tx_count if current_acc else 0} giao dịch)")

        if accounts:
            acc_paths = [str(a.path) for a in accounts]
            acc_labels = {
                str(a.path): f"{a.display_name} ({a.tx_count} GD — {a.file_name})"
                for a in accounts
            }
            active_str = str(active_path)
            if st.session_state.get("personal_account_switcher") != active_str and active_str in acc_paths:
                st.session_state["personal_account_switcher"] = active_str
            cur_idx = acc_paths.index(active_str) if active_str in acc_paths else 0
            st.selectbox(
                "Chuyển sang tài khoản khác",
                options=acc_paths,
                index=cur_idx,
                format_func=lambda p: acc_labels.get(p, Path(p).name),
                key="personal_account_switcher",
                on_change=_on_account_select,
                args=(base_data_dir, "personal_account_switcher"),
            )

        tab_new, tab_rename, tab_upload = st.tabs([
            "➕ Tạo tài khoản mới",
            "✏️ Đổi tên / Xóa",
            "📂 Nhập file .db thành tài khoản",
        ])

        with tab_new:
            with st.form("create_account_form", clear_on_submit=True):
                new_acc_name = st.text_input(
                    "Tên tài khoản mới",
                    placeholder="VD: Nguyễn Văn A - HK1, Quỹ CLB UTH...",
                    max_chars=80,
                )
                seed_opt = st.checkbox("Nạp sẵn dữ liệu mẫu 6 tháng cho tài khoản mới", value=False)
                if st.form_submit_button("Tạo tài khoản (.db riêng)", type="primary", width="stretch"):
                    try:
                        created = create_account(accounts_dir, new_acc_name, seed_sample=seed_opt)
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        st.error(f"Không tạo được tài khoản: {exc}")
                    else:
                        _activate_account(
                            base_data_dir,
                            created,
                            f"Đã tạo tài khoản '{new_acc_name.strip()}' ({created.name}).",
                        )

        with tab_rename:
            with st.form("rename_account_form", enter_to_submit=False):
                renamed_val = st.text_input("Tên hiển thị của tài khoản đang mở", value=curr_label, max_chars=80)
                if st.form_submit_button("Lưu tên tài khoản", type="primary", width="stretch"):
                    try:
                        # Đóng tạm kết nối để đổi tên file an toàn trên Windows
                        ext_store.close()
                        store.close()
                        new_path = rename_account(active_path, renamed_val, accounts_dir)
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        st.error(f"Không đổi tên được tài khoản: {exc}")
                    else:
                        _activate_account(
                            base_data_dir,
                            new_path,
                            f"Đã đổi tên tài khoản thành '{renamed_val.strip()}'.",
                        )
            if current_acc and current_acc.is_managed and len(accounts) > 1:
                confirm_del = st.checkbox(
                    f"Xác nhận xóa vĩnh viễn tài khoản '{curr_label}' ({active_path.name})",
                    key="confirm_delete_account_chk",
                )
                if st.button("🗑️ Xóa tài khoản này", width="stretch", disabled=not confirm_del, key="delete_account_btn"):
                    fallback = next(a.path for a in accounts if a.path != active_path)
                    try:
                        ext_store.close()
                        store.close()
                        delete_account(active_path, accounts_dir)
                    except (ValueError, OSError) as exc:
                        st.error(f"Không xóa được tài khoản: {exc}")
                    else:
                        _activate_account(
                            base_data_dir,
                            fallback,
                            f"Đã xóa tài khoản '{curr_label}' và chuyển về '{fallback.name}'.",
                        )
            else:
                st.caption("Chỉ xóa được tài khoản do bạn tạo trong thư mục `data/accounts/` khi còn ít nhất 2 tài khoản.")

        with tab_upload:
            with st.form("import_account_db_form", clear_on_submit=True):
                imp_name = st.text_input(
                    "Tên tài khoản cho file .db tải lên",
                    placeholder="VD: Dữ liệu thật Kaggle, Nhóm 3 UTH...",
                    max_chars=80,
                )
                imp_file = st.file_uploader("Chọn tệp SQLite (.db) của THU CHI UTH", type=["db"], key="import_acc_db_file")
                if st.form_submit_button("Thêm làm tài khoản riêng", type="primary", width="stretch"):
                    if imp_file is None:
                        st.error("Vui lòng chọn tệp .db trước khi tải lên.")
                    else:
                        try:
                            imported = import_db_as_account(
                                accounts_dir,
                                imp_name or Path(imp_file.name).stem,
                                imp_file.getvalue(),
                            )
                        except (ValueError, OSError, sqlite3.Error) as exc:
                            st.error(f"Không nhập được file .db: {exc}")
                        else:
                            _activate_account(
                                base_data_dir,
                                imported,
                                f"Đã thêm tài khoản mới từ file ({imported.name}).",
                            )


def _render_ai_data_cleaner_studio(
    base_data_dir: Path,
    store: ExpenseStore,
    ext_store: ExtensionsStore,
) -> None:
    """Studio AI làm sạch dữ liệu thô (CSV/Excel/Văn bản) thành dữ liệu chuẩn web & lưu thành tài khoản .db."""
    accounts_dir = accounts_dir_for(base_data_dir)
    preferred_provider = ext_store.get_setting("ai_provider", "auto")

    with st.container(border=True):
        _html_md(
            f'<div class="section-heading" style="margin-top:0;">'
            f'{lucide_svg("sparkles", 17, "#34D399")}'
            f'<span>AI Làm Sạch &amp; Chuẩn Hóa Dữ Liệu Thô</span></div>'
        )
        st.caption(
            "Tải lên file CSV/Excel thô bất kỳ (Kaggle, ngân hàng, khảo sát...) hoặc dán văn bản ghi chú thô. "
            "AI sẽ tự nhận diện cột, khử trùng lặp, loại nhiễu, chuẩn hóa ngày/tiền/danh mục đúng chuẩn web."
        )

        input_mode = st.radio(
            "Nguồn dữ liệu thô",
            ["📄 Tải file CSV / Excel thô", "📝 Dán văn bản / ghi chú thô"],
            horizontal=True,
            key="v2_cleaner_mode",
        )

        opt_c1, opt_c2 = st.columns([1, 1])
        with opt_c1:
            use_ai = st.checkbox("Dùng AI (Gemini / OpenAI) phân tích & ánh xạ thông minh", value=True, key="v2_cleaner_use_ai")
        with opt_c2:
            curr_choice = st.selectbox(
                "Đơn vị tiền tệ gốc",
                ["Tự động", "VND", "INR", "USD", "EUR"],
                key="v2_cleaner_currency",
            )

        if input_mode == "📄 Tải file CSV / Excel thô":
            raw_file = st.file_uploader(
                "Chọn file dữ liệu thô (.csv hoặc .xlsx)",
                type=["csv", "xlsx", "xls"],
                key="v2_cleaner_file_uploader",
            )
            if st.button("🤖 AI Phân tích & Làm sạch file", type="primary", width="stretch", key="v2_run_file_clean_btn"):
                if raw_file is None:
                    st.error("Vui lòng chọn file CSV hoặc Excel thô trước.")
                else:
                    with st.spinner("AI đang đọc và chuẩn hóa dữ liệu thô..."):
                        try:
                            result = clean_tabular_file(
                                raw_file.name,
                                raw_file.getvalue(),
                                use_ai=use_ai,
                                currency_override=curr_choice,
                                preferred_provider=preferred_provider,
                            )
                        except Exception as exc:
                            st.error(f"Không xử lý được file thô: {exc}")
                        else:
                            st.session_state["v2_cleaner_result"] = result
                            st.session_state["v2_cleaner_source_name"] = Path(raw_file.name).stem
        else:
            raw_text = st.text_area(
                "Dán văn bản thu chi thô (mỗi dòng hoặc cách nhau dấu chấm phẩy)",
                placeholder="VD:\n01/11 bố mẹ gửi 4.5tr sinh hoạt phí\n02/11 đóng tiền trọ 2tr2\n03/11 ăn cơm trưa UTH 40k; đổ xăng 70 nghìn",
                height=120,
                key="v2_cleaner_raw_text",
            )
            if st.button("🤖 AI Trích xuất & Chuẩn hóa văn bản", type="primary", width="stretch", key="v2_run_text_clean_btn"):
                with st.spinner("AI đang trích xuất và chuẩn hóa giao dịch..."):
                    try:
                        result = clean_raw_text(
                            raw_text,
                            use_ai=use_ai,
                            preferred_provider=preferred_provider,
                        )
                    except Exception as exc:
                        st.error(f"Không trích xuất được dữ liệu: {exc}")
                    else:
                        st.session_state["v2_cleaner_result"] = result
                        st.session_state["v2_cleaner_source_name"] = "du_lieu_van_ban_ai"

        res = st.session_state.get("v2_cleaner_result")
        if res and res.rows:
            st.success(f"✅ Hoàn tất ({res.ai_provider}): {res.ai_summary}")
            s = res.stats
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Dòng thô", s["raw_rows"])
            m2.metric("Dòng sạch chuẩn", s["clean_rows"])
            m3.metric("Đã loại trùng / nhiễu", s["dropped_dups"] + s["dropped_transfers"])
            m4.metric("Ghi chú đã bù", s["imputed_notes"])

            preview_rows = [
                {
                    "Ngày": r["date"],
                    "Loại": r["type_label"],
                    "Danh mục": r["category"],
                    "Số tiền (VNĐ)": r["amount"],
                    "Ghi chú sạch": r["note"],
                }
                for r in res.rows[:25]
            ]
            st.dataframe(preview_rows, width="stretch", hide_index=True)
            if len(res.rows) > 25:
                st.caption(f"Đang xem trước 25/{len(res.rows)} dòng sạch ({s['date_min']} → {s['date_max']}).")

            act_c1, act_c2 = st.columns([1.4, 1])
            with act_c1:
                default_name = st.session_state.get("v2_cleaner_source_name", "tai_khoan_sach_ai")
                new_acc_title = st.text_input(
                    "Đặt tên tài khoản mới cho dữ liệu sạch này",
                    value=default_name,
                    max_chars=80,
                    key="v2_cleaner_new_acc_name",
                )
                if st.button("💾 Lưu thành Tài khoản (.db) mới & Mở ngay", type="primary", width="stretch", key="v2_save_clean_new_acc"):
                    try:
                        new_db = create_account(accounts_dir, new_acc_title, seed_sample=False)
                        new_store = ExpenseStore(new_db)
                        try:
                            with new_store.connection:
                                new_store.connection.executemany(
                                    "INSERT INTO transactions(date, kind, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                                    [(r["date"], r["kind"], r["category"], int(r["amount"]), r["note"]) for r in res.rows],
                                )
                        finally:
                            new_store.close()
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        st.error(f"Không lưu được tài khoản mới: {exc}")
                    else:
                        st.session_state.pop("v2_cleaner_result", None)
                        _activate_account(
                            base_data_dir,
                            new_db,
                            f"Đã tạo tài khoản '{new_acc_title.strip()}' với {len(res.rows)} giao dịch sạch!",
                        )
            with act_c2:
                st.write("")
                st.write("")
                if st.button("➕ Nạp vào Tài khoản đang mở", width="stretch", key="v2_append_clean_curr"):
                    try:
                        with store.connection:
                            store.connection.executemany(
                                "INSERT INTO transactions(date, kind, category, amount, note) VALUES (?, ?, ?, ?, ?)",
                                [(r["date"], r["kind"], r["category"], int(r["amount"]), r["note"]) for r in res.rows],
                            )
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(f"Không nạp được dữ liệu: {exc}")
                    else:
                        st.session_state.pop("v2_cleaner_result", None)
                        if res.rows:
                            st.session_state["pending_month"] = res.rows[-1]["date"][:7]
                        _notice(f"Đã nạp thêm {len(res.rows)} giao dịch sạch vào tài khoản đang mở.")
                st.download_button(
                    "📥 Tải CSV chuẩn sạch",
                    data=rows_to_clean_csv_bytes(res.rows, format_mode="v2"),
                    file_name=f"{default_name}_clean.csv",
                    mime="text/csv",
                    width="stretch",
                    key="v2_download_clean_csv",
                )


def _render_sqlite_database_viewer(
    db_path: str | Path,
    store: ExpenseStore,
    ext_store: ExtensionsStore,
) -> None:
    """Trình xem trực tiếp các bảng SQLite (.db) của tài khoản đang mở ngay trên giao diện Web."""
    active_p = Path(db_path).resolve()
    ext_p = Path(str(ext_store.db_path)).resolve() if str(ext_store.db_path) != ":memory:" else None

    with st.container(border=True):
        _html_md(
            f'<div class="section-heading" style="margin-top:0;">'
            f'{lucide_svg("file-spreadsheet", 17, "#34D399")}'
            f'<span>Trình Xem Cơ Sở Dữ Liệu SQLite (.db) Trực Tiếp Trên Web</span></div>'
        )
        st.caption(
            f"📂 **File DB chính:** `{active_p}`  \n"
            + (f"📂 **File DB mở rộng (Hóa đơn OCR / AI):** `{ext_p}`" if ext_p else "")
        )

        db_choice = st.radio(
            "Chọn tệp cơ sở dữ liệu muốn xem",
            [
                f"1️⃣ DB Chính ({active_p.name} — Giao dịch & Ngân sách)",
                f"2️⃣ DB Mở rộng ({ext_p.name if ext_p else 'extensions.db'} — 51 Hóa đơn OCR, AI, Cài đặt)",
            ],
            horizontal=True,
            key="web_db_file_choice",
        )
        conn = store.connection if db_choice.startswith("1️⃣") else ext_store.connection

        raw_tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        priority = {"transactions": 0, "budgets": 1, "receipts": 0, "ai_history": 1, "ui_settings": 2}
        tables = sorted(raw_tables, key=lambda t: (priority.get(t, 9), t))
        if not tables:
            st.info("Chưa có bảng dữ liệu nào.")
            return

        table_counts = {
            t: int(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0])
            for t in tables
        }
        c_sel, c_lim = st.columns([2, 1])
        with c_sel:
            picked_table = st.selectbox(
                "Chọn bảng (Table) để xem dữ liệu",
                options=tables,
                format_func=lambda t: f"📋 Bảng {t} ({table_counts.get(t, 0)} dòng)",
                key="web_db_table_picker",
            )
        with c_lim:
            max_rows = st.selectbox(
                "Số dòng hiển thị tối đa",
                options=[50, 200, 500, 2500],
                index=1,
                key="web_db_row_limit",
            )

        # Lấy danh sách cột (bỏ cột image_blob nhị phân để bảng hiển thị mượt)
        col_info = conn.execute(f'PRAGMA table_info("{picked_table}")').fetchall()
        col_names = [c[1] for c in col_info if c[1] != "image_blob"]
        col_expr = ", ".join(f'"{c}"' for c in col_names) if col_names else "*"

        order_clause = " ORDER BY id DESC" if "id" in col_names else ""
        rows = conn.execute(
            f'SELECT {col_expr} FROM "{picked_table}"{order_clause} LIMIT ?',
            (int(max_rows),),
        ).fetchall()
        records = [dict(zip(col_names, r)) for r in rows]

        st.markdown(f"**Bảng `{picked_table}`** — Đang hiển thị **{len(records)} / {table_counts[picked_table]}** bản ghi:")
        st.dataframe(records, width="stretch", hide_index=True)

        with st.expander("🔍 Xem cấu trúc bảng (Schema & Ràng buộc CHECK SQLite)"):
            ddl_row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                (picked_table,),
            ).fetchone()
            if ddl_row and ddl_row[0]:
                st.code(ddl_row[0], language="sql")
            schema_rows = [
                {"Thứ tự": c[0], "Tên cột": c[1], "Kiểu dữ liệu": c[2], "NOT NULL": bool(c[3]), "Mặc định": c[4], "Khóa chính (PK)": bool(c[5])}
                for c in col_info
            ]
            st.dataframe(schema_rows, width="stretch", hide_index=True)

        with st.expander("💻 Chạy truy vấn SQL trực tiếp (Chỉ đọc — SELECT)"):
            default_sql = f'SELECT {col_expr} FROM "{picked_table}" LIMIT 20;'
            custom_sql = st.text_area("Câu lệnh SQL (SELECT / PRAGMA)", value=default_sql, height=75, key="web_db_custom_sql")
            if st.button("▶️ Chạy câu lệnh SQL", type="primary", key="web_db_run_sql_btn"):
                cleaned_sql = (custom_sql or "").strip()
                if not cleaned_sql.lower().startswith(("select", "pragma", "with")):
                    st.error("Để an toàn dữ liệu, ô truy vấn nhanh chỉ cho phép câu lệnh đọc (SELECT / PRAGMA).")
                else:
                    try:
                        cur = conn.execute(cleaned_sql)
                        q_cols = [d[0] for d in (cur.description or [])]
                        q_rows = cur.fetchall()
                        q_data = [
                            {k: (f"<BLOB {len(v)} bytes>" if isinstance(v, (bytes, bytearray)) else v) for k, v in zip(q_cols, r)}
                            for r in q_rows[:500]
                        ]
                        st.success(f"Truy vấn thành công: trả về {len(q_rows)} dòng.")
                        st.dataframe(q_data, width="stretch", hide_index=True)
                    except sqlite3.Error as exc:
                        st.error(f"Lỗi cú pháp SQL: {exc}")


def _sidebar(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    demo: bool,
    dark_mode: bool,
    db_path: str | Path | None = None,
    base_data_dir: Path | None = None,
) -> str:
    """Sidebar thu gọn mặc định (initial_sidebar_state='collapsed'), giữ đủ widget tương thích kiểm thử."""
    with st.sidebar:
        logo_icon = mascot_logo_svg(34)
        _html_md(
            f'<div class="brand"><div class="brand-icon">{logo_icon}</div>'
            f'<div class="brand-name">THU CHI UTH</div>'
            f'<div class="muted">Mobile-First Money Calendar</div></div>'
        )
        if db_path is not None and base_data_dir is not None:
            active_path = Path(db_path).resolve()
            accounts = list_accounts(base_data_dir, extra_paths=(active_path,))
            if accounts:
                acc_paths = [str(a.path) for a in accounts]
                acc_labels = {
                    str(a.path): f"👤 {a.display_name} ({a.tx_count} GD)"
                    for a in accounts
                }
                active_str = str(active_path)
                if st.session_state.get("sidebar_account_switcher") != active_str and active_str in acc_paths:
                    st.session_state["sidebar_account_switcher"] = active_str
                cur_idx = acc_paths.index(active_str) if active_str in acc_paths else 0
                st.selectbox(
                    "Tài khoản dữ liệu (.db)",
                    options=acc_paths,
                    index=cur_idx,
                    format_func=lambda p: acc_labels.get(p, Path(p).name),
                    key="sidebar_account_switcher",
                    on_change=_on_account_select,
                    args=(base_data_dir, "sidebar_account_switcher"),
                )
                st.caption(f"File DB: `{active_path.name}`")
        today = date.today()
        if st.session_state.pop("reset_quick_form", False):
            st.session_state["quick_date"] = today
            st.session_state["quick_amount"] = 45_000
            st.session_state["quick_note"] = ""
        pending = st.session_state.pop("pending_month", None)
        if pending:
            st.session_state["report_month"] = pending
        selected = st.session_state.get("report_month", today.strftime("%Y-%m"))
        months = sorted(set(store.available_months() + [today.strftime("%Y-%m"), selected]), reverse=True)
        month = st.selectbox("Chọn tháng xem báo cáo", months, key="report_month")
        with st.expander("Xem một tháng khác"):
            with st.form("choose_month", enter_to_submit=False):
                custom_month = st.text_input("Tháng (YYYY-MM)", value=month)
                if st.form_submit_button("Xem tháng", width="stretch"):
                    try:
                        st.session_state["pending_month"] = validate_month(custom_month.strip())
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

        st.divider()
        theme_btn_label = "☀️ Light Mode" if dark_mode else "🌙 Dark Mode"
        if st.button(theme_btn_label, width="stretch", key="toggle_theme_btn"):
            ext_store.set_theme_mode("light" if dark_mode else "dark")
            st.rerun()

        # Các nút điều hướng Studio trong Sidebar (tương thích kiểm thử)
        for s_lbl, s_panel, s_tab in (
            ("📅 Lịch Tài Chính", "none", "lich"),
            ("📸 Quét Hóa Đơn AI", "ocr", "ocr"),
            ("🎙️ Nhập Giọng Nói", "voice", "voice"),
            ("🤖 Trợ Lý AI", "assistant", "canhan"),
            ("💾 Sao Lưu & Cài Đặt", "backup", "canhan"),
        ):
            if st.button(s_lbl, width="stretch", key=f"side_nav_{s_panel}"):
                st.session_state["active_studio_panel"] = s_panel
                st.session_state["active_mobile_tab"] = s_tab
                st.rerun()

        st.divider()
        kind_label = st.radio("Loại giao dịch", ["Chi tiêu", "Thu nhập"], horizontal=True, key="quick_kind")
        kind = "expense" if kind_label == "Chi tiêu" else "income"
        categories = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
        st.session_state.setdefault("quick_amount", 45_000)
        with st.container(border=True):
            category = st.selectbox("Danh mục", categories, format_func=_category_label, key=f"quick_category_{kind}")
            transaction_date = st.date_input(
                "Ngày giao dịch",
                min_value=date.min,
                max_value=date.max,
                key="quick_date",
            )
            amount = st.number_input(
                "Số tiền (VNĐ)",
                min_value=0,
                max_value=MAX_AMOUNT,
                step=5_000,
                format="%d",
                key="quick_amount",
            )
            note = st.text_input(
                "Ghi chú chi tiết",
                max_chars=200,
                placeholder="VD: Cơm trưa, đổ xăng, tiền trọ…",
                key="quick_note",
            )
            if st.button("💾 Lưu giao dịch", type="primary", width="stretch"):
                try:
                    store.add_transaction(transaction_date.isoformat(), kind, category, amount, note)
                except (ValueError, sqlite3.Error) as exc:
                    st.error(f"Không lưu được giao dịch: {exc}")
                else:
                    st.session_state["pending_month"] = transaction_date.strftime("%Y-%m")
                    st.session_state["selected_calendar_date"] = transaction_date.isoformat()
                    st.session_state["reset_quick_form"] = True
                    _notice("Đã lưu giao dịch thành công.")
    return month


# =============================================================================
# TAB 1: LỊCH TÀI CHÍNH (GIỐNG SÁT ẢNH 1 — TINH GỌN TỐI ĐA 5 KHỐI)
# =============================================================================
def _render_tab_lich(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
    summary: dict[str, int],
    budgets: dict[str, Any],
    dark_mode: bool,
    demo: bool,
) -> None:
    year, month_num = map(int, month.split("-"))
    prev_m = shift_month(month, -1)
    next_m = shift_month(month, 1)

    # 1. HEADER 1 HÀNG DUY NHẤT (Logo Heo Con UniSpend + Money Calendar | Nút tròn Theme + < Thg 11, 2026 >)
    pig_logo_svg = mascot_logo_svg(30)
    theme_svg = lucide_svg("sun" if dark_mode else "moon", 17, "#F59E0B" if dark_mode else "#16A36A")
    chev_l = lucide_svg("chevron-left", 15, "#34D399")
    chev_r = lucide_svg("chevron-right", 15, "#34D399")

    header_parts = [
        '<div class="monii-top-header mobile-only-header">',
        '<div class="monii-brand-block">',
        f'<div class="monii-brand-logo">{pig_logo_svg}<span>THU CHI UTH</span></div>',
        '<div class="monii-brand-sub">Money Calendar</div>',
        '</div>',
        '<div class="monii-header-controls">',
        f'<a href="?tab=lich&theme=toggle" target="_self" class="monii-theme-circle" title="Đổi Light/Dark Mode">{theme_svg}</a>',
        '<div class="monii-month-pill">',
        f'<a href="?tab=lich&month={prev_m}" target="_self" class="monii-month-arrow" title="Tháng trước">{chev_l}</a>',
        f'<span class="monii-month-label">Thg {month_num}, {year}</span>',
        f'<a href="?tab=lich&month={next_m}" target="_self" class="monii-month-arrow" title="Tháng sau">{chev_r}</a>',
        '</div>',
        '</div>',
        '</div>',
    ]
    _html_md("".join(header_parts))

    # 2. THẺ "KHẢ DỤNG THÁNG" (Tag KHẢ DỤNG THÁNG + Số tiền lớn + Pill gợi ý AI + Mascot củ mầm ôm lịch & đồng xu vàng)
    total_budget = budgets.get(TOTAL_BUDGET_CATEGORY)
    if total_budget:
        avail_amount = total_budget.remaining
        if total_budget.exceeded:
            ai_tip = f"Vượt ngân sách {money(-total_budget.remaining)}! Ưu tiên khoản thiết yếu."
        elif total_budget.near_limit:
            ai_tip = f"Đã dùng {total_budget.ratio * 100:.0f}% ngân sách, còn {money(total_budget.remaining)}."
        else:
            ai_tip = f"Chi tiêu đúng hạn! Còn {money(total_budget.remaining)} ngân sách tháng."
    else:
        avail_amount = summary["balance"]
        if summary["income"] == 0 and summary["expense"] == 0:
            ai_tip = "Tháng mới vừa bắt đầu! Chi tiêu đúng hạn..."
        elif summary["balance"] >= 0:
            ai_tip = f"Tháng mới thuận lợi! Số dư khả dụng {money(summary['balance'])}."
        else:
            ai_tip = f"Chi vượt thu {money(-summary['balance'])}. Hãy đặt hạn mức ngân sách!"

    wallet_svg = lucide_svg("wallet", 13, "#9CA3AF")
    swap_svg = lucide_svg("arrow-left-right", 12, "#9CA3AF")
    bulb_svg = lucide_svg("lightbulb", 15, "#FBBF24")
    pen_svg = lucide_svg("pen-line", 14, "#D1D5DB")
    mascot_svg = mascot_calendar_svg(width=122, height=122)

    hero_parts = [
        '<div class="hero-banner mobile-only-hero">',
        '<div class="hero-grid">',
        '<div style="min-width:0;">',
        f'<div class="hero-avail-pill">{wallet_svg}<span>KHẢ DỤNG THÁNG</span>{swap_svg}</div>',
        f'<div class="hero-big-amount">{money(avail_amount)}</div>',
        f'<div class="hero-ai-pill" title="{escape(ai_tip)}">{bulb_svg}<span>{escape(ai_tip)}</span></div>',
        '</div>',
        '<div class="hero-mascot-wrap">',
        f'<a href="?tab=canhan" target="_self" class="hero-edit-pencil-badge" title="Chỉnh hạn mức ngân sách tháng">{pen_svg}</a>',
        mascot_svg,
        '</div>',
        '</div>',
        '</div>',
    ]
    _html_md("".join(hero_parts))

    # 3. KHU VỰC "LỊCH TÀI CHÍNH" (Hộp CHI / THU + Lưới lịch 7 cột T2..CN bấm trực tiếp)
    days_in_month = monthrange(year, month_num)[1]
    low_th, high_th = ext_store.get_calendar_thresholds()
    txs = store.list_transactions(month=month)
    receipts = ext_store.list_receipts(month=month)

    receipts_by_date: dict[str, list[Any]] = {}
    receipts_by_tx: dict[int, Any] = {}
    for rec in receipts:
        receipts_by_date.setdefault(rec.purchase_date, []).append(rec)
        if rec.transaction_id is not None:
            receipts_by_tx[int(rec.transaction_id)] = rec

    day_income: dict[str, int] = {f"{month}-{d:02d}": 0 for d in range(1, days_in_month + 1)}
    day_expense: dict[str, int] = {f"{month}-{d:02d}": 0 for d in range(1, days_in_month + 1)}
    day_txs: dict[str, list[Any]] = {f"{month}-{d:02d}": [] for d in range(1, days_in_month + 1)}

    for tx in txs:
        if tx.date in day_txs:
            day_txs[tx.date].append(tx)
            if tx.kind == "income":
                day_income[tx.date] += tx.amount
            else:
                day_expense[tx.date] += tx.amount

    today_iso = date.today().isoformat()
    default_sel = today_iso if today_iso.startswith(month) else f"{month}-01"
    selected_date = str(st.session_state.get("selected_calendar_date", default_sel))
    if not selected_date.startswith(month) or selected_date not in day_txs:
        selected_date = default_sel
        st.session_state["selected_calendar_date"] = selected_date

    flame_svg = lucide_svg("flame", 15, "#F87171")
    cam_small_svg = lucide_svg("camera", 13, "#9CA3AF")
    _html_md(
        "".join([
            '<div class="cal-section-bar">',
            f'<div class="cal-section-title">{flame_svg}<span>LỊCH TÀI CHÍNH</span></div>',
            f'<a href="?tab=hoadon&bmode=gallery" target="_self" class="cal-photo-pill">{cam_small_svg}<span>Kho ảnh</span></a>',
            '</div>',
        ])
    )

    # Build toàn bộ HTML lưới lịch bằng list phẳng "".join(cal_parts) không có dòng trống hay thụt lề
    cal_parts: list[str] = [
        '<div class="cal-wrapper">',
        '<div class="cal-top-pair">',
        '<div class="cal-box-chi">',
        f'<div class="cal-box-chi-label">{lucide_svg("arrow-up-right", 14, "#F87171")}<span>CHI</span></div>',
        f'<div class="cal-box-chi-val">{money(summary["expense"])}</div>',
        '</div>',
        '<div class="cal-box-thu">',
        f'<div class="cal-box-thu-label">{lucide_svg("arrow-down-left", 14, "#4ADE80")}<span>THU</span></div>',
        f'<div class="cal-box-thu-val">{"+" if summary["income"] > 0 else ""}{money(summary["income"])}</div>',
        '</div>',
        '</div>',
        '<div class="cal-grid-7">',
    ]
    for wd in WEEKDAY_LABELS:
        cal_parts.append(f'<div class="cal-weekday">{wd}</div>')

    for week in monthcalendar(year, month_num):
        for day_num in week:
            if day_num == 0:
                cal_parts.append('<div class="cal-cell-empty"></div>')
                continue
            d_iso = f"{month}-{day_num:02d}"
            exp_val = day_expense[d_iso]
            inc_val = day_income[d_iso]
            has_rec = bool(receipts_by_date.get(d_iso))
            is_selected = d_iso == selected_date

            classes = ["cal-cell"]
            if exp_val > 0:
                if exp_val <= low_th:
                    classes.append("cal-cell-low")
                elif exp_val <= high_th:
                    classes.append("cal-cell-mid")
                else:
                    classes.append("cal-cell-high")
            if is_selected:
                classes.append("cal-cell-selected")

            cell_inner: list[str] = [f'<div class="cal-day-num">{day_num}</div>']
            if exp_val > 0:
                cell_inner.append(f'<div class="cal-day-exp">-{compact_money(exp_val)}</div>')
            elif inc_val > 0:
                cell_inner.append(f'<div class="cal-day-inc">+{compact_money(inc_val)}</div>')
            elif is_selected or has_rec:
                cell_inner.append('<div class="cal-day-dot"></div>')

            cls_str = " ".join(classes)
            cal_parts.append(
                f'<a href="?tab=lich&day={d_iso}" target="_self" class="{cls_str}">{"".join(cell_inner)}</a>'
            )

    cal_parts.append('</div></div>')

    # Thẻ Chi tiêu an toàn & Báo cáo cảnh báo vượt mức (3 cấp: An toàn | Sắp chạm ngưỡng | Vượt định mức)
    daily_safe, cap_amount, used_pct, safe_status = _compute_safe_daily_allowance(month, summary, budgets)
    actual_pct = (summary["expense"] / cap_amount * 100.0) if cap_amount > 0 else 0.0
    over_amount = max(0, summary["expense"] - cap_amount)
    remaining_amount = max(0, cap_amount - summary["expense"])
    is_over = over_amount > 0
    is_warn = (not is_over) and actual_pct >= 80.0
    safe_bar_pct = min(100.0, max(0.0, actual_pct))

    if is_over:
        safe_card_border = "border-color:rgba(248,113,113,0.52);"
        safe_icon = lucide_svg("alert-triangle", 18, "#F87171")
        safe_badge_html = f'<span class="dt-safe-badge danger">Vượt định mức (+{actual_pct - 100.0:.1f}%)</span>'
        safe_bar_bg = "linear-gradient(90deg, #DC2626, #F87171)"
        safe_amount_html = (
            f'<div class="dt-safe-amount" style="color:#F87171;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;">'
            f'<span>0 ₫ <span style="font-size:0.85rem;font-weight:600;color:var(--text-muted);">/ ngày</span></span>'
            f'<span style="font-size:0.86rem;font-weight:800;color:#FCA5A5;background:rgba(220,38,38,0.18);'
            f'border:1px solid rgba(248,113,113,0.4);padding:2px 10px;border-radius:999px;">Vượt {money(over_amount)}</span>'
            f'</div>'
        )
    elif is_warn:
        safe_card_border = "border-color:rgba(251,191,36,0.48);"
        safe_icon = lucide_svg("alert-triangle", 18, "#FBBF24")
        safe_badge_html = (
            '<span class="dt-safe-badge" style="background:rgba(245,158,11,0.16);color:#FBBF24;'
            'border-color:rgba(251,191,36,0.38);">Sắp chạm ngưỡng</span>'
        )
        safe_bar_bg = "linear-gradient(90deg, #D97706, #FBBF24)"
        safe_amount_html = (
            f'<div class="dt-safe-amount" style="color:#FBBF24;">{money(daily_safe)} '
            '<span style="font-size:0.85rem;font-weight:600;color:var(--text-muted);">/ ngày</span></div>'
        )
    else:
        safe_card_border = ""
        safe_icon = lucide_svg("shield-check", 18, "#34D399")
        safe_badge_html = f'<span class="dt-safe-badge">{escape(safe_status)}</span>'
        safe_bar_bg = "linear-gradient(90deg, #16A36A, #34D399)"
        safe_amount_html = (
            f'<div class="dt-safe-amount">{money(daily_safe)} '
            '<span style="font-size:0.85rem;font-weight:600;color:var(--text-muted);">/ ngày</span></div>'
        )

    # Báo cáo chi tiết danh mục vượt mức (nếu có)
    exceeded_cats = [
        st_item for cat_k, st_item in budgets.items()
        if cat_k != TOTAL_BUDGET_CATEGORY and st_item.exceeded
    ]
    alert_report_html = ""
    if is_over or exceeded_cats:
        cat_lines: list[str] = []
        if is_over:
            cat_lines.append(
                f"<div>• <strong>Tổng ngân sách tháng:</strong> Vượt <strong>{money(over_amount)}</strong> "
                f"(đã chi {money(summary['expense'])} / {money(cap_amount)} — <strong>{actual_pct:.1f}%</strong>).</div>"
            )
        for ex_st in exceeded_cats:
            cat_lines.append(
                f"<div>• <strong>{escape(_category_label(ex_st.category))}:</strong> Vượt "
                f"<strong>{money(-ex_st.remaining)}</strong> ({ex_st.ratio * 100:.0f}% định mức).</div>"
            )
        alert_report_html = "".join([
            '<div style="margin-top:12px;padding:12px 14px;border-radius:14px;'
            'background:rgba(220,38,38,0.12);border:1px solid rgba(248,113,113,0.38);">',
            f'<div style="display:flex;align-items:center;gap:6px;font-size:0.82rem;font-weight:800;color:#F87171;margin-bottom:6px;">'
            f'{lucide_svg("alert-triangle", 15, "#F87171")}<span>BÁO CÁO CẢNH BÁO VƯỢT ĐỊNH MỨC</span></div>',
            f'<div style="font-size:0.79rem;line-height:1.55;color:var(--text-main);">{"".join(cat_lines)}</div>',
            '<div style="display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;">',
            '<a href="?tab=thongke" target="_self" style="font-size:0.75rem;font-weight:700;color:#FCA5A5;text-decoration:none;'
            'background:rgba(220,38,38,0.2);border:1px solid rgba(248,113,113,0.35);padding:5px 11px;border-radius:999px;">Xem báo cáo chi tiết →</a>',
            '<a href="?tab=canhan" target="_self" style="font-size:0.75rem;font-weight:700;color:var(--text-main);text-decoration:none;'
            'background:var(--bg-card-elevated);border:1px solid var(--border-input);padding:5px 11px;border-radius:999px;">Điều chỉnh hạn mức</a>',
            '</div></div>',
        ])
    elif is_warn:
        alert_report_html = (
            '<div style="margin-top:12px;padding:10px 14px;border-radius:14px;'
            'background:rgba(245,158,11,0.12);border:1px solid rgba(251,191,36,0.35);'
            'font-size:0.79rem;color:var(--text-main);">'
            f'<strong>Lưu ý:</strong> Bạn đã dùng <strong>{actual_pct:.1f}%</strong> định mức tháng, '
            f'còn lại <strong>{money(remaining_amount)}</strong>. Hãy ưu tiên các khoản thiết yếu!</div>'
        )

    desktop_safe_card = "".join([
        f'<div class="dt-safe-card" style="{safe_card_border}">',
        '<div class="dt-safe-head">',
        f'<div class="dt-safe-title">{safe_icon}<span>Chi tiêu an toàn</span></div>',
        safe_badge_html,
        '</div>',
        safe_amount_html,
        f'<div class="dt-safe-bar-track"><div class="dt-safe-bar-fill" style="width:{safe_bar_pct:.1f}%;background:{safe_bar_bg};"></div></div>',
        '<div class="dt-safe-meta">',
        f'<span>Đã chi tháng này: <strong style="color:{"#F87171" if is_over else "var(--text-main)"};">{money(summary["expense"])}</strong></span>',
        f'<span>Định mức: <strong>{money(cap_amount)}</strong> (<strong style="color:{"#F87171" if is_over else "#34D399"};">{actual_pct:.1f}%</strong>)</span>',
        '</div>',
        alert_report_html,
        '</div>',
    ])

    # 4. CHI TIẾT NGÀY ĐANG CHỌN & QUICK ADD (GỌN DƯỚI LỊCH TRÊN MOBILE, CỘT PHẢI TRÊN MÁY TÍNH)
    sel_txs = day_txs[selected_date]
    sel_dt = date.fromisoformat(selected_date)
    weekday_vn = WEEKDAY_FULL_VN[sel_dt.weekday()]
    day_header_str = f"{weekday_vn}, {sel_dt.day} tháng {sel_dt.month}"
    day_net_exp = day_expense[selected_date]
    day_net_inc = day_income[selected_date]

    if day_net_exp > 0:
        day_hero_val = f"-{money(day_net_exp)}"
        day_hero_color = "#F87171"
    elif day_net_inc > 0:
        day_hero_val = f"+{money(day_net_inc)}"
        day_hero_color = "#4ADE80"
    else:
        day_hero_val = "0 ₫"
        day_hero_color = "#9CA3AF"

    day_parts: list[str] = [
        '<div class="day-inspector-card">',
        '<div class="day-inspector-head">',
        f'<div class="day-inspector-date">{lucide_svg("calendar", 17, "#34D399")}<span>{escape(day_header_str)}</span></div>',
        f'<div class="day-inspector-total" style="color:{day_hero_color};font-size:1.1rem;">{day_hero_val}</div>',
        '</div>',
    ]
    if sel_txs:
        for tx in sel_txs:
            icon_box = category_lucide_box(tx.category, tx.note, box_size=36)
            tx_title = escape(tx.note or tx.category)
            rec_attached = receipts_by_tx.get(tx.id)
            rec_label = f" · HĐ #{rec_attached.id}" if rec_attached else ""
            amt_prefix = "+" if tx.kind == "income" else "-"
            amt_color = "#4ADE80" if tx.kind == "income" else "#F87171"
            day_parts.append(
                f'<div class="day-tx-item">'
                f'<div class="day-tx-left">{icon_box}<div>'
                f'<div class="day-tx-title">{tx_title}</div>'
                f'<div class="day-tx-cat">#{tx.id} · {escape(tx.category)}{escape(rec_label)}</div>'
                f'</div></div>'
                f'<div class="day-tx-amount" style="color:{amt_color};">{amt_prefix}{money(tx.amount)}</div>'
                f'</div>'
            )
    else:
        day_parts.append(
            '<div style="font-size:0.8rem;color:var(--text-muted);padding:4px 0;">'
            'Chưa có giao dịch trong ngày này. Mở mục Ghi nhanh bên dưới để thêm.</div>'
        )
    day_parts.append('</div>')

    # Thẻ Gợi ý từ Uni AI + Mascot (chỉ hiện trên cột phải Máy tính >= 1024px)
    desktop_ai_card = "".join([
        '<div class="dt-ai-mascot-card desktop-only-widget">',
        '<div style="min-width:0;">',
        f'<div class="dt-ai-kicker">{lucide_svg("sparkles", 15, "#34D399")}<span>Gợi ý từ Uni AI</span></div>',
        f'<div class="dt-ai-body">{escape(ai_tip)}</div>',
        f'<a href="?tab=thongke" target="_self" class="dt-ai-btn">Xem phân tích {lucide_svg("arrow-right", 13, "#34D399")}</a>',
        '</div>',
        f'<div style="display:flex;justify-content:center;align-items:center;">{mascot_calendar_svg(width=98, height=98)}</div>',
        '</div>',
    ])

    # Thẻ Giao dịch gần đây (chỉ hiện trên cột phải Máy tính >= 1024px)
    recent_rows: list[str] = [
        '<div class="dt-recent-card desktop-only-widget">',
        '<div class="dt-recent-head">',
        f'<div class="dt-recent-title">{lucide_svg("arrow-left-right", 16, "#34D399")}<span>Giao dịch gần đây</span></div>',
        '<a href="?tab=thongke" target="_self" class="dt-recent-all">Xem tất cả →</a>',
        '</div>',
    ]
    if txs:
        for rtx in txs[:4]:
            r_icon = category_lucide_box(rtx.category, rtx.note, box_size=34)
            r_prefix = "+" if rtx.kind == "income" else "-"
            r_color = "#4ADE80" if rtx.kind == "income" else "#F87171"
            recent_rows.append(
                f'<div class="day-tx-item">'
                f'<div class="day-tx-left">{r_icon}<div>'
                f'<div class="day-tx-title">{escape(rtx.note or rtx.category)}</div>'
                f'<div class="day-tx-cat">{display_date(rtx.date)} · {escape(rtx.category)}</div>'
                f'</div></div>'
                f'<div class="day-tx-amount" style="color:{r_color};">{r_prefix}{money(rtx.amount)}</div>'
                f'</div>'
            )
    else:
        recent_rows.append(
            '<div style="font-size:0.8rem;color:var(--text-muted);padding:4px 0;">Chưa có giao dịch nào trong tháng.</div>'
        )
    recent_rows.append('</div>')

    # Khung 2 cột trên Máy Tính / 1 cột nguyên bản trên Điện Thoại
    workspace_html = "".join([
        '<div class="desktop-split-workspace">',
        '<div class="desktop-split-left">',
        "".join(cal_parts),
        desktop_safe_card,
        '</div>',
        '<div class="desktop-split-right">',
        desktop_ai_card,
        "".join(day_parts),
        "".join(recent_rows),
        '</div>',
        '</div>',
    ])
    _html_md(workspace_html)

    if sel_txs:
        with st.expander(f"✏️ Sửa / Xóa giao dịch ngày {display_date(selected_date)} ({len(sel_txs)} khoản)"):
            day_tx_map = {t.id: t for t in sel_txs}
            chosen_day_tx_id = st.selectbox(
                "Chọn giao dịch",
                list(day_tx_map.keys()),
                format_func=lambda tid: f"#{tid} · {day_tx_map[tid].category} · {money(day_tx_map[tid].amount)} · {day_tx_map[tid].note or ''}",
                key=f"day_panel_tx_sel_{selected_date}",
            )
            chosen_tx = day_tx_map[chosen_day_tx_id]
            with st.form(f"day_panel_edit_form_{chosen_tx.id}", enter_to_submit=False):
                dp_c1, dp_c2 = st.columns(2)
                with dp_c1:
                    dp_cats = EXPENSE_CATEGORIES if chosen_tx.kind == "expense" else INCOME_CATEGORIES
                    dp_cat = st.selectbox(
                        "Danh mục",
                        dp_cats,
                        index=dp_cats.index(chosen_tx.category) if chosen_tx.category in dp_cats else 0,
                        format_func=_category_label,
                    )
                with dp_c2:
                    dp_amt = st.number_input(
                        "Số tiền (VNĐ)",
                        min_value=1_000,
                        max_value=MAX_AMOUNT,
                        value=int(chosen_tx.amount),
                        step=5_000,
                        format="%d",
                    )
                dp_note = st.text_input("Ghi chú", value=chosen_tx.note, max_chars=200)
                b_upd, b_del = st.columns(2)
                with b_upd:
                    do_upd = st.form_submit_button("Lưu cập nhật", type="primary", width="stretch")
                with b_del:
                    do_del = st.form_submit_button("Xóa khoản này", width="stretch")
                if do_upd:
                    try:
                        store.update_transaction(chosen_tx.id, chosen_tx.date, chosen_tx.kind, dp_cat, int(dp_amt), dp_note)
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(str(exc))
                    else:
                        _notice(f"Đã cập nhật giao dịch #{chosen_tx.id}.")
                if do_del:
                    try:
                        store.delete_transaction(chosen_tx.id)
                    except (ValueError, sqlite3.Error) as exc:
                        st.error(str(exc))
                    else:
                        _notice(f"Đã xóa giao dịch #{chosen_tx.id}.")

    default_wallet = ext_store.get_setting("default_wallet", "Ví tiền mặt") or "Ví tiền mặt"
    with st.expander(f"⚡ Quick Add — Ghi nhanh ngày {display_date(selected_date)}"):
        cal_kind_lbl = st.radio(
            "Loại giao dịch ngày chọn",
            ["Chi tiêu", "Thu nhập"],
            horizontal=True,
            key=f"cal_add_kind_{selected_date}",
            label_visibility="collapsed",
        )
        cal_kind = "expense" if cal_kind_lbl == "Chi tiêu" else "income"
        cal_cats = EXPENSE_CATEGORIES if cal_kind == "expense" else INCOME_CATEGORIES
        wallet_opts = ["Ví tiền mặt", "Tài khoản Ngân hàng", "Ví MoMo / ZaloPay"]
        if default_wallet not in wallet_opts:
            wallet_opts.insert(0, default_wallet)
        with st.form(f"cal_quick_add_{selected_date}_{cal_kind}", enter_to_submit=False):
            qa_c1, qa_c2 = st.columns(2)
            with qa_c1:
                cal_cat = st.selectbox("Danh mục", cal_cats, format_func=_category_label)
            with qa_c2:
                cal_wallet = st.selectbox("Chọn ví", wallet_opts, index=wallet_opts.index(default_wallet))
            cal_amt = st.number_input("Số tiền (VNĐ)", min_value=1_000, max_value=MAX_AMOUNT, value=35_000, step=5_000, format="%d")
            cal_note = st.text_input("Ghi chú", max_chars=200, placeholder="VD: Cà phê, Ăn trưa, Di chuyển...")
            if st.form_submit_button(f"+ Lưu giao dịch ({display_date(selected_date)})", type="primary", width="stretch"):
                final_note = cal_note.strip()
                if cal_wallet != "Ví tiền mặt" and f"[{cal_wallet}]" not in final_note:
                    final_note = f"{final_note} [{cal_wallet}]".strip()[:200]
                try:
                    store.add_transaction(selected_date, cal_kind, cal_cat, int(cal_amt), final_note)
                except (ValueError, sqlite3.Error) as exc:
                    st.error(f"Không lưu được: {exc}")
                else:
                    _notice(f"Đã thêm giao dịch vào ngày {display_date(selected_date)}.")

    # 5. HAI NÚT NỔI (FAB) CỐ ĐỊNH GÓC DƯỚI BÊN PHẢI (Camera -> ?tab=ocr, Micro -> ?tab=voice)
    fab_parts = [
        '<div class="unispend-fab-stack">',
        f'<a href="?tab=ocr" target="_self" class="unispend-fab-btn fab-cam" title="Quét hóa đơn AI">{lucide_svg("camera", 22, "#FFFFFF")}</a>',
        f'<a href="?tab=voice" target="_self" class="unispend-fab-btn fab-mic" title="Nhập bằng giọng nói">{lucide_svg("mic", 21, "#E5E7EB")}</a>',
        '</div>',
    ]
    _html_md("".join(fab_parts))

    # Các nút Streamlit tương thích kiểm thử cho Radial FAB
    st.session_state.setdefault("radial_fab_open", False)
    with st.expander("Phím tắt Camera / Thư viện / Giọng nói", expanded=False):
        if st.button("📷 Quét Hóa Đơn (+)", key="cal_fab_camera", width="stretch"):
            st.session_state["radial_fab_open"] = True
            st.rerun()
        if st.session_state.get("radial_fab_open"):
            rb1, rb2, rb3, rb4 = st.columns(4)
            with rb1:
                if st.button("📷 Camera", key="rad_btn_cam", width="stretch"):
                    st.session_state["ocr_input_mode"] = "📷 Chụp ảnh bằng Camera"
                    st.session_state["active_studio_panel"] = "ocr"
                    st.session_state["active_mobile_tab"] = "ocr"
                    st.session_state["radial_fab_open"] = False
                    st.rerun()
            with rb2:
                if st.button("🖼️ Thư viện", key="rad_btn_gal", width="stretch"):
                    st.session_state["ocr_input_mode"] = "📤 Tải ảnh hóa đơn (JPG/PNG)"
                    st.session_state["active_studio_panel"] = "ocr"
                    st.session_state["active_mobile_tab"] = "ocr"
                    st.session_state["radial_fab_open"] = False
                    st.rerun()
            with rb3:
                if st.button("🎙️ Giọng nói", key="rad_btn_mic", width="stretch"):
                    st.session_state["active_studio_panel"] = "voice"
                    st.session_state["active_mobile_tab"] = "voice"
                    st.session_state["radial_fab_open"] = False
                    st.rerun()
            with rb4:
                if st.button("✕ Đóng", key="rad_btn_close", width="stretch"):
                    st.session_state["radial_fab_open"] = False
                    st.rerun()


# =============================================================================
# TAB 2: HÓA ĐƠN & ĐĂNG KÝ (GIỐNG SÁT ẢNH 2)
# =============================================================================
def _render_receipt_vault_gallery(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
) -> None:
    """Kho lưu trữ ảnh hóa đơn đã chụp / quét OCR (Receipt Vault & Gallery)."""
    all_receipts = ext_store.list_receipts()
    with_images = [r for r in all_receipts if r.image_blob]
    total_val = sum(r.total_amount for r in all_receipts)

    # 1. Thẻ tóm tắt Kho ảnh hóa đơn
    _html_md(
        "".join([
            '<div class="cal-top-pair" style="margin-top:4px;">',
            '<div class="cal-box-thu" style="padding:14px 16px;">',
            f'<div class="cal-box-thu-label">{lucide_svg("image", 15, "#4ADE80")}<span>ẢNH HÓA ĐƠN ĐÃ LƯU</span></div>',
            f'<div class="cal-box-thu-val" style="font-size:1.65rem;margin:4px 0;">{len(all_receipts)}</div>',
            f'<div style="font-size:0.75rem;color:var(--text-muted);">{len(with_images)} hóa đơn có ảnh gốc</div>',
            '</div>',
            '<div class="cal-box-chi" style="padding:14px 16px;">',
            f'<div class="cal-box-chi-label">{lucide_svg("wallet", 15, "#F87171")}<span>TỔNG GIÁ TRỊ LƯU TRỮ</span></div>',
            f'<div class="cal-box-chi-val" style="font-size:1.35rem;margin:6px 0;">{money(total_val)}</div>',
            '<div style="font-size:0.75rem;color:var(--text-muted);">Tất cả hóa đơn trong kho</div>',
            '</div>',
            '</div>',
        ])
    )

    # 2. Form chụp / tải nhanh ảnh hóa đơn vào kho (kèm lối tắt sang Quét AI tự động)
    with st.expander("📸 Chụp / Tải ảnh hóa đơn mới vào kho", expanded=(len(all_receipts) == 0)):
        st.caption(
            "Lưu trữ ảnh hóa đơn gốc trực tiếp vào kho SQLite trên máy bạn. "
            "Nếu muốn AI tự đọc số tiền & món hàng từ ảnh, dùng nút Quét Hóa Đơn AI bên dưới."
        )
        vault_src = st.radio(
            "Cách thêm ảnh hóa đơn",
            ["📁 Tải ảnh từ thiết bị (JPG/PNG)", "📷 Chụp trực tiếp bằng Camera"],
            horizontal=True,
            key="vault_img_source",
        )
        vault_file = None
        if vault_src.startswith("📁"):
            vault_file = st.file_uploader(
                "Chọn ảnh hóa đơn để lưu kho",
                type=["jpg", "jpeg", "png"],
                key="vault_upload_file",
            )
        else:
            vault_file = st.camera_input("Chụp ảnh hóa đơn", key="vault_camera_file")

        if vault_file is not None:
            st.image(vault_file.getvalue(), caption="Ảnh hóa đơn chuẩn bị lưu kho", width="stretch")

        with st.form("vault_save_receipt_form", enter_to_submit=False):
            vc1, vc2 = st.columns(2)
            with vc1:
                v_store = st.text_input("Tên cửa hàng / nơi mua", placeholder="VD: Highlands Coffee, WinMart…", max_chars=120)
                v_date = st.date_input("Ngày trên hóa đơn", value=date.today(), min_value=date.min, max_value=date.max)
            with vc2:
                v_amount = st.number_input("Tổng tiền (VNĐ)", min_value=0, max_value=MAX_AMOUNT, value=50_000, step=5_000, format="%d")
                v_cat = st.selectbox("Danh mục", EXPENSE_CATEGORIES, format_func=_category_label)
            v_note = st.text_input("Ghi chú ngắn (tùy chọn)", placeholder="VD: Hóa đơn ăn trưa, mua sách giáo trình…", max_chars=200)
            v_also_tx = st.checkbox("Đồng thời ghi thành giao dịch chi tiêu vào Lịch tài chính", value=True)
            v_submit = st.form_submit_button("💾 Lưu ảnh vào Kho hóa đơn", type="primary", width="stretch")
            if v_submit:
                if vault_file is None:
                    st.warning("Vui lòng chọn hoặc chụp một ảnh hóa đơn trước khi lưu.")
                else:
                    img_bytes = vault_file.getvalue()
                    img_mime = getattr(vault_file, "type", None) or "image/jpeg"
                    img_hash = hashlib.sha256(img_bytes).hexdigest()
                    clean_store = v_store.strip() or "Hóa đơn đã lưu"
                    dup = ext_store.find_duplicate_receipt(img_hash, clean_store, v_date.isoformat(), int(v_amount))
                    if dup:
                        st.warning(f"Ảnh hóa đơn này đã tồn tại trong kho (Mã #{dup.id} · {dup.store_name}).")
                    else:
                        tx_id: int | None = None
                        if v_also_tx and int(v_amount) > 0:
                            note_str = v_note.strip() or clean_store
                            tx_id = store.add_transaction(v_date.isoformat(), "expense", v_cat, int(v_amount), note_str)
                        ext_store.add_receipt(
                            transaction_id=tx_id,
                            store_name=clean_store,
                            purchase_date=v_date.isoformat(),
                            purchase_time="",
                            items=[],
                            discount=0,
                            total_amount=int(v_amount),
                            payment_method="Không rõ",
                            suggested_category=v_cat,
                            image_bytes=img_bytes,
                            image_mime=img_mime,
                            raw_text=v_note.strip(),
                        )
                        _notice(f"Đã lưu ảnh hóa đơn '{clean_store}' vào Kho ảnh thành công!")

        _html_md(
            '<div style="margin-top:8px;">'
            f'<a href="?tab=ocr" target="_self" class="udt-pill-btn" style="width:100%;justify-content:center;">'
            f'{lucide_svg("scan-line", 15, "#34D399")}<span>Mở Quét Hóa Đơn AI tự động (Tesseract + Gemini)</span></a>'
            '</div>'
        )

    # 3. Bộ lọc 3 cột gọn gàng: Phạm vi | Danh mục | Tìm kiếm
    f_c1, f_c2, f_c3 = st.columns([1.0, 1.0, 1.6])
    with f_c1:
        scope_opt = st.selectbox(
            "Phạm vi",
            [f"Tất cả ({len(all_receipts)})", f"Tháng {month}"],
            key="vault_scope_filter",
        )
    with f_c2:
        cat_filter = st.selectbox(
            "Danh mục",
            ["Tất cả", *EXPENSE_CATEGORIES],
            key="vault_cat_filter",
        )
    with f_c3:
        q_search = st.text_input(
            "Tìm nhanh hóa đơn",
            placeholder="Tên quán, món hàng, ngày…",
            key="vault_search_query",
        ).strip().casefold()

    shown = all_receipts if scope_opt.startswith("Tất cả") else ext_store.list_receipts(month=month)
    if cat_filter != "Tất cả":
        shown = [r for r in shown if r.suggested_category == cat_filter]
    if q_search:
        shown = [
            r for r in shown
            if q_search in (r.store_name or "").casefold()
            or q_search in (r.suggested_category or "").casefold()
            or q_search in (r.raw_text or "").casefold()
            or q_search in (r.purchase_date or "").casefold()
        ]

    # Phân trang 10 hóa đơn/trang cho mượt & gọn mắt
    page_size = 10
    total_pages = max(1, (len(shown) + page_size - 1) // page_size)
    p_c1, p_c2 = st.columns([2.2, 1.0])
    with p_c1:
        _html_md(
            "".join([
                '<div class="cal-section-bar" style="margin:6px 0;">',
                f'<div class="cal-section-title">{lucide_svg("image", 15, "#34D399")}<span>KHO ẢNH HÓA ĐƠN</span></div>',
                f'<div class="cal-photo-pill">{len(shown)} hóa đơn · {money(sum(r.total_amount for r in shown))}</div>',
                '</div>',
            ])
        )
    with p_c2:
        cur_page = int(
            st.selectbox(
                "Trang",
                list(range(1, total_pages + 1)),
                format_func=lambda p: f"Trang {p}/{total_pages}",
                key="vault_page_num",
                label_visibility="collapsed",
            )
        )

    if not shown:
        q_svg = mascot_question_svg(width=102, height=102)
        _html_md(
            "".join([
                '<div class="bills-empty-state">',
                q_svg,
                '<div class="bills-empty-title">Kho ảnh hóa đơn chưa có mục nào</div>',
                '<div class="bills-empty-sub">Chụp ảnh hóa đơn ở mục trên hoặc dùng Quét Hóa Đơn AI để lưu tự động vào kho!</div>',
                '</div>',
            ])
        )
        return

    start_i = (cur_page - 1) * page_size
    page_items = shown[start_i : start_i + page_size]

    # 4. Hiển thị lưới 2 cột gọn gàng, sạch sẽ
    for row_idx in range(0, len(page_items), 2):
        row_pair = page_items[row_idx : row_idx + 2]
        grid_cols = st.columns(2)
        for col_idx, rec in enumerate(row_pair):
            with grid_cols[col_idx]:
                with st.container(border=True):
                    tx_badge = f"GD #{rec.transaction_id}" if rec.transaction_id else "Chỉ lưu ảnh"
                    _html_md(
                        "".join([
                            '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px;">',
                            f'<div style="font-size:0.9rem;font-weight:800;color:var(--text-main);line-height:1.25;">{escape(rec.store_name)}</div>',
                            f'<span class="essential-pill pill-safe" style="font-size:0.66rem;padding:2px 8px;flex-shrink:0;">{escape(rec.suggested_category)}</span>',
                            '</div>',
                            f'<div style="font-size:1.12rem;font-weight:900;color:#F87171;margin-bottom:6px;">-{money(rec.total_amount)}</div>',
                        ])
                    )
                    thumb_c, meta_c = st.columns([1.0, 1.35])
                    with thumb_c:
                        if rec.image_blob:
                            st.image(rec.image_blob, width="stretch")
                        else:
                            _html_md(
                                '<div style="height:88px;border-radius:10px;background:var(--bg-card-elevated);'
                                'border:1px dashed var(--border-input);display:flex;align-items:center;'
                                f'justify-content:center;color:var(--text-muted);">{lucide_svg("file-text", 22, "#34D399")}</div>'
                            )
                    with meta_c:
                        _html_md(
                            f'<div style="font-size:0.75rem;color:var(--text-muted);line-height:1.55;">'
                            f'<strong>{display_date(rec.purchase_date)}</strong> {escape(rec.purchase_time or "")}<br>'
                            f'TT: {escape(rec.payment_method or "Không rõ")}<br>'
                            f'Mã: #{rec.id} · {escape(tx_badge)}'
                            f'</div>'
                        )
                        b1, b2 = st.columns(2)
                        with b1:
                            if rec.image_blob:
                                ext_name = "png" if "png" in (rec.image_mime or "").lower() else "jpg"
                                st.download_button(
                                    "📥 Tải",
                                    data=rec.image_blob,
                                    file_name=f"UniSpend_HoaDon_{rec.id}_{rec.purchase_date}.{ext_name}",
                                    mime=rec.image_mime or "image/jpeg",
                                    width="stretch",
                                    key=f"vault_dl_{rec.id}",
                                )
                        with b2:
                            if st.button("🗑️ Xóa", key=f"vault_del_{rec.id}", width="stretch"):
                                ext_store.delete_receipt(rec.id)
                                _notice(f"Đã xóa hóa đơn #{rec.id} khỏi kho ảnh.")

                    if rec.items or rec.raw_text or rec.image_blob:
                        with st.expander(f"🔍 Xem chi tiết & ảnh lớn (#{rec.id})"):
                            if rec.image_blob:
                                st.image(rec.image_blob, width="stretch")
                            if rec.items:
                                for it in rec.items:
                                    if isinstance(it, dict):
                                        st.write(f"- **{it.get('name', 'Món hàng')}**: {money(int(it.get('price', 0) or 0))}")
                            if rec.raw_text:
                                st.code(rec.raw_text, language="text")


def _render_tab_hoadon(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
) -> None:
    st.session_state.setdefault("bills_submode", "recurring")
    submode = st.session_state["bills_submode"]

    # 1. Header
    _html_md(
        '<div style="padding:4px 2px 6px 2px;">'
        '<div style="font-size:1.55rem;font-weight:900;color:var(--text-main);letter-spacing:-0.02em;">Hóa Đơn &amp; Kho Ảnh</div>'
        '<div style="font-size:0.8rem;color:var(--text-muted);margin-top:2px;">Quản lý hóa đơn định kỳ, sổ ghi nợ và kho lưu trữ ảnh hóa đơn</div>'
        '</div>'
    )

    # 2. Thanh chuyển đổi 3 chế độ nằm ngang (Segmented Control bo tròn 999px)
    rec_cls = "monii-seg-item active" if submode == "recurring" else "monii-seg-item"
    debt_cls = "monii-seg-item active" if submode == "debt" else "monii-seg-item"
    gal_cls = "monii-seg-item active" if submode == "gallery" else "monii-seg-item"
    clock_svg = lucide_svg("clock", 14, "currentColor")
    coins_svg = lucide_svg("hand-coins", 14, "currentColor")
    img_svg = lucide_svg("image", 14, "currentColor")
    _html_md(
        "".join([
            '<div class="monii-segmented-bar">',
            f'<a href="?tab=hoadon&bmode=recurring" target="_self" class="{rec_cls}">{clock_svg}<span>Định kỳ</span></a>',
            f'<a href="?tab=hoadon&bmode=debt" target="_self" class="{debt_cls}">{coins_svg}<span>Sổ nợ</span></a>',
            f'<a href="?tab=hoadon&bmode=gallery" target="_self" class="{gal_cls}">{img_svg}<span>Kho ảnh</span></a>',
            '</div>',
        ])
    )

    if submode == "gallery":
        _render_receipt_vault_gallery(store, ext_store, month)
        return

    all_rec_items = ext_store.list_recurring_items()
    if submode == "recurring":
        filtered_items = [it for it in all_rec_items if it.item_type in ("recurring", "payable")]
    else:
        filtered_items = [it for it in all_rec_items if it.item_type == "debt"]

    unpaid_items = [it for it in filtered_items if it.active and it.last_recorded_date[:7] != month]
    paid_items = [it for it in filtered_items if not it.active or it.last_recorded_date[:7] == month]

    # 3. Hai thẻ tóm tắt nằm ngang bằng nhau (CHƯA THANH TOÁN | ĐÃ THANH TOÁN)
    _html_md(
        "".join([
            '<div class="cal-top-pair" style="margin-top:4px;">',
            '<div class="cal-box-chi" style="padding:14px 16px;">',
            f'<div class="cal-box-chi-label">{lucide_svg("arrow-up-right", 15, "#F87171")}<span>CHƯA THANH TOÁN</span></div>',
            f'<div class="cal-box-chi-val" style="font-size:1.7rem;margin:4px 0;">{len(unpaid_items)}</div>',
            f'<div style="font-size:0.75rem;color:var(--text-muted);">{len(unpaid_items)} khoản cần chi</div>',
            '</div>',
            '<div class="cal-box-thu" style="padding:14px 16px;">',
            f'<div class="cal-box-thu-label">{lucide_svg("check-circle-2", 15, "#4ADE80")}<span>ĐÃ THANH TOÁN</span></div>',
            f'<div class="cal-box-thu-val" style="font-size:1.7rem;margin:4px 0;">{len(paid_items)}</div>',
            f'<div style="font-size:0.75rem;color:var(--text-muted);">{len(paid_items)} khoản đã chi</div>',
            '</div>',
            '</div>',
        ])
    )

    # 4. Danh sách hóa đơn
    _html_md(
        "".join([
            '<div class="cal-section-bar">',
            f'<div class="cal-section-title">{lucide_svg("calendar-check", 15, "#34D399")}<span>DANH SÁCH HÓA ĐƠN</span></div>',
            f'<div class="cal-photo-pill">{len(filtered_items)} khoản</div>',
            '</div>',
        ])
    )

    freq_labels = {"monthly": "Hằng tháng", "weekly": "Hằng tuần", "once": "Một lần"}
    if not filtered_items:
        q_svg = mascot_question_svg(width=102, height=102)
        _html_md(
            "".join([
                '<div class="bills-empty-state">',
                q_svg,
                '<div class="bills-empty-title">Chưa có hóa đơn nào trong tháng này</div>',
                '<div class="bills-empty-sub">Thêm Hóa Đơn để quản lý tiền điện, nước, tiền nhà...</div>',
                '</div>',
            ])
        )
    else:
        for item in filtered_items:
            due_str = display_date(item.next_due_date)
            is_paid_month = not item.active or item.last_recorded_date[:7] == month
            badge_text = "Đã thanh toán" if is_paid_month else f"Hạn: {due_str}"
            t_cls = "pill-safe" if is_paid_month else "pill-warning"
            partner_str = f" · {escape(item.counterparty)}" if item.counterparty else ""
            _html_md(
                "".join([
                    '<div class="essential-card" style="padding:14px 16px;">',
                    '<div class="essential-header">',
                    f'<div class="essential-title">{category_lucide_box(item.category, item.title, box_size=34)}<span>{escape(item.title)}</span></div>',
                    f'<span class="essential-pill {t_cls}">{escape(badge_text)} · {freq_labels.get(item.frequency, item.frequency)}</span>',
                    '</div>',
                    f'<div class="essential-amount" style="margin:4px 0;">{money(item.amount)}</div>',
                    f'<div class="essential-limit">Danh mục: <strong>{escape(item.category)}</strong>{partner_str}</div>',
                    f'<div class="essential-desc">{escape(item.note)}</div>',
                    '</div>',
                ])
            )
            bc1, bc2 = st.columns(2)
            with bc1:
                if item.active and not is_paid_month:
                    if st.button(
                        f"✓ Đã thanh toán ({due_str[:5]})",
                        key=f"bill_pay_{item.id}",
                        type="primary",
                        width="stretch",
                    ):
                        rec_note = f"[Hóa đơn] {item.title}" + (f" - {item.note}" if item.note else "")
                        store.add_transaction(item.next_due_date, item.kind, item.category, item.amount, rec_note[:200])
                        ext_store.mark_recurring_recorded(item.id, item.next_due_date)
                        _notice(f"Đã ghi nhận thanh toán hóa đơn '{item.title}' ({money(item.amount)}).")
            with bc2:
                if st.button("🗑️ Xóa hóa đơn", key=f"bill_del_{item.id}", width="stretch"):
                    ext_store.delete_recurring_item(item.id)
                    _notice(f"Đã xóa hóa đơn '{item.title}'.")

    # 5. Nút "+ Thêm Hóa Đơn" màu xanh lá dạng viên thuốc
    st.session_state.setdefault("show_add_bill_form", False)
    _, btn_col = st.columns([1.1, 1.0])
    with btn_col:
        if st.button("＋ Thêm Hóa Đơn", type="primary", width="stretch", key="toggle_add_bill_btn"):
            st.session_state["show_add_bill_form"] = not st.session_state["show_add_bill_form"]
            st.rerun()

    if st.session_state.get("show_add_bill_form"):
        with st.container(border=True):
            st.markdown("##### ＋ Thêm Hóa Đơn / Khoản Định Kỳ / Sổ Ghi Nợ")
            rec_kind_lbl = st.radio("Loại dòng tiền", ["Chi tiêu", "Thu nhập"], horizontal=True, key="tab2_rec_kind")
            rec_kind = "expense" if rec_kind_lbl == "Chi tiêu" else "income"
            rec_cats = EXPENSE_CATEGORIES if rec_kind == "expense" else INCOME_CATEGORIES
            with st.form("tab2_add_bill_form", enter_to_submit=False):
                r_title = st.text_input("Tên hóa đơn", max_chars=120, placeholder="VD: Tiền điện, Tiền nước, Tiền nhà...")
                r_type = st.selectbox(
                    "Phân loại",
                    ["recurring", "payable", "debt"],
                    index=0 if submode == "recurring" else 2,
                    format_func=lambda x: {
                        "recurring": "Hóa đơn định kỳ (Tiền nhà, Điện, Nước, Wifi...)",
                        "payable": "Khoản phải trả / Lịch hẹn thanh toán",
                        "debt": "Sổ ghi nợ",
                    }[x],
                )
                r_cat = st.selectbox("Danh mục", rec_cats, format_func=_category_label)
                r_amt = st.number_input("Số tiền (VNĐ)", min_value=1_000, max_value=MAX_AMOUNT, value=500_000, step=50_000, format="%d")
                r_freq = st.selectbox(
                    "Chu kỳ",
                    ["monthly", "weekly", "once"],
                    format_func=lambda x: {"monthly": "Hằng tháng", "weekly": "Hằng tuần", "once": "Một lần"}[x],
                )
                r_due = st.date_input("Ngày đến hạn", value=date.today())
                r_partner = st.text_input("Người nhận / Chủ nợ (tùy chọn)", max_chars=100)
                r_note = st.text_input("Ghi chú", max_chars=180)
                if st.form_submit_button("Lưu Hóa Đơn", type="primary", width="stretch"):
                    try:
                        ext_store.add_recurring_item(
                            title=r_title,
                            item_type=r_type,
                            kind=rec_kind,
                            category=r_cat,
                            amount=int(r_amt),
                            frequency=r_freq,
                            due_day=r_due.day,
                            next_due_date=r_due.isoformat(),
                            counterparty=r_partner,
                            note=r_note,
                        )
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["show_add_bill_form"] = False
                        _notice("Đã thêm hóa đơn mới thành công.")


# =============================================================================
# TAB 3: THỐNG KÊ CHI TIÊU (LƯỚI KPI 2X2 + DONUT + 8 HẠNG MỤC + BIỂU ĐỒ)
# =============================================================================
def _alerts(statuses, *, detailed: bool = False) -> None:
    active = [status for status in statuses if status.near_limit]
    if detailed:
        active = statuses
    if not statuses:
        st.info("Chưa đặt ngân sách tháng này. Mở tab Cá nhân để thiết lập hạn mức.")
    elif not active:
        check_svg = lucide_svg("check-circle-2", 17, "#4ADE80")
        _html_md(
            f'<div class="alert-box alert-safe"><div style="display:flex;align-items:center;gap:8px;">{check_svg}<strong>Chi tiêu đang trong định mức ngân sách.</strong></div></div>'
        )
    for status in active:
        level, title, detail = _status_text(status)
        icon_svg = lucide_svg("alert-triangle" if level != "safe" else "check-circle-2", 16, "#F87171" if level == "danger" else "#FBBF24")
        _html_md(
            f'<div class="alert-box alert-{level}"><div style="display:flex;align-items:center;gap:8px;">'
            f'{icon_svg}<span><strong>{escape(status.category)}:</strong> {escape(detail)}</span></div>'
            f'<span class="essential-pill pill-{level}">{title}</span></div>'
        )


def _render_kpi_2x2(month: str, summary: dict[str, int], budgets: dict[str, Any]) -> None:
    """4 thẻ KPI xếp theo lưới 2x2 chuẩn Mobile để số tiền không bao giờ bị rớt dòng chữ đ."""
    daily_safe, cap_amount, used_pct, status_label = _compute_safe_daily_allowance(month, summary, budgets)
    total = budgets.get(TOTAL_BUDGET_CATEGORY)
    bal_positive = summary["balance"] >= 0
    exp_badge = f"{total.ratio * 100:.0f}% hạn mức" if total else f"{summary['count']} khoản"

    kpi_parts = [
        '<div class="kpi-grid-2x2">',
        # Card 1: Số dư hiện tại
        '<div class="pro-kpi-card">',
        f'<div class="pro-kpi-head">{lucide_box("wallet", color="#34D399", bg="rgba(22,163,106,0.16)", size=18, box_size=36, radius=11)}'
        f'<div class="pro-kpi-meta"><span class="pro-kpi-label">Số dư hiện tại</span><span class="pro-kpi-amount">{money(summary["balance"])}</span></div></div>',
        f'<div class="pro-kpi-foot"><span class="pro-kpi-trend" style="color:{"#4ADE80" if bal_positive else "#F87171"};">'
        f'{"Dương" if bal_positive else "Âm"} thu - chi</span>{mini_sparkline_svg("#34D399" if bal_positive else "#F87171", "up")}</div>',
        '</div>',
        # Card 2: Thu nhập
        '<div class="pro-kpi-card">',
        f'<div class="pro-kpi-head">{lucide_box("arrow-down-left", color="#4ADE80", bg="rgba(22,163,106,0.16)", size=18, box_size=36, radius=11)}'
        f'<div class="pro-kpi-meta"><span class="pro-kpi-label">Thu nhập</span><span class="pro-kpi-amount" style="color:#4ADE80;">{money(summary["income"])}</span></div></div>',
        f'<div class="pro-kpi-foot"><span class="pro-kpi-trend" style="color:#4ADE80;">Tháng {escape(month)}</span>{mini_sparkline_svg("#4ADE80", "up")}</div>',
        '</div>',
        # Card 3: Chi tiêu
        '<div class="pro-kpi-card">',
        f'<div class="pro-kpi-head">{lucide_box("arrow-up-right", color="#F87171", bg="rgba(220,38,38,0.16)", size=18, box_size=36, radius=11)}'
        f'<div class="pro-kpi-meta"><span class="pro-kpi-label">Chi tiêu</span><span class="pro-kpi-amount" style="color:#F87171;">{money(summary["expense"])}</span></div></div>',
        f'<div class="pro-kpi-foot"><span class="pro-kpi-trend" style="color:#F87171;">{escape(exp_badge)}</span>{mini_sparkline_svg("#F87171", "expense")}</div>',
        '</div>',
        # Card 4: Có thể chi hôm nay
        '<div class="pro-kpi-card">',
        f'<div class="pro-kpi-head">{lucide_box("calendar-check", color="#34D399", bg="rgba(22,163,106,0.16)", size=18, box_size=36, radius=11)}'
        f'<div class="pro-kpi-meta"><span class="pro-kpi-label">Có thể chi hôm nay</span><span class="pro-kpi-amount">{money(daily_safe)}</span></div></div>',
        f'<div class="progress-track" style="height:5px;margin:4px 0;"><div class="progress-fill" style="width:{max(8.0, 100.0 - used_pct):.1f}%;background:#16A36A;"></div></div>',
        f'<div style="font-size:0.68rem;color:var(--text-muted);display:flex;justify-content:space-between;"><span>{escape(status_label)}</span><span>{compact_money(cap_amount)}</span></div>',
        '</div>',
        '</div>',
    ]
    _html_md("".join(kpi_parts))


def _render_tab_thongke(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
    summary: dict[str, int],
    statuses: list[Any],
    budgets: dict[str, Any],
    dark_mode: bool,
) -> None:
    year, month_num = map(int, month.split("-"))
    prev_m = shift_month(month, -1)
    next_m = shift_month(month, 1)
    chev_l = lucide_svg("chevron-left", 15, "#34D399")
    chev_r = lucide_svg("chevron-right", 15, "#34D399")

    _html_md(
        "".join([
            '<div class="monii-top-header">',
            '<div style="font-size:1.45rem;font-weight:900;color:var(--text-main);">Thống Kê Chi Tiêu</div>',
            '<div class="monii-month-pill">',
            f'<a href="?tab=thongke&month={prev_m}" target="_self" class="monii-month-arrow">{chev_l}</a>',
            f'<span class="monii-month-label">Thg {month_num}, {year}</span>',
            f'<a href="?tab=thongke&month={next_m}" target="_self" class="monii-month-arrow">{chev_r}</a>',
            '</div>',
            '</div>',
        ])
    )

    # 1. Lưới 2x2 KPI & Cảnh báo ngân sách
    _render_kpi_2x2(month, summary, budgets)
    _alerts(statuses)

    # 2. Thẻ Tổng quan Donut + Mascot UniBean ôm ví + Xuất Excel/PDF + 8 hạng mục tỷ trọng
    _charts(store, month, statuses, budgets, dark_mode)

    # 3. Theo dõi 3 khoản chi thiết yếu
    _html_md(
        f'<div class="section-heading">{lucide_svg("utensils", 18, "#34D399")}<span>Theo dõi 3 khoản chi thiết yếu</span></div>'
    )
    totals = store.category_totals(month)
    for category in ("Ăn uống", "Tiền trọ", "Đi lại"):
        icon, title, color, description = CATEGORY_META[category]
        spent = totals[category]
        status = budgets.get(category)
        share = spent / summary["expense"] * 100 if summary["expense"] else 0
        if status:
            level, badge, detail = _status_text(status)
            limit = money(status.limit)
            progress = min(100, status.ratio * 100)
            if level != "safe":
                color = "#F87171" if level == "danger" else "#FBBF24"
        else:
            level, badge, detail, limit, progress = (
                "neutral",
                "Chưa đặt hạn mức",
                "Đặt ngân sách ở tab Cá nhân để theo dõi",
                "Chưa thiết lập",
                0,
            )
        _html_md(
            "".join([
                '<div class="essential-card">',
                '<div class="essential-header">',
                f'<div class="essential-title">{icon}<span>{title}</span></div>',
                f'<span class="essential-pill pill-{level}">{badge}</span>',
                '</div>',
                f'<div class="essential-amount">{money(spent)}</div>',
                f'<div class="essential-limit">Định mức: <strong>{limit}</strong> · Chiếm <strong>{share:.1f}%</strong> tổng chi</div>',
                f'<div class="progress-track"><div class="progress-fill" style="width:{progress:.1f}%;background:{color}"></div></div>',
                f'<div style="font-size:0.78rem;font-weight:600;color:var(--text-main);">{detail}</div>',
                f'<div class="essential-desc">{description}</div>',
                '</div>',
            ])
        )


def _filter_records_by_period(
    all_records: list[Any],
    month: str,
    period_mode: str,
    ref_date: date,
    custom_range: tuple[date, date] | None = None,
) -> tuple[list[Any], str, int]:
    year, m_num = map(int, month.split("-"))
    if period_mode == "Ngày":
        d_iso = ref_date.isoformat()
        filtered = [r for r in all_records if r.date == d_iso]
        return filtered, f"Ngày {display_date(d_iso)}", 1
    if period_mode == "Tuần":
        start_w = ref_date - timedelta(days=ref_date.weekday())
        end_w = start_w + timedelta(days=6)
        s_iso, e_iso = start_w.isoformat(), end_w.isoformat()
        filtered = [r for r in all_records if s_iso <= r.date <= e_iso]
        return filtered, f"Tuần {display_date(s_iso)} – {display_date(e_iso)}", 7
    if period_mode == "Quý":
        q_idx = (m_num - 1) // 3 + 1
        start_m = (q_idx - 1) * 3 + 1
        end_m = start_m + 2
        s_ym = f"{year:04d}-{start_m:02d}"
        e_ym = f"{year:04d}-{end_m:02d}"
        filtered = [r for r in all_records if s_ym <= r.date[:7] <= e_ym]
        days = sum(monthrange(year, m)[1] for m in range(start_m, end_m + 1))
        return filtered, f"Quý {q_idx}/{year}", days
    if period_mode == "Năm":
        y_prefix = f"{year:04d}-"
        filtered = [r for r in all_records if r.date.startswith(y_prefix)]
        days = 366 if monthrange(year, 2)[1] == 29 else 365
        return filtered, f"Năm {year}", days
    if period_mode == "Khoảng tự chọn" and custom_range and len(custom_range) == 2:
        s_d, e_d = custom_range
        if s_d > e_d:
            s_d, e_d = e_d, s_d
        s_iso, e_iso = s_d.isoformat(), e_d.isoformat()
        filtered = [r for r in all_records if s_iso <= r.date <= e_iso]
        days = max(1, (e_d - s_d).days + 1)
        return filtered, f"{display_date(s_iso)} – {display_date(e_iso)}", days

    filtered = [r for r in all_records if r.date[:7] == month]
    return filtered, f"Tháng {m_num:02d}/{year}", monthrange(year, m_num)[1]


def _charts(
    store: ExpenseStore,
    month: str,
    statuses: list[Any],
    budgets: dict[str, Any],
    dark_mode: bool,
) -> None:
    year, number = map(int, month.split("-"))
    default_ref = date.today() if date.today().strftime("%Y-%m") == month else date(year, number, 1)

    stats_subtab = st.radio(
        "Chế độ xem thống kê",
        ["Tháng này", "Xu hướng"],
        horizontal=True,
        key="stats_subtab_radio",
        label_visibility="collapsed",
    )

    period_mode = st.selectbox(
        "Bộ lọc thời gian",
        ["Tháng", "Ngày", "Tuần", "Quý", "Năm", "Khoảng tự chọn"],
        key="stats_period_mode",
    )
    ref_date = default_ref
    custom_range = None
    if period_mode in ("Ngày", "Tuần"):
        ref_date = st.date_input("Chọn ngày mốc", value=default_ref, key="stats_ref_date")
    elif period_mode == "Khoảng tự chọn":
        start_default = date(year, number, 1)
        end_default = date(year, number, monthrange(year, number)[1])
        picked = st.date_input("Từ ngày – Đến ngày", value=(start_default, end_default), key="stats_custom_range")
        if isinstance(picked, (tuple, list)) and len(picked) == 2:
            custom_range = (picked[0], picked[1])

    all_txs = store.list_transactions()
    period_txs, period_label, day_span = _filter_records_by_period(
        all_txs, month, period_mode, ref_date, custom_range
    )

    p_income = sum(r.amount for r in period_txs if r.kind == "income")
    p_expense = sum(r.amount for r in period_txs if r.kind == "expense")
    p_balance = p_income - p_expense
    p_avg_daily = round(p_expense / max(1, day_span)) if p_expense > 0 else 0

    daily_exp_map: dict[str, int] = {}
    cat_exp_map: dict[str, int] = dict.fromkeys(EXPENSE_CATEGORIES, 0)
    for r in period_txs:
        if r.kind == "expense":
            daily_exp_map[r.date] = daily_exp_map.get(r.date, 0) + r.amount
            cat_exp_map[r.category] = cat_exp_map.get(r.category, 0) + r.amount

    if daily_exp_map:
        max_day_iso, max_day_amt = max(daily_exp_map.items(), key=lambda kv: kv[1])
        max_day_text = f"{display_date(max_day_iso)} ({money(max_day_amt)})"
    else:
        max_day_text = "—"

    eight_buckets = _compute_eight_category_breakdown(period_txs)
    nonzero_eight = [(c, a) for c, a in eight_buckets.items() if a > 0]
    if nonzero_eight:
        top_cat, top_cat_amt = max(nonzero_eight, key=lambda kv: kv[1])
        top_cat_text = f"{top_cat} ({compact_money(top_cat_amt)})"
    else:
        top_cat_text = "—"

    total_budget = budgets.get(TOTAL_BUDGET_CATEGORY)
    budget_rate_text = f"{total_budget.ratio * 100:.1f}%" if total_budget else "Chưa đặt"

    prev_m = shift_month(month, -1)
    prev_sum = store.summary(prev_m)
    diff_prev = p_expense - prev_sum["expense"]
    if prev_sum["expense"] > 0:
        pct_prev = diff_prev / prev_sum["expense"] * 100
        vs_prev_text = f"{pct_prev:+.1f}% so với {prev_m}"
    else:
        vs_prev_text = f"Tháng {prev_m}: 0 đ"

    extra_report_metrics = {
        "Kỳ báo cáo": period_label,
        "Trung bình chi mỗi ngày": money(p_avg_daily),
        "Ngày chi tiêu cao nhất": max_day_text,
        "Danh mục chi nhiều nhất": top_cat_text,
        "So với tháng trước": vs_prev_text,
        "Tỷ lệ sử dụng ngân sách": budget_rate_text,
    }
    period_summary_dict = {
        "income": p_income,
        "expense": p_expense,
        "balance": p_balance,
        "count": len(period_txs),
    }

    with st.container(border=True):
        ex_c1, ex_c2 = st.columns(2)
        with ex_c1:
            excel_bytes = export_excel_bytes(
                month,
                period_summary_dict,
                cat_exp_map,
                statuses,
                period_txs,
                extra_metrics=extra_report_metrics,
            )
            st.download_button(
                "📗 Xuất Excel",
                data=excel_bytes,
                file_name=f"THU_CHI_UTH_BaoCao_{month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
            )
        with ex_c2:
            pdf_bytes = export_pdf_bytes(
                month,
                period_summary_dict,
                cat_exp_map,
                statuses,
                period_txs,
                extra_metrics=extra_report_metrics,
            )
            st.download_button(
                "📄 Xuất PDF",
                data=pdf_bytes,
                file_name=f"THU_CHI_UTH_BaoCao_{month}.pdf",
                mime="application/pdf",
                width="stretch",
            )
        _render_excel_preview_expander(month, period_summary_dict, cat_exp_map, period_txs, key_prefix="thongke")

        ov_left, ov_right = st.columns([1.2, 1.0])
        with ov_left:
            if p_expense > 0:
                st.altair_chart(charts.category_donut(cat_exp_map, dark=dark_mode), width="stretch")
            else:
                _html_md(
                    '<div style="height:175px;display:flex;flex-direction:column;align-items:center;justify-content:center;'
                    'border:12px solid rgba(52,211,153,0.14);border-radius:50%;width:175px;margin:8px auto;">'
                    '<div style="font-size:0.68rem;font-weight:800;color:var(--text-muted);">TỔNG ĐÃ CHI TIÊU</div>'
                    '<div style="font-size:1.05rem;font-weight:900;color:var(--text-main);margin-top:4px;">0 đ</div>'
                    '<div style="font-size:0.68rem;color:var(--text-muted);margin-top:3px;">Chạm lát cắt</div>'
                    '</div>'
                )
        with ov_right:
            wallet_svg = mascot_wallet_svg(width=130, height=130)
            _html_md(
                "".join([
                    '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:6px;">',
                    wallet_svg,
                    '<div style="font-size:0.75rem;color:var(--text-muted);text-align:center;margin-top:4px;">',
                    f'Tổng chi: <strong style="color:#F87171;">{money(p_expense)}</strong><br/>',
                    f'Thu: <strong style="color:#4ADE80;">+{money(p_income)}</strong>',
                    '</div></div>',
                ])
            )

    # 2 Thẻ TB MỖI NGÀY & CHI NHIỀU NHẤT
    avg_display = money(p_avg_daily) if p_expense > 0 else "—"
    _html_md(
        "".join([
            '<div class="stats-pair-grid">',
            '<div class="stats-card-daily">',
            f'<div class="stats-mini-head" style="color:#F87171;display:flex;align-items:center;gap:5px;">{lucide_svg("trending-down", 15, "#F87171")}<span>TB MỖI NGÀY</span></div>',
            f'<div class="stats-mini-val">{escape(avg_display)}</div>',
            f'<div style="font-size:0.7rem;color:var(--text-muted);margin-top:3px;">{escape(vs_prev_text)}</div>',
            '</div>',
            '<div class="stats-card-topcat">',
            f'<div class="stats-mini-head" style="color:#4ADE80;display:flex;align-items:center;gap:5px;">{lucide_svg("award", 15, "#4ADE80")}<span>CHI NHIỀU NHẤT</span></div>',
            f'<div class="stats-mini-val">{escape(top_cat_text)}</div>',
            f'<div style="font-size:0.7rem;color:var(--text-muted);margin-top:3px;">Ngân sách: {escape(budget_rate_text)}</div>',
            '</div>',
            '</div>',
        ])
    )

    # 8 Hạng mục tỷ trọng
    _html_md(
        "".join([
            '<div class="cal-section-bar">',
            f'<div class="cal-section-title">{lucide_svg("trending-down", 15, "#34D399")}<span>TỶ TRỌNG HẠNG MỤC CHI TIÊU</span>{lucide_svg("leaf", 14, "#34D399")}</div>',
            '</div>',
        ])
    )
    cat_search = st.text_input(
        "Tìm kiếm hạng mục",
        placeholder="Tìm kiếm hạng mục...",
        key="stats_cat_search",
        label_visibility="collapsed",
    )

    cat_rows_html: list[str] = []
    kw_cat = cat_search.strip().casefold()
    for cat_name, icon, hex_color, bg_rgba in EIGHT_DISPLAY_CATEGORIES:
        if kw_cat and kw_cat not in cat_name.casefold():
            continue
        amt = eight_buckets.get(cat_name, 0)
        pct = (amt / p_expense * 100) if p_expense > 0 else 0.0
        pct_str = f"{pct:.0f}%" if pct == int(pct) else f"{pct:.1f}%"
        cat_rows_html.append(
            f'<div class="cat-row-item">'
            f'<div class="cat-row-top">'
            f'<div class="cat-row-left"><div class="cat-icon-box" style="background:{bg_rgba};color:{hex_color};">{icon}</div>'
            f'<div class="cat-row-name">{escape(cat_name)}</div></div>'
            f'<div class="cat-row-right"><div class="cat-row-amount">{money(amt)}</div>'
            f'<div class="cat-pct-pill" style="background:{bg_rgba};color:{hex_color};">{pct_str}</div></div>'
            f'</div>'
            f'<div class="progress-track" style="height:5px;margin:0;"><div class="progress-fill" style="width:{min(100.0, pct):.1f}%;background:{hex_color};"></div></div>'
            f'</div>'
        )
    if cat_rows_html:
        _html_md(f'<div class="cat-list-card">{"".join(cat_rows_html)}</div>')

    count = min(6, (year - 1) * 12 + number)
    monthly = store.monthly_totals(month, count=count)
    months = [row["month"] for row in monthly]
    records_6m = [record for record in all_txs if months[0] <= record.date[:7] <= month]

    if stats_subtab == "Xu hướng" or records_6m:
        _html_md(f'<div class="section-heading">{lucide_svg("trending-up", 18, "#34D399")}<span>Xu hướng Thu Chi 6 tháng</span></div>')
        st.altair_chart(charts.monthly_income_expense(monthly, dark=dark_mode), width="stretch")
        st.altair_chart(charts.financial_trend(monthly, dark=dark_mode), width="stretch")
        st.altair_chart(charts.daily_expenses(records_6m, month, dark=dark_mode), width="stretch")


# =============================================================================
# MÀN HÌNH PHỤ 1: QUÉT HÓA ĐƠN AI (?tab=ocr)
# =============================================================================
def _render_inline_api_gateway(
    store: ExpenseStore | None = None,
    month: str | None = None,
    key_prefix: str = "main",
) -> None:
    ai_st = check_api_status()
    tess_st = check_tesseract_status()
    exp_title = (
        f"🔌 Cổng AI API: Đã kết nối {ai_st.provider.upper()} ({ai_st.model})"
        if ai_st.configured
        else "🔌 Đấu Nối & Kiểm Tra API AI (Google Gemini / OpenAI / Tesseract)"
    )
    with st.expander(exp_title, expanded=not ai_st.configured and key_prefix == "settings"):
        st.caption(
            "Điền `GEMINI_API_KEY` để kích hoạt Quét ảnh hóa đơn (Gemini Vision + JSON 12 trường), "
            "Giọng nói (Gemini STT) và Cố vấn tài chính AI. Khóa được lưu vào `.env` cục bộ."
        )
        with st.form(f"api_gateway_form_{key_prefix}", enter_to_submit=False):
            gem_key_in = st.text_input(
                "Google Gemini API Key (GEMINI_API_KEY)",
                value="",
                type="password",
                placeholder=f"Đang dùng: {ai_st.masked_key}" if (ai_st.configured and ai_st.provider == "gemini") else "AIzaSy...",
            )
            curr_gem_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"
            model_opts = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
            if curr_gem_model not in model_opts:
                model_opts.insert(0, curr_gem_model)
            gem_model_in = st.selectbox("Gemini Model", model_opts, index=model_opts.index(curr_gem_model))
            oai_key_in = st.text_input(
                "OpenAI API Key (Tùy chọn - OPENAI_API_KEY)",
                value="",
                type="password",
                placeholder="sk-...",
            )
            tess_cmd_in = st.text_input(
                "Đường dẫn Tesseract OCR (TESSERACT_CMD)",
                value=tess_st.binary_path,
            )
            if st.form_submit_button("⚡ Lưu Cấu Hình & Đấu Nối API", type="primary", width="stretch"):
                new_status = save_ai_api_config(
                    gemini_api_key=gem_key_in,
                    gemini_model=gem_model_in,
                    openai_api_key=oai_key_in,
                    tesseract_cmd=tess_cmd_in,
                )
                clear_ocr_and_gemini_cache()
                st.session_state["api_gateway_diag"] = test_all_ai_pipelines(store, month)
                if new_status.configured:
                    _notice(f"Đã đấu nối thành công {new_status.provider.upper()} ({new_status.model})!")
                else:
                    st.warning("Chưa nhập API Key mới.")

        t_c1, t_c2 = st.columns(2)
        with t_c1:
            if st.button("🧪 Kiểm tra 3 luồng AI", width="stretch", key=f"btn_test_3_flows_{key_prefix}"):
                st.session_state["api_gateway_diag"] = test_all_ai_pipelines(store, month)
        with t_c2:
            if st.button("🔗 Ping Gemini API", width="stretch", key=f"btn_ping_gem_{key_prefix}"):
                ok_ping, msg_ping = test_gemini_connection()
                st.session_state["api_ping_msg"] = (ok_ping, msg_ping)

        if ping_res := st.session_state.get("api_ping_msg"):
            ok_p, msg_p = ping_res
            if ok_p:
                st.success(msg_p)
            else:
                st.warning(msg_p)

        if diag := st.session_state.get("api_gateway_diag"):
            ocr_p = diag["ocr_pipeline"]
            v_p = diag["voice_pipeline"]
            a_p = diag["analysis_pipeline"]
            st.info(
                f"1. Quét ảnh OCR: {'Sẵn sàng' if ocr_p['ok'] else 'Kiểm tra'} ({ocr_p['source']}) | "
                f"2. Giọng nói: {'Sẵn sàng' if v_p['ok'] else 'Kiểm tra'} ({v_p['source']}) | "
                f"3. Phân tích: {'Sẵn sàng' if a_p['ok'] else 'Kiểm tra'} ({a_p['source']})"
            )


def _render_receipt_scanner_studio(store: ExpenseStore, ext_store: ExtensionsStore) -> None:
    _html_md(
        "".join([
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">',
            f'<a href="?tab=lich" target="_self" class="cal-photo-pill">{lucide_svg("chevron-left", 15, "#34D399")}<span>Quay lại Lịch</span></a>',
            f'<div class="section-heading" style="margin:0;">{lucide_svg("camera", 18, "#34D399")}<span>Quét Hóa Đơn AI</span></div>',
            '</div>',
        ])
    )
    _render_inline_api_gateway(store, st.session_state.get("report_month"), key_prefix="ocr")

    tess_status = check_tesseract_status()
    ai_status = check_api_status("gemini")

    if tess_status.available and tess_status.has_vie:
        st.success(f"Tesseract OCR: Sẵn sàng ({tess_status.version}, vie+eng)")
    elif ai_status.configured:
        st.info(f"Gemini Vision ({ai_status.model}) đã sẵn sàng đọc trực tiếp ảnh hóa đơn.")
    else:
        st.warning("Chưa cài Tesseract OCR hoặc GEMINI_API_KEY. Bạn vẫn có thể nạp văn bản OCR mẫu bên dưới.")

    # Tách riêng 2 nút Kiểm tra Tesseract & Kiểm tra Gemini API thành 1 hàng riêng st.columns(2) không bị cắt chữ
    chk1, chk2 = st.columns(2)
    with chk1:
        if st.button("🔍 Kiểm tra Tesseract", width="stretch", key="btn_check_tess"):
            st.session_state["ocr_diag_notice"] = tess_status.message
    with chk2:
        if st.button("🔗 Kiểm tra Gemini API", width="stretch", key="btn_check_gemini"):
            ok_g, msg_g = test_gemini_connection()
            st.session_state["ocr_diag_notice"] = msg_g

    if diag_msg := st.session_state.pop("ocr_diag_notice", None):
        st.info(diag_msg)

    image_bytes: bytes | None = None
    image_mime = "image/jpeg"
    image_filename = ""

    with st.container(border=True):
        st.markdown("##### 1. Tải ảnh hoặc Chụp hóa đơn")
        input_mode = st.radio(
            "Nguồn hóa đơn",
            [
                "📤 Tải ảnh hóa đơn (JPG/PNG)",
                "📷 Chụp ảnh bằng Camera",
                "📄 Văn bản OCR thủ công / Hóa đơn mẫu",
            ],
            key="ocr_input_mode",
        )

        # Xếp dọc 2 ô Xoay ảnh đúng chiều và Tiền xử lý OpenCV (mỗi ô 1 hàng full width để không bị cắt chữ)
        rotate_deg = st.selectbox(
            "🔄 Xoay ảnh đúng chiều",
            [0, 90, 180, 270],
            format_func=lambda d: "0° (Tự động EXIF)" if d == 0 else f"Xoay {d}° theo chiều kim đồng hồ",
            key="ocr_rotate_deg",
        )
        preprocess_mode = st.selectbox(
            "✨ Tiền xử lý OpenCV",
            ["Bật (Grayscale + Khử nhiễu + CLAHE)", "Tắt (Giữ ảnh gốc)"],
            key="ocr_preprocess_select",
        )
        use_preprocess = preprocess_mode.startswith("Bật")

        if input_mode == "📷 Chụp ảnh bằng Camera":
            cam_photo = st.camera_input("Chụp hóa đơn")
            if cam_photo is not None:
                image_bytes = cam_photo.getvalue()
                image_mime = cam_photo.type or "image/jpeg"
                image_filename = "camera_capture.jpg"
        elif input_mode == "📤 Tải ảnh hóa đơn (JPG/PNG)":
            up_photo = st.file_uploader(
                "Chọn ảnh hóa đơn (JPG, JPEG, PNG — tối đa 10 MB)",
                type=["jpg", "jpeg", "png"],
                key="ocr_file_uploader",
            )
            if up_photo is not None:
                image_bytes = up_photo.getvalue()
                image_mime = up_photo.type or "image/jpeg"
                image_filename = up_photo.name or "uploaded.jpg"
        else:
            if st.button("📋 Nạp mẫu hóa đơn Siêu Thị Mini", key="load_sample_receipt_btn", width="stretch"):
                st.session_state["ocr_raw_text_input"] = SAMPLE_RECEIPT_TEXT
            st.text_area(
                "Văn bản OCR hóa đơn",
                height=140,
                placeholder="Dán văn bản OCR hóa đơn hoặc bấm nút nạp mẫu ở trên...",
                key="ocr_raw_text_input",
            )

        enhanced_preview_bytes: bytes | None = None
        if image_bytes:
            val_res = validate_receipt_image(image_bytes, filename=image_filename)
            if val_res.valid:
                try:
                    enhanced_preview_bytes = enhance_receipt_image_color(image_bytes, rotate_degrees=int(rotate_deg))
                except Exception:
                    enhanced_preview_bytes = None
            prev_c1, prev_c2 = st.columns(2)
            with prev_c1:
                st.image(
                    image_bytes,
                    caption=f"Ảnh gốc · {val_res.format} · {val_res.width}x{val_res.height}px · {val_res.size_bytes // 1024} KB",
                    width="stretch",
                )
            with prev_c2:
                if enhanced_preview_bytes:
                    st.image(
                        enhanced_preview_bytes,
                        caption="Ảnh đã tăng nét tự động (OpenCV Upscale + Unsharp Mask)",
                        width="stretch",
                    )
            if not val_res.valid:
                st.error(val_res.error_message)
            elif val_res.is_blurry:
                for w in val_res.warnings:
                    st.warning(w)

        consent_choice = st.radio(
            "Chế độ xử lý & Đồng ý bảo mật",
            [
                "🌟 Siêu chuẩn: Gemini Vision nhìn ảnh đã làm nét + đối chiếu Tesseract OCR (Khuyên dùng)",
                "Tesseract OCR + Gemini API phân tích JSON (Chỉ gửi văn bản OCR)",
                "Chỉ xử lý OCR cục bộ 100% trên máy (Không gửi dữ liệu ra ngoài)",
            ],
            key="ocr_privacy_consent_mode",
        )
        allow_gemini_text = not consent_choice.startswith("Chỉ xử lý")
        allow_gemini_vision = consent_choice.startswith("🌟")

        if st.button("🔍 Bắt đầu Nhận diện Hóa đơn", type="primary", width="stretch", key="run_ocr_btn"):
            progress_bar = st.progress(0, text="Đang khởi tạo luồng nhận diện...")
            raw_ocr_text = ""
            ocr_warnings: list[str] = []
            ocr_err_msg = ""
            proc_preview: bytes | None = None

            if input_mode == "📄 Văn bản OCR thủ công / Hóa đơn mẫu":
                progress_bar.progress(45, text="Đang đọc văn bản OCR...")
                raw_ocr_text = (st.session_state.get("ocr_raw_text_input") or "").strip()
                if not raw_ocr_text:
                    ocr_err_msg = "Vui lòng nhập hoặc nạp văn bản OCR hóa đơn trước khi phân tích."
            elif not image_bytes:
                ocr_err_msg = "Vui lòng tải ảnh JPG/PNG hoặc chụp ảnh hóa đơn trước khi nhấn Nhận diện."
            else:
                progress_bar.progress(35, text="Làm nét ảnh OpenCV & Chạy Tesseract OCR (vie+eng)...")
                tess_res = run_tesseract_ocr(
                    image_bytes,
                    filename=image_filename,
                    rotate_degrees=int(rotate_deg),
                    preprocess=use_preprocess,
                    lang="vie+eng",
                )
                proc_preview = tess_res.preprocessed_image
                ocr_warnings.extend(tess_res.warnings)
                if tess_res.success:
                    raw_ocr_text = tess_res.raw_text
                else:
                    ocr_err_msg = tess_res.message

            progress_bar.progress(80, text="Phân tích đa phương thức Gemini Vision + Pydantic Schema...")
            should_use_vision = bool(image_bytes) and (
                allow_gemini_vision
                or (allow_gemini_text and len(raw_ocr_text.strip()) < 15 and check_api_status().configured)
            )
            if should_use_vision and image_bytes:
                vision_payload = enhanced_preview_bytes or image_bytes
                vision_mime = "image/jpeg" if enhanced_preview_bytes else image_mime
                gem_res = analyze_receipt_image_with_gemini(
                    vision_payload,
                    mime_type=vision_mime,
                    user_consent=True,
                    raw_ocr_text=raw_ocr_text,
                    extra_warnings=ocr_warnings,
                )
                if gem_res.raw_ocr_text and not raw_ocr_text:
                    raw_ocr_text = gem_res.raw_ocr_text
                    ocr_err_msg = ""
            elif raw_ocr_text:
                gem_res = analyze_ocr_text_with_gemini(
                    raw_ocr_text,
                    user_consent=allow_gemini_text,
                    extra_warnings=ocr_warnings,
                )
            else:
                empty_schema = GeminiReceiptSchema(
                    confidence=0,
                    warnings=[*ocr_warnings, ocr_err_msg or "Không có dữ liệu OCR để phân tích."],
                )
                gem_res = None

            progress_bar.progress(100, text="Hoàn tất nhận diện!")
            schema_obj = gem_res.schema_data if gem_res else empty_schema
            st.session_state["ocr_manual_edit_text"] = raw_ocr_text
            st.session_state["ocr_show_editor_form"] = False
            st.session_state["ocr_draft"] = {
                "readable": schema_obj.total_amount is not None and schema_obj.total_amount > 0,
                "schema": schema_obj.model_dump(),
                "source": gem_res.source if gem_res else "ocr_error",
                "ocr_error": ocr_err_msg,
                "gemini_message": gem_res.message if gem_res else ocr_err_msg,
                "raw_text": raw_ocr_text,
                "image_bytes": image_bytes,
                "preprocessed_bytes": proc_preview,
                "image_mime": image_mime,
                "store_name": schema_obj.merchant_name or "",
                "purchase_date": schema_obj.transaction_date or "",
                "purchase_time": "",
                "items": [it.model_dump() for it in schema_obj.items],
                "discount": 0,
                "total_amount": schema_obj.total_amount or 0,
                "subtotal": schema_obj.subtotal,
                "tax_amount": schema_obj.tax_amount,
                "payment_method": schema_obj.payment_method or "",
                "suggested_category": schema_obj.suggested_category or "Khác",
                "description": schema_obj.description or "",
                "confidence": schema_obj.confidence,
                "warnings": list(schema_obj.warnings),
                "message": gem_res.message if gem_res else ocr_err_msg,
            }

    draft = st.session_state.get("ocr_draft")
    if draft:
        with st.container(border=True):
            st.markdown("##### 2. Kết quả Nhận diện & Xác nhận")
            if draft.get("ocr_error"):
                st.warning(draft["ocr_error"])
            if draft.get("gemini_message"):
                if draft.get("readable"):
                    st.success(draft["gemini_message"])
                else:
                    st.info(draft["gemini_message"])

            merchant_disp = escape(draft.get("store_name") or "Chưa xác định")
            date_raw = draft.get("purchase_date")
            date_disp = display_date(date_raw) if date_raw else "Chưa xác định"
            tot_raw = draft.get("total_amount")
            tot_disp = money(int(tot_raw)) if (tot_raw and int(tot_raw) > 0) else "Chưa xác định"
            cat_disp = escape(draft.get("suggested_category") or "Khác")
            conf_val = int(draft.get("confidence") or 0)

            _html_md(
                "".join([
                    '<div class="ocr-result-card">',
                    '<div class="day-inspector-head">',
                    f'<div class="day-inspector-date">{lucide_svg("shield-check", 17, "#34D399")}<span>Kết quả nhận diện</span></div>',
                    f'<span class="essential-pill pill-safe">Tin cậy: {conf_val}%</span>',
                    '</div>',
                    '<div class="ocr-kv-grid">',
                    f'<div class="ocr-kv-item"><span>Cửa hàng</span><strong>{merchant_disp}</strong></div>',
                    f'<div class="ocr-kv-item"><span>Ngày mua</span><strong>{escape(date_disp)}</strong></div>',
                    f'<div class="ocr-kv-item"><span>Tổng thanh toán</span><strong style="color:#4ADE80;">{escape(tot_disp)}</strong></div>',
                    f'<div class="ocr-kv-item"><span>Danh mục</span><strong>{cat_disp}</strong></div>',
                    '</div>',
                    '</div>',
                ])
            )

            can_direct_save = bool(draft.get("purchase_date")) and int(draft.get("total_amount") or 0) > 0
            act1, act2, act3 = st.columns(3)
            with act1:
                if st.button("✎ Chỉnh sửa", width="stretch", key="ocr_toggle_edit_btn"):
                    st.session_state["ocr_show_editor_form"] = not st.session_state.get("ocr_show_editor_form", False)
                    st.rerun()
            with act2:
                if st.button("✅ Xác nhận lưu", type="primary", width="stretch", key="ocr_direct_save_btn", disabled=not can_direct_save):
                    r_store = (draft.get("store_name") or "Cửa hàng").strip()
                    r_date_iso = draft["purchase_date"]
                    r_tot = int(draft["total_amount"])
                    storage_cat = map_gemini_category_to_storage(draft.get("suggested_category"))
                    r_desc = (draft.get("description") or f"Hóa đơn {r_store}").strip()[:200]
                    tx_id = store.add_transaction(r_date_iso, "expense", storage_cat, r_tot, r_desc)
                    ext_store.add_receipt(
                        transaction_id=tx_id,
                        store_name=r_store,
                        purchase_date=r_date_iso,
                        purchase_time="",
                        items=draft.get("items") or [],
                        discount=0,
                        total_amount=r_tot,
                        payment_method=draft.get("payment_method") or "Tiền mặt",
                        suggested_category=storage_cat,
                        image_bytes=draft.get("image_bytes"),
                        image_mime=draft.get("image_mime") or "image/jpeg",
                        raw_text=draft.get("raw_text") or "",
                    )
                    clear_ocr_and_gemini_cache()
                    st.session_state.pop("ocr_draft", None)
                    st.session_state["pending_month"] = r_date_iso[:7]
                    st.session_state["selected_calendar_date"] = r_date_iso
                    _notice(f"Đã lưu giao dịch #{tx_id} kèm hóa đơn '{r_store}' ({money(r_tot)}).")
            with act3:
                if st.button("✖ Hủy", width="stretch", key="ocr_cancel_top_btn"):
                    clear_ocr_and_gemini_cache()
                    st.session_state.pop("ocr_draft", None)
                    st.rerun()

            if st.session_state.get("ocr_show_editor_form") or not can_direct_save:
                with st.form("confirm_receipt_form", enter_to_submit=False):
                    r_store = st.text_input("Tên cửa hàng", value=draft.get("store_name") or "")
                    try:
                        d_val = date.fromisoformat(draft["purchase_date"]) if draft.get("purchase_date") else date.today()
                    except ValueError:
                        d_val = date.today()
                    r_date = st.date_input("Ngày giao dịch", value=d_val)
                    r_total = st.number_input("Tổng thanh toán (VNĐ)", min_value=0, max_value=MAX_AMOUNT, value=int(draft.get("total_amount") or 0), step=1_000, format="%d")
                    mapped_store_cat = map_gemini_category_to_storage(draft.get("suggested_category"))
                    r_cat = st.selectbox("Danh mục", EXPENSE_CATEGORIES, index=EXPENSE_CATEGORIES.index(mapped_store_cat), format_func=_category_label)
                    r_note = st.text_input("Ghi chú", value=(draft.get("description") or f"Hóa đơn {r_store}")[:200], max_chars=200)
                    if st.form_submit_button("✅ Lưu hóa đơn đã chỉnh sửa", type="primary", width="stretch"):
                        if int(r_total) <= 0:
                            st.error("Tổng tiền phải lớn hơn 0 VNĐ.")
                        else:
                            clean_store = r_store.strip() or "Cửa hàng"
                            tx_id = store.add_transaction(r_date.isoformat(), "expense", r_cat, int(r_total), r_note or f"Hóa đơn {clean_store}")
                            ext_store.add_receipt(
                                transaction_id=tx_id,
                                store_name=clean_store,
                                purchase_date=r_date.isoformat(),
                                purchase_time="",
                                items=draft.get("items") or [],
                                discount=0,
                                total_amount=int(r_total),
                                payment_method=draft.get("payment_method") or "Tiền mặt",
                                suggested_category=r_cat,
                                image_bytes=draft.get("image_bytes"),
                                image_mime=draft.get("image_mime") or "image/jpeg",
                                raw_text=draft.get("raw_text") or "",
                            )
                            clear_ocr_and_gemini_cache()
                            st.session_state.pop("ocr_draft", None)
                            _notice(f"Đã lưu hóa đơn '{clean_store}' ({money(int(r_total))}).")


# =============================================================================
# MÀN HÌNH PHỤ 2: NHẬP BẰNG GIỌNG NÓI (?tab=voice)
# =============================================================================
def _render_voice_assistant_studio(store: ExpenseStore, ext_store: ExtensionsStore) -> None:
    _html_md(
        "".join([
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">',
            f'<a href="?tab=lich" target="_self" class="cal-photo-pill">{lucide_svg("chevron-left", 15, "#34D399")}<span>Quay lại Lịch</span></a>',
            f'<div class="section-heading" style="margin:0;">{lucide_svg("mic", 18, "#34D399")}<span>Nhập Bằng Giọng Nói</span></div>',
            '</div>',
        ])
    )
    v_draft = st.session_state.get("voice_parsed_draft")
    current_spoken = (
        v_draft["transcript"]
        if v_draft
        else st.session_state.get("voice_transcript_input", "").strip()
    )
    spoken_display = (
        escape(current_spoken)
        if current_spoken
        else 'Ví dụ: "Ăn trưa phở bò 45k", "Đổ xăng năm chục", "Mua giày hai xị rưỡi"'
    )
    vol_svg = lucide_svg("volume-2", 15, "#34D399")

    with st.container(border=True):
        if hasattr(st, "audio_input"):
            audio_val = st.audio_input(
                "🎙️ Bấm nút Micro màu xanh bên dưới để ghi âm (bấm lại để dừng — tự động nhận diện tiếng Việt)",
                key="voice_native_audio_input",
            )
            if audio_val is not None:
                raw_audio = audio_val.getvalue()
                audio_hash = hashlib.sha256(raw_audio).hexdigest()
                if st.session_state.get("last_voice_audio_hash") != audio_hash:
                    st.session_state["last_voice_audio_hash"] = audio_hash
                    if check_api_status().configured:
                        with st.spinner("Đang nhận diện giọng nói tiếng Việt bằng Gemini AI…"):
                            ok, text_or_err = transcribe_audio_bytes(raw_audio, audio_val.type or "audio/wav")
                        if ok:
                            st.session_state["voice_transcript_input"] = text_or_err
                            st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense(text_or_err, use_ai=True)
                            st.rerun()
                        else:
                            st.warning(text_or_err)
                    else:
                        st.warning("Chưa cấu hình GEMINI_API_KEY để nhận diện giọng nói. Vào Cá nhân → Cổng đấu nối AI API để cài.")
                if st.button("🔊 Nhận diện lại đoạn ghi âm vừa rồi", width="stretch"):
                    with st.spinner("Đang nhận diện lại bằng Gemini AI…"):
                        ok, text_or_err = transcribe_audio_bytes(raw_audio, audio_val.type or "audio/wav")
                    if ok:
                        st.session_state["voice_transcript_input"] = text_or_err
                        st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense(text_or_err, use_ai=True)
                        st.rerun()
                    else:
                        st.warning(text_or_err)

        _html_md(
            "".join([
                '<div class="voice-transcript-box" style="margin:10px 0 12px 0;">',
                f'<div class="voice-transcript-label" style="display:flex;align-items:center;gap:5px;">{vol_svg}<span>LỜI BẠN NÓI:</span></div>',
                f'<div class="voice-transcript-content">{spoken_display}</div>',
                '</div>',
            ])
        )

        st.caption("Chạm chọn nhanh câu mẫu hoặc nhập trực tiếp:")
        s_c1, s_c2 = st.columns(2)
        with s_c1:
            if st.button('"Ăn trưa phở bò 45k"', width="stretch"):
                st.session_state["voice_transcript_input"] = "Ăn trưa phở bò 45k"
                st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense("Ăn trưa phở bò 45k", use_ai=True)
                st.rerun()
        with s_c2:
            if st.button('"Đổ xăng 70 ngàn"', width="stretch"):
                st.session_state["voice_transcript_input"] = "Đổ xăng 70 ngàn"
                st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense("Đổ xăng 70 ngàn", use_ai=True)
                st.rerun()

        transcript_text = st.text_input(
            "Lời bạn nói",
            placeholder='Ví dụ: "Ăn trưa phở bò 45k", "Đổ xăng 70 ngàn"...',
            key="voice_transcript_input",
        )
        if st.button("🧠 Phân tích câu nói", type="primary", width="stretch"):
            try:
                st.session_state["voice_parsed_draft"] = parse_vietnamese_voice_expense(transcript_text, use_ai=True)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    if v_draft:
        with st.container(border=True):
            st.markdown(
                f"**Kết quả:** `{v_draft['kind_label']}` · **{money(int(v_draft['amount']))}** · "
                f"Danh mục: **{v_draft['category_display']}** · Ngày: **{v_draft['date_display']}** · "
                f"Ghi chú: *{escape(v_draft['note'])}*"
            )
            act_c1, act_c2 = st.columns(2)
            with act_c1:
                if st.button("✎ Sửa chi tiết", width="stretch", key="voice_toggle_edit_btn"):
                    st.session_state["voice_show_detail_editor"] = not st.session_state.get("voice_show_detail_editor", False)
                    st.rerun()
            with act_c2:
                if st.button("✓ Lưu chi tiêu", type="primary", width="stretch", key="voice_direct_confirm_btn", disabled=not v_draft.get("valid_amount")):
                    tx_id = store.add_transaction(
                        v_draft["date"],
                        v_draft["kind"],
                        v_draft["category"],
                        int(v_draft["amount"]),
                        v_draft["note"],
                    )
                    saved_amt = int(v_draft["amount"])
                    saved_date = v_draft["date"]
                    st.session_state.pop("voice_parsed_draft", None)
                    st.session_state["pending_month"] = saved_date[:7]
                    st.session_state["selected_calendar_date"] = saved_date
                    _notice(f"Đã lưu giao dịch #{tx_id} từ giọng nói ({money(saved_amt)}).")

            if st.session_state.get("voice_show_detail_editor") or not v_draft.get("valid_amount"):
                with st.form("voice_confirm_form", enter_to_submit=False):
                    v_amt = st.number_input("Số tiền (VNĐ)", min_value=0, max_value=MAX_AMOUNT, value=int(v_draft.get("amount") or 0), step=5_000, format="%d")
                    v_cats = EXPENSE_CATEGORIES if v_draft["kind"] == "expense" else INCOME_CATEGORIES
                    v_cat = st.selectbox("Danh mục", v_cats, index=v_cats.index(v_draft["category"]) if v_draft["category"] in v_cats else 0, format_func=_category_label)
                    v_date = st.date_input("Ngày giao dịch", value=date.fromisoformat(v_draft["date"]))
                    v_note = st.text_input("Ghi chú", value=v_draft["note"], max_chars=200)
                    if st.form_submit_button("✅ Lưu chi tiêu đã sửa", type="primary", width="stretch"):
                        tx_id = store.add_transaction(v_date.isoformat(), v_draft["kind"], v_cat, int(v_amt), v_note)
                        st.session_state.pop("voice_parsed_draft", None)
                        _notice(f"Đã lưu giao dịch #{tx_id} ({money(int(v_amt))}).")


# =============================================================================
# TAB 4: CÁ NHÂN, TRỢ LÝ AI, CẤU HÌNH API & SAO LƯU (?tab=canhan)
# =============================================================================
def _render_ai_financial_assistant_studio(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
) -> None:
    _html_md(f'<div class="section-heading">{lucide_svg("bot", 18, "#34D399")}<span>Trợ Lý AI Phân Tích Chi Tiêu — {month}</span></div>')
    analysis = build_financial_analysis(store, month)
    s = analysis["summary"]
    ai_st = check_api_status()

    with st.container(border=True):
        st.markdown(
            f"- **Thu nhập:** **{money(s['income'])}** · **Chi tiêu:** **{money(s['expense'])}** · **Số dư:** **{money(s['balance'])}**\n"
            f"- **Chi nhiều nhất:** **{analysis['top_category']}** ({money(analysis['top_category_amount'])} — {analysis['top_category_share']:.1f}%)\n"
            f"- **Dự báo:** {analysis['forecast_note']}"
        )
        preset_questions = [
            "Tháng này tôi tiêu bao nhiêu?",
            "Tôi tiêu nhiều nhất vào danh mục nào?",
            "Tháng này tôi đã vượt ngân sách chưa?",
            "Tôi nên tiết kiệm bao nhiêu?",
        ]
        q_cols = st.columns(2)
        for idx, pq in enumerate(preset_questions):
            with q_cols[idx % 2]:
                if st.button(pq, key=f"preset_q_{idx}", width="stretch"):
                    res = answer_financial_question(store, month, pq, use_ai=True)
                    st.session_state["ai_last_qa"] = res
                    ext_store.log_ai_interaction("assistant", pq, res["answer"])

        custom_q = st.text_input(
            "Đặt câu hỏi cho Trợ lý AI",
            placeholder="VD: Danh mục ăn uống tháng này chiếm bao nhiêu %?",
            key="ai_custom_question_input",
        )
        b_ask, b_deep = st.columns(2)
        with b_ask:
            if st.button("🚀 Hỏi AI Assistant", type="primary", width="stretch"):
                if custom_q.strip():
                    res = answer_financial_question(store, month, custom_q.strip(), use_ai=True)
                    st.session_state["ai_last_qa"] = res
                    ext_store.log_ai_interaction("assistant", custom_q.strip(), res["answer"])
        with b_deep:
            if st.button("✨ Kế hoạch tiết kiệm 3 bước", width="stretch", key=f"btn_deep_ai_review_{month}"):
                deep_rev = generate_ai_deep_financial_review(store, month)
                st.session_state[f"ai_deep_review_{month}"] = deep_rev

        if last_qa := st.session_state.get("ai_last_qa"):
            st.success(last_qa["answer"])

        if deep_rev := st.session_state.get(f"ai_deep_review_{month}"):
            st.info(f"{deep_rev['overview']}\n\n" + "\n".join(f"{i}. {step}" for i, step in enumerate(deep_rev["action_plan"], 1)))


def _render_tab_canhan(
    db_path: str | Path,
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
    base_data_dir: Path | None = None,
) -> None:
    curr_rem = ext_store.get_setting("reminder_time", "20:00")
    _html_md(
        '<div style="padding:4px 2px 6px 2px;">'
        '<div style="font-size:1.5rem;font-weight:900;color:var(--text-main);">Cá Nhân &amp; Cài Đặt</div>'
        '<div style="font-size:0.8rem;color:var(--text-muted);">Tài khoản dữ liệu (.db), Tìm kiếm, Trợ lý AI, Cấu hình API &amp; Sao lưu</div>'
        '</div>'
    )

    # 0. Quản lý đa tài khoản (mỗi file .db là 1 tài khoản độc lập)
    resolved_base = base_data_dir or _resolve_base_data_dir(db_path)
    _render_account_manager(
        db_path,
        resolved_base,
        store,
        ext_store,
    )

    # 0b. AI Làm sạch & Chuẩn hóa dữ liệu thô (CSV/Excel/Văn bản)
    _render_ai_data_cleaner_studio(resolved_base, store, ext_store)

    # 0c. Xem trực tiếp bảng SQLite (.db) trên Web
    _render_sqlite_database_viewer(db_path, store, ext_store)

    # 1. Tìm kiếm nhanh giao dịch
    with st.container(border=True):
        _html_md(f'<div class="section-heading" style="margin-top:0;">{lucide_svg("search", 17, "#34D399")}<span>Tìm kiếm giao dịch</span></div>')
        q_kw = st.text_input("Từ khóa tìm kiếm", placeholder="Nhập ghi chú hoặc danh mục (VD: cà phê, xăng, trọ)...", key="personal_search_kw", label_visibility="collapsed")
        if q_kw and q_kw.strip():
            found = store.list_transactions(month=month, search=q_kw.strip())
            st.caption(f"Tìm thấy {len(found)} giao dịch trong tháng {month}:")
            for mtx in found[:8]:
                m_color = "#4ADE80" if mtx.kind == "income" else "#F87171"
                m_sign = "+" if mtx.kind == "income" else "-"
                _html_md(
                    f'<div class="monii-tx-card"><div class="day-tx-left">{category_lucide_box(mtx.category, mtx.note, box_size=34)}'
                    f'<div><div class="day-tx-title">{escape(mtx.note or mtx.category)}</div>'
                    f'<div class="day-tx-cat">#{mtx.id} · {display_date(mtx.date)} · {escape(mtx.category)}</div></div></div>'
                    f'<div class="day-tx-amount" style="color:{m_color};">{m_sign}{money(mtx.amount)}</div></div>'
                )

    # 2. Trợ lý AI
    _render_ai_financial_assistant_studio(store, ext_store, month)

    # 3. Cổng đấu nối API AI
    _render_inline_api_gateway(store, month, key_prefix="settings")

    # 4. Các thẻ cài đặt chuẩn MONii (Chỉnh lời nhắc & Xuất Excel miễn phí không cần PRO)
    rem_enabled = ext_store.get_setting("reminder_enabled", "1") == "1"
    rem_message = ext_store.get_setting("reminder_message", "Đừng quên ghi chép thu chi hôm nay nhé!")
    rem_status_badge = (
        f'<span class="essential-pill pill-safe">{escape(curr_rem)}</span>'
        if rem_enabled
        else '<span class="essential-pill pill-warn">Đang tắt</span>'
    )
    rem_sub_text = (
        f"Lúc {escape(curr_rem)} mỗi ngày · “{escape(rem_message)}”"
        if rem_enabled
        else "Nhắc nhở hằng ngày đang tạm tắt"
    )
    _html_md(
        "".join([
            '<div class="personal-group-label">THÔNG BÁO &amp; NHẮC NHỞ</div>',
            '<div class="personal-card-group">',
            '<div class="personal-row-item">',
            f'<div class="personal-row-left">{lucide_box("bell", color="#34D399", bg="rgba(22,163,106,0.16)", size=18, box_size=38, radius=11)}'
            f'<div><div class="personal-row-title">Giờ &amp; Lời Nhắc Nhở</div><div class="personal-row-sub">{rem_sub_text}</div></div></div>',
            rem_status_badge,
            '</div></div>',
        ])
    )

    with st.expander("🔔 Chỉnh giờ & nội dung lời nhắc hằng ngày"):
        with st.form("reminder_settings_form", enter_to_submit=False):
            rem_on_chk = st.checkbox("Bật lời nhắc ghi chép mỗi ngày", value=rem_enabled)
            rem_c1, rem_c2 = st.columns([1, 2])
            with rem_c1:
                rem_time_input = st.text_input("Giờ nhắc (HH:MM)", value=curr_rem, max_chars=5)
            with rem_c2:
                rem_msg_input = st.text_input(
                    "Nội dung lời nhắc",
                    value=rem_message,
                    max_chars=160,
                    placeholder="VD: Đừng quên ghi chép thu chi hôm nay nhé!",
                )
            if st.form_submit_button("Lưu lời nhắc", type="primary", width="stretch"):
                clean_time = rem_time_input.strip() or "20:00"
                clean_msg = rem_msg_input.strip() or "Đừng quên ghi chép thu chi hôm nay nhé!"
                ext_store.set_setting("reminder_enabled", "1" if rem_on_chk else "0")
                ext_store.set_setting("reminder_time", clean_time)
                ext_store.set_setting("reminder_message", clean_msg)
                _notice(f"Đã lưu lời nhắc ({'Bật lúc ' + clean_time if rem_on_chk else 'Đã tắt'}).")

    _html_md(
        "".join([
            '<div class="personal-group-label">DỮ LIỆU &amp; HỆ THỐNG</div>',
            '<div class="personal-card-group">',
            '<div class="personal-row-item">',
            f'<div class="personal-row-left">{lucide_box("file-spreadsheet", color="#34D399", bg="rgba(22,163,106,0.16)", size=18, box_size=38, radius=11)}'
            '<div><div class="personal-row-title"><span>Xuất Báo Cáo Ra Excel</span>'
            '<span class="essential-pill pill-safe" style="font-size:0.65rem;padding:2px 8px;">Miễn phí</span></div>'
            '<div class="personal-row-sub">Xuất file .xlsx đa sheet chi tiết theo từng tháng (không cần PRO)</div></div></div>',
            lucide_svg("chevron-right", 16, "#9CA3AF"),
            '</div></div>',
        ])
    )

    # Nút tải trực tiếp Excel & PDF miễn phí ngay tại mục Dữ liệu & Hệ thống
    try:
        cur_summary = store.summary(month)
        cur_statuses = store.budget_statuses(month)
        cur_txs = store.list_transactions(month=month)
        cur_cat_map: dict[str, int] = {}
        for t in cur_txs:
            if t.kind == "expense":
                cur_cat_map[t.category] = cur_cat_map.get(t.category, 0) + t.amount
        ex_btn_c1, ex_btn_c2 = st.columns(2)
        with ex_btn_c1:
            excel_bytes_free = export_excel_bytes(month, cur_summary, cur_cat_map, cur_statuses, cur_txs)
            st.download_button(
                "📗 Tải Báo Cáo Excel (.xlsx)",
                data=excel_bytes_free,
                file_name=f"THU_CHI_UTH_BaoCao_{month}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                width="stretch",
                key=f"canhan_free_excel_{month}",
            )
        with ex_btn_c2:
            pdf_bytes_free = export_pdf_bytes(month, cur_summary, cur_cat_map, cur_statuses, cur_txs)
            st.download_button(
                "📄 Tải Báo Cáo PDF",
                data=pdf_bytes_free,
                file_name=f"THU_CHI_UTH_BaoCao_{month}.pdf",
                mime="application/pdf",
                width="stretch",
                key=f"canhan_free_pdf_{month}",
            )
        _render_excel_preview_expander(month, cur_summary, cur_cat_map, cur_txs, key_prefix="canhan")
    except Exception as exc:
        st.warning(f"Không tạo được báo cáo tháng {month}: {exc}")

    _html_md(
        "".join([
            '<div class="privacy-shield-banner">',
            lucide_svg("shield-check", 18, "#34D399"),
            '<span>100% Riêng tư • Hoạt động offline • Dữ liệu mã hóa trên máy bạn</span>',
            '</div>',
        ])
    )

    with st.expander("⚙️ Ngưỡng màu lịch & Sao lưu SQLite"):
        low_th, high_th = ext_store.get_calendar_thresholds()
        with st.form("cal_threshold_form", enter_to_submit=False):
            new_low = st.number_input("Ngưỡng màu Xanh (≤ VNĐ)", min_value=10_000, max_value=50_000_000, value=low_th, step=10_000, format="%d")
            new_high = st.number_input("Ngưỡng màu Cam (≤ VNĐ)", min_value=20_000, max_value=100_000_000, value=high_th, step=50_000, format="%d")
            if st.form_submit_button("Lưu ngưỡng màu lịch", type="primary", width="stretch"):
                try:
                    ext_store.set_calendar_thresholds(int(new_low), int(new_high))
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    _notice("Đã cập nhật ngưỡng màu lịch.")

        try:
            backup_bytes = create_sqlite_backup(db_path)
            st.download_button(
                "📥 Tải bản sao lưu SQLite (.db)",
                data=backup_bytes,
                file_name=f"THU_CHI_UTH_Backup_{date.today().isoformat()}.db",
                mime="application/octet-stream",
                width="stretch",
            )
        except Exception as exc:
            st.error(f"Không tạo được bản sao lưu: {exc}")

        up_db = st.file_uploader("Khôi phục từ tệp SQLite (.db)", type=["db", "sqlite", "sqlite3", "bak"], key="restore_db_uploader")
        if up_db is not None:
            raw_db = up_db.getvalue()
            check = validate_sqlite_backup(raw_db)
            if not check["valid"]:
                st.error(str(check["message"]))
            else:
                st.info(str(check["message"]))
                if st.button("⚡ Xác nhận Khôi phục SQLite", type="primary", width="stretch"):
                    res = restore_sqlite_backup(db_path, raw_db)
                    _notice(str(res["message"]))


# =============================================================================
# CÁC HÀM TƯƠNG THÍCH KIỂM THỬ (NGÂN SÁCH & SỔ GIAO DỊCH)
# =============================================================================
def _budgets(
    store: ExpenseStore,
    ext_store: ExtensionsStore,
    month: str,
    statuses: list[Any],
    budgets: dict[str, Any],
    dark_mode: bool,
) -> None:
    with st.container(border=True):
        st.markdown(f"#### 🎯 Thiết lập hạn mức ngân sách tháng {month}")
        with st.form(f"budget_{month}", enter_to_submit=False):
            amounts = {}
            for category in (TOTAL_BUDGET_CATEGORY, *EXPENSE_CATEGORIES):
                title = (
                    "🎯 Tổng ngân sách tháng (VNĐ)"
                    if category == TOTAL_BUDGET_CATEGORY
                    else f"{_category_label(category)} (VNĐ)"
                )
                current = budgets.get(category)
                amounts[category] = st.number_input(
                    title,
                    min_value=0,
                    max_value=MAX_AMOUNT,
                    value=current.limit if current else 0,
                    step=50_000,
                    format="%d",
                    key=f"budget_{month}_{category}",
                )
            if st.form_submit_button("💾 Lưu ngân sách", type="primary", width="stretch"):
                try:
                    store.set_budgets(month, amounts)
                except (ValueError, sqlite3.Error) as exc:
                    st.error(f"Không lưu được ngân sách: {exc}")
                else:
                    _notice(f"Đã lưu ngân sách tháng {month}.")


def _csv_bytes(records) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(("Mã", "Ngày", "Loại", "Danh mục", "Số tiền (VNĐ)", "Ghi chú"))
    for record in records:
        note = record.note
        if note.lstrip().startswith(("=", "+", "-", "@")):
            note = "'" + note
        writer.writerow((record.id, record.date, TYPE_LABELS[record.kind], record.category, record.amount, note))
    return stream.getvalue().encode("utf-8-sig")


def _render_excel_preview_expander(
    month: str,
    summary_dict: dict[str, int],
    cat_exp_map: dict[str, int],
    txs: list[Any],
    key_prefix: str = "stats",
) -> None:
    """Xem trước trực tiếp 3 trang tính (Sheet) của file báo cáo Excel (.xlsx) trước khi tải."""
    with st.expander(f"👁️ Xem trước báo cáo Excel tháng {month} ({len(txs)} giao dịch)"):
        sheet_choice = st.radio(
            "Chọn trang tính (Sheet) muốn xem trước",
            ["📊 Sheet 1: Tổng quan", "🏷️ Sheet 2: Theo danh mục", "📝 Sheet 3: Chi tiết giao dịch"],
            horizontal=True,
            key=f"excel_prev_sheet_{key_prefix}_{month}",
        )
        if sheet_choice.startswith("📊"):
            st.dataframe(
                pd.DataFrame([
                    {"Chỉ tiêu": "Tháng báo cáo", "Giá trị": month},
                    {"Chỉ tiêu": "Tổng thu nhập", "Giá trị": money(summary_dict.get("income", 0))},
                    {"Chỉ tiêu": "Tổng chi tiêu", "Giá trị": money(summary_dict.get("expense", 0))},
                    {"Chỉ tiêu": "Số dư ròng", "Giá trị": money(summary_dict.get("balance", 0))},
                    {"Chỉ tiêu": "Tổng số giao dịch", "Giá trị": f"{len(txs)} khoản"},
                ]),
                hide_index=True,
                width="stretch",
            )
        elif sheet_choice.startswith("🏷️"):
            total_exp = sum(cat_exp_map.values()) or 1
            cat_rows = [
                {
                    "Danh mục": cat,
                    "Số tiền (VNĐ)": amt,
                    "Tỷ trọng (%)": round(amt / total_exp * 100.0, 1),
                }
                for cat, amt in sorted(cat_exp_map.items(), key=lambda kv: kv[1], reverse=True)
                if amt > 0
            ]
            if cat_rows:
                st.dataframe(
                    pd.DataFrame(cat_rows),
                    hide_index=True,
                    width="stretch",
                    column_config={"Số tiền (VNĐ)": st.column_config.NumberColumn(format="localized")},
                )
            else:
                st.info("Chưa có khoản chi tiêu nào trong kỳ này.")
        else:
            if txs:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Ngày": display_date(t.date),
                            "Loại": TYPE_LABELS.get(t.kind, t.kind),
                            "Danh mục": t.category,
                            "Số tiền (VNĐ)": t.amount,
                            "Ghi chú": t.note or "",
                        }
                        for t in txs
                    ]),
                    hide_index=True,
                    width="stretch",
                    column_config={"Số tiền (VNĐ)": st.column_config.NumberColumn(format="localized")},
                )
            else:
                st.info("Chưa có giao dịch nào để hiển thị.")


def _edit_transaction(store: ExpenseStore, records: list[Any]) -> None:
    indexed = {record.id: record for record in records}
    selected_id = st.selectbox(
        "Chọn giao dịch",
        list(indexed),
        key="edit_transaction_id",
        format_func=lambda value: f"#{value} · {indexed[value].date} · {indexed[value].category} · {money(indexed[value].amount)}",
    )
    record = indexed[selected_id]
    kind = st.radio(
        "Loại giao dịch cần sửa",
        ["expense", "income"],
        index=0 if record.kind == "expense" else 1,
        format_func=TYPE_LABELS.get,
        horizontal=True,
        key=f"edit_kind_{record.id}",
    )
    categories = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
    with st.form(f"edit_{record.id}_{kind}", enter_to_submit=False):
        transaction_date = st.date_input(
            "Ngày",
            value=date.fromisoformat(record.date),
            min_value=date.min,
            max_value=date.max,
        )
        category = st.selectbox(
            "Danh mục mới",
            categories,
            index=categories.index(record.category) if record.category in categories else 0,
            format_func=_category_label,
        )
        amount = st.number_input(
            "Số tiền mới (VNĐ)",
            min_value=0,
            max_value=MAX_AMOUNT,
            value=record.amount,
            format="%d",
            step=5_000,
        )
        note = st.text_input("Ghi chú mới", value=record.note, max_chars=200)
        if st.form_submit_button("Lưu thay đổi", type="primary", width="stretch"):
            try:
                store.update_transaction(record.id, transaction_date.isoformat(), kind, category, amount, note)
            except (ValueError, sqlite3.Error) as exc:
                st.error(f"Không sửa được giao dịch: {exc}")
            else:
                st.session_state["pending_month"] = transaction_date.strftime("%Y-%m")
                _notice(f"Đã cập nhật giao dịch #{record.id}.")


def _ledger(store: ExpenseStore, ext_store: ExtensionsStore, month: str) -> None:
    _html_md(f'<div class="section-heading">{lucide_svg("arrow-left-right", 18, "#34D399")}<span>Sổ giao dịch tháng {month}</span></div>')
    kind_column, category_column, search_column = st.columns([1, 1.2, 1.8])
    with kind_column:
        kind_label = st.selectbox("Lọc theo loại", ["Tất cả", "Chi tiêu", "Thu nhập"])
    with category_column:
        category = st.selectbox(
            "Lọc theo danh mục",
            ["Tất cả", *dict.fromkeys((*EXPENSE_CATEGORIES, *INCOME_CATEGORIES))],
        )
    with search_column:
        keyword = st.text_input("🔍 Tìm theo ghi chú hoặc danh mục", placeholder="Nhập từ khóa…")
    records = store.list_transactions(
        month=month,
        kind={"Chi tiêu": "expense", "Thu nhập": "income"}.get(kind_label),
        category=category if category != "Tất cả" else None,
        search=keyword,
    )
    income = sum(record.amount for record in records if record.kind == "income")
    expense = sum(record.amount for record in records if record.kind == "expense")
    info, download = st.columns([2.2, 1])
    with info:
        st.caption(f"{len(records)} giao dịch · Thu: {money(income)} · Chi: {money(expense)}")
    with download:
        st.download_button(
            "📥 Xuất CSV",
            _csv_bytes(records),
            file_name=f"chi_tieu_{month}.csv",
            mime="text/csv",
            width="stretch",
            disabled=not records,
        )
    if not records:
        st.info("Không có giao dịch khớp với bộ lọc.")
    else:
        st.dataframe(
            pd.DataFrame([
                {
                    "Mã GD": record.id,
                    "Ngày": record.date,
                    "Loại": TYPE_LABELS[record.kind],
                    "Danh mục": record.category,
                    "Số tiền (VNĐ)": record.amount,
                    "Ghi chú": record.note,
                }
                for record in records
            ]),
            hide_index=True,
            width="stretch",
            column_config={
                "Mã GD": st.column_config.NumberColumn(format="%d"),
                "Số tiền (VNĐ)": st.column_config.NumberColumn(format="localized"),
                "Ghi chú": st.column_config.TextColumn(width="large"),
            },
        )
        with st.expander("✏️ Sửa giao dịch"):
            _edit_transaction(store, records)
        with st.expander("🗑️ Xóa giao dịch nhập nhầm"):
            indexed = {record.id: record for record in records}
            selected_id = st.selectbox(
                "Giao dịch cần xóa",
                list(indexed),
                key="delete_transaction_id",
                format_func=lambda value: f"#{value} · {indexed[value].date} · {indexed[value].category} · {money(indexed[value].amount)}",
            )
            with st.form(f"delete_{selected_id}", enter_to_submit=False):
                confirmed = st.checkbox(f"Tôi xác nhận xóa giao dịch #{selected_id}.")
                if st.form_submit_button("Xóa giao dịch", width="stretch"):
                    if not confirmed:
                        st.warning("Đánh dấu xác nhận trước khi xóa giao dịch.")
                    else:
                        try:
                            store.delete_transaction(selected_id)
                        except (ValueError, sqlite3.Error) as exc:
                            st.error(f"Không xóa được giao dịch: {exc}")
                        else:
                            _notice(f"Đã xóa giao dịch #{selected_id}.")


def _render_desktop_sidebar(
    active_tab: str,
    month: str,
    summary: dict[str, int],
    budgets: dict[str, Any],
    dark_mode: bool,
    demo: bool,
    account_label: str = "",
) -> None:
    """Thanh Sidebar trái cố định dành riêng cho giao diện Web Desktop (>= 1024px).
    Ẩn hoàn toàn trên Mobile (< 1024px) để giữ nguyên 100% giao diện điện thoại.
    """
    daily_safe, cap_amount, used_pct, status_label = _compute_safe_daily_allowance(month, summary, budgets)
    nav_items = [
        ("lich", "?tab=lich", "calendar", "Lịch tài chính"),
        ("hoadon", "?tab=hoadon&bmode=recurring", "file-text", "Hóa đơn & Sổ nợ"),
        ("gallery", "?tab=hoadon&bmode=gallery", "image", "Kho ảnh hóa đơn"),
        ("thongke", "?tab=thongke", "pie-chart", "Thống kê chi tiêu"),
        ("cleaner", "?tab=cleaner", "sparkles", "AI Làm sạch dữ liệu"),
        ("dbview", "?tab=dbview", "file-spreadsheet", "Xem Database (.db)"),
        ("ocr", "?tab=ocr", "scan-line", "Quét hóa đơn AI"),
        ("voice", "?tab=voice", "mic", "Nhập giọng nói"),
        ("canhan", "?tab=canhan", "settings", "Cá nhân & Tài khoản"),
    ]
    cur_bmode = st.session_state.get("bills_submode", "recurring")
    nav_links: list[str] = []
    for tab_key, href_url, icon_name, label in nav_items:
        if tab_key == "gallery":
            is_act = active_tab == "hoadon" and cur_bmode == "gallery"
        elif tab_key == "hoadon":
            is_act = active_tab == "hoadon" and cur_bmode != "gallery"
        else:
            is_act = active_tab == tab_key
        cls = "uds-nav-link active" if is_act else "uds-nav-link"
        ic_color = "#34D399" if is_act else "#9CA3AF"
        nav_links.append(
            f'<a href="{href_url}" target="_self" class="{cls}">'
            f'{lucide_svg(icon_name, 18, ic_color)}<span>{label}</span></a>'
        )

    theme_icon = lucide_svg("sun" if dark_mode else "moon", 16, "#FBBF24" if dark_mode else "#34D399")
    theme_label = "Chuyển Light Mode" if dark_mode else "Chuyển Dark Mode"
    mode_badge = account_label or ("Dữ liệu mẫu" if demo else "Dữ liệu cá nhân")
    ai_hint = (
        f"Có thể chi an toàn <strong>{money(daily_safe)}/ngày</strong> ({status_label} · {used_pct:.0f}% hạn mức)."
        if cap_amount > 0
        else "Bắt đầu ghi chép để Uni AI phân tích hạn mức chi tiêu mỗi ngày."
    )

    sidebar_html = f"""
    <aside class="unispend-desktop-sidebar" aria-label="Điều hướng Web Desktop">
        <div>
            <div class="uds-brand">
                <div class="uds-brand-icon" style="background:transparent;box-shadow:none;width:44px;height:44px;">{mascot_logo_svg(44)}</div>
                <div>
                    <div class="uds-brand-title">THU CHI UTH</div>
                    <div class="uds-brand-sub">Quản lý tài chính thông minh</div>
                </div>
            </div>
            <div class="uds-nav-section-label">Điều hướng chính</div>
            <nav class="uds-nav-list">{"".join(nav_links)}</nav>
            <div class="uds-ai-card">
                <div class="uds-ai-title">{lucide_svg("sparkles", 15, "#34D399")}<span>Gợi ý từ Uni AI</span></div>
                <div class="uds-ai-desc">{ai_hint}</div>
                <a href="?tab=thongke" target="_self" class="uds-ai-cta">Xem phân tích chi tiết {lucide_svg("arrow-right", 13, "#34D399")}</a>
            </div>
        </div>
        <div class="uds-footer">
            <a href="?theme=toggle" target="_self" class="uds-theme-btn">{theme_icon}<span>{theme_label}</span></a>
            <div class="uds-mode-pill">Tháng {escape(month)} · {mode_badge}</div>
        </div>
    </aside>
    """
    _html_md(sidebar_html)


def _render_desktop_topbar(active_tab: str, month: str, dark_mode: bool, account_label: str = "") -> None:
    """Thanh Topbar tiêu đề & thao tác nhanh dành riêng cho Máy Tính (>= 1024px), ẩn trên Mobile."""
    year, month_num = map(int, month.split("-"))
    prev_m = shift_month(month, -1)
    next_m = shift_month(month, 1)
    today_m = date.today().strftime("%Y-%m")
    tab_titles = {
        "lich": ("Tổng quan tài chính", "Hãy cùng quản lý tài chính thông minh hơn nhé!"),
        "hoadon": ("Hóa đơn & Sổ ghi nợ", "Theo dõi khoản định kỳ, công nợ và trạng thái thanh toán."),
        "thongke": ("Thống kê chi tiêu", "Phân tích tỷ trọng danh mục, xu hướng và cảnh báo ngân sách."),
        "cleaner": ("AI Làm sạch dữ liệu thô", "Tải file CSV/Excel hoặc dán văn bản thô để AI chuẩn hóa thành tài khoản .db riêng."),
        "dbview": ("Trình xem Database SQLite (.db)", "Xem trực tiếp các bảng transactions, budgets, receipts, schema CHECK và chạy lệnh SQL."),
        "ocr": ("Quét hóa đơn AI", "Nhận diện hóa đơn tự động bằng Tesseract OCR 5.x & Gemini AI."),
        "voice": ("Nhập chi tiêu bằng giọng nói", "Ghi chép nhanh bằng tiếng Việt tự nhiên."),
        "canhan": ("Cá nhân & Tài khoản", "Chuyển tài khoản .db, AI làm sạch dữ liệu, trợ lý AI và sao lưu."),
    }
    title, subtitle = tab_titles.get(active_tab, tab_titles["lich"])
    if account_label:
        subtitle = f"Tài khoản đang mở: {account_label} · {subtitle}"
    chev_l = lucide_svg("chevron-left", 15, "#34D399")
    chev_r = lucide_svg("chevron-right", 15, "#34D399")
    theme_ic = lucide_svg("sun" if dark_mode else "moon", 16, "#F59E0B" if dark_mode else "#16A36A")

    topbar_html = f"""
    <header class="unispend-desktop-topbar" aria-label="Thanh tiêu đề Máy Tính">
        <div class="udt-left">
            <div class="udt-title">{escape(title)}</div>
            <div class="udt-sub">{escape(subtitle)}</div>
        </div>
        <div class="udt-right">
            <div class="monii-month-pill">
                <a href="?tab={active_tab}&month={prev_m}" target="_self" class="monii-month-arrow" title="Tháng trước">{chev_l}</a>
                <span class="monii-month-label">Tháng {month_num}, {year}</span>
                <a href="?tab={active_tab}&month={next_m}" target="_self" class="monii-month-arrow" title="Tháng sau">{chev_r}</a>
            </div>
            <a href="?tab={active_tab}&month={today_m}" target="_self" class="udt-pill-btn">Hôm nay</a>
            <a href="?tab={active_tab}&theme=toggle" target="_self" class="monii-theme-circle" title="Đổi Light/Dark Mode">{theme_ic}</a>
            <a href="?tab=ocr" target="_self" class="udt-pill-btn primary">{lucide_svg("camera", 15, "#FFFFFF")}<span>Quét hóa đơn</span></a>
            <a href="?tab=voice" target="_self" class="udt-pill-btn">{lucide_svg("mic", 15, "#34D399")}<span>Giọng nói</span></a>
        </div>
    </header>
    """
    _html_md(topbar_html)


def _render_desktop_kpi_strip(month: str, summary: dict[str, int], budgets: dict[str, Any]) -> None:
    """Dải 4 thẻ KPI tổng quan chỉ hiển thị trên Web Desktop (>= 1024px), ẩn hoàn toàn trên Mobile."""
    daily_safe, cap_amount, used_pct, status_label = _compute_safe_daily_allowance(month, summary, budgets)
    actual_pct = (summary["expense"] / cap_amount * 100.0) if cap_amount > 0 else 0.0
    over_amt = max(0, summary["expense"] - cap_amount)
    is_over_kpi = over_amt > 0
    kpi4_icon = (
        lucide_box("alert-triangle", "#F87171", "rgba(220, 38, 38, 0.18)", size=17, box_size=32)
        if is_over_kpi
        else lucide_box("shield-check", "#38BDF8", "rgba(56, 189, 248, 0.16)", size=17, box_size=32)
    )
    kpi4_val_style = ' style="color:#F87171;"' if is_over_kpi else ""
    kpi4_sub_html = (
        f'<span style="color:#F87171;font-weight:800;">Vượt {money(over_amt)}</span>'
        f'<span style="color:#F87171;">{actual_pct:.1f}%</span>'
        if is_over_kpi
        else f'<span>{escape(status_label)} · {actual_pct:.0f}%</span><span>/ {compact_money(cap_amount)}</span>'
    )
    bal_color = "#4ADE80" if summary["balance"] >= 0 else "#F87171"
    bal_variant = "up" if summary["balance"] >= 0 else "down"
    strip_html = f"""
    <section class="unispend-desktop-kpi-strip" aria-label="Tổng quan tài chính Web">
        <div class="udk-card">
            <div class="udk-top">
                <span class="udk-label">Số dư khả dụng</span>
                {lucide_box("wallet", "#34D399", "rgba(22, 163, 106, 0.16)", size=17, box_size=32)}
            </div>
            <div class="udk-val" style="color:{bal_color};">{money(summary["balance"])}</div>
            <div class="udk-sub"><span>Tháng {escape(month)}</span>{mini_sparkline_svg("#34D399", variant=bal_variant)}</div>
        </div>
        <div class="udk-card">
            <div class="udk-top">
                <span class="udk-label">Tổng thu nhập</span>
                {lucide_box("arrow-down-left", "#4ADE80", "rgba(22, 163, 106, 0.16)", size=17, box_size=32)}
            </div>
            <div class="udk-val" style="color:#4ADE80;">+{money(summary["income"])}</div>
            <div class="udk-sub"><span>Nguồn thu trong tháng</span>{mini_sparkline_svg("#4ADE80", variant="up")}</div>
        </div>
        <div class="udk-card">
            <div class="udk-top">
                <span class="udk-label">Tổng chi tiêu</span>
                {lucide_box("arrow-up-right", "#F87171", "rgba(220, 38, 38, 0.16)", size=17, box_size=32)}
            </div>
            <div class="udk-val" style="color:#F87171;">-{money(summary["expense"])}</div>
            <div class="udk-sub"><span>{summary["count"]} giao dịch đã ghi</span>{mini_sparkline_svg("#F87171", variant="expense")}</div>
        </div>
        <div class="udk-card" style="{'border-color:rgba(248,113,113,0.5);' if is_over_kpi else ''}">
            <div class="udk-top">
                <span class="udk-label">Có thể chi hôm nay</span>
                {kpi4_icon}
            </div>
            <div class="udk-val"{kpi4_val_style}>{money(daily_safe)}</div>
            <div class="udk-sub">{kpi4_sub_html}</div>
        </div>
    </section>
    """
    _html_md(strip_html)


def _render_fixed_bottom_navigation(active_tab: str) -> None:
    """Thanh Bottom Navigation cố định dạng viên thuốc nổi (4 Tab: Lịch | Hóa đơn | Thống kê | Cá nhân)."""
    nav_items = [
        ("lich", "calendar", "Lịch"),
        ("hoadon", "file-text", "Hóa đơn"),
        ("thongke", "pie-chart", "Thống kê"),
        ("canhan", "user", "Cá nhân"),
    ]
    nav_parts = ['<nav class="unispend-bottom-nav">']
    for tab_key, icon_name, label in nav_items:
        is_act = (active_tab == tab_key) or (tab_key == "lich" and active_tab in ("ocr", "voice"))
        cls_name = "unispend-nav-item active" if is_act else "unispend-nav-item"
        color = "#34D399" if is_act else "#9CA3AF"
        svg_ic = lucide_svg(icon_name, 19, color)
        nav_parts.append(
            f'<a href="?tab={tab_key}" target="_self" class="{cls_name}">{svg_ic}<span>{label}</span></a>'
        )
    nav_parts.append('</nav>')
    _html_md("".join(nav_parts))


def run_app(db_path, demo: bool = False) -> None:
    st.set_page_config(
        page_title="THU CHI UTH — Quản lý chi tiêu sinh viên",
        page_icon="🐷",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    base_data_dir = _resolve_base_data_dir(db_path)
    acc_state_key = f"active_account_db:{base_data_dir}"
    saved_acc = st.session_state.get(acc_state_key)
    persisted_acc = load_active_account(base_data_dir)
    if saved_acc and Path(saved_acc).is_file():
        active_db_path = Path(saved_acc)
    elif persisted_acc is not None:
        active_db_path = persisted_acc
        st.session_state[acc_state_key] = str(persisted_acc.resolve())
    else:
        active_db_path = Path(db_path)
    is_demo_db = demo and active_db_path.resolve() == Path(db_path).resolve()

    try:
        store = ExpenseStore(active_db_path)
        ext_store = ExtensionsStore(resolve_extensions_db_path(active_db_path, demo=is_demo_db))
    except (OSError, sqlite3.Error) as exc:
        st.error(f"Không mở được dữ liệu: {exc}")
        return

    try:
        demo_key = f"demo_initialized:{active_db_path.resolve()}"
        if is_demo_db and not st.session_state.get(demo_key):
            store.seed_demo()
            st.session_state[demo_key] = True

        active_tab = _sync_query_params(store, ext_store)

        if st.session_state.pop("account_just_switched", False):
            st.session_state.pop("selected_calendar_date", None)
            avail = store.available_months()
            if avail:
                st.session_state["pending_month"] = avail[0]
        elif "report_month" not in st.session_state and "pending_month" not in st.session_state:
            # Khi vừa chuyển trang (<a href="?tab=...">) sang tài khoản có dữ liệu khác tháng hiện tại
            today_m = date.today().strftime("%Y-%m")
            avail = store.available_months()
            if avail and today_m not in avail:
                st.session_state["pending_month"] = avail[0]

        dark_mode = ext_store.get_theme_mode() == "dark"
        hide_legacy = active_tab in ("lich", "hoadon", "ocr", "voice", "cleaner", "dbview")
        inject_mobile_styles(light_mode=not dark_mode, hide_legacy_tabs=hide_legacy)

        month = _sidebar(
            store,
            ext_store,
            is_demo_db,
            dark_mode,
            db_path=active_db_path,
            base_data_dir=base_data_dir,
        )

        notice = st.session_state.pop("notice", None)
        if notice:
            st.success(notice)

        summary = store.summary(month)
        statuses = store.budget_statuses(month)
        budgets = {status.category: status for status in statuses}

        accounts_now = list_accounts(base_data_dir, extra_paths=(active_db_path,))
        cur_acc_info = next((a for a in accounts_now if a.path == active_db_path.resolve()), None)
        active_account_label = (
            f"{cur_acc_info.display_name} ({cur_acc_info.file_name})"
            if cur_acc_info
            else active_db_path.name
        )

        # Sidebar & Topbar Máy Tính (>= 1024px) — ẩn hoàn toàn trên Mobile (< 1024px)
        _render_desktop_sidebar(
            active_tab, month, summary, budgets, dark_mode, is_demo_db,
            account_label=active_account_label,
        )
        _render_desktop_topbar(active_tab, month, dark_mode, account_label=active_account_label)

        # Thanh hiển thị Tài khoản đang mở + nút nhanh AI Làm sạch dữ liệu (hiện cả Desktop & Mobile)
        _acc_tx_cnt = cur_acc_info.tx_count if cur_acc_info else summary["count"]
        _html_md(
            '<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;'
            'gap:8px;padding:10px 14px;margin:4px 0 12px 0;border-radius:14px;'
            'background:rgba(16,185,129,0.10);border:1px solid rgba(52,211,153,0.35);">'
            f'<div style="font-size:0.86rem;font-weight:700;color:var(--text-main);">'
            f'👤 Tài khoản: <span style="color:#34D399;">{escape(active_account_label)}</span>'
            f' <span style="font-weight:500;color:var(--text-muted);">({ _acc_tx_cnt } giao dịch · Tháng {escape(month)})</span></div>'
            '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
            '<a href="?tab=dbview" target="_self" style="text-decoration:none;font-size:0.8rem;font-weight:700;'
            'padding:5px 11px;border-radius:999px;background:rgba(59,130,246,0.18);'
            'border:1px solid rgba(96,165,250,0.45);color:var(--text-main);">🗄️ Xem bảng .db</a>'
            '<a href="?tab=canhan" target="_self" style="text-decoration:none;font-size:0.8rem;font-weight:700;'
            'padding:5px 11px;border-radius:999px;background:rgba(255,255,255,0.08);'
            'border:1px solid rgba(148,163,184,0.35);color:var(--text-main);">🔄 Đổi / Tạo tài khoản</a>'
            '<a href="?tab=cleaner" target="_self" style="text-decoration:none;font-size:0.8rem;font-weight:700;'
            'padding:5px 11px;border-radius:999px;background:#10B981;color:#FFFFFF;">✨ AI Làm sạch dữ liệu thô</a>'
            '</div></div>'
        )

        # Hiển thị đúng màn hình theo Tab đang chọn
        if active_tab == "lich":
            _render_desktop_kpi_strip(month, summary, budgets)
            _render_tab_lich(store, ext_store, month, summary, budgets, dark_mode, is_demo_db)
        elif active_tab == "hoadon":
            _render_tab_hoadon(store, ext_store, month)
        elif active_tab == "thongke":
            _render_tab_thongke(store, ext_store, month, summary, statuses, budgets, dark_mode)
        elif active_tab == "cleaner":
            _render_ai_data_cleaner_studio(base_data_dir, store, ext_store)
        elif active_tab == "dbview":
            _render_sqlite_database_viewer(active_db_path, store, ext_store)
        elif active_tab == "canhan":
            _render_tab_canhan(active_db_path, store, ext_store, month, base_data_dir=base_data_dir)
        elif active_tab == "ocr":
            _render_receipt_scanner_studio(store, ext_store)
        elif active_tab == "voice":
            _render_voice_assistant_studio(store, ext_store)

        # Khối 4 tab tương thích ngược cho bộ kiểm thử tự động (ẩn hoàn toàn trên Tab Lịch & Hóa đơn qua CSS)
        overview, chart_tab, budget_tab, ledger = st.tabs([
            "📊 Tổng quan",
            "📈 Biểu đồ theo tháng",
            "🚨 Cảnh báo & Ngân sách",
            "📝 Sổ giao dịch",
        ])
        with overview:
            st.caption(f"Tổng giao dịch tháng {month}: {summary['count']} khoản.")
        with chart_tab:
            if active_tab != "thongke":
                st.caption("Biểu đồ thống kê chi tiết hiển thị tại Tab Thống kê.")
        with budget_tab:
            _budgets(store, ext_store, month, statuses, budgets, dark_mode)
        with ledger:
            _ledger(store, ext_store, month)

        _render_fixed_bottom_navigation(active_tab)
    except (OSError, sqlite3.Error) as exc:
        st.error(f"Không đọc hoặc lưu được dữ liệu: {exc}")
    finally:
        ext_store.close()
        store.close()
