"""Kiểm thử toàn diện hệ thống Tesseract OCR 5.x + Google Gemini API (expense_tracker/ocr_pipeline.py).

Bao phủ đầy đủ 11 kịch bản bắt buộc trong Mục 10:
1. Hóa đơn tiếng Việt (phân biệt ngày in vs ngày mua, bỏ qua SĐT/mã hóa đơn)
2. Hóa đơn tiếng Anh
3. Hóa đơn có VAT (phân biệt tiền hàng subtotal, thuế VAT và tổng thanh toán)
4. Hóa đơn nhiều mặt hàng
5. Hóa đơn có tổng tiền lớn
6. Hóa đơn ảnh mờ & ảnh sai định dạng
7. Hóa đơn bị xoay (tiền xử lý xoay chiều, Grayscale, khử nhiễu, CLAHE)
8. Hóa đơn thiếu ngày (trả về None, không tự tạo ngày)
9. Hóa đơn thiếu tổng tiền (trả về None, không tự bịa số tiền)
10. Gemini lỗi (chưa đồng ý gửi dữ liệu, API key sai, hết quota 429, mất mạng, JSON lỗi)
11. Tesseract OCR lỗi (không tìm thấy tesseract.exe, thiếu vie.traineddata, OCR rỗng)
"""

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

import cv2
import numpy as np
from PIL import Image, ImageDraw
import pytesseract
import requests

from expense_tracker.ocr_pipeline import (
    ALLOWED_GEMINI_CATEGORIES,
    GeminiReceiptSchema,
    analyze_ocr_text_with_gemini,
    analyze_receipt_image_with_gemini,
    check_tesseract_status,
    clear_ocr_and_gemini_cache,
    extract_structured_receipt_from_ocr_text,
    map_gemini_category_to_storage,
    preprocess_receipt_image,
    run_tesseract_ocr,
    validate_receipt_image,
)


