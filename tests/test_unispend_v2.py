"""Kiểm thử toàn diện các tính năng UniSpend 2.0:
- ExtensionsStore (Light/Dark theme, ngưỡng lịch, Hóa đơn & trùng lặp, Mục tiêu tiết kiệm, Định kỳ/Nợ)
- AI Service (Giọng nói tiếng Việt: 10K, 50K, 35 nghìn, 100 nghìn, 1 triệu, 1 triệu 2, 2 triệu rưỡi; OCR hóa đơn; Trợ lý tài chính từ dữ liệu thật)
- Xuất báo cáo Excel (.xlsx) & PDF (.pdf)
- Sao lưu (Backup), Kiểm tra (Validate) & Khôi phục (Restore) SQLite an toàn
- Tích hợp giao diện Streamlit UniSpend 2.0
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from streamlit.testing.v1 import AppTest

from expense_tracker.ai_service import (
    answer_financial_question,
    build_financial_analysis,
    generate_ai_deep_financial_review,
    parse_receipt_text,
    parse_vietnamese_spoken_amount,
    parse_vietnamese_voice_expense,
    save_ai_api_config,
    test_all_ai_pipelines,
)
from expense_tracker.charts import financial_trend
from expense_tracker.extensions_db import ExtensionsStore, resolve_extensions_db_path
from expense_tracker.lucide_icons import category_lucide_box, lucide_box, lucide_svg, mini_sparkline_svg
from expense_tracker.mascot import mascot_calendar_svg, mascot_question_svg, mascot_wallet_svg
from expense_tracker.reports_backup import (
    create_sqlite_backup,
    export_excel_bytes,
    export_pdf_bytes,
    restore_sqlite_backup,
    validate_sqlite_backup,
)
from expense_tracker.storage import ExpenseStore
from expense_tracker.ui import (
    EIGHT_DISPLAY_CATEGORIES,
    SAMPLE_RECEIPT_TEXT,
    _compute_eight_category_breakdown,
    _compute_safe_daily_allowance,
)


class UniSpendV2Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_path = Path(self.directory.name) / "expenses.db"
        self.ext_path = resolve_extensions_db_path(self.db_path, demo=False)
        self.store = ExpenseStore(self.db_path)
        self.ext_store = ExtensionsStore(self.ext_path)

    def tearDown(self):
        self.ext_store.close()
        self.store.close()
        self.directory.cleanup()

    def test_extensions_db_path_separates_user_and_demo(self):
        base = Path(self.directory.name)
        user_ext = resolve_extensions_db_path(base / "expenses.db", demo=False)
        demo_ext = resolve_extensions_db_path(base / "demo.db", demo=True)
        self.assertEqual(Path(user_ext).name, "unispend_extensions.db")
        self.assertEqual(Path(demo_ext).name, "unispend_extensions_demo.db")
        self.assertNotEqual(user_ext, demo_ext)

    def test_theme_mode_and_calendar_thresholds_persist(self):
        self.assertEqual(self.ext_store.get_theme_mode(), "dark")
        self.ext_store.set_theme_mode("light")
        self.assertEqual(self.ext_store.get_theme_mode(), "light")
        self.ext_store.set_theme_mode("dark")
        self.assertEqual(self.ext_store.get_theme_mode(), "dark")

        self.assertEqual(self.ext_store.get_calendar_thresholds(), (100_000, 500_000))
        self.ext_store.set_calendar_thresholds(150_000, 600_000)
        self.assertEqual(self.ext_store.get_calendar_thresholds(), (150_000, 600_000))
        with self.assertRaises(ValueError):
            self.ext_store.set_calendar_thresholds(500_000, 200_000)

    def test_eight_category_breakdown_and_mascot_svgs(self):
        self.store.add_transaction("2026-11-01", "expense", "Ăn uống", 50_000, "Phở bò")
        self.store.add_transaction("2026-11-02", "expense", "Tiền trọ", 1_500_000, "Tiền phòng")
        self.store.add_transaction("2026-11-03", "expense", "Đi lại", 40_000, "Đổ xăng")
        self.store.add_transaction("2026-11-04", "expense", "Khác", 120_000, "Mua sắm áo thun Shopee")
        self.store.add_transaction("2026-11-05", "expense", "Khác", 90_000, "Mua thuốc cảm tại nhà thuốc")
        self.store.add_transaction("2026-11-06", "expense", "Khác", 30_000, "Phí dịch vụ")

        buckets = _compute_eight_category_breakdown(self.store.list_transactions(month="2026-11"))
        self.assertEqual(
            set(buckets.keys()),
            {"Ăn uống", "Nhà cửa", "Di chuyển", "Mua sắm", "Giải trí", "Học tập", "Sức khỏe", "Khác"},
        )
        self.assertEqual(buckets["Ăn uống"], 50_000)
        self.assertEqual(buckets["Nhà cửa"], 1_500_000)
        self.assertEqual(buckets["Di chuyển"], 40_000)
        self.assertEqual(buckets["Mua sắm"], 120_000)
        self.assertEqual(buckets["Sức khỏe"], 90_000)
        self.assertEqual(buckets["Khác"], 30_000)

        for svg in (mascot_calendar_svg(), mascot_wallet_svg(), mascot_question_svg()):
            self.assertIn("<svg", svg)

        # Kiểm tra bộ icon Lucide SVG và thẻ Chi tiêu an toàn
        self.assertEqual(len(EIGHT_DISPLAY_CATEGORIES), 8)
        for _, cat_svg, _, _ in EIGHT_DISPLAY_CATEGORIES:
            self.assertIn("<svg", cat_svg)
        self.assertIn("<svg", lucide_svg("calendar"))
        self.assertIn("<svg", lucide_box("wallet"))
        self.assertIn("<svg", category_lucide_box("Ăn uống", "Cà phê sáng"))
        self.assertIn("<svg", mini_sparkline_svg())

        daily_safe, cap_amount, used_pct, status_label = _compute_safe_daily_allowance(
            "2026-11",
            self.store.summary("2026-11"),
            {},
        )
        self.assertGreater(daily_safe, 0)
        self.assertEqual(cap_amount, 6_500_000)
        self.assertEqual(status_label, "Trong giới hạn")

    def test_vietnamese_voice_parser_handles_all_required_patterns(self):
        today = date(2026, 11, 19)

        # Ví dụ 1 trong đề: "Tiền đổ xăng 50K"
        p1 = parse_vietnamese_voice_expense("Tiền đổ xăng 50K", today=today, use_ai=False)
        self.assertEqual(p1["kind"], "expense")
        self.assertEqual(p1["amount"], 50_000)
        self.assertEqual(p1["category"], "Đi lại")
        self.assertEqual(p1["note"], "Đổ xăng")
        self.assertEqual(p1["date"], "2026-11-19")
        self.assertEqual(p1["date_relative"], "Hôm nay")

        # Ví dụ 2 trong đề: "Ăn sáng 35 nghìn hôm qua"
        p2 = parse_vietnamese_voice_expense("Ăn sáng 35 nghìn hôm qua", today=today, use_ai=False)
        self.assertEqual(p2["kind"], "expense")
        self.assertEqual(p2["amount"], 35_000)
        self.assertEqual(p2["category"], "Ăn uống")
        self.assertEqual(p2["note"], "Ăn sáng")
        self.assertEqual(p2["date"], "2026-11-18")
        self.assertEqual(p2["date_relative"], "Hôm qua")

        # Các mẫu trong ảnh tham chiếu mới: "Ăn trưa phở bò 45k", "Đổ xăng 70 ngàn"
        p3 = parse_vietnamese_voice_expense("Ăn trưa phở bò 45k", today=today, use_ai=False)
        self.assertEqual((p3["kind"], p3["amount"], p3["category"], p3["note"]), ("expense", 45_000, "Ăn uống", "Ăn trưa phở bò"))

        p4 = parse_vietnamese_voice_expense("Đổ xăng 70 ngàn", today=today, use_ai=False)
        self.assertEqual((p4["kind"], p4["amount"], p4["category"], p4["note"]), ("expense", 70_000, "Đi lại", "Đổ xăng"))

        # Các cách nói số tiền bắt buộc: 10K, 50K, 100 nghìn, 1 triệu, 1 triệu 2, 2 triệu rưỡi
        cases = {
            "Mua nước 10K": 10_000,
            "Đổ xăng 50K": 50_000,
            "Đi chợ 100 nghìn": 100_000,
            "Học bổng 1 triệu": 1_000_000,
            "Lương làm thêm 1 triệu 2": 1_200_000,
            "Đóng tiền trọ 2 triệu rưỡi": 2_500_000,
        }
        for phrase, expected_amount in cases.items():
            with self.subTest(phrase=phrase):
                amt, _ = parse_vietnamese_spoken_amount(phrase)
                self.assertEqual(amt, expected_amount)

    def test_receipt_ocr_parser_extracts_items_and_never_fabricates_when_empty(self):
        parsed = parse_receipt_text(SAMPLE_RECEIPT_TEXT, today=date(2026, 11, 19))
        self.assertTrue(parsed["readable"])
        self.assertIn("SIÊU THỊ MINI", parsed["store_name"])
        self.assertEqual(parsed["total_amount"], 43_000)
        self.assertEqual(len(parsed["items"]), 3)

        # Khi văn bản không có số tiền, tuyệt đối không tự bịa
        unreadable = parse_receipt_text("Ảnh mờ không rõ chữ", today=date(2026, 11, 19))
        self.assertFalse(unreadable["readable"])
        self.assertEqual(unreadable["total_amount"], 0)

    def test_receipt_storage_links_to_transaction_and_detects_duplicates(self):
        tx_id = self.store.add_transaction("2026-11-19", "expense", "Ăn uống", 60_000, "Hóa đơn Circle K")
        img_bytes = b"\x89PNG\r\n\x1a\nfake-receipt-image"
        rec_id = self.ext_store.add_receipt(
            transaction_id=tx_id,
            store_name="Circle K",
            purchase_date="2026-11-19",
            purchase_time="12:35",
            items=[{"name": "Cơm nắm", "qty": 1, "unit_price": 60_000, "line_total": 60_000}],
            discount=0,
            total_amount=60_000,
            payment_method="MoMo",
            suggested_category="Ăn uống",
            image_bytes=img_bytes,
        )
        self.assertGreater(rec_id, 0)
        linked = self.ext_store.get_receipt_by_transaction(tx_id)
        self.assertIsNotNone(linked)
        self.assertEqual(linked.store_name, "Circle K")

        # Phát hiện trùng theo hash ảnh và theo (cửa hàng, ngày, tổng tiền)
        dup_by_hash = self.ext_store.find_duplicate_receipt(
            self.ext_store.compute_image_hash(img_bytes), "Khác", "2026-11-01", 10_000
        )
        self.assertIsNotNone(dup_by_hash)
        dup_by_meta = self.ext_store.find_duplicate_receipt("", "circle k", "2026-11-19", 60_000)
        self.assertIsNotNone(dup_by_meta)

    def test_ai_financial_assistant_uses_real_data_and_checks_forecast_sufficiency(self):
        self.store.add_transaction("2026-11-01", "income", "Gia đình hỗ trợ", 5_000_000, "Trợ cấp")
        self.store.add_transaction("2026-11-02", "expense", "Tiền trọ", 2_000_000, "Tiền phòng")
        self.store.set_budget("2026-11", "Tổng chi tiêu", 4_000_000)

        # Mới chỉ có 1 ngày chi tiêu -> không dự báo chắc chắn
        analysis_1d = build_financial_analysis(self.store, "2026-11", today=date(2026, 11, 10))
        self.assertFalse(analysis_1d["can_forecast"])
        self.assertIsNone(analysis_1d["projected_expense"])

        # Thêm đủ >= 3 ngày có giao dịch chi tiêu -> dự báo được
        self.store.add_transaction("2026-11-05", "expense", "Ăn uống", 300_000, "Ăn uống")
        self.store.add_transaction("2026-11-08", "expense", "Đi lại", 100_000, "Xăng")
        qa = answer_financial_question(self.store, "2026-11", "Tháng này tôi tiêu bao nhiêu?", use_ai=False)
        self.assertIn("2.400.000 đ", qa["answer"])

        qa_top = answer_financial_question(self.store, "2026-11", "Tôi tiêu nhiều nhất vào danh mục nào?", use_ai=False)
        self.assertIn("Tiền trọ", qa_top["answer"])

    def test_savings_goals_and_recurring_items_workflow(self):
        goal_id = self.ext_store.add_savings_goal("Mua giáo trình", 500_000, "2026-12-31", current_amount=200_000)
        goals = self.ext_store.list_savings_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].remaining_amount, 300_000)
        self.ext_store.update_savings_goal_amount(goal_id, 500_000)
        self.assertEqual(self.ext_store.list_savings_goals()[0].status, "completed")

        rec_id = self.ext_store.add_recurring_item(
            title="Tiền trọ tháng",
            item_type="recurring",
            kind="expense",
            category="Tiền trọ",
            amount=1_800_000,
            frequency="monthly",
            due_day=5,
            next_due_date="2026-11-05",
        )
        self.ext_store.mark_recurring_recorded(rec_id, "2026-11-05")
        updated_rec = self.ext_store.list_recurring_items()[0]
        self.assertEqual(updated_rec.next_due_date, "2026-12-05")

    def test_excel_pdf_export_and_sqlite_backup_restore(self):
        self.store.add_transaction("2026-11-10", "income", "Làm thêm", 1_500_000, "Gia sư")
        self.store.add_transaction("2026-11-12", "expense", "Ăn uống", 85_000, "Cơm trưa")
        self.store.set_budget("2026-11", "Ăn uống", 1_000_000)

        summary = self.store.summary("2026-11")
        cat_totals = self.store.category_totals("2026-11")
        statuses = self.store.budget_statuses("2026-11")
        txs = self.store.list_transactions(month="2026-11")

        xlsx_bytes = export_excel_bytes("2026-11", summary, cat_totals, statuses, txs)
        self.assertTrue(xlsx_bytes.startswith(b"PK"))

        pdf_bytes = export_pdf_bytes("2026-11", summary, cat_totals, statuses, txs)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

        chart = financial_trend(self.store.monthly_totals("2026-11", count=3))
        self.assertIsNotNone(chart)

        # Backup & Restore SQLite
        backup_data = create_sqlite_backup(self.db_path)
        validation = validate_sqlite_backup(backup_data)
        self.assertTrue(validation["valid"])
        self.assertEqual(validation["transactions_count"], 2)

        # Thêm 1 giao dịch mới rồi khôi phục lại từ bản backup (phải quay về 2 giao dịch)
        self.store.add_transaction("2026-11-15", "expense", "Khác", 50_000, "Phát sinh")
        self.assertEqual(len(self.store.list_transactions()), 3)
        self.store.close()

        restore_res = restore_sqlite_backup(self.db_path, backup_data)
        self.assertEqual(restore_res["transactions_count"], 2)
        self.assertTrue(Path(str(restore_res["safety_backup"])).is_file())

        self.store = ExpenseStore(self.db_path)
        self.assertEqual(len(self.store.list_transactions()), 2)

    def test_ui_theme_toggle_and_studio_navigation(self):
        source = (
            "from pathlib import Path\n"
            "from expense_tracker.ui import run_app\n"
            f"run_app(Path({str(self.db_path)!r}), demo=True)\n"
        )
        app = AppTest.from_string(source, default_timeout=30).run()
        self.assertEqual(list(app.exception), [])

        # Mặc định Dark Mode -> bấm chuyển sang Light Mode rồi về Dark Mode
        app.button(key="toggle_theme_btn").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any(btn.label == "🌙 Dark Mode" for btn in app.button))

        app.button(key="toggle_theme_btn").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any(btn.label == "☀️ Light Mode" for btn in app.button))

        # Mở menu Radial nổi (Camera / Thư viện / Giọng nói / Đóng)
        app.button(key="cal_fab_camera").click().run()
        self.assertEqual(list(app.exception), [])
        self.assertTrue(any(btn.key == "rad_btn_cam" for btn in app.button))
        app.button(key="rad_btn_close").click().run()
        self.assertEqual(list(app.exception), [])

        # Mở từng studio (OCR, Voice Bottom-Sheet Modal, Assistant, Backup) và kiểm tra không có khối HTML/SVG nào bị thụt lề 4+ dấu cách
        for label in ("📸 Quét Hóa Đơn AI", "🎙️ Nhập Giọng Nói", "🤖 Trợ Lý AI", "💾 Sao Lưu & Cài Đặt", "📅 Lịch Tài Chính"):
            next(btn for btn in app.button if btn.label == label).click().run()
            self.assertEqual(list(app.exception), [])
            for idx, md_el in enumerate(app.markdown):
                if idx == 0:
                    continue
                val = md_el.value
                if "<div" in val or "<svg" in val:
                    self.assertNotIn("\n\n", val)
                    for line in val.splitlines():
                        self.assertFalse(line.startswith("    "), f"Phát hiện dòng HTML thụt lề 4 dấu cách tại {label}: {line[:60]}")

    def test_api_gateway_and_three_ai_pipelines_integration(self):
        self.store.add_transaction("2026-11-01", "income", "Gia đình hỗ trợ", 5_000_000, "Trợ cấp")
        self.store.add_transaction("2026-11-02", "expense", "Ăn uống", 85_000, "Cơm trưa")
        self.store.add_transaction("2026-11-03", "expense", "Đi lại", 50_000, "Đổ xăng")

        # Kiểm tra lưu cấu hình API vào file .env tạm
        temp_env = Path(self.directory.name) / ".env.test"
        save_ai_api_config(gemini_model="gemini-2.5-flash", env_path=temp_env)
        self.assertTrue(temp_env.is_file())

        diag = test_all_ai_pipelines(self.store, "2026-11")
        self.assertTrue(diag["ocr_pipeline"]["ok"])
        self.assertEqual(diag["ocr_pipeline"]["total_amount"], 43_000)
        self.assertTrue(diag["voice_pipeline"]["ok"])
        self.assertEqual(diag["voice_pipeline"]["parsed_amount"], 45_000)
        self.assertTrue(diag["analysis_pipeline"]["ok"])

        deep_review = generate_ai_deep_financial_review(self.store, "2026-11")
        self.assertTrue(bool(deep_review["overview"]))
        self.assertGreaterEqual(len(deep_review["action_plan"]), 1)


if __name__ == "__main__":
    unittest.main()
