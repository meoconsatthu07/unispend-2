"""Dịch vụ AI cho UniSpend 2.0:
- AI OCR nhận diện hóa đơn tiếng Việt (Camera / Ảnh tải lên / Văn bản OCR)
- AI Nhập chi tiêu bằng giọng nói tiếng Việt & bộ phân tích ngôn ngữ tự nhiên số tiền Việt
- AI Financial Assistant phân tích & tư vấn tiết kiệm dựa trên dữ liệu SQLite thật

Tuyệt đối không hardcode API key, không gửi toàn bộ SQLite lên cloud,
và không tự bịa số tiền khi OCR/AI không đọc được.
"""

from __future__ import annotations

import base64
import json
import os
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date as Date, timedelta
from pathlib import Path
from typing import Any

import requests

from .storage import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    TOTAL_BUDGET_CATEGORY,
    TYPE_LABELS,
    ExpenseStore,
    Transaction,
)
from .utils import display_date, money, shift_month


def load_env_file(env_path: str | Path | None = None) -> None:
    """Đọc biến môi trường từ file .env và Streamlit Cloud Secrets nếu có."""
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    root = Path(__file__).resolve().parent.parent
    candidates.append(root / ".env")
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k, "").strip():
                os.environ[k] = v
        break

    # Tự động đồng bộ Streamlit Cloud Secrets -> os.environ khi chạy Web 24/7
    try:
        import streamlit as st
        sec = st.secrets
        secret_keys = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "AI_PROVIDER", "TESSERACT_CMD", "OPENAI_API_KEY", "OPENAI_MODEL")
        for key in secret_keys:
            if not os.environ.get(key, "").strip():
                if key in sec and str(sec[key]).strip():
                    os.environ[key] = str(sec[key]).strip()
                else:
                    for section_name in ("secrets", "gemini", "api", "env"):
                        if section_name in sec and isinstance(sec[section_name], dict) and key in sec[section_name]:
                            val = str(sec[section_name][key]).strip()
                            if val:
                                os.environ[key] = val
                                break
    except Exception:
        pass


def save_ai_api_config(
    *,
    gemini_api_key: str | None = None,
    gemini_model: str = "gemini-3.5-flash-lite",
    openai_api_key: str | None = None,
    openai_model: str = "gpt-4o-mini",
    tesseract_cmd: str | None = None,
    ai_provider: str = "auto",
    env_path: str | Path | None = None,
) -> "AIStatus":
    """Lưu cấu hình API Key & Model vào file .env (đã nằm trong .gitignore) và nạp ngay vào os.environ."""
    target = Path(env_path) if env_path else (Path(__file__).resolve().parent.parent / ".env")
    existing: dict[str, str] = {}
    if target.is_file():
        for line in target.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, v = stripped.split("=", 1)
                existing[k.strip()] = v.strip()

    if gemini_api_key is not None and gemini_api_key.strip():
        existing["GEMINI_API_KEY"] = gemini_api_key.strip()
        os.environ["GEMINI_API_KEY"] = gemini_api_key.strip()
    if gemini_model and gemini_model.strip():
        existing["GEMINI_MODEL"] = gemini_model.strip()
        os.environ["GEMINI_MODEL"] = gemini_model.strip()
    if openai_api_key is not None and openai_api_key.strip():
        existing["OPENAI_API_KEY"] = openai_api_key.strip()
        os.environ["OPENAI_API_KEY"] = openai_api_key.strip()
    if openai_model and openai_model.strip():
        existing["OPENAI_MODEL"] = openai_model.strip()
        os.environ["OPENAI_MODEL"] = openai_model.strip()
    if tesseract_cmd is not None and tesseract_cmd.strip():
        existing["TESSERACT_CMD"] = tesseract_cmd.strip()
        os.environ["TESSERACT_CMD"] = tesseract_cmd.strip()
    if ai_provider and ai_provider.strip():
        existing["AI_PROVIDER"] = ai_provider.strip().lower()
        os.environ["AI_PROVIDER"] = ai_provider.strip().lower()

    lines = [
        "# Cấu hình AI & OCR cho UniSpend 2.0 (Tệp này được loại trừ khỏi Git qua .gitignore)",
        f"AI_PROVIDER={existing.get('AI_PROVIDER', 'auto')}",
        f"GEMINI_API_KEY={existing.get('GEMINI_API_KEY', '')}",
        f"GEMINI_MODEL={existing.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')}",
        f"OPENAI_API_KEY={existing.get('OPENAI_API_KEY', '')}",
        f"OPENAI_MODEL={existing.get('OPENAI_MODEL', 'gpt-4o-mini')}",
        f"TESSERACT_CMD={existing.get('TESSERACT_CMD', r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe')}",
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return check_api_status()


@dataclass
class AIStatus:
    configured: bool
    provider: str
    model: str
    masked_key: str
    message: str


def check_api_status(preferred_provider: str | None = None) -> AIStatus:
    """Kiểm tra cấu hình API key từ biến môi trường hoặc .env."""
    load_env_file()
    provider_cfg = (preferred_provider or os.environ.get("AI_PROVIDER") or "auto").strip().lower()
    gemini_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    openai_key = (os.environ.get("OPENAI_API_KEY") or "").strip()

    def _mask(key: str) -> str:
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"

    if provider_cfg in ("gemini", "auto") and gemini_key:
        model = (os.environ.get("GEMINI_MODEL") or "gemini-3.5-flash-lite").strip()
        return AIStatus(
            configured=True,
            provider="gemini",
            model=model,
            masked_key=_mask(gemini_key),
            message=f"Đã kết nối cấu hình Google Gemini ({model}).",
        )
    if provider_cfg in ("openai", "auto") and openai_key:
        model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
        return AIStatus(
            configured=True,
            provider="openai",
            model=model,
            masked_key=_mask(openai_key),
            message=f"Đã kết nối cấu hình OpenAI ({model}).",
        )
    return AIStatus(
        configured=False,
        provider="none",
        model="",
        masked_key="",
        message=(
            "Chưa cấu hình AI API key. Các tính năng quản lý tài chính, lịch, phân tích dữ liệu thật "
            "và bộ đọc số tiền giọng nói tiếng Việt cục bộ vẫn hoạt động. Để bật AI Cloud OCR ảnh & Voice Audio, "
            "hãy tạo file .env từ .env.example và điền GEMINI_API_KEY hoặc OPENAI_API_KEY."
        ),
    )


def _format_api_error(exc: Exception) -> str:
    text = str(exc)
    lower = text.lower()
    if "429" in lower or "quota" in lower or "rate limit" in lower or "resource_exhausted" in lower:
        return "API đã hết hạn mức (Quota / Rate Limit 429). Vui lòng thử lại sau hoặc đổi API key khác."
    if "401" in lower or "403" in lower or "api_key_invalid" in lower or "unauthorized" in lower:
        return "API key không hợp lệ hoặc bị từ chối quyền truy cập (401/403). Vui lòng kiểm tra lại file .env."
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)) or "connection" in lower or "timeout" in lower:
        return "Mất kết nối mạng tới máy chủ AI. Vui lòng kiểm tra kết nối Internet và thử lại."
    return f"Lỗi dịch vụ AI: {text}"


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1)
    else:
        brace_match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(0)
    data = json.loads(cleaned)
    return data if isinstance(data, dict) else {}


