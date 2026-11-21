"""Quản lý đa tài khoản theo mô hình mỗi tệp SQLite (.db) là một tài khoản độc lập."""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .extensions_db import ExtensionsStore, resolve_extensions_db_path
from .reports_backup import validate_sqlite_backup
from .storage import ExpenseStore


@dataclass(frozen=True)
class AccountInfo:
    path: Path
    display_name: str
    file_name: str
    tx_count: int
    is_managed: bool  # True nếu nằm trong thư mục accounts/ (cho phép đổi tên file / xóa)


FRIENDLY_NAMES: dict[str, str] = {
    "expenses.db": "Tài khoản cá nhân mặc định",
    "demo.db": "Tài khoản Demo",
    "unispend2_clean.db": "Sinh viên UTH (Dữ liệu sạch 6 tháng)",
    "real_unispend2_clean.db": "Dữ liệu thật Kaggle (2.298 giao dịch)",
    "tai_khoan_uth_sach.db": "Sinh viên UTH (Dữ liệu sạch 6 tháng)",
    "tai_khoan_du_lieu_that.db": "Dữ liệu thật Kaggle (2.298 giao dịch)",
}


def slugify_account_name(name: str) -> str:
    """Chuyển tên tài khoản tiếng Việt sang tên file .db an toàn."""
    text = (name or "").strip().replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_only).strip("_").lower()
    return slug[:48] or "tai_khoan"


def _is_extension_or_backup(path: Path) -> bool:
    name = path.name.lower()
    return (
        not name.endswith(".db")
        or "extension" in name
        or name.endswith(".bak")
        or name.startswith("unispend3d")
        or name.startswith("real_unispend3d")
        or name == "student_expense.db"
    )


def _probe_v2_db(path: Path) -> tuple[bool, int]:
    """Kiểm tra file .db có đúng cấu trúc UniSpend 2.0 (bảng transactions có cột kind)."""
    if not path.is_file():
        return False, 0
    try:
        conn = sqlite3.connect(str(path))
        try:
            cols = {
                row[1]
                for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
            }
            if not {"date", "kind", "category", "amount", "note"} <= cols:
                return False, 0
            count = int(conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
            return True, count
        finally:
            conn.close()
    except sqlite3.Error:
        return False, 0


def _read_display_name(db_path: Path, demo: bool = False) -> str:
    ext_path = resolve_extensions_db_path(db_path, demo=demo)
    if isinstance(ext_path, Path) and ext_path.is_file():
        try:
            ext = ExtensionsStore(ext_path)
            try:
                saved = ext.get_setting("wallet_name", "").strip()
                if saved and saved != ExtensionsStore.DEFAULT_SETTINGS["wallet_name"]:
                    return saved
            finally:
                ext.close()
        except sqlite3.Error:
            pass
    if db_path.name in FRIENDLY_NAMES:
        return FRIENDLY_NAMES[db_path.name]
    return db_path.stem.replace("_", " ").strip().title()


def accounts_dir_for(base_data_dir: str | Path) -> Path:
    path = Path(base_data_dir).resolve() / "accounts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_accounts(
    base_data_dir: str | Path,
    extra_paths: Iterable[str | Path] = (),
) -> list[AccountInfo]:
    """Liệt kê tất cả các file .db tương thích UniSpend 2.0 dưới dạng danh sách tài khoản."""
    base = Path(base_data_dir).resolve()
    managed_dir = accounts_dir_for(base)

    candidates: list[Path] = []
    seen: set[Path] = set()

    def _add(p: Path) -> None:
        rp = p.resolve()
        if rp not in seen and not _is_extension_or_backup(rp):
            seen.add(rp)
            candidates.append(rp)

    for p in extra_paths:
        if p and str(p) != ":memory:":
            _add(Path(p))

    for folder in (managed_dir, base, base / "clean_dataset", base / "real_dataset"):
        if folder.is_dir():
            for f in sorted(folder.glob("*.db")):
                _add(f)

    results: list[AccountInfo] = []
    for cand in candidates:
        valid, tx_count = _probe_v2_db(cand)
        if not valid:
            continue
        is_managed = cand.parent == managed_dir
        results.append(
            AccountInfo(
                path=cand,
                display_name=_read_display_name(cand, demo=(cand.name == "demo.db")),
                file_name=cand.name,
                tx_count=tx_count,
                is_managed=is_managed,
            )
        )
    return results


def _unique_db_path(accounts_dir: Path, slug: str) -> Path:
    target = accounts_dir / f"{slug}.db"
    idx = 2
    while target.exists():
        target = accounts_dir / f"{slug}_{idx}.db"
        idx += 1
    return target


