"""Cơ sở dữ liệu SQLite mở rộng cho UniSpend 2.0 (data/unispend_extensions.db).

Lưu trữ độc lập các tính năng bổ sung mà không sửa đổi cấu trúc SQLite gốc:
- Hóa đơn & ảnh đính kèm (receipts)
- Mục tiêu tiết kiệm (savings_goals)
- Giao dịch định kỳ, lịch thanh toán, khoản nợ/phải trả (recurring_items)
- Cấu hình giao diện Light/Dark & ngưỡng lịch tài chính (ui_settings)
- Lịch sử tương tác AI (ai_history)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import date as Date, datetime
from pathlib import Path
from typing import Any

from .storage import EXPENSE_CATEGORIES, INCOME_CATEGORIES, MAX_AMOUNT, TYPE_LABELS


def resolve_extensions_db_path(primary_db_path: str | Path, demo: bool = False) -> Path | str:
    """Tách biệt hoàn toàn DB mở rộng của người dùng, chế độ demo và kiểm thử."""
    raw = str(primary_db_path)
    if raw == ":memory:":
        return ":memory:"
    path = Path(primary_db_path).resolve()
    if demo or path.name == "demo.db":
        return path.with_name("unispend_extensions_demo.db")
    if path.name == "expenses.db":
        return path.with_name("unispend_extensions.db")
    return path.with_name(f"{path.stem}_extensions.db")


@dataclass(frozen=True)
class ReceiptRecord:
    id: int
    transaction_id: int | None
    store_name: str
    purchase_date: str
    purchase_time: str
    items: list[dict[str, Any]]
    discount: int
    total_amount: int
    payment_method: str
    suggested_category: str
    image_hash: str
    image_mime: str
    image_blob: bytes | None
    raw_text: str
    created_at: str


@dataclass(frozen=True)
class SavingsGoal:
    id: int
    title: str
    target_amount: int
    current_amount: int
    deadline: str
    category: str
    note: str
    status: str

    @property
    def remaining_amount(self) -> int:
        return max(0, self.target_amount - self.current_amount)

    @property
    def progress_ratio(self) -> float:
        return min(1.0, self.current_amount / self.target_amount) if self.target_amount > 0 else 0.0


@dataclass(frozen=True)
class RecurringItem:
    id: int
    title: str
    item_type: str  # 'recurring' | 'debt' | 'payable'
    kind: str       # 'expense' | 'income'
    category: str
    amount: int
    frequency: str  # 'monthly' | 'weekly' | 'once'
    due_day: int
    next_due_date: str
    counterparty: str
    note: str
    active: bool
    last_recorded_date: str


class ExtensionsStore:
    """Quản lý SQLite mở rộng cho các tính năng UniSpend 2.0."""

    DEFAULT_SETTINGS = {
        "theme_mode": "dark",
        "cal_low_threshold": "100000",
        "cal_high_threshold": "500000",
        "wallet_name": "Ví sinh viên UniSpend",
        "wallet_note": "Chi tiêu cá nhân hằng tháng",
        "reminder_time": "20:00",
        "notify_80": "1",
        "notify_100": "1",
        "ai_provider": "auto",
    }

    def __init__(self, ext_db_path: str | Path):
        self.db_path = ext_db_path
        if str(ext_db_path) != ":memory:":
            Path(ext_db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(ext_db_path))
        self.connection.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.connection:
            self.connection.executescript("""
                CREATE TABLE IF NOT EXISTS ui_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS receipts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_id INTEGER,
                    store_name TEXT NOT NULL,
                    purchase_date TEXT NOT NULL CHECK(length(purchase_date) = 10),
                    purchase_time TEXT NOT NULL DEFAULT '',
                    items_json TEXT NOT NULL DEFAULT '[]',
                    discount INTEGER NOT NULL DEFAULT 0 CHECK(discount >= 0),
                    total_amount INTEGER NOT NULL CHECK(total_amount > 0 AND total_amount <= 1000000000000),
                    payment_method TEXT NOT NULL DEFAULT '',
                    suggested_category TEXT NOT NULL,
                    image_hash TEXT NOT NULL DEFAULT '',
                    image_mime TEXT NOT NULL DEFAULT 'image/jpeg',
                    image_blob BLOB,
                    raw_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_receipts_date ON receipts(purchase_date);
                CREATE INDEX IF NOT EXISTS idx_receipts_tx ON receipts(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_receipts_hash ON receipts(image_hash);

                CREATE TABLE IF NOT EXISTS savings_goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    target_amount INTEGER NOT NULL CHECK(target_amount > 0 AND target_amount <= 1000000000000),
                    current_amount INTEGER NOT NULL DEFAULT 0 CHECK(current_amount >= 0),
                    deadline TEXT NOT NULL CHECK(length(deadline) = 10),
                    category TEXT NOT NULL DEFAULT 'Mục tiêu cá nhân',
                    note TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'completed'))
                );

                CREATE TABLE IF NOT EXISTS recurring_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    item_type TEXT NOT NULL CHECK(item_type IN ('recurring', 'debt', 'payable')),
                    kind TEXT NOT NULL CHECK(kind IN ('expense', 'income')),
                    category TEXT NOT NULL,
                    amount INTEGER NOT NULL CHECK(amount > 0 AND amount <= 1000000000000),
                    frequency TEXT NOT NULL DEFAULT 'monthly' CHECK(frequency IN ('monthly', 'weekly', 'once')),
                    due_day INTEGER NOT NULL DEFAULT 1 CHECK(due_day BETWEEN 1 AND 31),
                    next_due_date TEXT NOT NULL CHECK(length(next_due_date) = 10),
                    counterparty TEXT NOT NULL DEFAULT '',
                    note TEXT NOT NULL DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
                    last_recorded_date TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS ai_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feature TEXT NOT NULL,
                    prompt_summary TEXT NOT NULL,
                    response_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
            for key, default_val in self.DEFAULT_SETTINGS.items():
                self.connection.execute(
                    "INSERT OR IGNORE INTO ui_settings(key, value) VALUES (?, ?)",
                    (key, default_val),
                )

    def close(self) -> None:
        self.connection.close()

    # -------------------------------------------------------------------------
    # CẤU HÌNH GIAO DIỆN & NGƯỠNG LỊCH TÀI CHÍNH
    # -------------------------------------------------------------------------
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.connection.execute("SELECT value FROM ui_settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else self.DEFAULT_SETTINGS.get(key, default)

    def set_setting(self, key: str, value: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO ui_settings(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(key), str(value)),
            )

    def get_theme_mode(self) -> str:
        mode = self.get_setting("theme_mode", "light").lower()
        return "dark" if mode == "dark" else "light"

    def set_theme_mode(self, mode: str) -> str:
        clean = "dark" if str(mode).lower() == "dark" else "light"
        self.set_setting("theme_mode", clean)
        return clean

    def get_calendar_thresholds(self) -> tuple[int, int]:
        try:
            low = int(self.get_setting("cal_low_threshold", "100000"))
            high = int(self.get_setting("cal_high_threshold", "500000"))
            if low <= 0 or high <= low:
                return 100_000, 500_000
            return low, high
        except ValueError:
            return 100_000, 500_000

    def set_calendar_thresholds(self, low: int, high: int) -> None:
        if type(low) is not int or type(high) is not int or low <= 0 or high <= low:
            raise ValueError("Ngưỡng cam phải lớn hơn ngưỡng xanh và lớn hơn 0.")
        self.set_setting("cal_low_threshold", str(low))
        self.set_setting("cal_high_threshold", str(high))

    # -------------------------------------------------------------------------
    # QUẢN LÝ HÓA ĐƠN (RECEIPTS) & KIỂM TRA TRÙNG LẶP
    # -------------------------------------------------------------------------
    @staticmethod
    def compute_image_hash(image_bytes: bytes | None) -> str:
        if not image_bytes:
            return ""
        return hashlib.sha256(image_bytes).hexdigest()

    def find_duplicate_receipt(
        self,
        image_hash: str,
        store_name: str,
        purchase_date: str,
        total_amount: int,
    ) -> ReceiptRecord | None:
        if image_hash:
            row = self.connection.execute(
                "SELECT * FROM receipts WHERE image_hash=? ORDER BY id DESC LIMIT 1",
                (image_hash,),
            ).fetchone()
            if row:
                return self._row_to_receipt(row)
        if store_name.strip() and purchase_date and total_amount > 0:
            row = self.connection.execute(
                """
                SELECT * FROM receipts
                WHERE lower(trim(store_name))=lower(trim(?))
                  AND purchase_date=?
                  AND total_amount=?
                ORDER BY id DESC LIMIT 1
                """,
                (store_name, purchase_date, int(total_amount)),
            ).fetchone()
            if row:
                return self._row_to_receipt(row)
        return None

    def add_receipt(
        self,
        *,
        transaction_id: int | None,
        store_name: str,
        purchase_date: str,
        purchase_time: str = "",
        items: list[dict[str, Any]] | None = None,
        discount: int = 0,
        total_amount: int,
        payment_method: str = "",
        suggested_category: str = "Khác",
        image_bytes: bytes | None = None,
        image_mime: str = "image/jpeg",
        raw_text: str = "",
    ) -> int:
        Date.fromisoformat(purchase_date)
        store_clean = (store_name or "Cửa hàng").strip()[:120] or "Cửa hàng"
        if type(total_amount) is not int or not 0 < total_amount <= MAX_AMOUNT:
            raise ValueError("Tổng tiền hóa đơn phải là số nguyên dương hợp lệ.")
        if type(discount) is not int or discount < 0:
            raise ValueError("Giảm giá không hợp lệ.")
        if suggested_category not in EXPENSE_CATEGORIES:
            suggested_category = "Khác"
        image_hash = self.compute_image_hash(image_bytes)
        items_json = json.dumps(items or [], ensure_ascii=False)
        created_at = datetime.now().isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO receipts(
                    transaction_id, store_name, purchase_date, purchase_time,
                    items_json, discount, total_amount, payment_method,
                    suggested_category, image_hash, image_mime, image_blob,
                    raw_text, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transaction_id,
                    store_clean,
                    purchase_date,
                    purchase_time.strip()[:20],
                    items_json,
                    discount,
                    total_amount,
                    payment_method.strip()[:60],
                    suggested_category,
                    image_hash,
                    image_mime or "image/jpeg",
                    image_bytes,
                    raw_text.strip()[:4000],
                    created_at,
                ),
            )
        return int(cursor.lastrowid)

    def list_receipts(self, month: str | None = None, purchase_date: str | None = None) -> list[ReceiptRecord]:
        clauses, params = [], []
        if month:
            clauses.append("substr(purchase_date, 1, 7) = ?")
            params.append(month)
        if purchase_date:
            clauses.append("purchase_date = ?")
            params.append(purchase_date)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT * FROM receipts" + where + " ORDER BY purchase_date DESC, id DESC",
            params,
        ).fetchall()
        return [self._row_to_receipt(row) for row in rows]

    def get_receipt_by_transaction(self, transaction_id: int) -> ReceiptRecord | None:
        row = self.connection.execute(
            "SELECT * FROM receipts WHERE transaction_id=? ORDER BY id DESC LIMIT 1",
            (transaction_id,),
        ).fetchone()
        return self._row_to_receipt(row) if row else None

    def delete_receipt(self, receipt_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM receipts WHERE id=?", (int(receipt_id),))

    @staticmethod
    def _row_to_receipt(row: sqlite3.Row) -> ReceiptRecord:
        try:
            items = json.loads(row["items_json"] or "[]")
        except json.JSONDecodeError:
            items = []
        return ReceiptRecord(
            id=int(row["id"]),
            transaction_id=row["transaction_id"],
            store_name=row["store_name"],
            purchase_date=row["purchase_date"],
            purchase_time=row["purchase_time"],
            items=items if isinstance(items, list) else [],
            discount=int(row["discount"]),
            total_amount=int(row["total_amount"]),
            payment_method=row["payment_method"],
            suggested_category=row["suggested_category"],
            image_hash=row["image_hash"],
            image_mime=row["image_mime"],
            image_blob=row["image_blob"],
            raw_text=row["raw_text"],
            created_at=row["created_at"],
        )

    # -------------------------------------------------------------------------
    # MỤC TIÊU TIẾT KIỆM (SAVINGS GOALS)
    # -------------------------------------------------------------------------
    def add_savings_goal(
        self,
        title: str,
        target_amount: int,
        deadline: str,
        current_amount: int = 0,
        category: str = "Mục tiêu cá nhân",
        note: str = "",
    ) -> int:
        clean_title = (title or "").strip()
        if not clean_title or len(clean_title) > 120:
            raise ValueError("Tên mục tiêu tiết kiệm phải từ 1 đến 120 ký tự.")
        if type(target_amount) is not int or not 0 < target_amount <= MAX_AMOUNT:
            raise ValueError("Số tiền mục tiêu phải là số nguyên dương.")
        if type(current_amount) is not int or not 0 <= current_amount <= MAX_AMOUNT:
            raise ValueError("Số tiền đã tích lũy không hợp lệ.")
        Date.fromisoformat(deadline)
        status = "completed" if current_amount >= target_amount else "active"
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO savings_goals(title, target_amount, current_amount, deadline, category, note, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (clean_title, target_amount, current_amount, deadline, category.strip() or "Mục tiêu cá nhân", note.strip()[:200], status),
            )
        return int(cursor.lastrowid)

    def update_savings_goal_amount(self, goal_id: int, new_current_amount: int) -> None:
        if type(new_current_amount) is not int or not 0 <= new_current_amount <= MAX_AMOUNT:
            raise ValueError("Số tiền cập nhật không hợp lệ.")
        row = self.connection.execute(
            "SELECT target_amount FROM savings_goals WHERE id=?",
            (goal_id,),
        ).fetchone()
        if not row:
            raise ValueError("Không tìm thấy mục tiêu tiết kiệm.")
        status = "completed" if new_current_amount >= int(row["target_amount"]) else "active"
        with self.connection:
            self.connection.execute(
                "UPDATE savings_goals SET current_amount=?, status=? WHERE id=?",
                (new_current_amount, status, goal_id),
            )

    def delete_savings_goal(self, goal_id: int) -> None:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM savings_goals WHERE id=?", (goal_id,))
            if cursor.rowcount == 0:
                raise ValueError("Không tìm thấy mục tiêu tiết kiệm.")

    def list_savings_goals(self) -> list[SavingsGoal]:
        rows = self.connection.execute(
            "SELECT * FROM savings_goals ORDER BY CASE WHEN status='active' THEN 0 ELSE 1 END, deadline ASC, id DESC"
        ).fetchall()
        return [
            SavingsGoal(
                id=int(r["id"]),
                title=r["title"],
                target_amount=int(r["target_amount"]),
                current_amount=int(r["current_amount"]),
                deadline=r["deadline"],
                category=r["category"],
                note=r["note"],
                status=r["status"],
            )
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # GIAO DỊCH ĐỊNH KỲ, LỊCH THANH TOÁN & KHOẢN NỢ / PHẢI TRẢ
    # -------------------------------------------------------------------------
    def add_recurring_item(
        self,
        *,
        title: str,
        item_type: str = "recurring",
        kind: str = "expense",
        category: str = "Khác",
        amount: int,
        frequency: str = "monthly",
        due_day: int = 1,
        next_due_date: str,
        counterparty: str = "",
        note: str = "",
    ) -> int:
        clean_title = (title or "").strip()
        if not clean_title or len(clean_title) > 120:
            raise ValueError("Tên khoản thanh toán phải từ 1 đến 120 ký tự.")
        if item_type not in ("recurring", "debt", "payable"):
            raise ValueError("Phân loại khoản thanh toán không hợp lệ.")
        if kind not in TYPE_LABELS:
            raise ValueError("Loại thu/chi không hợp lệ.")
        valid_cats = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
        if category not in valid_cats:
            raise ValueError("Danh mục không phù hợp với loại giao dịch.")
        if type(amount) is not int or not 0 < amount <= MAX_AMOUNT:
            raise ValueError("Số tiền phải là số nguyên dương.")
        if frequency not in ("monthly", "weekly", "once"):
            raise ValueError("Chu kỳ không hợp lệ.")
        due_date_obj = Date.fromisoformat(next_due_date)
        due_day = max(1, min(31, int(due_day or due_date_obj.day)))
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO recurring_items(
                    title, item_type, kind, category, amount,
                    frequency, due_day, next_due_date, counterparty, note, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    clean_title,
                    item_type,
                    kind,
                    category,
                    amount,
                    frequency,
                    due_day,
                    next_due_date,
                    counterparty.strip()[:100],
                    note.strip()[:200],
                ),
            )
        return int(cursor.lastrowid)

    def mark_recurring_recorded(self, item_id: int, recorded_date: str) -> None:
        row = self.connection.execute("SELECT * FROM recurring_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ValueError("Không tìm thấy khoản định kỳ / phải trả.")
        curr_due = Date.fromisoformat(row["next_due_date"])
        freq = row["frequency"]
        active = 1
        if freq == "once":
            active = 0
            next_due = curr_due.isoformat()
        elif freq == "weekly":
            from datetime import timedelta
            next_due = (curr_due + timedelta(days=7)).isoformat()
        else:
            from calendar import monthrange
            year = curr_due.year + (1 if curr_due.month == 12 else 0)
            month = 1 if curr_due.month == 12 else curr_due.month + 1
            day = min(int(row["due_day"]), monthrange(year, month)[1])
            next_due = Date(year, month, day).isoformat()
        with self.connection:
            self.connection.execute(
                "UPDATE recurring_items SET last_recorded_date=?, next_due_date=?, active=? WHERE id=?",
                (recorded_date, next_due, active, item_id),
            )

    def delete_recurring_item(self, item_id: int) -> None:
        with self.connection:
            cursor = self.connection.execute("DELETE FROM recurring_items WHERE id=?", (item_id,))
            if cursor.rowcount == 0:
                raise ValueError("Không tìm thấy khoản thanh toán.")

    def list_recurring_items(self, active_only: bool = False) -> list[RecurringItem]:
        where = " WHERE active = 1" if active_only else ""
        rows = self.connection.execute(
            "SELECT * FROM recurring_items" + where + " ORDER BY active DESC, next_due_date ASC, id DESC"
        ).fetchall()
        return [
            RecurringItem(
                id=int(r["id"]),
                title=r["title"],
                item_type=r["item_type"],
                kind=r["kind"],
                category=r["category"],
                amount=int(r["amount"]),
                frequency=r["frequency"],
                due_day=int(r["due_day"]),
                next_due_date=r["next_due_date"],
                counterparty=r["counterparty"],
                note=r["note"],
                active=bool(r["active"]),
                last_recorded_date=r["last_recorded_date"],
            )
            for r in rows
        ]

    # -------------------------------------------------------------------------
    # LỊCH SỬ AI
    # -------------------------------------------------------------------------
    def log_ai_interaction(self, feature: str, prompt_summary: str, response_text: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO ai_history(feature, prompt_summary, response_text, created_at) VALUES (?, ?, ?, ?)",
                (
                    feature.strip()[:40],
                    prompt_summary.strip()[:500],
                    response_text.strip()[:4000],
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def list_ai_history(self, feature: str | None = None, limit: int = 15) -> list[dict[str, Any]]:
        if feature:
            rows = self.connection.execute(
                "SELECT * FROM ai_history WHERE feature=? ORDER BY id DESC LIMIT ?",
                (feature, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                "SELECT * FROM ai_history ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