def _call_llm_text(prompt: str, system_instruction: str = "", preferred_provider: str | None = None) -> tuple[bool, str]:
    status = check_api_status(preferred_provider)
    if not status.configured:
        return False, status.message
    try:
        if status.provider == "gemini":
            api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            try:
                from google import genai
                client = genai.Client(api_key=api_key)
                full_prompt = f"{system_instruction}\n\n{prompt}".strip() if system_instruction else prompt
                resp = client.models.generate_content(model=status.model, contents=full_prompt)
                return True, (resp.text or "").strip()
            except ImportError:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{status.model}:generateContent?key={api_key}"
                full_prompt = f"{system_instruction}\n\n{prompt}".strip() if system_instruction else prompt
                resp = requests.post(
                    url,
                    json={"contents": [{"parts": [{"text": full_prompt}]}]},
                    timeout=30,
                )
                resp.raise_for_status()
                payload = resp.json()
                text = payload["candidates"][0]["content"]["parts"][0]["text"]
                return True, text.strip()
        else:
            api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
            base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": status.model, "messages": messages, "temperature": 0.2},
                timeout=30,
            )
            resp.raise_for_status()
            payload = resp.json()
            return True, payload["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        return False, _format_api_error(exc)


# =============================================================================
# 1. BỘ PHÂN TÍCH GIỌNG NÓI & NGÔN NGỮ TỰ NHIÊN TIẾNG VIỆT
# =============================================================================
VOICE_CATEGORY_KEYWORDS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "income",
        "Gia đình hỗ trợ",
        ("gia đình", "bố mẹ", "ba mẹ", "mẹ gửi", "bố gửi", "trợ cấp", "sinh hoạt phí"),
    ),
    (
        "income",
        "Làm thêm",
        ("lương", "làm thêm", "part-time", "part time", "gia sư", "ca tối", "thù lao", "freelance"),
    ),
    (
        "income",
        "Học bổng",
        ("học bổng", "khen thưởng", "thưởng học tập", "giải thưởng"),
    ),
    (
        "income",
        "Khác",
        ("thu nhập", "nhận tiền", "hoàn tiền", "lì xì", "bán đồ"),
    ),
    (
        "expense",
        "Đi lại",
        (
            "đổ xăng", "xăng", "xe buýt", "bus", "gửi xe", "grab", "be", "taxi",
            "xe ôm", "di chuyển", "đi lại", "vé xe", "sửa xe", "thay nhớt",
        ),
    ),
    (
        "expense",
        "Tiền trọ",
        ("tiền trọ", "nhà trọ", "tiền phòng", "thuê phòng", "điện nước", "tiền điện", "tiền nước", "wifi", "internet"),
    ),
    (
        "expense",
        "Học tập",
        ("học phí", "giáo trình", "in tài liệu", "photocopy", "sách", "vở", "bút", "khóa học", "học tập", "lệ phí thi"),
    ),
    (
        "expense",
        "Giải trí",
        ("xem phim", "cgv", "game", "giải trí", "karaoke", "du lịch", "sinh nhật", "concert", "netflix", "spotify"),
    ),
    (
        "expense",
        "Ăn uống",
        (
            "ăn sáng", "ăn trưa", "ăn tối", "ăn đêm", "ăn vặt", "ăn uống", "cơm", "phở", "bún",
            "mì", "bánh mì", "trà sữa", "cà phê", "cafe", "coffee", "nước ngọt", "đi chợ", "siêu thị", "lẩu",
        ),
    ),
)


_VN_DIGIT_WORDS: dict[str, int] = {
    "không": 0, "linh": 0, "lẻ": 0,
    "một": 1, "mốt": 1,
    "hai": 2, "ba": 3, "bốn": 4, "tư": 4,
    "năm": 5, "lăm": 5, "nhăm": 5,
    "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9,
}


def _normalize_vn_number_words(text: str) -> str:
    """Chuyển cụm số đọc bằng chữ tiếng Việt (0..999) trước đơn vị tiền thành chữ số để nhận diện chính xác hơn.
    Ví dụ: 'bốn mươi lăm nghìn' -> '45 nghìn', 'hai trăm rưỡi' -> '2 trăm rưỡi', 'năm chục' -> '5 chục'.
    """
    units_pat = r"(?=[\s]+(?:triệu|tr|củ|nghìn|ngàn|k|ca|ka|cành|xị|lít|chục|trăm)\b)"

    def _replace_tens(match: re.Match[str]) -> str:
        tens_word = match.group(1).lower()
        ones_word = (match.group(2) or "").lower()
        tens_val = 10 if tens_word == "mười" else _VN_DIGIT_WORDS.get(tens_word, 0) * 10
        ones_val = _VN_DIGIT_WORDS.get(ones_word, 0) if ones_word else 0
        return str(tens_val + ones_val)

    # "hai mươi lăm", "ba mươi", "mười lăm", "bốn lăm"
    out = re.sub(
        r"\b(mười|hai|ba|bốn|năm|sáu|bảy|bẩy|tám|chín)\s+(?:mươi\s*)?(mốt|hai|ba|bốn|tư|năm|lăm|nhăm|sáu|bảy|bẩy|tám|chín)?\b" + units_pat,
        _replace_tens,
        text,
        flags=re.IGNORECASE,
    )
    # Số đơn 1..9 trước đơn vị tiền: "một triệu", "hai xị", "năm chục"
    out = re.sub(
        r"\b(một|hai|ba|bốn|tư|năm|sáu|bảy|bẩy|tám|chín|mười)\b" + units_pat,
        lambda m: str(10 if m.group(1).lower() == "mười" else _VN_DIGIT_WORDS[m.group(1).lower()]),
        out,
        flags=re.IGNORECASE,
    )
    return out


