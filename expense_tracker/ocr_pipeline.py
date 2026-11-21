"""Hệ thống nhận diện hóa đơn bằng Tesseract OCR 5.x kết hợp Google Gemini API cho UniSpend 2.0.

Quy trình 9 bước chuẩn kỹ thuật:
1. Tiếp nhận ảnh chụp hoặc tải lên.
2. Kiểm tra định dạng (JPG/JPEG/PNG/WEBP/BMP), dung lượng, kích thước, độ mờ (Laplacian variance).
3. Tiền xử lý ảnh bằng Pillow + OpenCV: xoay đúng chiều (EXIF & góc xoay), chuẩn hóa kích thước,
   chuyển Grayscale, khử nhiễu (Denoise) và tăng tương phản cục bộ (CLAHE).
4. Chạy Tesseract OCR cục bộ với ngôn ngữ `vie+eng` (kiểm tra `tesseract.exe` và `vie.traineddata`).
5. Gửi văn bản OCR (hoặc ảnh khi người dùng bật tùy chọn & đồng ý) lên Google Gemini API.
6. Nhận kết quả JSON từ Gemini theo đúng cấu trúc chuẩn.
7. Kiểm tra và chuẩn hóa dữ liệu bằng Pydantic Schema (`GeminiReceiptSchema`).
8. Trả kết quả cùng danh sách `warnings` cho giao diện để người dùng kiểm tra / chỉnh sửa.
9. Chỉ lưu vào SQLite khi người dùng nhấn nút Xác nhận.

Nguyên tắc an toàn & trung thực:
- Không tự bịa tên cửa hàng, ngày giao dịch hay số tiền khi OCR/AI không đọc được (`null`).
- Không lấy số điện thoại hoặc mã hóa đơn làm số tiền.
- Phân biệt ngày in hóa đơn với ngày giao dịch và tiền hàng (`subtotal`) với tổng thanh toán (`total_amount`).
- Không gửi dữ liệu ra dịch vụ Gemini bên ngoài khi chưa có sự đồng ý (`user_consent=True`).
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import date as Date
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, ValidationError, field_validator
import pytesseract
import requests

from .ai_service import check_api_status, load_env_file
from .storage import EXPENSE_CATEGORIES, MAX_AMOUNT


ALLOWED_GEMINI_CATEGORIES: tuple[str, ...] = (
    "Ăn uống",
    "Di chuyển",
    "Mua sắm",
    "Học tập",
    "Hóa đơn",
    "Giải trí",
    "Sức khỏe",
    "Khác",
)

SUPPORTED_IMAGE_FORMATS: tuple[str, ...] = ("JPEG", "JPG", "PNG", "WEBP", "BMP")
MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
BLUR_VARIANCE_THRESHOLD: float = 45.0

# Bộ nhớ đệm trong phiên để tránh gọi lại Tesseract hoặc Gemini nhiều lần cho cùng một hóa đơn
_OCR_TEXT_CACHE: dict[str, "TesseractOCRResult"] = {}
_GEMINI_PARSE_CACHE: dict[str, "GeminiAnalysisResult"] = {}


def clear_ocr_and_gemini_cache() -> int:
    """Xóa bộ nhớ đệm OCR và ảnh tạm sau khi hoàn thành hoặc hủy thao tác."""
    count = len(_OCR_TEXT_CACHE) + len(_GEMINI_PARSE_CACHE)
    _OCR_TEXT_CACHE.clear()
    _GEMINI_PARSE_CACHE.clear()
    root = Path(__file__).resolve().parent.parent
    for temp_dir in (root / "data" / "ocr_cache", root / "data" / "temp_receipts"):
        if temp_dir.is_dir():
            shutil.rmtree(temp_dir, ignore_errors=True)
    return count


def map_gemini_category_to_storage(suggested_category: str | None) -> str:
    """Ánh xạ danh mục gợi ý 8 nhóm của Gemini sang 6 danh mục lưu trữ của ExpenseStore."""
    cat = (suggested_category or "").strip()
    mapping = {
        "Ăn uống": "Ăn uống",
        "Di chuyển": "Đi lại",
        "Đi lại": "Đi lại",
        "Học tập": "Học tập",
        "Hóa đơn": "Tiền trọ",
        "Tiền trọ": "Tiền trọ",
        "Giải trí": "Giải trí",
        "Mua sắm": "Khác",
        "Sức khỏe": "Khác",
        "Khác": "Khác",
    }
    mapped = mapping.get(cat, "Khác")
    return mapped if mapped in EXPENSE_CATEGORIES else "Khác"


# =============================================================================
# 1. PYDANTIC SCHEMA KIỂM TRA DỮ LIỆU JSON TỪ GEMINI (SECTION 5 & 6)
# =============================================================================
def _looks_like_phone_or_code(num_val: int, raw_context: str = "") -> bool:
    """Loại trừ số điện thoại (10-11 số bắt đầu bằng 0 hoặc 84) hoặc mã số quá lớn."""
    if num_val <= 0 or num_val > MAX_AMOUNT:
        return True
    s = str(num_val)
    if len(s) in (9, 10, 11) and num_val % 100 != 0:
        return True
    return False


def _normalize_date_str(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s.lower() in ("null", "none", "n/a", "unknown"):
        return None
    m_iso = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s)
    if m_iso:
        y, mo, d = map(int, m_iso.groups())
        try:
            return Date(y, mo, d).isoformat()
        except ValueError:
            return None
    m_dmy = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", s)
    if m_dmy:
        d, mo, y = map(int, m_dmy.groups())
        try:
            return Date(y, mo, d).isoformat()
        except ValueError:
            return None
    m_ymd_slash = re.search(r"\b(\d{4})/(\d{1,2})/(\d{1,2})\b", s)
    if m_ymd_slash:
        y, mo, d = map(int, m_ymd_slash.groups())
        try:
            return Date(y, mo, d).isoformat()
        except ValueError:
            return None
    return None


def _coerce_optional_vnd_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if (0 < value <= MAX_AMOUNT and not _looks_like_phone_or_code(value)) else None
    if isinstance(value, float):
        if not np.isfinite(value):
            return None
        iv = int(round(value))
        return iv if (0 < iv <= MAX_AMOUNT and not _looks_like_phone_or_code(iv)) else None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", "n/a"):
        return None
    cleaned = re.sub(r"[^\d.,-]", "", s)
    if not cleaned or cleaned.startswith("-"):
        return None
    if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", cleaned):
        digits = re.sub(r"[.,]", "", cleaned)
        iv = int(digits)
        return iv if (0 < iv <= MAX_AMOUNT and not _looks_like_phone_or_code(iv)) else None
    try:
        iv = int(round(float(cleaned.replace(",", "."))))
        return iv if (0 < iv <= MAX_AMOUNT and not _looks_like_phone_or_code(iv)) else None
    except ValueError:
        return None


class ReceiptLineItemSchema(BaseModel):
    name: str
    qty: int = 1
    unit_price: int | None = None
    line_total: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _clean_name(cls, v: Any) -> str:
        s = str(v or "").strip()
        return s[:120] if s else "Mặt hàng"

    @field_validator("qty", mode="before")
    @classmethod
    def _clean_qty(cls, v: Any) -> int:
        try:
            q = int(round(float(v)))
            return max(1, min(9999, q))
        except Exception:
            return 1

    @field_validator("unit_price", "line_total", mode="before")
    @classmethod
    def _clean_price(cls, v: Any) -> int | None:
        return _coerce_optional_vnd_int(v)


class GeminiReceiptSchema(BaseModel):
    """Schema chuẩn kiểm tra kết quả phân tích hóa đơn từ Gemini API."""

    merchant_name: str | None = None
    transaction_date: str | None = None
    total_amount: int | None = None
    subtotal: int | None = None
    tax_amount: int | None = None
    currency: str = "VND"
    items: list[ReceiptLineItemSchema] = Field(default_factory=list)
    suggested_category: str | None = None
    description: str | None = None
    payment_method: str | None = None
    confidence: int = 0
    warnings: list[str] = Field(default_factory=list)

    @field_validator("merchant_name", "description", "payment_method", mode="before")
    @classmethod
    def _clean_optional_text(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in ("null", "none", "n/a", "unknown", "không rõ"):
            return None
        return s[:160]

    @field_validator("transaction_date", mode="before")
    @classmethod
    def _validate_tx_date(cls, v: Any) -> str | None:
        return _normalize_date_str(v)

    @field_validator("total_amount", "subtotal", "tax_amount", mode="before")
    @classmethod
    def _validate_amounts(cls, v: Any) -> int | None:
        return _coerce_optional_vnd_int(v)

    @field_validator("currency", mode="before")
    @classmethod
    def _validate_currency(cls, v: Any) -> str:
        s = str(v or "VND").strip().upper()
        return s if s in ("VND", "VNĐ", "USD") else "VND"

    @field_validator("suggested_category", mode="before")
    @classmethod
    def _validate_category(cls, v: Any) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s or s.lower() in ("null", "none"):
            return None
        if s in ALLOWED_GEMINI_CATEGORIES:
            return s
        alias_map = {
            "đi lại": "Di chuyển",
            "di chuyển": "Di chuyển",
            "tiền trọ": "Hóa đơn",
            "nhà cửa": "Hóa đơn",
            "điện nước": "Hóa đơn",
            "ăn uống": "Ăn uống",
            "thực phẩm": "Ăn uống",
            "mua sắm": "Mua sắm",
            "siêu thị": "Mua sắm",
            "học tập": "Học tập",
            "giải trí": "Giải trí",
            "sức khỏe": "Sức khỏe",
            "y tế": "Sức khỏe",
        }
        return alias_map.get(s.casefold(), "Khác")

    @field_validator("confidence", mode="before")
    @classmethod
    def _validate_confidence(cls, v: Any) -> int:
        try:
            f = float(v)
            if 0.0 < f <= 1.0:
                f *= 100.0
            return max(0, min(100, int(round(f))))
        except Exception:
            return 0

    @field_validator("warnings", mode="before")
    @classmethod
    def _validate_warnings(cls, v: Any) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [v.strip()] if v.strip() else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []


# =============================================================================
# 2. KIỂM TRA ẢNH & TIỀN XỬ LÝ ẢNH (PILLOW + OPENCV) (SECTION 4 - BƯỚC 2 & 3)
# =============================================================================
@dataclass
class ImageValidationResult:
    valid: bool
    format: str = ""
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    blur_score: float = 0.0
    is_blurry: bool = False
    error_code: str = ""
    error_message: str = ""
    warnings: list[str] = field(default_factory=list)


def validate_receipt_image(
    image_bytes: bytes | None,
    filename: str = "",
    max_bytes: int = MAX_IMAGE_SIZE_BYTES,
) -> ImageValidationResult:
    """Bước 2: Kiểm tra định dạng, dung lượng, tính hợp lệ, kích thước và độ mờ của ảnh."""
    if not image_bytes:
        return ImageValidationResult(
            valid=False,
            error_code="EMPTY_IMAGE",
            error_message="Chưa có dữ liệu ảnh hóa đơn.",
        )

    size_bytes = len(image_bytes)
    if size_bytes > max_bytes:
        mb = size_bytes / (1024 * 1024)
        max_mb = max_bytes / (1024 * 1024)
        return ImageValidationResult(
            valid=False,
            size_bytes=size_bytes,
            error_code="IMAGE_TOO_LARGE",
            error_message=f"Dung lượng ảnh ({mb:.1f} MB) vượt quá giới hạn cho phép ({max_mb:.0f} MB).",
        )

    if filename:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext and ext not in ("jpg", "jpeg", "png", "webp", "bmp"):
            return ImageValidationResult(
                valid=False,
                size_bytes=size_bytes,
                error_code="INVALID_EXTENSION",
                error_message=f"Định dạng tệp '.{ext}' không được hỗ trợ. Chỉ chấp nhận JPG, JPEG, PNG, WEBP, BMP.",
            )

    try:
        with Image.open(io.BytesIO(image_bytes)) as probe_img:
            probe_img.verify()
        with Image.open(io.BytesIO(image_bytes)) as img:
            fmt = (img.format or "").upper()
            width, height = img.size
            rgb = img.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return ImageValidationResult(
            valid=False,
            size_bytes=size_bytes,
            error_code="CORRUPTED_OR_INVALID_IMAGE",
            error_message=f"Tệp ảnh không hợp lệ hoặc bị hỏng: {exc}",
        )

    if fmt and fmt not in SUPPORTED_IMAGE_FORMATS:
        return ImageValidationResult(
            valid=False,
            format=fmt,
            width=width,
            height=height,
            size_bytes=size_bytes,
            error_code="UNSUPPORTED_FORMAT",
            error_message=f"Định dạng ảnh '{fmt}' không được hỗ trợ (hỗ trợ JPG, JPEG, PNG).",
        )

    if width < 60 or height < 60:
        return ImageValidationResult(
            valid=False,
            format=fmt,
            width=width,
            height=height,
            size_bytes=size_bytes,
            error_code="IMAGE_TOO_SMALL",
            error_message=f"Kích thước ảnh quá nhỏ ({width}x{height}px), không đủ độ phân giải để đọc chữ.",
        )

    # Tính độ sắc nét bằng phương sai Laplacian (OpenCV)
    np_rgb = np.array(rgb)
    gray = cv2.cvtColor(np_rgb, cv2.COLOR_RGB2GRAY)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    is_blurry = blur_score < BLUR_VARIANCE_THRESHOLD

    warnings: list[str] = []
    if is_blurry:
        warnings.append(
            f"Ảnh hóa đơn có độ nét thấp / bị mờ (chỉ số nét {blur_score:.1f} < {BLUR_VARIANCE_THRESHOLD:.0f}). "
            "Nên chụp lại nơi đủ sáng hoặc kiểm tra kỹ các số tiền sau khi nhận diện."
        )

    return ImageValidationResult(
        valid=True,
        format=fmt or "JPEG",
        width=width,
        height=height,
        size_bytes=size_bytes,
        blur_score=round(blur_score, 2),
        is_blurry=is_blurry,
        warnings=warnings,
    )


def enhance_receipt_image_color(
    image_bytes: bytes,
    rotate_degrees: int = 0,
    target_min_dim: int = 1500,
    max_dimension: int = 2200,
) -> bytes:
    """Làm nét ảnh màu hóa đơn (phóng đại ảnh nhỏ + tăng nét Unsharp Mask + cân bằng sáng CLAHE)
    để hiển thị preview rõ nét và gửi Gemini Vision đọc chữ chính xác nhất.
    """
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        img = ImageOps.exif_transpose(raw_img)
        if rotate_degrees % 360 != 0:
            img = img.rotate(-rotate_degrees, expand=True)
        rgb = img.convert("RGB")

    np_img = np.array(rgb)
    h, w = np_img.shape[:2]
    max_side = max(w, h)
    if max_side > max_dimension:
        scale = max_dimension / float(max_side)
        np_img = cv2.resize(np_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    elif max_side < target_min_dim:
        scale = min(2.6, float(target_min_dim) / float(max_side))
        np_img = cv2.resize(np_img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Tăng tương phản nhẹ kênh độ sáng L trong không gian LAB (giữ màu trung thực)
    lab = cv2.cvtColor(np_img, cv2.COLOR_RGB2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    l_eq = clahe.apply(l_ch)
    merged = cv2.cvtColor(cv2.merge((l_eq, a_ch, b_ch)), cv2.COLOR_LAB2RGB)

    # Unsharp masking để chữ nhỏ trên giấy nhiệt sắc nét hẳn
    blurred = cv2.GaussianBlur(merged, (0, 0), sigmaX=1.2)
    sharpened = cv2.addWeighted(merged, 1.55, blurred, -0.55, 0)

    out_buf = io.BytesIO()
    Image.fromarray(sharpened).save(out_buf, format="JPEG", quality=93)
    return out_buf.getvalue()


def preprocess_receipt_image(
    image_bytes: bytes,
    rotate_degrees: int = 0,
    max_dimension: int = 2000,
) -> tuple[bytes, dict[str, Any]]:
    """Bước 3: Tiền xử lý ảnh hóa đơn trước khi đưa vào Tesseract OCR:
    - Xoay đúng chiều EXIF + góc xoay tùy chỉnh (90/180/270 độ)
    - Phóng đại thông minh ảnh nhỏ (600x600 -> ~1500px) bằng INTER_CUBIC
    - Chuyển Grayscale + CLAHE tăng tương phản + Unsharp Mask làm sắc nét biên chữ
    """
    with Image.open(io.BytesIO(image_bytes)) as raw_img:
        img = ImageOps.exif_transpose(raw_img)
        if rotate_degrees % 360 != 0:
            img = img.rotate(-rotate_degrees, expand=True)
        rgb = img.convert("RGB")
        orig_w, orig_h = rgb.size

    np_img = np.array(rgb)
    gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)

    # Điều chỉnh kích thước để chữ hóa đơn đạt độ cao lý tưởng cho Tesseract 5.x
    h, w = gray.shape[:2]
    scale = 1.0
    if max(w, h) > max_dimension:
        scale = max_dimension / float(max(w, h))
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    elif max(w, h) < 1200:
        scale = min(2.5, 1500.0 / float(max(w, h)))
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    # Tăng tương phản cục bộ CLAHE + Unsharp Mask làm nét biên chữ (không làm mờ chữ nhỏ)
    clahe = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8))
    contrasted = clahe.apply(gray)
    soft_blur = cv2.GaussianBlur(contrasted, (0, 0), sigmaX=1.1)
    sharpened = cv2.addWeighted(contrasted, 1.6, soft_blur, -0.6, 0)

    processed_pil = Image.fromarray(sharpened)
    out_buf = io.BytesIO()
    processed_pil.save(out_buf, format="PNG")
    meta = {
        "original_size": (orig_w, orig_h),
        "processed_size": processed_pil.size,
        "rotated_degrees": rotate_degrees % 360,
        "scale_factor": round(scale, 2),
    }
    return out_buf.getvalue(), meta


# =============================================================================
# 3. TESSERACT OCR 5.X ENGINE (VIE+ENG) (SECTION 4 - BƯỚC 4 & SECTION 8)
# =============================================================================
@dataclass
class TesseractStatus:
    available: bool
    binary_path: str
    version: str
    languages: list[str]
    has_vie: bool
    has_eng: bool
    error_code: str = ""
    message: str = ""


def resolve_tesseract_cmd() -> str:
    """Xác định đường dẫn tesseract.exe từ biến môi trường TESSERACT_CMD hoặc đường dẫn cài đặt chuẩn."""
    load_env_file()
    configured = (os.environ.get("TESSERACT_CMD") or "").strip().strip('"').strip("'")
    candidates = []
    if configured:
        candidates.append(configured)
    candidates.extend([
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    ])
    which_tess = shutil.which("tesseract")
    if which_tess:
        candidates.append(which_tess)

    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            pytesseract.pytesseract.tesseract_cmd = str(Path(candidate))
            return str(Path(candidate))

    default_path = configured or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    pytesseract.pytesseract.tesseract_cmd = default_path
    return default_path


def check_tesseract_status() -> TesseractStatus:
    """Kiểm tra cài đặt Tesseract OCR 5.x và gói ngôn ngữ vie.traineddata / eng.traineddata."""
    cmd_path = resolve_tesseract_cmd()
    if not Path(cmd_path).is_file():
        return TesseractStatus(
            available=False,
            binary_path=cmd_path,
            version="",
            languages=[],
            has_vie=False,
            has_eng=False,
            error_code="TESSERACT_NOT_FOUND",
            message=(
                f"Không tìm thấy Tesseract OCR tại '{cmd_path}'. "
                "Vui lòng cài đặt Tesseract OCR 5.x (UB-Mannheim cho Windows) kèm gói ngôn ngữ 'vie' và 'eng', "
                "hoặc cấu hình đúng đường dẫn TESSERACT_CMD trong file .env."
            ),
        )
    try:
        version_str = str(pytesseract.get_tesseract_version())
        langs = [lang.lower() for lang in pytesseract.get_languages(config="")]
        has_vie = "vie" in langs
        has_eng = "eng" in langs
        if not has_vie:
            return TesseractStatus(
                available=True,
                binary_path=cmd_path,
                version=version_str,
                languages=langs,
                has_vie=False,
                has_eng=has_eng,
                error_code="MISSING_VIE_TRAINEDDATA",
                message=(
                    f"Đã tìm thấy Tesseract {version_str} nhưng thiếu file ngôn ngữ tiếng Việt 'vie.traineddata' "
                    f"trong thư mục tessdata (các ngôn ngữ hiện có: {', '.join(langs) or 'không có'})."
                ),
            )
        return TesseractStatus(
            available=True,
            binary_path=cmd_path,
            version=version_str,
            languages=langs,
            has_vie=has_vie,
            has_eng=has_eng,
            error_code="",
            message=f"Tesseract OCR {version_str} sẵn sàng (hỗ trợ vie+eng).",
        )
    except Exception as exc:
        return TesseractStatus(
            available=False,
            binary_path=cmd_path,
            version="",
            languages=[],
            has_vie=False,
            has_eng=False,
            error_code="TESSERACT_EXEC_ERROR",
            message=f"Không khởi chạy được Tesseract OCR tại '{cmd_path}': {exc}",
        )


@dataclass
class TesseractOCRResult:
    success: bool
    raw_text: str
    language_used: str
    preprocessed_image: bytes | None = None
    validation: ImageValidationResult | None = None
    error_code: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)


def run_tesseract_ocr(
    image_bytes: bytes,
    *,
    filename: str = "",
    rotate_degrees: int = 0,
    preprocess: bool = True,
    lang: str = "vie+eng",
) -> TesseractOCRResult:
    """Bước 4: Kiểm tra ảnh -> Tiền xử lý -> Trích xuất văn bản bằng Tesseract OCR (vie+eng).
    Tuyệt đối không giả lập văn bản OCR khi Tesseract chưa cài hoặc không đọc được chữ.
    """
    validation = validate_receipt_image(image_bytes, filename=filename)
    if not validation.valid:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=lang,
            validation=validation,
            error_code=validation.error_code,
            message=validation.error_message,
            warnings=list(validation.warnings),
        )

    cache_key = hashlib.sha256(
        image_bytes + f"|rot={rotate_degrees}|pre={preprocess}|lang={lang}".encode("utf-8")
    ).hexdigest()
    if cache_key in _OCR_TEXT_CACHE:
        return _OCR_TEXT_CACHE[cache_key]

    try:
        if preprocess or rotate_degrees % 360 != 0:
            proc_bytes, _ = preprocess_receipt_image(image_bytes, rotate_degrees=rotate_degrees)
        else:
            proc_bytes = image_bytes
    except Exception as exc:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=lang,
            validation=validation,
            error_code="PREPROCESS_ERROR",
            message=f"Lỗi tiền xử lý ảnh hóa đơn: {exc}",
            warnings=list(validation.warnings),
        )

    tess_status = check_tesseract_status()
    if not tess_status.available:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code=tess_status.error_code or "TESSERACT_NOT_FOUND",
            message=tess_status.message,
            warnings=list(validation.warnings),
        )

    warnings = list(validation.warnings)
    effective_lang = lang
    if "vie" in lang and not tess_status.has_vie:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code="MISSING_VIE_TRAINEDDATA",
            message=tess_status.message,
            warnings=warnings,
        )

    try:
        with Image.open(io.BytesIO(proc_bytes)) as pil_img:
            extracted = pytesseract.image_to_string(
                pil_img,
                lang=effective_lang,
                config="--oem 3 --psm 6",
            )
    except pytesseract.TesseractNotFoundError:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=effective_lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code="TESSERACT_NOT_FOUND",
            message=f"Không tìm thấy tệp thực thi Tesseract tại '{tess_status.binary_path}'.",
            warnings=warnings,
        )
    except pytesseract.TesseractError as exc:
        err_str = str(exc)
        code = "MISSING_VIE_TRAINEDDATA" if "vie" in err_str.lower() else "TESSERACT_RUNTIME_ERROR"
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=effective_lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code=code,
            message=f"Lỗi khi chạy Tesseract OCR: {err_str}",
            warnings=warnings,
        )
    except Exception as exc:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=effective_lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code="OCR_UNEXPECTED_ERROR",
            message=f"Lỗi không xác định khi đọc OCR: {exc}",
            warnings=warnings,
        )

    cleaned_text = "\n".join(line.rstrip() for line in (extracted or "").splitlines() if line.strip()).strip()
    if not cleaned_text:
        return TesseractOCRResult(
            success=False,
            raw_text="",
            language_used=effective_lang,
            preprocessed_image=proc_bytes,
            validation=validation,
            error_code="EMPTY_OCR_RESULT",
            message="Tesseract OCR không nhận diện được chữ nào trên ảnh hóa đơn (ảnh có thể quá mờ hoặc không có văn bản).",
            warnings=warnings,
        )

    if len(cleaned_text) < 15:
        warnings.append("Văn bản OCR trích xuất được rất ngắn, một số thông tin trên hóa đơn có thể bị thiếu.")

    result = TesseractOCRResult(
        success=True,
        raw_text=cleaned_text,
        language_used=effective_lang,
        preprocessed_image=proc_bytes,
        validation=validation,
        error_code="",
        message="Tesseract OCR đã trích xuất văn bản thành công.",
        warnings=warnings,
    )
    _OCR_TEXT_CACHE[cache_key] = result
    return result


# =============================================================================
# 4. BỘ BÓC TÁCH HÓA ĐƠN CỤC BỘ (VIỆT + ANH + VAT) & GEMINI API (SECTION 5-9)
# =============================================================================
def _parse_money_token_strict(line: str) -> int | None:
    """Trích xuất số tiền VND từ một dòng hóa đơn, loại trừ số điện thoại, mã số thuế, mã hóa đơn và ngày tháng."""
    cleaned_line = re.sub(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", " ", line)
    cleaned_line = re.sub(r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", " ", cleaned_line)
    cleaned_line = re.sub(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?\b", " ", cleaned_line)
    # Loại trừ dòng chỉ chứa SĐT / Hotline / MST / Mã HD
    if re.search(r"\b(?:sdt|sđt|đt|tel|phone|hotline|mst|tax\s*id|mã\s*hđ|ma\s*hd|invoice\s*no|receipt\s*no)\b", cleaned_line, flags=re.IGNORECASE):
        if not re.search(r"\b(?:tổng|total|amount|thanh toán|thành tiền)\b", cleaned_line, flags=re.IGNORECASE):
            return None

    # Khớp số có phân nhóm nghìn chuẩn (VD: 43.000, 1.250.000, 1,250,000)
    grouped_matches = re.findall(r"(?<![\d.,])([1-9]\d{0,2}(?:[.,]\d{3})+)(?![\d.,])", cleaned_line)
    if grouped_matches:
        val = int(re.sub(r"[.,]", "", grouped_matches[-1]))
        if not _looks_like_phone_or_code(val):
            return val

    # Khớp hậu tố K / nghìn / ngàn (VD: 45k, 120 nghìn)
    k_match = re.findall(r"\b(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:k|nghìn|ngàn)\b", cleaned_line, flags=re.IGNORECASE)
    if k_match:
        val = int(round(float(k_match[-1].replace(",", ".")) * 1000))
        if 0 < val <= MAX_AMOUNT:
            return val

    # Khớp số nguyên VND trần (từ 1.000 đến 1.000.000.000.000, chia hết cho 100 hoặc 500)
    plain_matches = re.findall(r"(?<![\d/-])(\d{4,12})(?![\d/-])", cleaned_line)
    for token in reversed(plain_matches):
        if token.startswith("0"):
            continue
        val = int(token)
        if not _looks_like_phone_or_code(val) and val % 100 == 0:
            return val
    return None


def _infer_category_from_text(text: str) -> str:
    lower = text.casefold()
    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("Di chuyển", ("xăng", "petrolimex", "pvoil", "grab", "be", "taxi", "bus", "vé xe", "gửi xe", "parking", "fuel")),
        ("Hóa đơn", ("điện lực", "evn", "tiền điện", "tiền nước", "sawaco", "internet", "viettel", "vnpt", "fpt", "tiền trọ", "tiền nhà", "utility")),
        ("Học tập", ("nhà sách", "fahasa", "phương nam", "giáo trình", "photocopy", "in ấn", "học phí", "tuition", "bookstore")),
        ("Sức khỏe", ("nhà thuốc", "pharmacity", "long châu", "an khang", "bệnh viện", "phòng khám", "thuốc", "pharmacy", "clinic", "hospital")),
        ("Giải trí", ("cgv", "lotte cinema", "galaxy", "karaoke", "game", "netflix", "spotify", "cinema", "ticket")),
        ("Mua sắm", ("siêu thị", "winmart", "co.op", "bách hóa xanh", "circle k", "gs25", "7-eleven", "familymart", "shopee", "lazada", "uniqlo", "minimart", "supermarket", "mart")),
        ("Ăn uống", ("cơm", "phở", "bún", "mì", "bánh mì", "trà sữa", "cà phê", "cafe", "coffee", "highlands", "phúc long", "kfc", "jollibee", "lotteria", "quán", "nhà hàng", "restaurant", "food", "drink", "nước suối", "sữa tươi")),
    )
    for cat, kws in rules:
        if any(kw in lower for kw in kws):
            return cat
    return "Khác"


def extract_structured_receipt_from_ocr_text(raw_text: str) -> GeminiReceiptSchema:
    """Phân tích văn bản OCR sang GeminiReceiptSchema theo đúng quy tắc:
    - Không bịa tên cửa hàng, ngày giao dịch hay tổng tiền (trả về None nếu không có).
    - Phân biệt ngày in hóa đơn (print date) với ngày giao dịch (transaction date).
    - Phân biệt tiền hàng (subtotal), thuế VAT (tax_amount) và tổng thanh toán (total_amount).
    - Không lấy số điện thoại hoặc mã hóa đơn làm số tiền.
    """
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    warnings: list[str] = []
    if not lines:
        return GeminiReceiptSchema(
            confidence=0,
            warnings=["Không có văn bản OCR để phân tích."],
        )

    # 1. Tên cửa hàng (Merchant Name)
    merchant_name: str | None = None
    skip_header_pattern = re.compile(
        r"^(?:hóa\s*đơn|hoa\s*don|phiếu\s*thanh\s*toán|receipt|tax\s*invoice|invoice|bill|welcome|xin\s*chào|cảm\s*ơn|thank\s*you|mst|tax\s*id|địa\s*chỉ|address|tel|đt|sđt|phone|hotline|ngày|date|cashier|thu\s*ngân|số\s*hđ|no\.)\b",
        flags=re.IGNORECASE,
    )
    for line in lines[:5]:
        if skip_header_pattern.search(line):
            continue
        if re.fullmatch(r"[\d\W_]+", line):
            continue
        if _parse_money_token_strict(line) is not None and len(line.split()) <= 3:
            continue
        merchant_name = line[:120]
        break

    if not merchant_name:
        warnings.append("Không nhận diện chắc chắn tên cửa hàng trên hóa đơn.")

    # 2. Ngày giao dịch vs Ngày in hóa đơn
    tx_date: str | None = None
    fallback_date: str | None = None
    print_date_keywords = ("ngày in", "ngay in", "printed", "print date", "in lúc", "in ngày")
    tx_date_keywords = ("ngày mua", "ngay mua", "ngày gd", "ngày giao dịch", "ngày:", "date:", "transaction date", "order date", "ngày bán")

    for line in lines:
        lower = line.casefold()
        found_d = _normalize_date_str(line)
        if not found_d:
            continue
        if any(pk in lower for pk in print_date_keywords):
            continue
        if any(tk in lower for tk in tx_date_keywords):
            tx_date = found_d
            break
        if fallback_date is None:
            fallback_date = found_d

    if tx_date is None:
        tx_date = fallback_date
    if tx_date is None:
        warnings.append("Hóa đơn thiếu hoặc không đọc được ngày giao dịch.")

    # 3. Subtotal, VAT/Tax, Total Amount, Payment Method & Items
    subtotal: int | None = None
    tax_amount: int | None = None
    total_amount: int | None = None
    payment_method: str | None = None
    items: list[ReceiptLineItemSchema] = []

    total_kws = (
        "tổng thanh toán", "tong thanh toan", "tổng cộng", "tong cong", "khách phải trả",
        "thanh toán:", "tổng tiền thanh toán", "grand total", "total due", "amount due",
        "total amount", "net total", "total:", "tổng tiền:",
    )
    subtotal_kws = (
        "tạm tính", "tam tinh", "cộng tiền hàng", "tiền hàng", "subtotal", "sub-total", "sub total", "pre-tax",
    )
    tax_kws = ("vat", "thuế gtgt", "thue gtgt", "tax", "gst")
    ignore_money_kws = (
        "tiền khách đưa", "khách đưa", "tiền mặt khách", "tiền thừa", "tiền thối",
        "change", "tendered", "cash received", "sđt", "sdt", "tel", "hotline", "mst",
    )
    payment_map = {
        "Tiền mặt": ("tiền mặt", "cash"),
        "Chuyển khoản / QR": ("chuyển khoản", "vietqr", "qr pay", "banking", "bank transfer"),
        "Ví điện tử": ("momo", "zalopay", "vnpay", "shopeepay", "apple pay", "google pay"),
        "Thẻ ngân hàng": ("thẻ", "visa", "mastercard", "atm", "pos", "credit card", "debit card"),
    }

    for line in lines:
        lower = line.casefold()
        for pay_label, kws in payment_map.items():
            if any(kw in lower for kw in kws) and not payment_method:
                payment_method = pay_label

        if any(ik in lower for ik in ignore_money_kws):
            continue

        if any(tk in lower for tk in tax_kws) and not any(tot in lower for tot in total_kws):
            amt = _parse_money_token_strict(line)
            if amt is not None:
                tax_amount = amt
            continue

        if any(sk in lower for sk in subtotal_kws):
            amt = _parse_money_token_strict(line)
            if amt is not None:
                subtotal = amt
            continue

        if any(tot in lower for tot in total_kws):
            amt = _parse_money_token_strict(line)
            if amt is not None:
                total_amount = amt
            continue

        # Dòng mặt hàng có số lượng x đơn giá = thành tiền
        m_item_mult = re.search(
            r"^(.+?)\s+(\d{1,3})\s*[xX*]\s*([0-9][0-9.,]*)\s*(?:=|\s)\s*([0-9][0-9.,]*)\s*(?:đ|đồng|vnd|k)?$",
            line,
            flags=re.IGNORECASE,
        )
        if m_item_mult:
            item_name = m_item_mult.group(1).strip(" -•:*")
            qty = int(m_item_mult.group(2))
            u_price = _parse_money_token_strict(m_item_mult.group(3))
            l_total = _parse_money_token_strict(m_item_mult.group(4))
            if item_name and l_total is not None:
                items.append(
                    ReceiptLineItemSchema(
                        name=item_name,
                        qty=qty,
                        unit_price=u_price or (l_total // max(1, qty)),
                        line_total=l_total,
                    )
                )
                continue

        # Dòng mặt hàng đơn giản: Tên món + Số tiền phân nhóm nghìn
        m_item_pair = re.search(
            r"^([A-Za-zÀ-ỹ][^\d]{1,48}?)\s+([1-9]\d{0,2}(?:[.,]\d{3})+)\s*(?:đ|đồng|vnd)?$",
            line,
            flags=re.IGNORECASE,
        )
        if m_item_pair and not skip_header_pattern.search(line):
            item_name = m_item_pair.group(1).strip(" -•:*")
            l_total = _parse_money_token_strict(m_item_pair.group(2))
            if item_name and l_total is not None:
                items.append(
                    ReceiptLineItemSchema(
                        name=item_name,
                        qty=1,
                        unit_price=l_total,
                        line_total=l_total,
                    )
                )

    if total_amount is None:
        warnings.append("Không tìm thấy dòng Tổng thanh toán rõ ràng trên hóa đơn (total_amount = null).")

    suggested_cat = _infer_category_from_text(raw_text)
    desc_parts = []
    if merchant_name:
        desc_parts.append(f"Hóa đơn {merchant_name}")
    if items:
        preview_names = ", ".join(it.name for it in items[:3])
        desc_parts.append(f"({preview_names})")
    description = " ".join(desc_parts).strip() or None

    confidence = 30
    if merchant_name:
        confidence += 20
    if tx_date:
        confidence += 20
    if total_amount is not None:
        confidence += 25
    if items:
        confidence += 5

    return GeminiReceiptSchema(
        merchant_name=merchant_name,
        transaction_date=tx_date,
        total_amount=total_amount,
        subtotal=subtotal,
        tax_amount=tax_amount,
        currency="VND",
        items=items,
        suggested_category=suggested_cat,
        description=description,
        payment_method=payment_method,
        confidence=min(95, confidence),
        warnings=warnings,
    )


# =============================================================================
# 5. KẾT NỐI GEMINI API PHÂN TÍCH VĂN BẢN OCR / ẢNH HÓA ĐƠN (SECTION 5–9)
# =============================================================================
@dataclass
class GeminiAnalysisResult:
    success: bool
    schema_data: GeminiReceiptSchema
    source: str  # 'gemini_text' | 'gemini_vision' | 'local_ocr_fallback'
    raw_ocr_text: str
    error_code: str = ""
    message: str = ""


def _build_gemini_receipt_prompt(ocr_text: str = "") -> str:
    categories_str = ", ".join(ALLOWED_GEMINI_CATEGORIES)
    base_rules = f"""Bạn là chuyên gia AI phân tích hóa đơn tài chính cho ứng dụng UniSpend 2.0.