def _make_test_image_bytes(
    width: int = 400,
    height: int = 600,
    sharp: bool = True,
    fmt: str = "PNG",
) -> bytes:
    """Tạo ảnh hóa đơn thử nghiệm trong bộ nhớ (sắc nét hoặc làm mờ Gaussian)."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    if sharp:
        for y in range(30, height - 30, 24):
            draw.rectangle([30, y, width - 30, y + 6], fill=(15, 15, 15))
            for x in range(40, width - 40, 18):
                draw.rectangle([x, y - 4, x + 8, y + 10], fill=(0, 0, 0))
    else:
        # Ảnh đồng nhất độ tương phản cực thấp -> phương sai Laplacian ~ 0 (bị mờ)
        draw.rectangle([50, 50, width - 50, height - 50], fill=(240, 240, 240))
        np_arr = cv2.GaussianBlur(np.array(img), (31, 31), 15)
        img = Image.fromarray(np_arr)

    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class OCRPipelineTests(unittest.TestCase):
    def setUp(self):
        clear_ocr_and_gemini_cache()
        self.addCleanup(clear_ocr_and_gemini_cache)

    # 1. Hóa đơn tiếng Việt
    def test_vietnamese_receipt_distinguishes_print_date_and_ignores_phone(self):
        text = """
        SIÊU THỊ MINI UNIMART
        Hotline: 0901234567 - Mã HĐ: 0987654321
        Ngày in: 19/11/2026 18:30
        Ngày mua: 11/11/2026 12:15
        Nước suối 1 x 8.000 = 8.000
        Bánh mì 1 x 15.000 = 15.000
        Sữa tươi 1 x 20.000 = 20.000
        Tổng cộng: 43.000 đ
        Thanh toán: Ví MoMo
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertEqual(schema.merchant_name, "SIÊU THỊ MINI UNIMART")
        self.assertEqual(schema.transaction_date, "2026-11-11")
        self.assertEqual(schema.total_amount, 43_000)
        self.assertEqual(len(schema.items), 3)
        self.assertEqual(schema.payment_method, "Ví điện tử")
        self.assertIn(schema.suggested_category, ALLOWED_GEMINI_CATEGORIES)

    # 2. Hóa đơn tiếng Anh
    def test_english_receipt_extraction(self):
        text = """
        HIGHLANDS COFFEE STORE
        Order Date: 2026-11-15
        Phin Sua Da 1 x 39,000 = 39,000
        Banh Mi Que 2 x 19,000 = 38,000
        Subtotal: 77,000
        Grand Total: 77,000 VND
        Payment: Credit Card Visa
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertEqual(schema.merchant_name, "HIGHLANDS COFFEE STORE")
        self.assertEqual(schema.transaction_date, "2026-11-15")
        self.assertEqual(schema.subtotal, 77_000)
        self.assertEqual(schema.total_amount, 77_000)
        self.assertEqual(schema.suggested_category, "Ăn uống")
        self.assertEqual(schema.payment_method, "Thẻ ngân hàng")

    # 3. Hóa đơn có VAT (không nhầm tiền hàng với tổng thanh toán)
    def test_vat_receipt_separates_subtotal_tax_and_total(self):
        text = """
        NHÀ SÁCH FAHASA QUẬN 1
        Ngày giao dịch: 14/11/2026
        Giáo trình Cấu trúc dữ liệu 1 x 150.000 = 150.000
        Vở sinh viên 5 x 10.000 = 50.000
        Cộng tiền hàng: 200.000
        Thuế GTGT (VAT 8%): 16.000
        Tổng thanh toán: 216.000 đ
        Tiền khách đưa: 500.000
        Tiền thừa: 284.000
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertEqual(schema.subtotal, 200_000)
        self.assertEqual(schema.tax_amount, 16_000)
        self.assertEqual(schema.total_amount, 216_000)
        self.assertEqual(schema.suggested_category, "Học tập")
        self.assertEqual(map_gemini_category_to_storage(schema.suggested_category), "Học tập")

    # 4. Hóa đơn nhiều mặt hàng
    def test_multi_item_receipt_parses_all_items(self):
        lines = ["BÁCH HÓA XANH", "Ngày mua: 10/11/2026"]
        expected_total = 0
        for idx in range(1, 9):
            price = idx * 12_000
            expected_total += price
            lines.append(f"Mặt hàng thiết yếu {idx} 1 x {price:,} = {price:,}".replace(",", "."))
        lines.append(f"Tổng cộng: {expected_total:,} đ".replace(",", "."))
        schema = extract_structured_receipt_from_ocr_text("\n".join(lines))
        self.assertEqual(len(schema.items), 8)
        self.assertEqual(schema.total_amount, expected_total)

    # 5. Hóa đơn có tổng tiền lớn
    def test_large_total_amount_receipt(self):
        text = """
        TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI
        Ngày giao dịch: 05/11/2026
        Học phí học kỳ I năm học 2026-2027 1 x 18.500.000 = 18.500.000
        Tổng thanh toán: 18.500.000 đ
        Chuyển khoản VietQR
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertEqual(schema.total_amount, 18_500_000)
        self.assertEqual(schema.payment_method, "Chuyển khoản / QR")

    # 6. Hóa đơn ảnh mờ & ảnh sai định dạng
    def test_blurry_and_invalid_image_validation(self):
        sharp_bytes = _make_test_image_bytes(sharp=True)
        sharp_val = validate_receipt_image(sharp_bytes, filename="receipt.png")
        self.assertTrue(sharp_val.valid)
        self.assertFalse(sharp_val.is_blurry)

        blurry_bytes = _make_test_image_bytes(sharp=False)
        blurry_val = validate_receipt_image(blurry_bytes, filename="blurry.png")
        self.assertTrue(blurry_val.valid)
        self.assertTrue(blurry_val.is_blurry)
        self.assertTrue(any("mờ" in w for w in blurry_val.warnings))

        bad_ext = validate_receipt_image(sharp_bytes, filename="virus.exe")
        self.assertFalse(bad_ext.valid)
        self.assertEqual(bad_ext.error_code, "INVALID_EXTENSION")

        corrupted = validate_receipt_image(b"not-an-image-content", filename="bad.jpg")
        self.assertFalse(corrupted.valid)
        self.assertEqual(corrupted.error_code, "CORRUPTED_OR_INVALID_IMAGE")

    # 7. Hóa đơn bị xoay
    def test_rotated_image_preprocessing(self):
        rect_bytes = _make_test_image_bytes(width=320, height=560, sharp=True)
        proc_bytes, meta = preprocess_receipt_image(rect_bytes, rotate_degrees=90)
        self.assertTrue(proc_bytes.startswith(b"\x89PNG"))
        self.assertEqual(meta["rotated_degrees"], 90)
        with Image.open(io.BytesIO(proc_bytes)) as out_img:
            out_w, out_h = out_img.size
            self.assertGreater(out_w, out_h)

    # 8. Hóa đơn thiếu ngày (trả về None, không tự tạo ngày)
    def test_receipt_missing_date_returns_null(self):
        text = """
        QUÁN CƠM SINH VIÊN
        Cơm sườn nướng 1 x 35.000 = 35.000
        Tổng thanh toán: 35.000 đ
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertIsNone(schema.transaction_date)
        self.assertEqual(schema.total_amount, 35_000)
        self.assertTrue(any("ngày" in w.lower() for w in schema.warnings))

    # 9. Hóa đơn thiếu tổng tiền (trả về None, không lấy SĐT làm số tiền)
    def test_receipt_missing_total_returns_null(self):
        text = """
        CỬA HÀNG TIỆN LỢI
        SĐT: 0912345678
        Ngày mua: 18/11/2026
        Cảm ơn quý khách hẹn gặp lại
        """
        schema = extract_structured_receipt_from_ocr_text(text)
        self.assertEqual(schema.transaction_date, "2026-11-18")
        self.assertIsNone(schema.total_amount)
        self.assertTrue(any("tổng thanh toán" in w.lower() for w in schema.warnings))

    # 10. Xử lý lỗi Gemini (Consent, Invalid Key, Quota, Network, Invalid JSON)
    def test_gemini_error_handling_and_privacy_consent_gate(self):
        sample_ocr = "QUÁN PHỞ\nNgày mua: 19/11/2026\nPhở bò 1 x 45.000 = 45.000\nTổng cộng: 45.000 đ"

        # Chưa đồng ý gửi dữ liệu -> không gọi API bên ngoài, dùng bộ bóc tách local
        res_no_consent = analyze_ocr_text_with_gemini(sample_ocr, user_consent=False)
        self.assertEqual(res_no_consent.error_code, "CONSENT_REQUIRED")
        self.assertEqual(res_no_consent.schema_data.total_amount, 45_000)

        # Gửi ảnh khi chưa đồng ý -> từ chối
        img_bytes = _make_test_image_bytes()
        img_no_consent = analyze_receipt_image_with_gemini(img_bytes, user_consent=False)
        self.assertFalse(img_no_consent.success)
        self.assertEqual(img_no_consent.error_code, "IMAGE_CONSENT_REQUIRED")

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-test-key", "GEMINI_MODEL": "gemini-2.5-flash"}):
            # Lỗi API Key không hợp lệ (401/403)
            with patch("google.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.models.generate_content.side_effect = RuntimeError("403 API_KEY_INVALID")
                clear_ocr_and_gemini_cache()
                res_bad_key = analyze_ocr_text_with_gemini(sample_ocr, user_consent=True)
                self.assertFalse(res_bad_key.success)
                self.assertEqual(res_bad_key.error_code, "GEMINI_INVALID_KEY")
                # Vẫn bảo toàn kết quả OCR local để người dùng sửa thủ công
                self.assertEqual(res_bad_key.schema_data.total_amount, 45_000)

            # Lỗi hết hạn mức Quota (429)
            with patch("google.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.models.generate_content.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED quota")
                clear_ocr_and_gemini_cache()
                res_quota = analyze_ocr_text_with_gemini(sample_ocr, user_consent=True)
                self.assertFalse(res_quota.success)
                self.assertEqual(res_quota.error_code, "GEMINI_QUOTA_EXCEEDED")

            # Lỗi mất kết nối mạng
            with patch("google.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.models.generate_content.side_effect = requests.ConnectionError("Network unreachable")
                clear_ocr_and_gemini_cache()
                res_net = analyze_ocr_text_with_gemini(sample_ocr, user_consent=True)
                self.assertFalse(res_net.success)
                self.assertEqual(res_net.error_code, "GEMINI_NETWORK_ERROR")

            # Lỗi Gemini trả về JSON không hợp lệ
            with patch("google.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.models.generate_content.return_value.text = "Đây không phải JSON"
                clear_ocr_and_gemini_cache()
                res_bad_json = analyze_ocr_text_with_gemini(sample_ocr, user_consent=True)
                self.assertFalse(res_bad_json.success)
                self.assertEqual(res_bad_json.error_code, "GEMINI_INVALID_JSON")
                self.assertEqual(res_bad_json.schema_data.total_amount, 45_000)

            # Gemini trả về JSON hợp lệ nhưng thiếu dữ liệu + danh mục lạ -> Pydantic chuẩn hóa an toàn
            with patch("google.genai.Client") as mock_client_cls:
                mock_client_cls.return_value.models.generate_content.return_value.text = """
                ```json
                {
                  "merchant_name": "Siêu thị Mini",
                  "transaction_date": null,
                  "total_amount": 43000,
                  "subtotal": 43000,
                  "tax_amount": null,
                  "currency": "VND",
                  "items": [{"name": "Sữa tươi", "qty": 1, "unit_price": 43000, "line_total": 43000}],
                  "suggested_category": "Danh mục không tồn tại",
                  "description": "Mua sữa",
                  "payment_method": "Tiền mặt",
                  "confidence": 88,
                  "warnings": []
                }
                ```
                """
                clear_ocr_and_gemini_cache()
                res_ok = analyze_ocr_text_with_gemini(sample_ocr, user_consent=True)
                self.assertTrue(res_ok.success)
                self.assertEqual(res_ok.schema_data.merchant_name, "Siêu thị Mini")
                self.assertIsNone(res_ok.schema_data.transaction_date)
                self.assertEqual(res_ok.schema_data.total_amount, 43_000)
                self.assertEqual(res_ok.schema_data.suggested_category, "Khác")
                self.assertTrue(any("transaction_date" in w for w in res_ok.schema_data.warnings))

    # 11. Xử lý lỗi Tesseract OCR (Thiếu binary, thiếu vie.traineddata, kết quả rỗng)
    def test_tesseract_error_handling_never_fakes_result(self):
        img_bytes = _make_test_image_bytes(sharp=True)

        # Trường hợp không tìm thấy tesseract.exe
        with patch("expense_tracker.ocr_pipeline.resolve_tesseract_cmd", return_value=r"C:\nonexistent\tesseract.exe"):
            status_missing = check_tesseract_status()
            self.assertFalse(status_missing.available)
            self.assertEqual(status_missing.error_code, "TESSERACT_NOT_FOUND")

            clear_ocr_and_gemini_cache()
            ocr_missing = run_tesseract_ocr(img_bytes)
            self.assertFalse(ocr_missing.success)
            self.assertEqual(ocr_missing.error_code, "TESSERACT_NOT_FOUND")
            self.assertEqual(ocr_missing.raw_text, "")

        # Trường hợp có Tesseract nhưng thiếu file vie.traineddata
        with patch("expense_tracker.ocr_pipeline.check_tesseract_status") as mock_status:
            mock_status.return_value.available = True
            mock_status.return_value.has_vie = False
            mock_status.return_value.error_code = "MISSING_VIE_TRAINEDDATA"
            mock_status.return_value.message = "Thiếu file vie.traineddata"
            clear_ocr_and_gemini_cache()
            ocr_no_vie = run_tesseract_ocr(img_bytes, lang="vie+eng")
            self.assertFalse(ocr_no_vie.success)
            self.assertEqual(ocr_no_vie.error_code, "MISSING_VIE_TRAINEDDATA")
            self.assertEqual(ocr_no_vie.raw_text, "")

        # Trường hợp Tesseract chạy nhưng không nhận diện được chữ nào (rỗng)
        with patch("expense_tracker.ocr_pipeline.check_tesseract_status") as mock_status, \
             patch("pytesseract.image_to_string", return_value="   \n  "):
            mock_status.return_value.available = True
            mock_status.return_value.has_vie = True
            clear_ocr_and_gemini_cache()
            ocr_empty = run_tesseract_ocr(img_bytes, lang="vie+eng")
            self.assertFalse(ocr_empty.success)
            self.assertEqual(ocr_empty.error_code, "EMPTY_OCR_RESULT")
            self.assertEqual(ocr_empty.raw_text, "")


if __name__ == "__main__":
    unittest.main()