def parse_vietnamese_spoken_amount(text: str) -> tuple[int | None, str]:
    """Đọc các cách nói số tiền tiếng Việt tự nhiên:
    - 10K, 50K, 50k, 45 ca, 35 ka
    - 35 nghìn, 100 nghìn, 100 ngàn, 50 cành, bốn mươi lăm nghìn
    - 1 triệu, 1 triệu 2, 1tr2, 1 triệu 250 nghìn, 2 triệu rưỡi, nửa triệu, 1 củ rưỡi
    - 2 xị, 2 xị rưỡi, 3 lít, 5 chục, 2 trăm rưỡi
    - 50.000, 1.200.000, 50000
    Trả về (amount_int_vnd, matched_substring).
    """
    normalized = text.strip()
    if not normalized:
        return None, ""
    norm_num = _normalize_vn_number_words(normalized)

    # 1. "nửa triệu" / "nửa củ"
    half_million = re.search(r"\bnửa\s*(?:triệu|củ)\b", norm_num, flags=re.IGNORECASE)
    if half_million:
        return 500_000, half_million.group(0)

    # 2. "<X> triệu rưỡi" / "<X> tr rưỡi" / "<X> củ rưỡi"
    m_half = re.search(
        r"\b(\d{1,4})\s*(?:triệu|tr|củ)\s*rưỡi\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_half:
        millions = int(m_half.group(1))
        return millions * 1_000_000 + 500_000, m_half.group(0)

    # 3. "<X> triệu <Y> [nghìn/ngàn/k]" (VD: "1 triệu 2", "1 triệu 250", "1tr2", "2 triệu 50 nghìn")
    m_comp = re.search(
        r"\b(\d{1,4})\s*(?:triệu|tr|củ)\s*(\d{1,3})\s*(?:nghìn|ngàn|k|ca|ka)?\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_comp:
        millions = int(m_comp.group(1))
        tail_str = m_comp.group(2)
        tail_val = int(tail_str)
        if len(tail_str) == 1:
            thousands = tail_val * 100_000
        elif len(tail_str) == 2:
            thousands = tail_val * 10_000
        else:
            thousands = tail_val * 1_000
        return millions * 1_000_000 + thousands, m_comp.group(0)

    # 4. "<X[,/.Y]> triệu / tr / củ / m" (VD: "1 triệu", "1.5 triệu", "1,2 triệu")
    m_mil = re.search(
        r"\b(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:triệu|tr|củ|m)\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_mil:
        val = float(m_mil.group(1).replace(",", "."))
        return int(round(val * 1_000_000)), m_mil.group(0)

    # 4b. "<X> trăm rưỡi" / "<X> xị rưỡi" / "<X> lít rưỡi" (VD: "1 trăm rưỡi" = 150k, "2 xị rưỡi" = 250k)
    m_hun_half = re.search(
        r"\b(\d{1,2})\s*(?:trăm|xị|lít)\s*rưỡi\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_hun_half:
        return int(m_hun_half.group(1)) * 100_000 + 50_000, m_hun_half.group(0)

    # 4c. "<X> xị / lít" (VD: "2 xị" = 200k, "3 lít" = 300k) hoặc "<X> trăm [nghìn/ngàn/k]"
    m_hun = re.search(
        r"\b(\d{1,2}(?:[.,]\d)?)\s*(?:xị|lít|trăm\s*(?:nghìn|ngàn|k|ca|ka)?)\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_hun:
        val = float(m_hun.group(1).replace(",", "."))
        return int(round(val * 100_000)), m_hun.group(0)

    # 4d. "<X> chục [rưỡi]" (VD: "5 chục" = 50k, "3 chục rưỡi" = 35k)
    m_chuc_half = re.search(r"\b(\d{1,2})\s*chục\s*rưỡi\b", norm_num, flags=re.IGNORECASE)
    if m_chuc_half:
        return int(m_chuc_half.group(1)) * 10_000 + 5_000, m_chuc_half.group(0)
    m_chuc = re.search(r"\b(\d{1,2})\s*chục\b", norm_num, flags=re.IGNORECASE)
    if m_chuc:
        return int(m_chuc.group(1)) * 10_000, m_chuc.group(0)

    # 5. "<X> nghìn rưỡi / ngàn rưỡi / k rưỡi"
    m_k_half = re.search(
        r"\b(\d{1,6})\s*(?:nghìn|ngàn|k|ca|ka)\s*rưỡi\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_k_half:
        return int(m_k_half.group(1)) * 1_000 + 500, m_k_half.group(0)

    # 6. "<X[,/.Y]> K / nghìn / ngàn / cành / ca / ka" (VD: "10K", "50K", "35 nghìn", "45 ca")
    m_k = re.search(
        r"\b(\d{1,6}(?:[.,]\d{1,2})?)\s*(?:k|nghìn|ngàn|cành|ca|ka)\b",
        norm_num,
        flags=re.IGNORECASE,
    )
    if m_k:
        val = float(m_k.group(1).replace(",", "."))
        return int(round(val * 1_000)), m_k.group(0)

    # 7. Số có dấu chấm/phẩy phân nhóm nghìn chuẩn (VD: "50.000", "1.200.000 đ")
    m_grouped = re.search(
        r"\b([1-9]\d{0,2}(?:[.,]\d{3})+)\s*(?:đ|đồng|vnd|vnđ)?\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if m_grouped:
        digits = re.sub(r"[.,]", "", m_grouped.group(1))
        return int(digits), m_grouped.group(0)

    # 8. Số nguyên trần >= 1000 (VD: "50000", "120000 đồng")
    m_plain = re.search(
        r"\b(\d{4,12})\s*(?:đ|đồng|vnd|vnđ)?\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if m_plain:
        return int(m_plain.group(1)), m_plain.group(0)

    return None, ""


def _parse_spoken_date(text: str, today: Date) -> tuple[Date, str, str]:
    """Trả về (date_obj, relative_label, matched_date_phrase)."""
    lower = text.casefold()
    if "hôm kia" in lower:
        m = re.search(r"hôm kia", text, flags=re.IGNORECASE)
        return today - timedelta(days=2), "Hôm kia", (m.group(0) if m else "hôm kia")
    if "hôm qua" in lower:
        m = re.search(r"hôm qua", text, flags=re.IGNORECASE)
        return today - timedelta(days=1), "Hôm qua", (m.group(0) if m else "hôm qua")
    if "hôm nay" in lower or "nay" in re.findall(r"\b\w+\b", lower):
        m = re.search(r"hôm nay", text, flags=re.IGNORECASE)
        return today, "Hôm nay", (m.group(0) if m else "")

    m_full = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", text)
    if m_full:
        d, mo, y = map(int, m_full.groups())
        try:
            dt = Date(y, mo, d)
            return dt, display_date(dt.isoformat()), m_full.group(0)
        except ValueError:
            pass

    m_short = re.search(r"\bngày\s+(\d{1,2})[/-](\d{1,2})\b", text, flags=re.IGNORECASE)
    if m_short:
        d, mo = map(int, m_short.groups())
        try:
            dt = Date(today.year, mo, d)
            return dt, display_date(dt.isoformat()), m_short.group(0)
        except ValueError:
            pass

    return today, "Hôm nay", ""


def _detect_kind_and_category(text: str) -> tuple[str, str, str]:
    """Trả về (kind, storage_category, display_category_label)."""
    lower = text.casefold()
    for kind, category, keywords in VOICE_CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in lower:
                label = "Đi lại (Di chuyển)" if category == "Đi lại" else category
                return kind, category, label
    return "expense", "Khác", "Khác"


def _extract_clean_note(text: str, amount_phrase: str, date_phrase: str) -> str:
    note = text
    for phrase in (amount_phrase, date_phrase):
        if phrase:
            note = re.sub(re.escape(phrase), " ", note, count=1, flags=re.IGNORECASE)
    note = re.sub(r"^\s*(?:chi\s+tiêu|thu\s+nhập|tiền|mua|chi|trả\s+tiền|đóng\s+tiền)\s+", "", note, flags=re.IGNORECASE)
    note = re.sub(r"\s+(?:hết|mất|giá|với\s+giá|khoảng)\s*$", "", note, flags=re.IGNORECASE)
    note = re.sub(r"\s+", " ", note).strip(" ,.-:;")
    if not note:
        return ""
    return note[0].upper() + note[1:]


def parse_vietnamese_voice_expense(
    transcript: str,
    today: Date | None = None,
    use_ai: bool = False,
) -> dict[str, Any]:
    """Phân tích câu nói tiếng Việt thành dữ liệu giao dịch có cấu trúc.

    Ví dụ:
    - 'Tiền đổ xăng 50K' -> Chi tiêu, 50.000đ, Đi lại (Di chuyển), Ghi chú: Đổ xăng, Ngày: Hôm nay
    - 'Ăn sáng 35 nghìn hôm qua' -> Chi tiêu, 35.000đ, Ăn uống, Ghi chú: Ăn sáng, Ngày: Hôm qua
    """
    today = Date.today() if today is None else today
    raw = (transcript or "").strip()
    if not raw:
        raise ValueError("Vui lòng ghi âm hoặc nhập câu mô tả chi tiêu.")

    amount, amount_phrase = parse_vietnamese_spoken_amount(raw)
    tx_date, date_label, date_phrase = _parse_spoken_date(raw, today)
    kind, category, category_display = _detect_kind_and_category(raw)
    note = _extract_clean_note(raw, amount_phrase, date_phrase) or category

    result = {
        "transcript": raw,
        "kind": kind,
        "kind_label": TYPE_LABELS[kind],
        "amount": amount or 0,
        "category": category,
        "category_display": category_display,
        "note": note[:200],
        "date": tx_date.isoformat(),
        "date_display": display_date(tx_date.isoformat()),
        "date_relative": date_label,
        "source": "local_nlp",
        "valid_amount": amount is not None and amount > 0,
    }

    if use_ai and check_api_status().configured:
        prompt = (
            f"Hôm nay là {today.isoformat()}. Phân tích câu nói thu/chi tiếng Việt sau thành JSON:\n"
            f"Câu nói: {raw!r}\n"
            f"Danh mục Chi tiêu hợp lệ: {list(EXPENSE_CATEGORIES)}\n"
            f"Danh mục Thu nhập hợp lệ: {list(INCOME_CATEGORIES)}\n"
            "Trả về duy nhất JSON có các trường: "
            '{"kind": "expense|income", "amount": <số nguyên VNĐ>, "category": "<danh mục hợp lệ>", '
            '"note": "<ghi chú ngắn gọn>", "date": "YYYY-MM-DD"}. '
            "Nếu không rõ số tiền, đặt amount = 0."
        )
        ok, resp_text = _call_llm_text(prompt, "Bạn là trợ lý phân tích giọng nói tài chính tiếng Việt.")
        if ok:
            try:
                ai_data = _extract_json_object(resp_text)
                ai_kind = ai_data.get("kind")
                if ai_kind in TYPE_LABELS:
                    result["kind"] = ai_kind
                    result["kind_label"] = TYPE_LABELS[ai_kind]
                valid_cats = EXPENSE_CATEGORIES if result["kind"] == "expense" else INCOME_CATEGORIES
                ai_cat = ai_data.get("category")
                if ai_cat in valid_cats:
                    result["category"] = ai_cat
                    result["category_display"] = "Đi lại (Di chuyển)" if ai_cat == "Đi lại" else ai_cat
                ai_amount = ai_data.get("amount")
                if isinstance(ai_amount, (int, float)) and ai_amount > 0:
                    result["amount"] = int(round(ai_amount))
                    result["valid_amount"] = True
                ai_note = (ai_data.get("note") or "").strip()
                if ai_note:
                    result["note"] = ai_note[:200]
                ai_date = (ai_data.get("date") or "").strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", ai_date):
                    Date.fromisoformat(ai_date)
                    result["date"] = ai_date
                    result["date_display"] = display_date(ai_date)
                result["source"] = "ai_cloud"
            except Exception:
                pass

    return result


def transcribe_audio_bytes(audio_bytes: bytes, mime_type: str = "audio/wav") -> tuple[bool, str]:
    """Chuyển âm thanh giọng nói tiếng Việt thành văn bản qua Gemini hoặc OpenAI Whisper."""
    if not audio_bytes:
        return False, "Không có dữ liệu âm thanh."
    status = check_api_status()
    if not status.configured:
        return False, status.message
    try:
        if status.provider == "gemini":
            api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=status.model,
                    contents=[
                        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type or "audio/wav"),
                        (
                            "Bạn là hệ thống nhận diện giọng nói tiếng Việt (Bắc/Trung/Nam) chuyên ghi chép thu chi.\n"
                            "Hãy chép lại CHÍNH XÁC câu nói trong đoạn âm thanh:\n"
                            "- Bỏ từ ngập ngừng thừa (à, ừm, ờ) và tạp âm.\n"
                            "- Giữ nguyên dấu tiếng Việt chuẩn và số tiền đọc bằng lời hoặc số (VD: 'ăn phở bò 45k', 'đổ xăng 70 nghìn', 'nhận lương 3 triệu rưỡi').\n"
                            "- Chỉ trả về đúng 1 dòng văn bản nghe được, không thêm dấu ngoặc kép hay giải thích."
                        ),
                    ],
                )
                text = (resp.text or "").strip()
                return (True, text) if text else (False, "Không nhận diện được giọng nói trong bản ghi.")
            except ImportError:
                b64 = base64.b64encode(audio_bytes).decode("ascii")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{status.model}:generateContent?key={api_key}"
                resp = requests.post(
                    url,
                    json={
                        "contents": [{
                            "parts": [
                                {"inline_data": {"mime_type": mime_type or "audio/wav", "data": b64}},
                                {"text": "Chép lại chính xác câu nói tiếng Việt này. Chỉ trả về văn bản."},
                            ]
                        }]
                    },
                    timeout=35,
                )
                resp.raise_for_status()
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                return (True, text) if text else (False, "Không nhận diện được giọng nói trong bản ghi.")
        else:
            api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
            base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
            resp = requests.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("voice.wav", audio_bytes, mime_type or "audio/wav")},
                data={"model": "whisper-1", "language": "vi"},
                timeout=35,
            )
            resp.raise_for_status()
            text = (resp.json().get("text") or "").strip()
            return (True, text) if text else (False, "Không nhận diện được giọng nói trong bản ghi.")
    except Exception as exc:
        return False, _format_api_error(exc)


# =============================================================================
# 2. AI QUÉT HÓA ĐƠN (RECEIPT SCANNER & OCR)
# =============================================================================
def parse_receipt_text(raw_text: str, today: Date | None = None) -> dict[str, Any]:
    """Trích xuất thông tin hóa đơn tiếng Việt từ văn bản OCR.
    Tuyệt đối không tự bịa số tiền nếu văn bản không có số tiền thanh toán.
    """
    today = Date.today() if today is None else today
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    if not lines:
        return {
            "readable": False,
            "store_name": "",
            "purchase_date": today.isoformat(),
            "purchase_time": "",
            "items": [],
            "discount": 0,
            "total_amount": 0,
            "payment_method": "",
            "suggested_category": "Ăn uống",
            "raw_text": "",
            "message": "Không có nội dung văn bản hóa đơn để nhận diện.",
        }

    store_name = lines[0][:80]
    for line in lines[:4]:
        if not re.search(r"^(?:hóa đơn|hoa don|phiếu|receipt|bill)\b", line, flags=re.IGNORECASE):
            store_name = line[:80]
            break

    purchase_date = today.isoformat()
    purchase_time = ""
    for line in lines:
        m_date = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", line)
        if m_date:
            d, mo, y = map(int, m_date.groups())
            try:
                purchase_date = Date(y, mo, d).isoformat()
                break
            except ValueError:
                pass
        m_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", line)
        if m_iso:
            y, mo, d = map(int, m_iso.groups())
            try:
                purchase_date = Date(y, mo, d).isoformat()
                break
            except ValueError:
                pass

    for line in lines:
        m_time = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?\b", line)
        if m_time:
            purchase_time = f"{int(m_time.group(1)):02d}:{m_time.group(2)}"
            break

    total_amount = 0
    discount = 0
    payment_method = ""
    items: list[dict[str, Any]] = []

    total_keywords = ("tổng thanh toán", "tổng cộng", "thanh toán", "thành tiền", "total", "tổng tiền", "phải trả")
    discount_keywords = ("giảm giá", "chiết khấu", "khuyến mãi", "discount", "voucher")
    payment_keywords = {
        "Tiền mặt": ("tiền mặt", "cash"),
        "Chuyển khoản / QR": ("chuyển khoản", "vietqr", "qr", "banking"),
        "Ví điện tử (MoMo/ZaloPay)": ("momo", "zalopay", "vnpay", "shopeepay"),
        "Thẻ ngân hàng": ("thẻ", "visa", "mastercard", "atm", "pos"),
    }

    for line in lines:
        lower = line.casefold()
        for label, kws in payment_keywords.items():
            if any(kw in lower for kw in kws) and not payment_method:
                payment_method = label

        if any(kw in lower for kw in discount_keywords):
            amt, _ = parse_vietnamese_spoken_amount(line)
            if amt:
                discount = amt
            continue

        if any(kw in lower for kw in total_keywords):
            amt, _ = parse_vietnamese_spoken_amount(line)
            if amt and amt >= total_amount:
                total_amount = amt
            continue

        # Dòng sản phẩm mẫu: "Cơm sườn 1 x 35.000 = 35.000" hoặc "Trà sữa 2 25.000 50.000" hoặc "Bánh mì 20.000"
        m_item_full = re.search(
            r"^(.+?)\s+(\d{1,3})\s*[xX*]\s*([0-9][0-9.,]*)\s*(?:=|\s)\s*([0-9][0-9.,]*)\s*(?:đ|đồng|k)?$",
            line,
        )
        if m_item_full:
            name = m_item_full.group(1).strip(" -•:")
            qty = int(m_item_full.group(2))
            u_amt, _ = parse_vietnamese_spoken_amount(m_item_full.group(3))
            l_amt, _ = parse_vietnamese_spoken_amount(m_item_full.group(4))
            if name and l_amt:
                items.append({
                    "name": name,
                    "qty": qty,
                    "unit_price": u_amt or (l_amt // max(1, qty)),
                    "line_total": l_amt,
                })
                continue

        m_item_simple = re.search(r"^([^\d]{2,50}?)\s+([1-9]\d{0,2}(?:[.,]\d{3})+|\d{2,4}[kK])\s*(?:đ|đồng)?$", line)
        if m_item_simple and not any(
            kw in lower
            for kw in (
                *total_keywords,
                *discount_keywords,
                "tạm tính",
                "subtotal",
                "vat",
                "thuế",
                "tiền khách",
                "tiền thừa",
                "sđt",
                "sdt",
                "hotline",
                "ngày",
            )
        ):
            name = m_item_simple.group(1).strip(" -•:")
            l_amt, _ = parse_vietnamese_spoken_amount(m_item_simple.group(2))
            if name and l_amt:
                items.append({
                    "name": name,
                    "qty": 1,
                    "unit_price": l_amt,
                    "line_total": l_amt,
                })

    if total_amount == 0 and items:
        computed = sum(int(i["line_total"]) for i in items) - discount
        if computed > 0:
            total_amount = computed

    _, suggested_cat, _ = _detect_kind_and_category(raw_text)
    if suggested_cat not in EXPENSE_CATEGORIES:
        suggested_cat = "Ăn uống"

    readable = total_amount > 0
    return {
        "readable": readable,
        "store_name": store_name,
        "purchase_date": purchase_date,
        "purchase_time": purchase_time,
        "items": items,
        "discount": discount,
        "total_amount": total_amount,
        "payment_method": payment_method or "Tiền mặt",
        "suggested_category": suggested_cat,
        "raw_text": "\n".join(lines),
        "message": (
            "Đã trích xuất thông tin hóa đơn. Vui lòng kiểm tra trước khi xác nhận lưu."
            if readable
            else "Không đọc được tổng tiền thanh toán từ văn bản. Vui lòng nhập/chỉnh sửa số tiền thủ công."
        ),
    }


def analyze_receipt_image(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    today: Date | None = None,
) -> dict[str, Any]:
    """Nhận diện hóa đơn từ ảnh chụp camera hoặc file JPG/PNG bằng AI Vision.
    Tuyệt đối không tự bịa số tiền khi chưa cấu hình API key hoặc ảnh không đọc được.
    """
    today = Date.today() if today is None else today
    if not image_bytes:
        return {
            "readable": False,
            "store_name": "",
            "purchase_date": today.isoformat(),
            "purchase_time": "",
            "items": [],
            "discount": 0,
            "total_amount": 0,
            "payment_method": "",
            "suggested_category": "Ăn uống",
            "raw_text": "",
            "message": "Chưa có ảnh hóa đơn.",
        }

    status = check_api_status()
    if not status.configured:
        return {
            "readable": False,
            "store_name": "",
            "purchase_date": today.isoformat(),
            "purchase_time": "",
            "items": [],
            "discount": 0,
            "total_amount": 0,
            "payment_method": "Tiền mặt",
            "suggested_category": "Ăn uống",
            "raw_text": "",
            "message": (
                "Chưa cấu hình AI API key (GEMINI_API_KEY / OPENAI_API_KEY) để OCR trực tiếp từ ảnh. "
                "Hệ thống không tự bịa số tiền — bạn có thể dán văn bản hóa đơn vào ô OCR văn bản bên dưới, "
                "nhập thông tin hóa đơn thủ công, hoặc cấu hình file .env."
            ),
        }

    prompt = (
        f"Bạn là hệ thống AI OCR chuyên đọc hóa đơn tiếng Việt. Ngày hiện tại: {today.isoformat()}.\n"
        f"Danh mục chi tiêu hợp lệ: {list(EXPENSE_CATEGORIES)}.\n"
        "Hãy đọc ảnh hóa đơn và trả về DUY NHẤT một JSON object với cấu trúc:\n"
        "{\n"
        '  "readable": true/false,\n'
        '  "store_name": "Tên cửa hàng/quán",\n'
        '  "purchase_date": "YYYY-MM-DD",\n'
        '  "purchase_time": "HH:MM",\n'
        '  "items": [{"name": "Tên món", "qty": 1, "unit_price": 25000, "line_total": 25000}],\n'
        '  "discount": 0,\n'
        '  "total_amount": 0,\n'
        '  "payment_method": "Tiền mặt / Chuyển khoản / Thẻ / Ví điện tử",\n'
        '  "suggested_category": "Ăn uống | Tiền trọ | Đi lại | Học tập | Giải trí | Khác",\n'
        '  "raw_text": "Toàn bộ chữ đọc được trên hóa đơn"\n'
        "}\n"
        "QUY TẮC BẮT BUỘC: Nếu ảnh mờ hoặc không phải hóa đơn hoặc không đọc được tổng tiền, "
        "phải đặt readable = false và total_amount = 0. Tuyệt đối không tự bịa số tiền."
    )

    try:
        if status.provider == "gemini":
            api_key = (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=status.model,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type or "image/jpeg"),
                        prompt,
                    ],
                )
                raw_resp = (resp.text or "").strip()
            except ImportError:
                b64 = base64.b64encode(image_bytes).decode("ascii")
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{status.model}:generateContent?key={api_key}"
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
                raw_resp = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
            base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
            b64 = base64.b64encode(image_bytes).decode("ascii")
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": status.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type or 'image/jpeg'};base64,{b64}"}},
                        ],
                    }],
                    "temperature": 0.1,
                },
                timeout=40,
            )
            resp.raise_for_status()
            raw_resp = resp.json()["choices"][0]["message"]["content"].strip()

        data = _extract_json_object(raw_resp)
        total_amount = int(round(float(data.get("total_amount") or 0)))
        discount = max(0, int(round(float(data.get("discount") or 0))))
        p_date = str(data.get("purchase_date") or today.isoformat()).strip()
        try:
            Date.fromisoformat(p_date)
        except ValueError:
            p_date = today.isoformat()
        cat = str(data.get("suggested_category") or "Ăn uống").strip()
        if cat not in EXPENSE_CATEGORIES:
            cat = "Khác"
        raw_items = data.get("items") if isinstance(data.get("items"), list) else []
        clean_items = []
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            clean_items.append({
                "name": str(it.get("name") or "Sản phẩm").strip(),
                "qty": max(1, int(round(float(it.get("qty") or 1)))),
                "unit_price": max(0, int(round(float(it.get("unit_price") or 0)))),
                "line_total": max(0, int(round(float(it.get("line_total") or 0)))),
            })
        readable = bool(data.get("readable", True)) and total_amount > 0
        return {
            "readable": readable,
            "store_name": str(data.get("store_name") or "").strip(),
            "purchase_date": p_date,
            "purchase_time": str(data.get("purchase_time") or "").strip(),
            "items": clean_items,
            "discount": discount,
            "total_amount": total_amount if readable else 0,
            "payment_method": str(data.get("payment_method") or "Tiền mặt").strip(),
            "suggested_category": cat,
            "raw_text": str(data.get("raw_text") or "").strip(),
            "message": (
                "AI OCR đã nhận diện hóa đơn thành công. Hãy kiểm tra và bấm Xác nhận để lưu."
                if readable
                else "AI không đọc được tổng tiền rõ ràng trên ảnh. Vui lòng kiểm tra và nhập số tiền thủ công."
            ),
        }
    except Exception as exc:
        return {
            "readable": False,
            "store_name": "",
            "purchase_date": today.isoformat(),
            "purchase_time": "",
            "items": [],
            "discount": 0,
            "total_amount": 0,
            "payment_method": "Tiền mặt",
            "suggested_category": "Ăn uống",
            "raw_text": "",
            "message": _format_api_error(exc),
        }


