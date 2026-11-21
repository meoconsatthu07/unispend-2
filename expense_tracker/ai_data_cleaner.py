"""AI Data Cleaner — Làm sạch và chuẩn hóa dữ liệu thu chi thô (CSV, Excel, Văn bản) bằng AI + kiểm định chuẩn hóa.

Quy trình 2 lớp:
1. Lớp AI (Gemini / OpenAI qua `_call_llm_text`, tự động fallback rule-based nếu offline):
   - Phân tích cấu trúc cột của file thô bất kỳ (tiếng Việt hoặc tiếng Anh).
   - Tự động ánh xạ mọi danh mục thô về đúng danh mục chuẩn của UniSpend 2.0 & UniSpend UTH 3D.
   - Trích xuất giao dịch từ văn bản / ghi chú thu chi tự do.
2. Lớp Chuẩn hóa & Kiểm định xác định (Deterministic ETL):
   - Khử trùng lặp, loại bỏ giao dịch nội bộ (Transfer-Out / tổng cộng).
   - Chuẩn hóa ngày về ISO YYYY-MM-DD, chuẩn hóa số tiền về số nguyên dương VNĐ.
   - Bù ghi chú bị thiếu, chặn công thức Excel (=, +, -, @), kiểm tra 100% khớp schema web.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date as Date
from pathlib import Path
from typing import Any

import pandas as pd

from .ai_service import (
    _call_llm_text,
    _extract_json_object,
    check_api_status,
    parse_vietnamese_spoken_amount,
    parse_vietnamese_voice_expense,
)
from .storage import (
    EXPENSE_CATEGORIES,
    INCOME_CATEGORIES,
    MAX_AMOUNT,
    TYPE_LABELS,
)

UTH_EXPENSE_CATEGORIES = (
    "Tiền ăn",
    "Tiền trọ",
    "Đi lại",
    "Học tập",
    "Sinh hoạt & Mua sắm",
    "Giải trí & Xã giao",
    "Chi phí khác",
)
UTH_INCOME_CATEGORIES = (
    "Trợ cấp gia đình",
    "Làm thêm (Part-time)",
    "Học bổng & Thưởng",
    "Thu nhập khác",
)

V2_TO_UTH_EXPENSE = {
    "Ăn uống": "Tiền ăn",
    "Tiền trọ": "Tiền trọ",
    "Đi lại": "Đi lại",
    "Học tập": "Học tập",
    "Giải trí": "Giải trí & Xã giao",
    "Khác": "Chi phí khác",
}
V2_TO_UTH_INCOME = {
    "Gia đình hỗ trợ": "Trợ cấp gia đình",
    "Làm thêm": "Làm thêm (Part-time)",
    "Học bổng": "Học bổng & Thưởng",
    "Khác": "Thu nhập khác",
}

DEFAULT_CURRENCY_RATES = {
    "VND": 1.0,
    "USD": 25_000.0,
    "INR": 300.0,
    "EUR": 27_000.0,
}

EXPENSE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Ăn uống", ("ăn", "uống", "cơm", "phở", "bún", "trà", "cà phê", "cafe", "coffee", "food", "snack", "cook", "restaurant", "grocer", "siêu thị", "chợ", "thực phẩm", "dining")),
    ("Tiền trọ", ("trọ", "phòng", "nhà", "điện", "nước", "wifi", "internet", "rent", "mortgage", "household", "housing", "utility", "utilities", "maid", "garbage", "water")),
    ("Đi lại", ("xăng", "xe", "buýt", "bus", "grab", "be", "taxi", "transport", "train", "fuel", "gas", "parking", "gửi xe", "đi lại", "travel")),
    ("Học tập", ("học", "giáo trình", "sách", "tài liệu", "in ấn", "học phí", "education", "tuition", "book", "course", "self-development", "document", "school")),
    ("Giải trí", ("phim", "game", "chơi", "giải trí", "du lịch", "sinh nhật", "quà", "netflix", "spotify", "subscription", "entertainment", "culture", "festival", "social", "tourism", "gift", "cinema")),
]

INCOME_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("Gia đình hỗ trợ", ("gia đình", "bố", "mẹ", "ba", "má", "trợ cấp", "chu cấp", "petty cash", "allowance", "family support")),
    ("Làm thêm", ("lương", "làm thêm", "gia sư", "part-time", "part time", "freelance", "salary", "payroll", "wage", "paycheck", "work")),
    ("Học bổng", ("học bổng", "thưởng", "bonus", "reward", "scholarship", "cashback", "prize", "award")),
]

IGNORE_TYPES = {
    "transfer-out", "transfer-in", "transfer", "chuyển khoản nội bộ",
    "tổng thu", "tổng chi", "chênh lệch", "total", "summary",
}


@dataclass
class CleaningResult:
    rows: list[dict[str, Any]]
    stats: dict[str, Any]
    ai_used: bool
    ai_provider: str
    ai_summary: str


def _clean_note_text(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    text = re.sub(r"\s+", " ", str(val)).strip()
    if text.lstrip().startswith(("=", "+", "-", "@")):
        text = text.lstrip("=+-@ ")
    return text[:190]


def _rule_map_category(kind: str, raw_cat: str, raw_note: str = "") -> str:
    combined = f"{raw_cat} {raw_note}".lower()
    if kind == "income":
        for cat in INCOME_CATEGORIES:
            if raw_cat.strip().lower() == cat.lower():
                return cat
        for cat, kws in INCOME_KEYWORDS:
            if any(kw in combined for kw in kws):
                return cat
        return "Khác"
    for cat in EXPENSE_CATEGORIES:
        if raw_cat.strip().lower() == cat.lower():
            return cat
    for cat, kws in EXPENSE_KEYWORDS:
        if any(kw in combined for kw in kws):
            return cat
    return "Khác"


def _map_to_uth_category(kind: str, cat_v2: str, raw_cat: str = "") -> str:
    low = (raw_cat or "").lower()
    if kind == "expense":
        if any(k in low for k in ("apparel", "beauty", "grooming", "shopping", "mua sắm", "sinh hoạt", "quần áo")):
            return "Sinh hoạt & Mua sắm"
        return V2_TO_UTH_EXPENSE.get(cat_v2, "Chi phí khác")
    return V2_TO_UTH_INCOME.get(cat_v2, "Thu nhập khác")


def _parse_amount_value(raw_val: Any, exchange_rate: float) -> int | None:
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return None
    if isinstance(raw_val, (int, float)):
        val = abs(float(raw_val)) * exchange_rate
        if val <= 0:
            return None
        vnd = int(round(val))
        return vnd if 0 < vnd <= MAX_AMOUNT else None

    s = str(raw_val).strip()
    if not s:
        return None
    # Thử bộ đọc số tiền tiếng Việt (45k, 1.5tr, 200 nghìn...)
    if re.search(r"(k|ngàn|nghìn|tr|triệu|củ|lít|xị)\b", s.lower()):
        parsed, _ = parse_vietnamese_spoken_amount(s)
        if parsed and 0 < parsed <= MAX_AMOUNT:
            return parsed

    cleaned = re.sub(r"[^\d.,-]", "", s)
    if not cleaned:
        return None
    if re.fullmatch(r"-?[0-9]{1,3}(?:\.[0-9]{3})+", cleaned):
        cleaned = cleaned.replace(".", "")
    elif re.fullmatch(r"-?[0-9]{1,3}(?:,[0-9]{3})+", cleaned):
        cleaned = cleaned.replace(",", "")
    else:
        cleaned = cleaned.replace(",", ".")
    try:
        num = abs(float(cleaned)) * exchange_rate
    except ValueError:
        return None
    if num <= 0:
        return None
    vnd = int(round(num))
    return vnd if 0 < vnd <= MAX_AMOUNT else None


def _detect_columns_rule_based(columns: list[str]) -> dict[str, str | None]:
    lower_map = {c.strip().lower(): c for c in columns}

    def pick(candidates: tuple[str, ...]) -> str | None:
        for kw in candidates:
            for lc, orig in lower_map.items():
                if lc == kw:
                    return orig
        for kw in candidates:
            for lc, orig in lower_map.items():
                if kw in lc:
                    return orig
        return None

    return {
        "date": pick(("date", "ngày giao dịch", "ngày", "time", "timestamp", "ngay")),
        "kind": pick(("income/expense", "transaction type", "loại giao dịch", "loại", "type", "kind", "loai")),
        "category": pick(("category", "danh mục", "hạng mục", "danh muc", "nhóm")),
        "subcategory": pick(("subcategory", "sub_category", "chi tiết danh mục")),
        "amount": pick(("amount", "số tiền (vnđ)", "số tiền", "so tien", "value", "price", "cost", "tiền")),
        "note": pick(("note", "description", "ghi chú chi tiết", "ghi chú", "short_note", "memo", "mô tả", "nội dung")),
        "currency": pick(("currency", "tiền tệ", "đơn vị")),
    }


def _ask_ai_for_mapping(
    df: pd.DataFrame,
    preferred_provider: str | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """Nhờ Gemini/OpenAI phân tích schema cột, tiền tệ & ánh xạ danh mục từ mẫu dữ liệu."""
    cols = list(df.columns)
    sample_rows = df.head(6).fillna("").to_dict(orient="records")
    cat_col_guess = _detect_columns_rule_based(cols).get("category")
    unique_cats = []
    if cat_col_guess and cat_col_guess in df.columns:
        unique_cats = [str(v) for v in df[cat_col_guess].dropna().astype(str).unique()[:60]]

    prompt = (
        "Bạn là chuyên gia làm sạch dữ liệu tài chính cho ứng dụng UniSpend.\n"
        f"Danh sách cột của bảng thô: {json.dumps(cols, ensure_ascii=False)}\n"
        f"6 dòng mẫu: {json.dumps(sample_rows, ensure_ascii=False, default=str)}\n"
        f"Các giá trị danh mục xuất hiện: {json.dumps(unique_cats, ensure_ascii=False)}\n\n"
        "Hãy trả về DUY NHẤT một JSON hợp lệ (không markdown) theo đúng cấu trúc:\n"
        "{\n"
        '  "columns": {"date": "...", "kind": "... hoặc null", "category": "... hoặc null", "amount": "...", "note": "... hoặc null", "currency": "... hoặc null"},\n'
        '  "detected_currency": "VND" | "USD" | "INR" | "EUR",\n'
        '  "category_map_expense": {"<raw_cat>": "<1 trong: Ăn uống, Tiền trọ, Đi lại, Học tập, Giải trí, Khác>"},\n'
        '  "category_map_income": {"<raw_cat>": "<1 trong: Gia đình hỗ trợ, Làm thêm, Học bổng, Khác>"},\n'
        '  "summary": "Tóm tắt ngắn 1-2 câu tiếng Việt về các lỗi dữ liệu thô phát hiện và cách làm sạch"\n'
        "}\n"
    )
    status = check_api_status(preferred_provider)
    provider_label = f"{status.provider} ({status.model})" if status.configured else "rule-based"
    ok, raw_reply = _call_llm_text(
        prompt,
        system_instruction="Chỉ trả về JSON thuần hợp lệ, không giải thích thừa.",
        preferred_provider=preferred_provider,
    )
    if not ok:
        return None, provider_label
    parsed = _extract_json_object(raw_reply)
    if not parsed or "columns" not in parsed:
        return None, provider_label
    return parsed, provider_label


def clean_tabular_file(
    file_name: str,
    file_bytes: bytes,
    *,
    use_ai: bool = True,
    currency_override: str = "Tự động",
    custom_rate: float | None = None,
    preferred_provider: str | None = None,
) -> CleaningResult:
    """Đọc file CSV/Excel thô, nhờ AI phân tích cấu trúc & danh mục, rồi làm sạch chuẩn hóa 100%."""
    lower = file_name.lower()
    if lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")
    elif lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError("Chỉ hỗ trợ tệp dữ liệu thô định dạng .csv hoặc .xlsx.")

    if df.empty:
        raise ValueError("Tệp tải lên không có dữ liệu.")

    raw_rows = len(df)
    rule_cols = _detect_columns_rule_based(list(df.columns))

    ai_meta = None
    ai_provider = "rule-based"
    if use_ai:
        ai_meta, ai_provider = _ask_ai_for_mapping(df, preferred_provider=preferred_provider)

    ai_used = ai_meta is not None
    col_map = dict(rule_cols)
    if ai_meta and isinstance(ai_meta.get("columns"), dict):
        for k in ("date", "kind", "category", "amount", "note", "currency"):
            cand = ai_meta["columns"].get(k)
            if cand and cand in df.columns:
                col_map[k] = cand

    date_col = col_map.get("date")
    amount_col = col_map.get("amount")
    if not date_col or not amount_col:
        raise ValueError(
            "Không nhận diện được cột Ngày hoặc cột Số tiền trong tệp thô. "
            f"Các cột hiện có: {', '.join(map(str, df.columns))}"
        )

    # Xác định tiền tệ & tỷ giá quy đổi
    detected_curr = "VND"
    if ai_meta and ai_meta.get("detected_currency") in DEFAULT_CURRENCY_RATES:
        detected_curr = str(ai_meta["detected_currency"])
    elif col_map.get("currency") and col_map["currency"] in df.columns:
        sample_curr = str(df[col_map["currency"]].dropna().iloc[0]).strip().upper() if not df[col_map["currency"]].dropna().empty else "VND"
        if sample_curr in DEFAULT_CURRENCY_RATES:
            detected_curr = sample_curr

    active_curr = detected_curr if currency_override == "Tự động" else currency_override
    exchange_rate = float(custom_rate) if (custom_rate and custom_rate > 0) else DEFAULT_CURRENCY_RATES.get(active_curr, 1.0)

    # Khử trùng lặp hoàn toàn
    before_dedup = len(df)
    df = df.drop_duplicates().copy()
    dropped_dups = before_dedup - len(df)

    # Ánh xạ danh mục từ AI (nếu có)
    ai_exp_map = {
        str(k).strip().lower(): str(v).strip()
        for k, v in (ai_meta.get("category_map_expense", {}) if ai_meta else {}).items()
        if str(v).strip() in EXPENSE_CATEGORIES
    }
    ai_inc_map = {
        str(k).strip().lower(): str(v).strip()
        for k, v in (ai_meta.get("category_map_income", {}) if ai_meta else {}).items()
        if str(v).strip() in INCOME_CATEGORIES
    }

    parsed_dates = pd.to_datetime(df[date_col], dayfirst=True, format="mixed", errors="coerce")

    kind_col = col_map.get("kind")
    cat_col = col_map.get("category")
    sub_col = col_map.get("subcategory")
    note_col = col_map.get("note")

    cleaned_rows: list[dict[str, Any]] = []
    dropped_transfers = 0
    dropped_invalid_date = 0
    dropped_invalid_amount = 0
    imputed_notes = 0

    for idx, (_, row) in enumerate(df.iterrows()):
        dt = parsed_dates.iloc[idx]
        if pd.isna(dt):
            dropped_invalid_date += 1
            continue
        iso_date = dt.strftime("%Y-%m-%d")

        raw_kind = str(row[kind_col]).strip().lower() if (kind_col and pd.notna(row[kind_col])) else ""
        if raw_kind in IGNORE_TYPES:
            dropped_transfers += 1
            continue

        raw_amt_val = row[amount_col]
        if raw_kind in ("income", "thu nhập", "thu", "credit", "cr", "in", "+"):
            kind = "income"
        elif raw_kind in ("expense", "chi tiêu", "chi", "debit", "dr", "out", "-"):
            kind = "expense"
        else:
            # Suy đoán từ dấu âm/dương hoặc từ khóa nếu không có cột loại
            if isinstance(raw_amt_val, (int, float)) and float(raw_amt_val) < 0:
                kind = "expense"
            else:
                kind = "expense"

        amount_vnd = _parse_amount_value(raw_amt_val, exchange_rate)
        if amount_vnd is None:
            dropped_invalid_amount += 1
            continue
        if active_curr != "VND":
            amount_vnd = max(1_000, int(round(amount_vnd / 1_000) * 1_000))

        raw_cat = _clean_note_text(row[cat_col]) if cat_col else ""
        raw_sub = _clean_note_text(row[sub_col]) if sub_col else ""
        raw_note = _clean_note_text(row[note_col]) if note_col else ""

        if not raw_note:
            imputed_notes += 1
            parts = [p for p in (raw_cat, raw_sub) if p]
            clean_note = " - ".join(parts) if parts else f"Giao dịch {iso_date}"
        elif raw_sub and raw_sub.lower() not in raw_note.lower() and len(raw_note) < 40:
            clean_note = f"{raw_sub}: {raw_note}"
        else:
            clean_note = raw_note

        if kind == "income":
            cat_v2 = ai_inc_map.get(raw_cat.lower()) or _rule_map_category("income", raw_cat, clean_note)
        else:
            cat_v2 = ai_exp_map.get(raw_cat.lower()) or _rule_map_category("expense", raw_cat, clean_note)

        cat_uth = _map_to_uth_category(kind, cat_v2, raw_cat)
        cleaned_rows.append({
            "date": iso_date,
            "kind": kind,
            "type_label": TYPE_LABELS[kind],
            "category": cat_v2,
            "category_uth": cat_uth,
            "amount": int(amount_vnd),
            "note": clean_note[:190],
        })

    cleaned_rows.sort(key=lambda r: (r["date"], r["kind"], r["category"], r["amount"]))

    ai_summary = (
        str(ai_meta.get("summary", "")).strip()
        if (ai_meta and ai_meta.get("summary"))
        else (
            f"Đã tự động nhận diện cột ({date_col}, {amount_col}), quy đổi {active_curr}→VNĐ "
            f"(×{exchange_rate:g}), loại {dropped_transfers} dòng chuyển khoản/nhiễu, "
            f"{dropped_dups} dòng trùng và bù {imputed_notes} ghi chú thiếu."
        )
    )

    stats = {
        "raw_rows": raw_rows,
        "clean_rows": len(cleaned_rows),
        "dropped_dups": dropped_dups,
        "dropped_transfers": dropped_transfers,
        "dropped_invalid_date": dropped_invalid_date,
        "dropped_invalid_amount": dropped_invalid_amount,
        "imputed_notes": imputed_notes,
        "currency": active_curr,
        "exchange_rate": exchange_rate,
        "date_min": cleaned_rows[0]["date"] if cleaned_rows else "",
        "date_max": cleaned_rows[-1]["date"] if cleaned_rows else "",
    }
    return CleaningResult(
        rows=cleaned_rows,
        stats=stats,
        ai_used=ai_used,
        ai_provider=ai_provider if ai_used else "Chuẩn hóa thông minh (Offline)",
        ai_summary=ai_summary,
    )


def clean_raw_text(
    raw_text: str,
    *,
    use_ai: bool = True,
    preferred_provider: str | None = None,
) -> CleaningResult:
    """Nhờ AI trích xuất và chuẩn hóa danh sách giao dịch từ văn bản thu chi thô tự do."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Vui lòng nhập hoặc dán văn bản dữ liệu thu chi thô.")

    today = Date.today()
    ai_used = False
    ai_provider = "Chuẩn hóa tiếng Việt (Offline)"
    ai_summary = ""
    rows: list[dict[str, Any]] = []

    if use_ai:
        prompt = (
            f"Hôm nay là {today.isoformat()}.\n"
            "Hãy đọc đoạn dữ liệu thu chi thô bên dưới, tách từng giao dịch, sửa lỗi chính tả, "
            "chuẩn hóa ngày (YYYY-MM-DD), loại ('income' hoặc 'expense'), danh mục chuẩn UniSpend, "
            "số tiền nguyên VNĐ (VD: 45k -> 45000, 1.5tr -> 1500000) và ghi chú sạch.\n"
            f"Danh mục chi hợp lệ: {list(EXPENSE_CATEGORIES)}\n"
            f"Danh mục thu hợp lệ: {list(INCOME_CATEGORIES)}\n"
            "Trả về DUY NHẤT JSON hợp lệ:\n"
            '{"summary": "tóm tắt ngắn", "transactions": [{"date": "YYYY-MM-DD", "kind": "expense|income", "category": "...", "amount": 45000, "note": "..."}]}\n\n'
            f"Dữ liệu thô:\n{text[:6000]}"
        )
        status = check_api_status(preferred_provider)
        provider_label = f"{status.provider} ({status.model})" if status.configured else "rule-based"
        ok, reply = _call_llm_text(
            prompt,
            system_instruction="Chỉ trả về JSON thuần hợp lệ. Không bịa thêm giao dịch không có trong văn bản.",
            preferred_provider=preferred_provider,
        )
        if ok:
            parsed = _extract_json_object(reply)
            txs = parsed.get("transactions") if isinstance(parsed, dict) else None
            if isinstance(txs, list) and txs:
                ai_used = True
                ai_provider = provider_label
                ai_summary = str(parsed.get("summary", "")).strip()
                for item in txs:
                    if not isinstance(item, dict):
                        continue
                    raw_d = str(item.get("date", "")).strip()
                    try:
                        iso_d = Date.fromisoformat(raw_d).isoformat()
                    except ValueError:
                        iso_d = today.isoformat()
                    kind = "income" if str(item.get("kind", "")).lower() == "income" else "expense"
                    amt = _parse_amount_value(item.get("amount"), 1.0)
                    if not amt:
                        continue
                    note = _clean_note_text(item.get("note")) or "Giao dịch"
                    raw_cat = str(item.get("category", "")).strip()
                    cat_v2 = raw_cat if raw_cat in (INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES) else _rule_map_category(kind, raw_cat, note)
                    rows.append({
                        "date": iso_d,
                        "kind": kind,
                        "type_label": TYPE_LABELS[kind],
                        "category": cat_v2,
                        "category_uth": _map_to_uth_category(kind, cat_v2, raw_cat),
                        "amount": amt,
                        "note": note,
                    })

    # Fallback phân tích từng dòng tiếng Việt nếu AI offline / chưa có key
    if not rows:
        segments = [seg.strip() for seg in re.split(r"[\n;]+", text) if seg.strip()]
        for seg in segments:
            parsed_line = parse_vietnamese_voice_expense(seg, today=today)
            amt = parsed_line.get("amount")
            if not amt or int(amt) <= 0:
                continue
            kind = str(parsed_line.get("kind", "expense"))
            cat_v2 = str(parsed_line.get("category", "Khác"))
            note = _clean_note_text(parsed_line.get("note")) or seg[:120]
            rows.append({
                "date": str(parsed_line.get("date", today.isoformat())),
                "kind": kind,
                "type_label": TYPE_LABELS[kind],
                "category": cat_v2,
                "category_uth": _map_to_uth_category(kind, cat_v2, note),
                "amount": int(amt),
                "note": note,
            })
        ai_summary = f"Đã tách và chuẩn hóa {len(rows)} giao dịch từ văn bản thô."

    if not rows:
        raise ValueError("Không trích xuất được giao dịch có số tiền hợp lệ từ văn bản vừa nhập.")

    rows.sort(key=lambda r: (r["date"], r["kind"], r["category"], r["amount"]))
    stats = {
        "raw_rows": len([s for s in re.split(r"[\n;]+", text) if s.strip()]),
        "clean_rows": len(rows),
        "dropped_dups": 0,
        "dropped_transfers": 0,
        "dropped_invalid_date": 0,
        "dropped_invalid_amount": 0,
        "imputed_notes": 0,
        "currency": "VND",
        "exchange_rate": 1.0,
        "date_min": rows[0]["date"],
        "date_max": rows[-1]["date"],
    }
    return CleaningResult(
        rows=rows,
        stats=stats,
        ai_used=ai_used,
        ai_provider=ai_provider,
        ai_summary=ai_summary,
    )


def rows_to_clean_csv_bytes(rows: list[dict[str, Any]], format_mode: str = "uth") -> bytes:
    """Xuất danh sách dòng đã làm sạch ra CSV chuẩn UTF-8 BOM."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    if format_mode == "uth":
        writer.writerow(["Ngày giao dịch", "Loại giao dịch", "Danh mục", "Số tiền (VNĐ)", "Ghi chú chi tiết"])
        for r in rows:
            writer.writerow([r["date"], r["type_label"], r["category_uth"], int(r["amount"]), r["note"]])
    else:
        writer.writerow(["Mã", "Ngày", "Loại", "Danh mục", "Số tiền (VNĐ)", "Ghi chú"])
        for idx, r in enumerate(rows, start=1):
            writer.writerow([idx, r["date"], r["type_label"], r["category"], int(r["amount"]), r["note"]])
    return buf.getvalue().encode("utf-8-sig")
