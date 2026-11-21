"""Entry point 24/7 cho Streamlit Community Cloud (không chỉnh sửa app.py / main.py)."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from expense_tracker.ui import run_app

# Nạp khóa API an toàn từ Streamlit Cloud Secrets vào os.environ (nếu có cấu hình)
for _env_key in ("GEMINI_API_KEY", "GEMINI_MODEL", "AI_PROVIDER", "TESSERACT_CMD", "OPENAI_API_KEY"):
    try:
        if _env_key in st.secrets and not os.environ.get(_env_key):
            os.environ[_env_key] = str(st.secrets[_env_key])
    except Exception:
        pass

os.environ.setdefault("TESSERACT_CMD", "/usr/bin/tesseract")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.5-flash-lite")
os.environ.setdefault("AI_PROVIDER", "gemini")

_base_dir = Path(__file__).resolve().parent
_db_path = _base_dir / "data" / "demo.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)

run_app(_db_path, demo=True)