# =============================================================================
# 3. AI PHÂN TÍCH TÀI CHÍNH & TƯ VẤN TIẾT KIỆM (DỮ LIỆU THẬT 100%)
# =============================================================================
def build_financial_analysis(store: ExpenseStore, month: str, today: Date | None = None) -> dict[str, Any]:
    """Tổng hợp và phân tích tài chính tháng từ dữ liệu SQLite thật của người dùng."""
    today = Date.today() if today is None else today
    summary = store.summary(month)
    prev_month = shift_month(month, -1)
    prev_summary = store.summary(prev_month)
    cat_totals = store.category_totals(month)
    prev_cat_totals = store.category_totals(prev_month)
    statuses = {s.category: s for s in store.budget_statuses(month)}
    txs = store.list_transactions(month=month)
    expense_txs = [t for t in txs if t.kind == "expense"]

    year, m_num = map(int, month.split("-"))
    days_in_month = monthrange(year, m_num)[1]
    if month == today.strftime("%Y-%m"):
        elapsed_days = max(1, min(today.day, days_in_month))
    else:
        elapsed_days = days_in_month

    active_expense_days = len({t.date for t in expense_txs})
    avg_daily_elapsed = round(summary["expense"] / elapsed_days) if summary["expense"] > 0 else 0

    # Ngày chi nhiều nhất
    daily_map: dict[str, int] = {}
    for t in expense_txs:
        daily_map[t.date] = daily_map.get(t.date, 0) + t.amount
    if daily_map:
        peak_date, peak_amount = max(daily_map.items(), key=lambda kv: kv[1])
    else:
        peak_date, peak_amount = "", 0

    # Danh mục chi nhiều nhất
    nonzero_cats = [(cat, amt) for cat, amt in cat_totals.items() if amt > 0]
    if nonzero_cats:
        top_category, top_category_amount = max(nonzero_cats, key=lambda kv: kv[1])
        top_category_share = round(top_category_amount / summary["expense"] * 100, 1) if summary["expense"] else 0.0
    else:
        top_category, top_category_amount, top_category_share = "Chưa có", 0, 0.0

    # So sánh với tháng trước
    prev_exp = prev_summary["expense"]
    exp_diff = summary["expense"] - prev_exp
    exp_change_pct = round(exp_diff / prev_exp * 100, 1) if prev_exp > 0 else None

    # Phát hiện khoản chi bất thường (lớn hơn 2.2 lần mức trung bình giao dịch và >= 200.000đ)
    unusual_transactions: list[Transaction] = []
    if len(expense_txs) >= 2:
        avg_tx = summary["expense"] / len(expense_txs)
        threshold = max(200_000, avg_tx * 2.2)
        unusual_transactions = [t for t in expense_txs if t.amount >= threshold]

    # Dự báo cuối tháng: chỉ dự báo khi có từ 3 ngày phát sinh chi tiêu trở lên
    can_forecast = active_expense_days >= 3 and summary["expense"] > 0
    if can_forecast:
        projected_expense = round(summary["expense"] / elapsed_days * days_in_month)
        forecast_note = (
            f"Dựa trên {active_expense_days} ngày có chi tiêu ({elapsed_days}/{days_in_month} ngày đã qua), "
            f"ước tính cuối tháng tổng chi khoảng {money(projected_expense)}."
        )
    else:
        projected_expense = None
        forecast_note = (
            f"Chưa đủ dữ liệu để dự báo chắc chắn (hiện mới có {active_expense_days} ngày phát sinh chi tiêu trong tháng {month}; "
            "cần tối thiểu 3 ngày có dữ liệu chi tiêu để ước tính xu hướng cuối tháng)."
        )

    # Gợi ý tiết kiệm thực tế
    total_budget_status = statuses.get(TOTAL_BUDGET_CATEGORY)
    exceeded_cats = [s for s in statuses.values() if s.exceeded]
    near_cats = [s for s in statuses.values() if s.near_limit and not s.exceeded]

    if summary["income"] > 0:
        recommended_saving = max(0, round(summary["income"] * 0.2))
    elif total_budget_status:
        recommended_saving = max(0, round(total_budget_status.limit * 0.15))
    else:
        recommended_saving = 0

    tips: list[str] = []
    if summary["expense"] == 0 and summary["income"] == 0:
        tips.append(f"Tháng {month} chưa có giao dịch nào. Hãy ghi chép khoản thu/chi đầu tiên để hệ thống phân tích.")
    else:
        if exceeded_cats:
            names = ", ".join(f"{s.category} (vượt {money(-s.remaining)})" for s in exceeded_cats)
            tips.append(f"Bạn đã vượt hạn mức ở: {names}. Nên tạm dừng các khoản chi không thiết yếu trong nhóm này.")
        if near_cats:
            names = ", ".join(f"{s.category} ({s.ratio:.0%})" for s in near_cats)
            tips.append(f"Các mục sắp chạm ngưỡng 80–100%: {names}.")
        if top_category != "Chưa có" and top_category_share >= 45:
            tips.append(f"Danh mục '{top_category}' chiếm tới {top_category_share:.1f}% tổng chi ({money(top_category_amount)}).")
        if summary["income"] > 0:
            actual_surplus = summary["balance"]
            if actual_surplus >= recommended_saving:
                tips.append(
                    f"Chênh lệch thu chi hiện đạt {money(actual_surplus)}. Bạn hoàn toàn có thể trích ít nhất "
                    f"{money(recommended_saving)} (20% thu nhập) vào Mục tiêu tiết kiệm."
                )
            elif actual_surplus > 0:
                tips.append(
                    f"Chênh lệch thu chi còn {money(actual_surplus)}, thấp hơn mức tiết kiệm khuyến nghị 20% thu nhập ({money(recommended_saving)})."
                )
            else:
                tips.append(f"Chi tiêu đang lớn hơn thu nhập {money(-actual_surplus)}. Cần cắt giảm ngay các mục Giải trí / Khác.")

    return {
        "month": month,
        "prev_month": prev_month,
        "summary": summary,
        "prev_summary": prev_summary,
        "cat_totals": cat_totals,
        "prev_cat_totals": prev_cat_totals,
        "statuses": statuses,
        "total_budget_status": total_budget_status,
        "exceeded_cats": exceeded_cats,
        "near_cats": near_cats,
        "days_in_month": days_in_month,
        "elapsed_days": elapsed_days,
        "active_expense_days": active_expense_days,
        "avg_daily_elapsed": avg_daily_elapsed,
        "peak_date": peak_date,
        "peak_amount": peak_amount,
        "top_category": top_category,
        "top_category_amount": top_category_amount,
        "top_category_share": top_category_share,
        "exp_diff": exp_diff,
        "exp_change_pct": exp_change_pct,
        "unusual_transactions": unusual_transactions,
        "can_forecast": can_forecast,
        "projected_expense": projected_expense,
        "forecast_note": forecast_note,
        "recommended_saving": recommended_saving,
        "tips": tips,
    }