def create_account(
    accounts_dir: str | Path,
    display_name: str,
    seed_sample: bool = False,
) -> Path:
    """Tạo một tài khoản mới tương ứng một file SQLite .db độc lập."""
    clean_name = (display_name or "").strip()
    if not clean_name:
        raise ValueError("Vui lòng nhập tên tài khoản.")
    folder = Path(accounts_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    db_path = _unique_db_path(folder, slugify_account_name(clean_name))

    store = ExpenseStore(db_path)
    try:
        if seed_sample:
            store.seed_demo()
    finally:
        store.close()

    ext = ExtensionsStore(resolve_extensions_db_path(db_path))
    try:
        ext.set_setting("wallet_name", clean_name)
    finally:
        ext.close()
    return db_path


def import_db_as_account(
    accounts_dir: str | Path,
    display_name: str,
    file_bytes: bytes,
) -> Path:
    """Tải lên một file SQLite .db hợp lệ và lưu thành một tài khoản riêng mới."""
    check = validate_sqlite_backup(file_bytes)
    if not check["valid"]:
        raise ValueError(str(check["message"]))

    clean_name = (display_name or "").strip()
    if not clean_name:
        raise ValueError("Vui lòng đặt tên cho tài khoản mới.")

    folder = Path(accounts_dir).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    db_path = _unique_db_path(folder, slugify_account_name(clean_name))
    db_path.write_bytes(file_bytes)

    valid, _ = _probe_v2_db(db_path)
    if not valid:
        db_path.unlink(missing_ok=True)
        raise ValueError("Tệp SQLite không đúng cấu trúc bảng của UniSpend 2.0.")

    ext = ExtensionsStore(resolve_extensions_db_path(db_path))
    try:
        ext.set_setting("wallet_name", clean_name)
    finally:
        ext.close()
    return db_path


def rename_account(
    db_path: str | Path,
    new_display_name: str,
    accounts_dir: str | Path,
) -> Path:
    """Đổi tên hiển thị tài khoản (và đổi tên file .db nếu nằm trong thư mục accounts/)."""
    clean_name = (new_display_name or "").strip()
    if not clean_name:
        raise ValueError("Tên tài khoản mới không được để trống.")

    src = Path(db_path).resolve()
    folder = Path(accounts_dir).resolve()
    target = src

    if src.parent == folder:
        new_slug = slugify_account_name(clean_name)
        candidate = folder / f"{new_slug}.db"
        if candidate != src:
            if candidate.exists():
                candidate = _unique_db_path(folder, new_slug)
            old_ext = resolve_extensions_db_path(src)
            shutil.move(str(src), str(candidate))
            target = candidate
            new_ext = resolve_extensions_db_path(target)
            if isinstance(old_ext, Path) and isinstance(new_ext, Path) and old_ext.is_file():
                shutil.move(str(old_ext), str(new_ext))

    ext = ExtensionsStore(resolve_extensions_db_path(target, demo=(target.name == "demo.db")))
    try:
        ext.set_setting("wallet_name", clean_name)
    finally:
        ext.close()
    return target


def delete_account(db_path: str | Path, accounts_dir: str | Path) -> None:
    """Xóa một tài khoản nằm trong thư mục accounts/ cùng file mở rộng tương ứng."""
    src = Path(db_path).resolve()
    folder = Path(accounts_dir).resolve()
    if src.parent != folder:
        raise ValueError("Chỉ có thể xóa các tài khoản do người dùng tạo trong thư mục accounts/.")
    ext_path = resolve_extensions_db_path(src)
    src.unlink(missing_ok=True)
    if isinstance(ext_path, Path) and ext_path.is_file():
        ext_path.unlink(missing_ok=True)


def _state_file(base_data_dir: str | Path) -> Path:
    return Path(base_data_dir).resolve() / ".active_account.json"


def save_active_account(base_data_dir: str | Path, db_path: str | Path) -> None:
    """Lưu tài khoản đang chọn xuống đĩa để không bị mất khi chuyển tab (<a href='?tab=...'>) hoặc F5."""
    state_path = _state_file(base_data_dir)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"active_db": str(Path(db_path).resolve())}
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_active_account(base_data_dir: str | Path) -> Path | None:
    """Đọc tài khoản đang hoạt động từ đĩa (nếu file .db vẫn tồn tại và hợp lệ)."""
    state_path = _state_file(base_data_dir)
    if not state_path.is_file():
        return None
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        raw = str(data.get("active_db") or "").strip()
        if not raw:
            return None
        candidate = Path(raw)
        valid, _ = _probe_v2_db(candidate)
        return candidate if valid else None
    except (OSError, ValueError, TypeError):
        return None