Hãy phân tích dữ liệu hóa đơn và trả về DUY NHẤT một JSON object đúng chuẩn cấu trúc sau:
{{
  "merchant_name": null,
  "transaction_date": null,
  "total_amount": null,
  "subtotal": null,
  "tax_amount": null,
  "currency": "VND",
  "items": [
    {{"name": "Tên mặt hàng", "qty": 1, "unit_price": 10000, "line_total": 10000}}
  ],
  "suggested_category": null,
  "description": null,
  "payment_method": null,
  "confidence": 0,
  "warnings": []
}}

QUY TẮC BẮT BUỘC:
1. total_amount, subtotal, tax_amount phải là số nguyên VND (integer) hoặc null.
2. Không tự đổi hoặc tự bịa số tiền nếu không có căn cứ rõ ràng trên hóa đơn.
3. Không nhầm tiền hàng (subtotal / tạm tính) với tổng thanh toán cuối cùng (total_amount, đã gồm VAT/giảm giá).
4. Tuyệt đối không lấy số điện thoại (SĐT/Tel/Hotline), mã số thuế hoặc mã hóa đơn làm số tiền.
5. Nếu trường nào không chắc chắn hoặc không có trên hóa đơn, bắt buộc trả về null và ghi rõ lý do vào mảng "warnings".
6. Không tự tạo ngày giao dịch (transaction_date định dạng "YYYY-MM-DD" hoặc null). Phải phân biệt ngày in hóa đơn (print date) với ngày giao dịch thực tế nếu có cả hai.
7. Không bịa tên cửa hàng (merchant_name).
8. suggested_category CHỈ ĐƯỢC CHỌN một trong các giá trị: [{categories_str}]. Nếu không phù hợp, trả về "Khác".
9. confidence là số nguyên từ 0 đến 100 (chỉ mang tính tham khảo).
"""
    if ocr_text:
        return f"{base_rules}\nVĂN BẢN OCR TRÍCH XUẤT TỪ HÓA ĐƠN:\n\"\"\"\n{ocr_text}\n\"\"\""
    return base_rules


def _extract_gemini_json_dict(raw_response_text: str) -> dict[str, Any]:
    cleaned = (raw_response_text or "").strip()
    if not cleaned:
        raise ValueError("Gemini trả về phản hồi rỗng.")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        brace = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if brace:
            cleaned = brace.group(0)
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Phản hồi JSON từ Gemini không phải là một đối tượng (object).")
    return parsed


def _classify_gemini_exception(exc: Exception) -> tuple[str, str]:
    text = str(exc)
    lower = text.lower()
    if "429" in lower or "quota" in lower or "rate limit" in lower or "resource_exhausted" in lower:
        return "GEMINI_QUOTA_EXCEEDED", "Đã hết hạn mức gọi Gemini API (Quota / Rate Limit 429). Bạn vẫn có thể xem và chỉnh sửa văn bản OCR thủ công."
    if "401" in lower or "403" in lower or "api_key_invalid" in lower or "invalid api key" in lower or "permission_denied" in lower:
        return "GEMINI_INVALID_KEY", "GEMINI_API_KEY không hợp lệ hoặc bị từ chối quyền (401/403). Vui lòng kiểm tra lại cấu hình trong file .env."
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)) or "connection" in lower or "timeout" in lower or "unreachable" in lower:
        return "GEMINI_NETWORK_ERROR", "Lỗi kết nối mạng tới máy chủ Google Gemini. Hệ thống đã chuyển sang phân tích văn bản OCR cục bộ."
    return "GEMINI_API_ERROR", "Không thể phân tích qua Gemini API lúc này. Bạn vẫn có thể chỉnh sửa trực tiếp kết quả OCR bên dưới."


def test_gemini_connection() -> tuple[bool, str]:
    """Kiểm tra kết nối thực tế tới Google Gemini API mà không lộ API Key."""
    load_env_file()
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    model = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    if not api_key:
        return False, "Chưa cấu hình GEMINI_API_KEY trong file .env."
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model,
            contents='Trả về đúng chuỗi JSON: {"status": "ok"}',
        )
        if resp and (resp.text or "").strip():
            return True, f"Kết nối Google Gemini ({model}) hoạt động tốt."
        return False, "Gemini phản hồi rỗng."
    except Exception as exc:
        _, msg = _classify_gemini_exception(exc)
        return False, msg


def analyze_ocr_text_with_gemini(
    ocr_text: str,
    *,
    user_consent: bool = True,
    extra_warnings: list[str] | None = None,
) -> GeminiAnalysisResult:
    """Bước 5–7: Gửi văn bản OCR cho Gemini phân tích -> Kiểm tra bằng Pydantic Schema.
    Nếu chưa có sự đồng ý của người dùng, chưa cấu hình key hoặc Gemini lỗi,
    trả về kết quả bóc tách cục bộ từ văn bản OCR để người dùng vẫn chỉnh sửa thủ công được.
    """
    clean_ocr = (ocr_text or "").strip()
    base_warnings = list(extra_warnings or [])
    if not clean_ocr:
        empty_schema = GeminiReceiptSchema(
            confidence=0,
            warnings=[*base_warnings, "Không có văn bản OCR để phân tích."],
        )
        return GeminiAnalysisResult(
            success=False,
            schema_data=empty_schema,
            source="local_ocr_fallback",
            raw_ocr_text="",
            error_code="EMPTY_OCR_TEXT",
            message="Không có văn bản OCR để gửi phân tích.",
        )

    local_fallback = extract_structured_receipt_from_ocr_text(clean_ocr)
    for w in base_warnings:
        if w not in local_fallback.warnings:
            local_fallback.warnings.insert(0, w)

    if not user_consent:
        if "Chưa cấp quyền gửi dữ liệu lên Gemini Cloud — đang dùng bộ bóc tách OCR cục bộ." not in local_fallback.warnings:
            local_fallback.warnings.append("Chưa cấp quyền gửi dữ liệu lên Gemini Cloud — đang dùng bộ bóc tách OCR cục bộ.")
        return GeminiAnalysisResult(
            success=True,
            schema_data=local_fallback,
            source="local_ocr_fallback",
            raw_ocr_text=clean_ocr,
            error_code="CONSENT_REQUIRED",
            message="Đang phân tích văn bản OCR cục bộ trên máy (chưa gửi dữ liệu lên dịch vụ Gemini bên ngoài).",
        )

    load_env_file()
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    model = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()

    if not api_key:
        return GeminiAnalysisResult(
            success=False,
            schema_data=local_fallback,
            source="local_ocr_fallback",
            raw_ocr_text=clean_ocr,
            error_code="GEMINI_KEY_MISSING",
            message=(
                "Chưa cấu hình GEMINI_API_KEY trong file .env. "
                "Hệ thống đã bóc tách sơ bộ từ văn bản OCR cục bộ — bạn có thể xem và chỉnh sửa thủ công trước khi lưu."
            ),
        )

    cache_key = hashlib.sha256(f"text|{model}|{clean_ocr}".encode("utf-8")).hexdigest()
    if cache_key in _GEMINI_PARSE_CACHE:
        return _GEMINI_PARSE_CACHE[cache_key]

    prompt = _build_gemini_receipt_prompt(clean_ocr)
    try:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(model=model, contents=prompt)
            raw_reply = (resp.text or "").strip()
        except ImportError:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            resp = requests.post(
                url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=35,
            )
            resp.raise_for_status()
            raw_reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        raw_dict = _extract_gemini_json_dict(raw_reply)
        validated = GeminiReceiptSchema.model_validate(raw_dict)
        for w in base_warnings:
            if w not in validated.warnings:
                validated.warnings.insert(0, w)
        if validated.total_amount is None:
            w_msg = "Gemini không xác định chắc chắn tổng tiền thanh toán (total_amount = null)."
            if w_msg not in validated.warnings:
                validated.warnings.append(w_msg)
        if validated.transaction_date is None:
            w_msg = "Gemini không xác định chắc chắn ngày giao dịch (transaction_date = null)."
            if w_msg not in validated.warnings:
                validated.warnings.append(w_msg)

        result = GeminiAnalysisResult(
            success=True,
            schema_data=validated,
            source="gemini_text",
            raw_ocr_text=clean_ocr,
            error_code="",
            message=f"Gemini ({model}) đã phân tích văn bản OCR hóa đơn thành công.",
        )
        _GEMINI_PARSE_CACHE[cache_key] = result
        return result

    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        local_fallback.warnings.append("Gemini trả về JSON không hợp lệ hoặc thiếu trường chuẩn — đã chuyển sang kết quả bóc tách OCR cục bộ.")
        return GeminiAnalysisResult(
            success=False,
            schema_data=local_fallback,
            source="local_ocr_fallback",
            raw_ocr_text=clean_ocr,
            error_code="GEMINI_INVALID_JSON",
            message=f"Gemini trả về cấu trúc JSON không hợp lệ ({exc}). Bạn vẫn có thể chỉnh sửa dữ liệu OCR thủ công.",
        )
    except Exception as exc:
        code, msg = _classify_gemini_exception(exc)
        return GeminiAnalysisResult(
            success=False,
            schema_data=local_fallback,
            source="local_ocr_fallback",
            raw_ocr_text=clean_ocr,
            error_code=code,
            message=msg,
        )


def analyze_receipt_image_with_gemini(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    *,
    user_consent: bool = False,
    raw_ocr_text: str = "",
    extra_warnings: list[str] | None = None,
) -> GeminiAnalysisResult:
    """Tùy chọn dự phòng: Gửi trực tiếp ảnh hóa đơn lên Gemini Vision khi OCR quá kém
    và người dùng đã đồng ý rõ ràng (user_consent=True).
    """
    base_warnings = list(extra_warnings or [])
    fallback_schema = extract_structured_receipt_from_ocr_text(raw_ocr_text) if raw_ocr_text.strip() else GeminiReceiptSchema(warnings=base_warnings)

    if not user_consent:
        return GeminiAnalysisResult(
            success=False,
            schema_data=fallback_schema,
            source="local_ocr_fallback",
            raw_ocr_text=raw_ocr_text,
            error_code="IMAGE_CONSENT_REQUIRED",
            message="Chưa thể gửi ảnh hóa đơn lên dịch vụ Gemini bên ngoài khi bạn chưa đánh dấu đồng ý gửi ảnh.",
        )

    validation = validate_receipt_image(image_bytes)
    if not validation.valid:
        return GeminiAnalysisResult(
            success=False,
            schema_data=fallback_schema,
            source="local_ocr_fallback",
            raw_ocr_text=raw_ocr_text,
            error_code=validation.error_code,
            message=validation.error_message,
        )

    load_env_file()
    api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    model = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
    if not api_key:
        return GeminiAnalysisResult(
            success=False,
            schema_data=fallback_schema,
            source="local_ocr_fallback",
            raw_ocr_text=raw_ocr_text,
            error_code="GEMINI_KEY_MISSING",
            message="Chưa cấu hình GEMINI_API_KEY trong file .env để phân tích ảnh trực tiếp.",
        )

    img_hash = hashlib.sha256(image_bytes + f"|vision|{model}".encode("utf-8")).hexdigest()
    if img_hash in _GEMINI_PARSE_CACHE:
        return _GEMINI_PARSE_CACHE[img_hash]

    vision_instruction = (
        "BẠN ĐANG NHÌN TRỰC TIẾP ẢNH HÓA ĐƠN GỐC ĐÃ ĐƯỢC LÀM NÉT. "
        "Hãy đọc kỹ từng dòng chữ và con số trực tiếp trên ảnh hóa đơn (ưu tiên những gì nhìn thấy trên ảnh hơn văn bản OCR thô nếu OCR bị nhận nhầm).\n"
        "- Chú ý phân biệt đúng: tên quán/cửa hàng ở đầu hóa đơn, danh sách đầy đủ từng món hàng + đơn giá + thành tiền, Tạm tính vs Thanh toán / Tổng cộng cuối cùng.\n"
        "- Không nhầm số điện thoại, mã hóa đơn hay tiền khách đưa với tổng thanh toán.\n\n"
    )
    prompt = vision_instruction + _build_gemini_receipt_prompt(raw_ocr_text)
    try:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"),
                    prompt,
                ],
            )
            raw_reply = (resp.text or "").strip()
        except ImportError:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            resp = requests.post(
                url,
                json={
                    "contents": [{
                        "parts": [
                            {"inline_data": {"mime_type": mime_type or "image/jpeg", "data": b64}},
                            {"text": prompt},
                        ]
                    }]
                },
                timeout=40,
            )
            resp.raise_for_status()
            raw_reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        raw_dict = _extract_gemini_json_dict(raw_reply)
        extracted_vision_ocr = str(raw_dict.pop("raw_text", "") or raw_ocr_text or "").strip()
        validated = GeminiReceiptSchema.model_validate(raw_dict)
        for w in (*base_warnings, *validation.warnings):
            if w not in validated.warnings:
                validated.warnings.insert(0, w)
        if not extracted_vision_ocr and validated.merchant_name:
            lines_synth = [validated.merchant_name]
            if validated.transaction_date:
                lines_synth.append(f"Ngày mua: {validated.transaction_date}")
            for it in validated.items:
                lines_synth.append(f"{it.name} {it.qty} x {it.unit_price or 0} = {it.line_total or 0}")
            if validated.total_amount:
                lines_synth.append(f"Tổng thanh toán: {validated.total_amount}")
            extracted_vision_ocr = "\n".join(lines_synth)

        result = GeminiAnalysisResult(
            success=True,
            schema_data=validated,
            source="gemini_vision",
            raw_ocr_text=extracted_vision_ocr,
            error_code="",
            message=f"Gemini Vision ({model}) đã phân tích trực tiếp ảnh hóa đơn thành công.",
        )
        _GEMINI_PARSE_CACHE[img_hash] = result
        return result

    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        return GeminiAnalysisResult(
            success=False,
            schema_data=fallback_schema,
            source="local_ocr_fallback",
            raw_ocr_text=raw_ocr_text,
            error_code="GEMINI_INVALID_JSON",
            message=f"Gemini trả về JSON không hợp lệ ({exc}). Vui lòng chỉnh sửa thủ công.",
        )
    except Exception as exc:
        code, msg = _classify_gemini_exception(exc)
        return GeminiAnalysisResult(
            success=False,
            schema_data=fallback_schema,
            source="local_ocr_fallback",
            raw_ocr_text=raw_ocr_text,
            error_code=code,
            message=msg,
        )