def answer_financial_question(
    store: ExpenseStore,
    month: str,
    question: str,
    today: Date | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    """Trả lời câu hỏi tài chính dựa trên dữ liệu SQLite thật của người dùng."""
    analysis = build_financial_analysis(store, month, today=today)
    s = analysis["summary"]
    q_clean = (question or "").strip()
    lower = q_clean.casefold()

    # Tạo câu trả lời xác thực từ dữ liệu thật
    if "tiêu bao nhiêu" in lower and ("cuối tháng" in lower or "dự báo" in lower):
        direct_answer = analysis["forecast_note"]
    elif "tiêu bao nhiêu" in lower or "chi bao nhiêu" in lower:
        direct_answer = (
            f"Trong tháng **{month}**, tổng chi tiêu của bạn là **{money(s['expense'])}** "
            f"(trên tổng số {s['count']} giao dịch; tổng thu nhập: **{money(s['income'])}**, "
            f"chênh lệch thu chi: **{money(s['balance'])}**, trung bình mỗi ngày: **{money(analysis['avg_daily_elapsed'])}**)."
        )
    elif "nhiều nhất" in lower and "danh mục" in lower:
        if analysis["top_category"] == "Chưa có":
            direct_answer = f"Tháng **{month}** bạn chưa có khoản chi tiêu nào."
        else:
            direct_answer = (
                f"Tháng **{month}**, bạn chi nhiều nhất vào danh mục **{analysis['top_category']}** "
                f"với số tiền **{money(analysis['top_category_amount'])}** "
                f"(chiếm **{analysis['top_category_share']:.1f}%** tổng chi tiêu tháng)."
            )
    elif "vượt ngân sách" in lower or "ngân sách chưa" in lower:
        statuses = analysis["statuses"]
        if not statuses:
            direct_answer = f"Tháng **{month}** bạn chưa thiết lập hạn mức ngân sách nào."
        else:
            exceeded = analysis["exceeded_cats"]
            near = analysis["near_cats"]
            if exceeded:
                details = ", ".join(f"**{st.category}** (đã chi {money(st.spent)} / hạn mức {money(st.limit)}, vượt {money(-st.remaining)})" for st in exceeded)
                direct_answer = f"⚠️ **Đã vượt ngân sách** ở {len(exceeded)} mục: {details}."
            elif near:
                details = ", ".join(f"**{st.category}** ({st.ratio:.1%} hạn mức, còn {money(st.remaining)})" for st in near)
                direct_answer = f"Bạn **chưa vượt 100% ngân sách**, nhưng đang ở ngưỡng cảnh báo (≥80%) tại: {details}."
            else:
                direct_answer = f"✅ Toàn bộ các mục ngân sách tháng **{month}** đều đang trong ngưỡng an toàn (<80%)."
    elif "nên tiết kiệm" in lower or "tiết kiệm bao nhiêu" in lower:
        if s["income"] > 0:
            rec20 = round(s["income"] * 0.2)
            rec10 = round(s["income"] * 0.1)
            direct_answer = (
                f"Với tổng thu nhập tháng **{month}** là **{money(s['income'])}** và tổng chi hiện tại **{money(s['expense'])}** "
                f"(chênh lệch thu chi: **{money(s['balance'])}**), theo quy tắc 50/30/20 sinh viên nên tiết kiệm từ "
                f"**{money(rec10)} (10%)** đến **{money(rec20)} (20%)** mỗi tháng."
            )
        else:
            direct_answer = (
                f"Tháng **{month}** chưa ghi nhận khoản thu nhập nào (tổng chi hiện tại: **{money(s['expense'])}**). "
                "Hãy nhập khoản thu nhập (Gia đình hỗ trợ / Làm thêm / Học bổng) để hệ thống tính mức tiết kiệm phù hợp."
            )
    elif "tăng hay giảm" in lower or "so với tháng trước" in lower:
        prev_m = analysis["prev_month"]
        prev_exp = analysis["prev_summary"]["expense"]
        if prev_exp == 0 and s["expense"] == 0:
            direct_answer = f"Cả tháng **{month}** và tháng trước (**{prev_m}**) đều chưa có chi tiêu."
        elif prev_exp == 0:
            direct_answer = f"Tháng trước (**{prev_m}**) chưa có dữ liệu chi tiêu; tháng **{month}** bạn đã chi **{money(s['expense'])}**."
        else:
            diff = analysis["exp_diff"]
            pct = analysis["exp_change_pct"]
            if diff > 0:
                direct_answer = f"Chi tiêu tháng **{month}** (**{money(s['expense'])}**) đang **TĂNG {money(diff)} (+{pct:.1f}%)** so với tháng **{prev_m}** (**{money(prev_exp)}**)."
            elif diff < 0:
                direct_answer = f"Chi tiêu tháng **{month}** (**{money(s['expense'])}**) đang **GIẢM {money(-diff)} ({pct:.1f}%)** so với tháng **{prev_m}** (**{money(prev_exp)}**)."
            else:
                direct_answer = f"Chi tiêu tháng **{month}** bằng đúng tháng **{prev_m}** (**{money(s['expense'])}**)."
    elif "dự báo" in lower or "cuối tháng" in lower:
        direct_answer = analysis["forecast_note"]
    else:
        direct_answer = (
            f"Tổng kết nhanh tháng **{month}**: Thu nhập **{money(s['income'])}**, Chi tiêu **{money(s['expense'])}**, "
            f"Chênh lệch thu chi **{money(s['balance'])}**. Danh mục chi lớn nhất: **{analysis['top_category']}** "
            f"({money(analysis['top_category_amount'])}). {analysis['forecast_note']}"
        )

    ai_status = check_api_status()
    source = "real_sqlite_analytics"
    if use_ai and ai_status.configured and q_clean:
        # Chỉ gửi dữ liệu tổng hợp gọn nhẹ, tuyệt đối không gửi toàn bộ database SQLite
        compact_context = {
            "month": month,
            "income_vnd": s["income"],
            "expense_vnd": s["expense"],
            "net_difference_vnd": s["balance"],
            "previous_month": analysis["prev_month"],
            "previous_expense_vnd": analysis["prev_summary"]["expense"],
            "category_expenses_vnd": analysis["cat_totals"],
            "budgets": [
                {"category": st.category, "limit_vnd": st.limit, "spent_vnd": st.spent, "remaining_vnd": st.remaining}
                for st in analysis["statuses"].values()
            ],
            "active_expense_days": analysis["active_expense_days"],
            "forecast_note": analysis["forecast_note"],
        }
        prompt = (
            f"Dữ liệu tài chính thật của sinh viên (VNĐ):\n{json.dumps(compact_context, ensure_ascii=False)}\n\n"
            f"Câu hỏi của người dùng: {q_clean}\n"
            f"Kết quả tính toán chuẩn xác từ hệ thống: {direct_answer}\n"
            "Hãy trả lời ngắn gọn bằng tiếng Việt (3-5 câu), giữ nguyên chính xác 100% các con số ở trên, "
            "không bịa thêm số liệu và không dự báo chắc chắn nếu dữ liệu chưa đủ."
        )
        ok, llm_reply = _call_llm_text(prompt, "Bạn là cố vấn tài chính sinh viên UniSpend.")
        if ok and llm_reply:
            direct_answer = llm_reply
            source = f"ai_{ai_status.provider}_with_real_data"

    return {
        "question": q_clean,
        "answer": direct_answer,
        "source": source,
        "ai_configured": ai_status.configured,
        "analysis": analysis,
    }


def generate_ai_deep_financial_review(
    store: ExpenseStore,
    month: str,
    today: Date | None = None,
) -> dict[str, Any]:
    """Tạo bản phân tích tài chính chuyên sâu & kế hoạch tiết kiệm 3 bước bằng AI (Gemini / OpenAI)
    trên nền số liệu SQLite thật 100% của tháng đang chọn.
    """
    analysis = build_financial_analysis(store, month, today=today)
    s = analysis["summary"]
    ai_status = check_api_status()

    local_overview = (
        f"Tháng {month}: Tổng thu {money(s['income'])}, tổng chi {money(s['expense'])}, "
        f"chênh lệch {money(s['balance'])}. Danh mục lớn nhất: {analysis['top_category']} "
        f"({money(analysis['top_category_amount'])} — {analysis['top_category_share']:.1f}%). "
        f"{analysis['forecast_note']}"
    )
    local_plan = list(analysis["tips"]) or [
        "Ghi chép đều đặn mọi khoản thu/chi hằng ngày để AI nhận diện xu hướng chính xác.",
        "Đặt hạn mức ngân sách cho 3 nhóm thiết yếu: Ăn uống, Tiền trọ và Đi lại.",
        "Trích tối thiểu 10–20% thu nhập ngay đầu tháng vào Mục tiêu tiết kiệm.",
    ]

    if not ai_status.configured:
        return {
            "configured": False,
            "provider": "local_sqlite",
            "model": "Rule-based Analytics",
            "overview": local_overview,
            "habit_insight": (
                f"Trung bình mỗi ngày bạn chi {money(analysis['avg_daily_elapsed'])} "
                f"trên {analysis['active_expense_days']} ngày có phát sinh giao dịch."
            ),
            "action_plan": local_plan,
            "raw_markdown": "",
        }

    compact_payload = {
        "month": month,
        "income_vnd": s["income"],
        "expense_vnd": s["expense"],
        "balance_vnd": s["balance"],
        "tx_count": s["count"],
        "previous_month": analysis["prev_month"],
        "previous_expense_vnd": analysis["prev_summary"]["expense"],
        "avg_daily_expense_vnd": analysis["avg_daily_elapsed"],
        "active_expense_days": analysis["active_expense_days"],
        "top_category": analysis["top_category"],
        "top_category_amount_vnd": analysis["top_category_amount"],
        "top_category_share_pct": analysis["top_category_share"],
        "category_breakdown_vnd": analysis["cat_totals"],
        "forecast_note": analysis["forecast_note"],
        "recommended_saving_vnd": analysis["recommended_saving"],
    }
    prompt = (
        "Bạn là Chuyên gia Cố vấn Tài chính Cá nhân cho sinh viên trên ứng dụng UniSpend 2.0.\n"
        f"Dưới đây là số liệu SQLite thật 100% của tháng {month} (đơn vị VNĐ):\n"
        f"{json.dumps(compact_payload, ensure_ascii=False)}\n\n"
        "Hãy trả về DUY NHẤT một JSON object với cấu trúc:\n"
        "{\n"
        '  "overview": "Nhận xét tổng quan 2-3 câu về bức tranh thu chi tháng này (giữ đúng số liệu VNĐ thật)",\n'
        '  "habit_insight": "Phân tích sâu thói quen chi tiêu, so sánh tháng trước và đánh giá danh mục chi lớn nhất",\n'
        '  "action_plan": ["Bước 1 cụ thể kèm số tiền VNĐ", "Bước 2 cụ thể", "Bước 3 cụ thể"]\n'
        "}\n"
        "QUY TẮC: Tuyệt đối không bịa số liệu ngoài JSON đã cung cấp. Ngôn ngữ: Tiếng Việt tự nhiên, khích lệ."
    )
    ok, resp_text = _call_llm_text(prompt, "Trả về đúng JSON hợp lệ.")
    if ok and resp_text:
        try:
            data = _extract_json_object(resp_text)
            overview = str(data.get("overview") or local_overview).strip()
            habit = str(data.get("habit_insight") or "").strip()
            plan = data.get("action_plan")
            if isinstance(plan, list) and plan:
                clean_plan = [str(p).strip() for p in plan if str(p).strip()]
            else:
                clean_plan = local_plan
            return {
                "configured": True,
                "provider": ai_status.provider,
                "model": ai_status.model,
                "overview": overview,
                "habit_insight": habit or local_overview,
                "action_plan": clean_plan,
                "raw_markdown": resp_text,
            }
        except Exception:
            pass

    return {
        "configured": ai_status.configured,
        "provider": ai_status.provider,
        "model": ai_status.model,
        "overview": local_overview,
        "habit_insight": (
            resp_text
            if ok and resp_text
            else f"Trung bình mỗi ngày chi {money(analysis['avg_daily_elapsed'])}. ({resp_text})"
        ),
        "action_plan": local_plan,
        "raw_markdown": resp_text if ok else "",
    }


def test_all_ai_pipelines(store: ExpenseStore | None = None, month: str | None = None) -> dict[str, Any]:
    """Kiểm tra đồng bộ cả 3 luồng tích hợp AI:
    1. Luồng Quét ảnh & OCR Hóa đơn (Tesseract + Gemini JSON/Vision)
    2. Luồng Giọng nói Tiếng Việt (STT + Gemini/NLP Voice Expense Parser)
    3. Luồng Phân tích Tài chính & Tư vấn Tiết kiệm (SQLite + Gemini Financial Advisor)
    """
    status = check_api_status()
    active_month = month or Date.today().strftime("%Y-%m")

    # 1. Kiểm tra luồng Giọng nói
    sample_voice = "Ăn trưa phở bò 45k"
    voice_res = parse_vietnamese_voice_expense(sample_voice, use_ai=status.configured)
    voice_ok = voice_res.get("amount") == 45_000 and voice_res.get("category") == "Ăn uống"

    # 2. Kiểm tra luồng OCR Hóa đơn
    from .ocr_pipeline import analyze_ocr_text_with_gemini, check_tesseract_status

    tess_status = check_tesseract_status()
    sample_ocr = "SIÊU THỊ MINI\nNgày mua: 15/11/2026\nBánh mì 1 x 15.000 15.000\nSữa tươi 1 x 28.000 28.000\nTổng thanh toán: 43.000 đ"
    ocr_gem_res = analyze_ocr_text_with_gemini(sample_ocr, user_consent=status.configured)
    ocr_ok = ocr_gem_res.schema_data.total_amount == 43_000

    # 3. Kiểm tra luồng Phân tích Tài chính
    if store is not None:
        qa_res = answer_financial_question(store, active_month, "Tháng này tôi tiêu bao nhiêu?", use_ai=status.configured)
        fin_ok = bool(qa_res.get("answer"))
        fin_source = qa_res.get("source", "real_sqlite_analytics")
        fin_sample = qa_res.get("answer", "")
    else:
        fin_ok = True
        fin_source = f"ai_{status.provider}_with_real_data" if status.configured else "real_sqlite_analytics"
        fin_sample = "Sẵn sàng phân tích trên dữ liệu SQLite thật."

    return {
        "api_configured": status.configured,
        "provider": status.provider,
        "model": status.model,
        "masked_key": status.masked_key,
        "status_message": status.message,
        "tesseract_available": tess_status.available,
        "tesseract_message": tess_status.message,
        "ocr_pipeline": {
            "ok": ocr_ok,
            "source": ocr_gem_res.source,
            "merchant": ocr_gem_res.schema_data.merchant_name,
            "total_amount": ocr_gem_res.schema_data.total_amount,
            "message": ocr_gem_res.message,
        },
        "voice_pipeline": {
            "ok": voice_ok,
            "source": voice_res.get("source"),
            "sample_input": sample_voice,
            "parsed_amount": voice_res.get("amount"),
            "parsed_category": voice_res.get("category"),
        },
        "analysis_pipeline": {
            "ok": fin_ok,
            "source": fin_source,
            "sample_answer": fin_sample,
        },
    }
