"""Hệ thống CSS & Design System chuẩn Mobile-First Dark-Green cho UniSpend 2.0 (MONii Inspired).

Khắc phục triệt để 7 lỗi hiển thị:
1. Khóa cứng nền tối #0B1410 trên mọi tầng DOM của Streamlit (không bao giờ hở nền trắng).
2. Định dạng chuẩn lưới lịch 7 cột với thẻ <a> bấm chọn ngày trực tiếp, không vỡ layout.
3. Minify HTML/SVG 1 dòng sạch sẽ, không bao giờ lộ raw HTML/SVG.
4. Ghi đè [data-testid="stAlert"] nền tối #16241D, chữ sáng #F3F4F6.
5. Ghi đè [data-testid="stFileUploader"] section nền tối #13201A, viền dashed #34D399.
6. Ghi đè div[data-baseweb="select"] & mũi tên dropdown nền #13201A, xóa sạch ô vuông trắng.
7. Khung Mobile-First max-width 480px, Bottom Navigation nổi cố định 4 tab và 2 nút FAB Camera/Mic.
"""

from __future__ import annotations

import re
import streamlit as st

UNISPEND_MOBILE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&display=swap');

:root {
    --bg-main: #0B1410;
    --bg-card: #13201A;
    --bg-card-elevated: #182921;
    --bg-input: #13201A;
    --bg-alert: #16241D;
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-input: rgba(255, 255, 255, 0.14);
    --uploader-btn-bg: #1E3328;
    --uploader-btn-text: #34D399;
    --primary: #16A36A;
    --primary-light: #34D399;
    --chi-bg: rgba(220, 38, 38, 0.14);
    --chi-border: rgba(220, 38, 38, 0.35);
    --chi-text: #F87171;
    --thu-bg: rgba(22, 163, 106, 0.14);
    --thu-border: rgba(22, 163, 106, 0.35);
    --thu-text: #4ADE80;
    --text-main: #F3F4F6;
    --text-muted: #9CA3AF;
    --bg-surface: #13201A;
    --bg-secondary: #182921;
    --color-primary: #16A36A;
    --color-primary-accent: #34D399;
    --color-danger: #F87171;
    --color-warning: #FBBF24;
    --color-text: #F3F4F6;
    --color-text-muted: #9CA3AF;
    --color-border: rgba(255, 255, 255, 0.08);
    --card-shadow: 0 12px 28px -8px rgba(0, 0, 0, 0.6);
    --ease-spring: cubic-bezier(0.22, 1, 0.36, 1);
}

/* ================= 1. KHÓA CỨNG NỀN TỐI CHO MỌI TẦNG DOM ================= */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
[data-testid="stVerticalBlock"],
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {
    background-color: var(--bg-main) !important;
    color: var(--text-main) !important;
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    -webkit-tap-highlight-color: transparent;
}

header[data-testid="stHeader"],
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="InputInstructions"],
footer,
#MainMenu {
    display: none !important;
}

/* Khung hiển thị Mobile-First chuẩn 480px (chỉ áp dụng cho màn hình < 820px) */
.block-container,
[data-testid="stMainBlockContainer"] {
    max-width: 480px !important;
    margin: 0 auto !important;
    padding: 0.75rem 0.85rem 130px 0.85rem !important;
}

[data-testid="stSidebar"], [data-testid="stSidebarContent"] {
    background-color: #0E1914 !important;
    color: var(--text-main) !important;
    border-right: 1px solid var(--border-subtle) !important;
}

[data-testid="stMain"] [data-testid="stMarkdownContainer"] > :is(h1, h2, h3, h4, h5, h6, p, ul, ol, span, div),
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] > :is(h1, h2, h3, h4, h5, h6, p, ul, ol, span, div),
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] p,
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label {
    color: var(--text-main) !important;
}

[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
    color: var(--text-muted) !important;
}

/* ================= 2. SỬA ST.ALERT, FILE UPLOADER & SELECTBOX (ĐỒNG BỘ DARK & LIGHT) ================= */
[data-testid="stAlert"] {
    background-color: var(--bg-alert) !important;
    border: 1px solid var(--border-input) !important;
    border-radius: 14px !important;
    color: var(--text-main) !important;
}
[data-testid="stAlert"] p,
[data-testid="stAlert"] div,
[data-testid="stAlert"] span {
    color: var(--text-main) !important;
}

[data-testid="stFileUploader"] section,
[data-testid="stFileUploaderDropzone"] {
    background-color: var(--bg-input) !important;
    border: 1.5px dashed rgba(22, 163, 106, 0.45) !important;
    border-radius: 16px !important;
    padding: 14px 16px !important;
}
[data-testid="stFileUploader"] section small,
[data-testid="stFileUploader"] section span,
[data-testid="stFileUploader"] section div,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span {
    color: var(--text-muted) !important;
}
[data-testid="stFileUploader"] section button,
[data-testid="stFileUploaderDropzone"] button {
    background-color: var(--uploader-btn-bg) !important;
    color: var(--uploader-btn-text) !important;
    border: 1px solid rgba(22, 163, 106, 0.4) !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    width: auto !important;
    min-width: 112px !important;
    height: auto !important;
    min-height: 36px !important;
    padding: 6px 16px !important;
    white-space: nowrap !important;
    overflow: visible !important;
}
[data-testid="stFileUploader"] section button *,
[data-testid="stFileUploaderDropzone"] button * {
    background: transparent !important;
    border: none !important;
    color: var(--uploader-btn-text) !important;
}

div[data-baseweb="select"],
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-baseweb="textarea"] {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-input) !important;
    color: var(--text-main) !important;
    border-radius: 12px !important;
}
div[data-baseweb="select"] > div,
div[data-baseweb="select"] > div > div,
div[data-baseweb="input"] > div,
div[data-baseweb="base-input"] > input,
div[data-baseweb="textarea"] > textarea,
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInputField"],
[data-testid="stDateInputField"] {
    background-color: var(--bg-input) !important;
    color: var(--text-main) !important;
    -webkit-text-fill-color: var(--text-main) !important;
    border-color: transparent !important;
}
div[data-baseweb="select"] svg,
[data-testid="stSelectbox"] svg {
    fill: var(--text-muted) !important;
    color: var(--text-muted) !important;
    background: transparent !important;
}
ul[data-testid="stSelectboxVirtualDropdown"],
div[data-baseweb="popover"] div,
div[data-baseweb="menu"] {
    background-color: var(--bg-card) !important;
    color: var(--text-main) !important;
}

[data-testid="stNumberInputContainer"] {
    background-color: var(--bg-input) !important;
    border: 1px solid var(--border-input) !important;
    border-radius: 12px !important;
}
[data-testid="stNumberInput"] button {
    background-color: var(--bg-card-elevated) !important;
    color: var(--text-main) !important;
    border-radius: 0 !important;
    min-height: 36px !important;
}

/* Biểu đồ Altair gọn đẹp, bo tròn, cắt sạch mép thừa & ẩn thanh công cụ kỹ thuật */
[data-testid="stVegaLiteChart"] {
    background-color: var(--bg-card) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 18px !important;
    padding: 10px 8px 4px 8px !important;
    margin-top: 10px !important;
    overflow: hidden !important;
    max-width: 100% !important;
}
[data-testid="stVegaLiteChart"] > div,
[data-testid="stVegaLiteChart"] .vega-embed {
    max-width: 100% !important;
    overflow: hidden !important;
}
[data-testid="stVegaLiteChart"] [data-testid="stElementToolbar"],
.vega-embed summary {
    display: none !important;
}

/* Radio buttons sạch đẹp cho cả Dark & Light Mode */
[data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {
    background-color: var(--bg-card-elevated) !important;
    border-color: var(--border-input) !important;
}

/* Bộ thu âm thật st.audio_input — phóng to nút Micro xanh nổi bật, bấm là ghi âm ngay */
[data-testid="stAudioInput"] {
    background-color: var(--bg-card) !important;
    border: 1.5px solid rgba(52, 211, 153, 0.4) !important;
    border-radius: 20px !important;
    padding: 14px 16px !important;
}
[data-testid="stAudioInput"] button {
    background-color: #16A36A !important;
    color: #FFFFFF !important;
    border: 2px solid #34D399 !important;
    border-radius: 999px !important;
    min-width: 46px !important;
    min-height: 46px !important;
}
[data-testid="stAudioInput"] button svg {
    fill: #FFFFFF !important;
    color: #FFFFFF !important;
}

[data-testid="stExpander"] details,
[data-testid="stExpanderDetails"],
[data-testid="stVerticalBlockBorderWrapper"] {
    background-color: var(--bg-card) !important;
    border-color: var(--border-subtle) !important;
    border-radius: 18px !important;
    color: var(--text-main) !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p {
    color: var(--text-main) !important;
    font-weight: 700 !important;
}

/* Nút bấm Streamlit — tuyệt đối không đặt border/background lên thẻ <p> bên trong nút */
[data-testid^="stBaseButton-primary"] {
    background-color: var(--primary) !important;
    border: 1px solid var(--primary) !important;
    color: #FFFFFF !important;
    border-radius: 999px !important;
    font-weight: 700 !important;
    min-height: 42px;
}
[data-testid^="stBaseButton-primary"] *,
[data-testid^="stBaseButton-primary"] [data-testid="stMarkdownContainer"] > p {
    background: transparent !important;
    border: none !important;
    color: #FFFFFF !important;
    margin: 0 !important;
    padding: 0 !important;
    font-weight: 700 !important;
}
[data-testid^="stBaseButton-secondary"] {
    background-color: var(--bg-card-elevated) !important;
    border: 1px solid var(--border-input) !important;
    color: var(--text-main) !important;
    border-radius: 999px !important;
    font-weight: 600 !important;
    min-height: 42px;
}
[data-testid^="stBaseButton-secondary"] *,
[data-testid^="stBaseButton-secondary"] [data-testid="stMarkdownContainer"] > p {
    background: transparent !important;
    border: none !important;
    color: var(--text-main) !important;
    margin: 0 !important;
    padding: 0 !important;
    font-weight: 600 !important;
}

/* ================= 3. HEADER 1 HÀNG DUY NHẤT (TAB LỊCH) ================= */
.monii-top-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 4px 2px 12px 2px;
}
.monii-brand-block {
    display: flex;
    flex-direction: column;
}
.monii-brand-logo {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 1.45rem;
    font-weight: 900;
    color: var(--text-main);
    letter-spacing: -0.03em;
    line-height: 1.05;
}
.monii-brand-sub {
    font-size: 0.76rem;
    color: var(--text-muted);
    font-weight: 500;
    margin-top: 2px;
}
.monii-header-controls {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.monii-theme-circle {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #F59E0B;
    text-decoration: none !important;
    flex-shrink: 0;
}
.monii-month-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    padding: 4px 6px;
}
.monii-month-arrow {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--bg-card-elevated);
    border: 1px solid rgba(52, 211, 153, 0.25);
    color: var(--primary-light) !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none !important;
    font-weight: 800;
    font-size: 0.82rem;
}
.monii-month-label {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--text-main);
    padding: 0 4px;
    white-space: nowrap;
}

/* ================= 4. THẺ HERO "KHẢ DỤNG THÁNG" ================= */
.hero-banner {
    background: var(--bg-card);
    border-radius: 22px;
    padding: 18px 18px 16px 18px;
    border: 1px solid var(--border-subtle);
    box-shadow: var(--card-shadow);
    margin-bottom: 14px;
    position: relative;
    overflow: hidden;
}
.hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 128px;
    align-items: center;
    gap: 10px;
}
.hero-avail-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    width: fit-content;
    background: var(--bg-card-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-muted);
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 5px 11px;
    border-radius: 999px;
    margin-bottom: 10px;
}
.hero-big-amount {
    font-size: 1.92rem;
    font-weight: 900;
    color: var(--text-main);
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin-bottom: 12px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}
.hero-ai-pill {
    background: var(--bg-card-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    padding: 7px 12px;
    font-size: 0.76rem;
    color: var(--text-main);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.hero-mascot-wrap {
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    width: 128px;
    height: 128px;
}
.hero-edit-pencil-badge {
    position: absolute;
    top: 2px;
    right: 2px;
    width: 30px;
    height: 30px;
    border-radius: 50%;
    background: var(--bg-card-elevated);
    border: 1px solid var(--border-subtle);
    color: var(--text-muted) !important;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none !important;
    z-index: 2;
}

/* ================= 5. KHU VỰC LỊCH TÀI CHÍNH 7 CỘT ================= */
.cal-section-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 10px 2px 10px 2px;
}
.cal-section-title {
    font-size: 0.82rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-muted);
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.cal-photo-pill {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 0.75rem;
    color: var(--text-muted) !important;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    text-decoration: none !important;
}
.cal-wrapper {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 24px;
    padding: 14px;
    box-shadow: var(--card-shadow);
    margin-bottom: 14px;
}
.cal-top-pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 14px;
}
.cal-box-chi {
    background: var(--chi-bg);
    border: 1px solid var(--chi-border);
    border-radius: 16px;
    padding: 11px 14px;
}
.cal-box-chi-label {
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--chi-text);
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 3px;
}
.cal-box-chi-val {
    font-size: 1.15rem;
    font-weight: 900;
    color: var(--chi-text);
    font-variant-numeric: tabular-nums;
}
.cal-box-thu {
    background: var(--thu-bg);
    border: 1px solid var(--thu-border);
    border-radius: 16px;
    padding: 11px 14px;
}
.cal-box-thu-label {
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--thu-text);
    display: flex;
    align-items: center;
    gap: 4px;
    margin-bottom: 3px;
}
.cal-box-thu-val {
    font-size: 1.15rem;
    font-weight: 900;
    color: var(--thu-text);
    font-variant-numeric: tabular-nums;
}

.cal-grid-7 {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 6px;
}
.cal-weekday {
    text-align: center;
    font-size: 0.73rem;
    font-weight: 700;
    color: var(--text-muted);
    padding: 4px 0 8px 0;
}
.cal-cell-empty {
    aspect-ratio: 1 / 1.08;
    border-radius: 12px;
    background: transparent;
}
a.cal-cell, .cal-cell {
    aspect-ratio: 1 / 1.08;
    border-radius: 12px;
    background: var(--bg-card-elevated);
    border: 1px solid rgba(255, 255, 255, 0.05);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3px 2px;
    text-decoration: none !important;
    color: var(--text-main) !important;
    position: relative;
    transition: transform 0.14s ease, border-color 0.14s ease;
}
a.cal-cell:hover {
    border-color: var(--primary-light);
    transform: translateY(-1px);
}
.cal-cell-low {
    background: rgba(22, 163, 106, 0.14) !important;
    border-color: rgba(52, 211, 153, 0.28) !important;
}
.cal-cell-mid {
    background: rgba(245, 158, 11, 0.14) !important;
    border-color: rgba(251, 191, 36, 0.32) !important;
}
.cal-cell-high {
    background: rgba(220, 38, 38, 0.16) !important;
    border-color: rgba(248, 113, 113, 0.38) !important;
}
.cal-cell-selected {
    border: 2px solid #22C55E !important;
    background: rgba(22, 163, 106, 0.22) !important;
    box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.15);
}
.cal-day-num {
    font-size: 0.88rem;
    font-weight: 800;
    color: var(--text-main);
    line-height: 1.1;
}
.cal-cell-selected .cal-day-num {
    color: #4ADE80 !important;
}
.cal-day-exp {
    font-size: 0.56rem;
    font-weight: 800;
    color: var(--chi-text);
    line-height: 1.05;
    margin-top: 2px;
    white-space: nowrap;
}
.cal-day-inc {
    font-size: 0.56rem;
    font-weight: 800;
    color: var(--thu-text);
    line-height: 1.05;
    margin-top: 1px;
    white-space: nowrap;
}
.cal-day-dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #34D399;
    margin-top: 3px;
}

/* ================= 6. CHI TIẾT NGÀY, HÓA ĐƠN & THỐNG KÊ ================= */
.day-inspector-card, .upcoming-bills-card, .essential-card, .cat-list-card, .ocr-result-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 22px;
    padding: 16px 18px;
    box-shadow: var(--card-shadow);
    margin-bottom: 12px;
}
.day-inspector-head, .upcoming-bills-head, .essential-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}
.day-inspector-date, .essential-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--text-main);
}
.day-inspector-total, .essential-amount {
    font-size: 1.35rem;
    font-weight: 900;
    font-variant-numeric: tabular-nums;
}
.day-tx-item, .upcoming-bill-row, .cat-row-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-subtle);
}
.cat-row-item {
    display: block;
}
.cat-row-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
}
.cat-row-left, .day-tx-left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.cat-row-right {
    display: flex;
    align-items: center;
    gap: 8px;
}
.cat-icon-box {
    width: 36px;
    height: 36px;
    border-radius: 11px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.cat-row-name, .day-tx-title {
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--text-main);
}
.day-tx-cat, .essential-limit, .essential-desc {
    font-size: 0.74rem;
    color: var(--text-muted);
}
.cat-row-amount, .day-tx-amount {
    font-size: 0.9rem;
    font-weight: 800;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
}
.cat-pct-pill, .essential-pill {
    font-size: 0.7rem;
    font-weight: 800;
    padding: 3px 9px;
    border-radius: 999px;
    white-space: nowrap;
}
.pill-safe { background: var(--thu-bg); color: var(--thu-text); }
.pill-warning { background: rgba(245, 158, 11, 0.16); color: #FBBF24; }
.pill-danger { background: var(--chi-bg); color: var(--chi-text); }
.pill-neutral { background: var(--bg-card-elevated); color: var(--text-muted); }

.progress-track {
    height: 6px;
    border-radius: 99px;
    background: var(--bg-card-elevated);
    overflow: hidden;
    margin: 6px 0;
}
.progress-fill {
    height: 100%;
    border-radius: 99px;
}

/* Segmented Control 2 chế độ (Tab Hóa Đơn & Tab Thống Kê) */
.monii-segmented-bar {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 5px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 999px;
    padding: 5px;
    margin: 10px 0 14px 0;
}
a.monii-seg-item {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 9px 12px;
    border-radius: 999px;
    font-size: 0.83rem;
    font-weight: 700;
    color: var(--text-muted) !important;
    text-decoration: none !important;
    border: 1px solid transparent;
}
a.monii-seg-item.active {
    background: var(--bg-card-elevated);
    color: var(--primary-light) !important;
    border-color: rgba(52, 211, 153, 0.38);
}

.bills-empty-state {
    background: var(--bg-card);
    border: 1.5px dashed rgba(255, 255, 255, 0.1);
    border-radius: 24px;
    padding: 34px 20px;
    text-align: center;
    margin: 10px 0 18px 0;
}
.bills-empty-title {
    font-size: 1rem;
    font-weight: 800;
    color: var(--text-main);
    margin: 12px 0 6px 0;
}
.bills-empty-sub {
    font-size: 0.8rem;
    color: var(--text-muted);
    max-width: 280px;
    margin: 0 auto;
    line-height: 1.45;
}

/* Lưới 2x2 KPI ở Tab Thống kê */
.kpi-grid-2x2 {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 14px;
}
.pro-kpi-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 18px;
    padding: 13px 14px;
}
.pro-kpi-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}
.pro-kpi-meta {
    display: flex;
    flex-direction: column;
    min-width: 0;
}
.pro-kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--text-muted);
}
.pro-kpi-amount {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}
.pro-kpi-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 4px;
}
.pro-kpi-trend {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 0.68rem;
    font-weight: 700;
}

.stats-pair-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 14px;
}
.stats-card-daily {
    background: var(--chi-bg);
    border: 1px solid var(--chi-border);
    border-radius: 18px;
    padding: 13px 14px;
}
.stats-card-topcat {
    background: var(--thu-bg);
    border: 1px solid var(--thu-border);
    border-radius: 18px;
    padding: 13px 14px;
}
.stats-mini-head {
    font-size: 0.72rem;
    font-weight: 800;
    margin-bottom: 6px;
}
.stats-mini-val {
    font-size: 1rem;
    font-weight: 900;
    color: var(--text-main);
}

/* ================= 7. NÚT NỔI FAB & THANH BOTTOM NAVIGATION CỐ ĐỊNH ================= */
.unispend-fab-stack {
    position: fixed;
    bottom: 94px;
    right: max(18px, calc(50% - 222px));
    display: flex;
    flex-direction: column;
    gap: 10px;
    z-index: 9998;
}
a.unispend-fab-btn {
    width: 50px;
    height: 50px;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    text-decoration: none !important;
    box-shadow: 0 8px 22px rgba(0, 0, 0, 0.55);
    transition: transform 0.16s ease;
}
a.unispend-fab-btn:hover {
    transform: scale(1.06);
}
a.unispend-fab-btn.fab-cam {
    background: #16A36A;
    border: 1.5px solid #34D399;
    color: #FFFFFF !important;
}
a.unispend-fab-btn.fab-mic {
    background: #1C2D25;
    border: 1.5px solid rgba(52, 211, 153, 0.35);
    color: #E5E7EB !important;
}

.unispend-bottom-nav {
    position: fixed;
    bottom: 14px;
    left: 50%;
    transform: translateX(-50%);
    width: calc(100% - 24px);
    max-width: 440px;
    z-index: 9999;
    background: rgba(18, 30, 24, 0.94);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 28px;
    padding: 6px;
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 4px;
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.65);
}
a.unispend-nav-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 3px;
    padding: 7px 4px;
    border-radius: 22px;
    text-decoration: none !important;
    color: var(--text-muted) !important;
    font-size: 0.72rem;
    font-weight: 700;
    border: 1px solid transparent;
    transition: all 0.16s ease;
}
a.unispend-nav-item.active {
    background: rgba(22, 163, 106, 0.22);
    border: 1px solid rgba(52, 211, 153, 0.45);
    color: #34D399 !important;
}

/* Màn hình Giọng nói & OCR */
.voice-bottom-sheet {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 24px;
    padding: 18px;
    margin-bottom: 14px;
}
.voice-sheet-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}
.voice-sheet-title {
    font-size: 1.05rem;
    font-weight: 800;
}
.voice-center-stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px 0 14px 0;
}
.voice-mic-outer-ring {
    width: 82px;
    height: 82px;
    border-radius: 50%;
    background: rgba(22, 163, 106, 0.16);
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
}
.voice-mic-inner-ring {
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: #16A36A;
    border: 2px solid #34D399;
    display: flex;
    align-items: center;
    justify-content: center;
}
.voice-waveform {
    display: flex;
    align-items: center;
    gap: 4px;
    height: 22px;
    margin-bottom: 8px;
}
.voice-wave-bar {
    width: 3.5px;
    height: 16px;
    border-radius: 99px;
    background: #34D399;
}
.voice-listening-text {
    font-size: 0.82rem;
    color: #34D399;
    font-weight: 600;
}
.voice-transcript-box {
    background: #17212B;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 12px 14px;
}
.voice-transcript-label {
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--text-muted);
    margin-bottom: 4px;
}
.voice-transcript-content {
    font-size: 0.88rem;
    color: var(--text-main);
}

.ocr-kv-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-top: 10px;
}
.ocr-kv-item {
    background: var(--bg-card-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.ocr-kv-item span {
    font-size: 0.7rem;
    color: var(--text-muted);
}
.ocr-kv-item strong {
    font-size: 0.85rem;
    color: var(--text-main);
}

.personal-group-label {
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin: 14px 4px 8px 4px;
}
.personal-card-group {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 20px;
    padding: 6px 14px;
    margin-bottom: 12px;
}
.personal-row-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 11px 2px;
    border-bottom: 1px solid var(--border-subtle);
}
.personal-row-item:last-child {
    border-bottom: none;
}
.personal-row-left {
    display: flex;
    align-items: center;
    gap: 10px;
}
.personal-row-title {
    font-size: 0.88rem;
    font-weight: 700;
    color: var(--text-main);
    display: flex;
    align-items: center;
    gap: 6px;
}
.personal-row-sub {
    font-size: 0.74rem;
    color: var(--text-muted);
}
.pro-badge-amber {
    background: linear-gradient(135deg, #F5A623, #E08911);
    color: #FFFFFF;
    font-size: 0.62rem;
    font-weight: 800;
    padding: 2px 7px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    gap: 3px;
}
.privacy-shield-banner {
    background: var(--thu-bg);
    border: 1px solid var(--thu-border);
    border-radius: 16px;
    padding: 11px 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--text-main);
    text-align: center;
    margin: 12px 0;
}
.section-heading {
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--text-main);
    margin: 12px 0 8px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.monii-tx-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 11px 14px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
}
.alert-box {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    padding: 11px 14px;
    border-radius: 14px;
    margin-bottom: 8px;
    font-size: 0.82rem;
}
.alert-danger { background: var(--chi-bg); border: 1px solid var(--chi-border); color: var(--text-main); }
.alert-warning { background: rgba(245, 158, 11, 0.14); border: 1px solid rgba(251, 191, 36, 0.35); color: var(--text-main); }
.alert-safe { background: var(--thu-bg); border: 1px solid var(--thu-border); color: var(--text-main); }

/* Thẻ Chi tiêu an toàn & Cảnh báo vượt mức (hiển thị đẹp trên cả Mobile & Desktop) */
.dt-safe-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 22px;
    padding: 16px 18px;
    box-shadow: var(--card-shadow);
    margin-bottom: 12px;
}
.dt-safe-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 10px;
}
.dt-safe-title {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--text-main);
}
.dt-safe-badge {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.74rem;
    font-weight: 800;
    background: rgba(22, 163, 106, 0.16);
    color: #34D399;
    border: 1px solid rgba(52, 211, 153, 0.3);
    white-space: nowrap;
}
.dt-safe-badge.danger {
    background: rgba(220, 38, 38, 0.16);
    color: #F87171;
    border-color: rgba(248, 113, 113, 0.35);
}
.dt-safe-amount {
    font-size: 1.45rem;
    font-weight: 900;
    color: var(--text-main);
    font-variant-numeric: tabular-nums;
    margin-bottom: 10px;
}
.dt-safe-bar-track {
    width: 100%;
    height: 9px;
    border-radius: 999px;
    background: var(--bg-card-elevated);
    overflow: hidden;
    margin-bottom: 8px;
}
.dt-safe-bar-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #16A36A, #34D399);
}
.dt-safe-meta {
    font-size: 0.78rem;
    color: var(--text-muted);
    display: flex;
    justify-content: space-between;
    gap: 8px;
    flex-wrap: wrap;
}

/* ================= 7. GIAO DIỆN WEB DESKTOP / MÁY TÍNH (>= 820px) ================= */
/* Mặc định ẩn hoàn toàn trên Mobile (< 820px) để giữ nguyên 100% giao diện điện thoại */
.unispend-desktop-sidebar,
.unispend-desktop-topbar,
.unispend-desktop-kpi-strip,
.desktop-only-widget,
.unispend-desktop-only {
    display: none !important;
}
.desktop-split-workspace,
.desktop-split-left,
.desktop-split-right {
    display: block;
}

@media (min-width: 820px) {
    /* Mở rộng khung làm việc Web Desktop, chừa đúng 244px cho Sidebar trái cố định */
    .block-container,
    [data-testid="stMainBlockContainer"],
    section.main .block-container {
        max-width: calc(100vw - 244px) !important;
        width: calc(100vw - 244px) !important;
        margin-left: 244px !important;
        margin-right: 0 !important;
        padding: 1.35rem 2rem 3.2rem 2rem !important;
    }

    /* Ẩn các thành phần chỉ dành cho Mobile trên màn hình máy tính */
    .unispend-bottom-nav,
    .unispend-fab-stack,
    .mobile-only-header,
    .mobile-only-hero {
        display: none !important;
    }

    /* Topbar dành riêng cho Máy Tính */
    .unispend-desktop-topbar {
        display: flex !important;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 18px;
        padding-bottom: 14px;
        border-bottom: 1px solid var(--border-subtle);
    }
    .udt-left {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }
    .udt-title {
        font-size: 1.55rem;
        font-weight: 900;
        color: var(--text-main);
        letter-spacing: -0.025em;
        line-height: 1.15;
    }
    .udt-sub {
        font-size: 0.84rem;
        color: var(--text-muted);
        font-weight: 500;
    }
    .udt-right {
        display: flex;
        align-items: center;
        gap: 10px;
        flex-wrap: wrap;
    }
    a.udt-pill-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 14px;
        border-radius: 999px;
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        color: var(--text-main) !important;
        font-size: 0.82rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.15s ease;
    }
    a.udt-pill-btn:hover {
        border-color: var(--primary-light);
        transform: translateY(-1px);
    }
    a.udt-pill-btn.primary {
        background: linear-gradient(135deg, #16A36A, #10B981);
        border-color: transparent;
        color: #FFFFFF !important;
        box-shadow: 0 6px 16px rgba(22, 163, 106, 0.3);
    }

    /* Bố cục 2 cột chuyên nghiệp cho màn hình Máy Tính */
    .desktop-split-workspace {
        display: grid !important;
        grid-template-columns: minmax(0, 1.85fr) minmax(320px, 1fr);
        gap: 20px;
        align-items: start;
        margin-bottom: 16px;
    }
    .desktop-split-left,
    .desktop-split-right {
        display: flex;
        flex-direction: column;
        gap: 16px;
        min-width: 0;
    }
    .desktop-only-widget {
        display: block !important;
    }

    /* Thẻ Chi tiêu an toàn dưới lịch (Desktop) */
    .dt-safe-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 22px;
        padding: 18px 22px;
        box-shadow: var(--card-shadow);
    }
    .dt-safe-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }
    .dt-safe-title {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.96rem;
        font-weight: 800;
        color: var(--text-main);
    }
    .dt-safe-badge {
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.74rem;
        font-weight: 800;
        background: rgba(22, 163, 106, 0.16);
        color: #34D399;
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .dt-safe-badge.danger {
        background: rgba(220, 38, 38, 0.16);
        color: #F87171;
        border-color: rgba(248, 113, 113, 0.35);
    }
    .dt-safe-amount {
        font-size: 1.5rem;
        font-weight: 900;
        color: var(--text-main);
        font-variant-numeric: tabular-nums;
        margin-bottom: 10px;
    }
    .dt-safe-bar-track {
        width: 100%;
        height: 9px;
        border-radius: 999px;
        background: var(--bg-card-elevated);
        overflow: hidden;
        margin-bottom: 8px;
    }
    .dt-safe-bar-fill {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #16A36A, #34D399);
    }
    .dt-safe-meta {
        font-size: 0.78rem;
        color: var(--text-muted);
        display: flex;
        justify-content: space-between;
    }

    /* Thẻ Gợi ý từ Uni AI + Mascot (Cột phải Desktop) */
    .dt-ai-mascot-card {
        background: linear-gradient(145deg, var(--bg-card), var(--bg-card-elevated));
        border: 1px solid rgba(52, 211, 153, 0.25);
        border-radius: 22px;
        padding: 18px 20px;
        box-shadow: var(--card-shadow);
        display: flex !important;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
    }
    .dt-ai-kicker {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 800;
        color: #34D399;
        margin-bottom: 6px;
    }
    .dt-ai-body {
        font-size: 0.84rem;
        line-height: 1.5;
        color: var(--text-main);
        margin-bottom: 12px;
    }
    a.dt-ai-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 7px 14px;
        border-radius: 999px;
        background: rgba(22, 163, 106, 0.22);
        border: 1px solid rgba(52, 211, 153, 0.4);
        color: #34D399 !important;
        font-size: 0.78rem;
        font-weight: 700;
        text-decoration: none !important;
    }

    /* Thẻ Giao dịch gần đây (Cột phải Desktop) */
    .dt-recent-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 22px;
        padding: 18px 20px;
        box-shadow: var(--card-shadow);
    }
    .dt-recent-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
    }
    .dt-recent-title {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 0.94rem;
        font-weight: 800;
        color: var(--text-main);
    }
    a.dt-recent-all {
        font-size: 0.76rem;
        font-weight: 700;
        color: #34D399 !important;
        text-decoration: none !important;
    }

    /* Fixed Left Sidebar chuẩn Web Dashboard */
    .unispend-desktop-sidebar {
        display: flex !important;
        flex-direction: column;
        justify-content: space-between;
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        width: 244px;
        z-index: 9990;
        background: var(--desktop-sidebar-bg, #0D1813);
        border-right: 1px solid var(--desktop-sidebar-border, rgba(52, 211, 153, 0.14));
        padding: 20px 16px 18px 16px;
        box-shadow: 6px 0 28px rgba(0, 0, 0, 0.28);
        overflow-y: auto;
    }
    .uds-brand {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 4px 8px 18px 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 16px;
    }
    .uds-brand-icon {
        width: 40px;
        height: 40px;
        border-radius: 13px;
        background: linear-gradient(135deg, #16A36A, #34D399);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8px 18px rgba(22, 163, 106, 0.35);
        flex-shrink: 0;
    }
    .uds-brand-title {
        font-size: 1.18rem;
        font-weight: 900;
        color: #F3F4F6;
        letter-spacing: -0.02em;
        line-height: 1.1;
    }
    .uds-brand-sub {
        font-size: 0.72rem;
        color: #9CA3AF;
        font-weight: 500;
        margin-top: 2px;
    }
    .uds-nav-section-label {
        font-size: 0.67rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: rgba(156, 163, 175, 0.78);
        padding: 4px 10px 8px 10px;
    }
    .uds-nav-list {
        display: flex;
        flex-direction: column;
        gap: 5px;
    }
    a.uds-nav-link {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 10px 13px;
        border-radius: 13px;
        text-decoration: none !important;
        color: #CBD5E1 !important;
        font-size: 0.88rem;
        font-weight: 600;
        border: 1px solid transparent;
        transition: all 0.16s ease;
    }
    a.uds-nav-link:hover {
        background: rgba(52, 211, 153, 0.1);
        color: #FFFFFF !important;
        transform: translateX(2px);
    }
    a.uds-nav-link.active {
        background: linear-gradient(135deg, rgba(22, 163, 106, 0.28), rgba(52, 211, 153, 0.14));
        border: 1px solid rgba(52, 211, 153, 0.42);
        color: #FFFFFF !important;
        font-weight: 700;
        box-shadow: 0 6px 16px rgba(16, 185, 129, 0.16);
    }
    .uds-ai-card {
        margin-top: 18px;
        background: rgba(22, 163, 106, 0.12);
        border: 1px solid rgba(52, 211, 153, 0.24);
        border-radius: 16px;
        padding: 13px 14px;
    }
    .uds-ai-title {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 800;
        color: #34D399;
        margin-bottom: 5px;
    }
    .uds-ai-desc {
        font-size: 0.75rem;
        line-height: 1.45;
        color: #D1D5DB;
        margin-bottom: 9px;
    }
    a.uds-ai-cta {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-size: 0.74rem;
        font-weight: 700;
        color: #34D399 !important;
        text-decoration: none !important;
    }
    .uds-footer {
        margin-top: 14px;
        padding-top: 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        flex-direction: column;
        gap: 8px;
    }
    a.uds-theme-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 9px 12px;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #F3F4F6 !important;
        font-size: 0.8rem;
        font-weight: 700;
        text-decoration: none !important;
        transition: all 0.16s ease;
    }
    a.uds-theme-btn:hover {
        background: rgba(52, 211, 153, 0.16);
        border-color: rgba(52, 211, 153, 0.35);
    }
    .uds-mode-pill {
        font-size: 0.7rem;
        color: #9CA3AF;
        text-align: center;
        font-weight: 600;
    }

    /* Dải 4 thẻ KPI tổng quan Web Desktop */
    .unispend-desktop-kpi-strip {
        display: grid !important;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-bottom: 18px;
    }
    .udk-card {
        background: var(--bg-card);
        border: 1px solid var(--border-subtle);
        border-radius: 20px;
        padding: 16px 18px;
        box-shadow: var(--card-shadow);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        gap: 8px;
    }
    .udk-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .udk-label {
        font-size: 0.78rem;
        font-weight: 700;
        color: var(--text-muted);
    }
    .udk-val {
        font-size: 1.42rem;
        font-weight: 900;
        color: var(--text-main);
        font-variant-numeric: tabular-nums;
        letter-spacing: -0.02em;
    }
    .udk-sub {
        font-size: 0.74rem;
        font-weight: 600;
        color: var(--text-muted);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 6px;
    }

    .unispend-desktop-only {
        display: block !important;
    }

    /* Nâng cấp tỷ lệ các block hiện có cho Web Desktop rộng rãi */
    .monii-top-header {
        padding: 2px 4px 16px 4px;
    }
    .monii-brand-logo {
        font-size: 1.65rem;
    }
    .monii-brand-sub {
        font-size: 0.84rem;
    }
    .hero-banner {
        padding: 24px 28px;
        border-radius: 24px;
        margin-bottom: 18px;
    }
    .hero-grid {
        grid-template-columns: minmax(0, 1fr) 154px;
        gap: 20px;
    }
    .hero-big-amount {
        font-size: 2.38rem;
    }
    .hero-ai-pill {
        font-size: 0.84rem;
        padding: 8px 15px;
    }
    .hero-mascot-wrap {
        width: 148px;
        height: 148px;
    }
    .cal-wrapper {
        padding: 20px 22px;
        border-radius: 26px;
        margin-bottom: 18px;
    }
    .cal-top-pair {
        gap: 14px;
        margin-bottom: 16px;
    }
    .cal-box-chi, .cal-box-thu {
        padding: 14px 18px;
        border-radius: 18px;
    }
    .cal-box-chi-val, .cal-box-thu-val {
        font-size: 1.38rem;
    }
    .cal-grid-7 {
        gap: 10px;
    }
    .cal-weekday {
        font-size: 0.82rem;
        padding: 4px 0 10px 0;
    }
    a.cal-cell, .cal-cell, .cal-cell-empty {
        aspect-ratio: auto;
        min-height: 76px;
        padding: 8px 10px;
        border-radius: 15px;
    }
    .cal-day-num {
        font-size: 0.98rem;
    }
    .cal-day-exp, .cal-day-inc {
        font-size: 0.72rem;
        margin-top: 3px;
    }
    .stats-kpi-2x2 {
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 14px !important;
    }
    .ocr-kv-grid {
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 12px !important;
    }
}
"""


def minify_html(raw_html: str) -> str:
    """Nén chuỗi HTML/SVG thành 1 dòng duy nhất, không có dòng trống và không có khoảng trắng đầu dòng
    để CommonMark của Streamlit không bao giờ hiểu nhầm là code block hoặc đóng thẻ <div> sớm.
    """
    no_comments = re.sub(r"<!--.*?-->", "", raw_html, flags=re.DOTALL)
    one_line = " ".join(line.strip() for line in no_comments.splitlines() if line.strip())
    return re.sub(r">\s+<", "><", one_line).strip()


def render_html(raw_html: str) -> None:
    """Render HTML đã được minify an toàn tuyệt đối với unsafe_allow_html=True."""
    st.markdown(minify_html(raw_html), unsafe_allow_html=True)


def inject_mobile_styles(light_mode: bool = False, hide_legacy_tabs: bool = True) -> None:
    """Nạp toàn bộ CSS Mobile-First Dark-Green (và tùy chọn Light Mode + ẩn tab cũ khi ở Tab Lịch/Hóa đơn)."""
    extra_rules = []
    if light_mode:
        extra_rules.append("""
        :root {
            --bg-main: #F4F8F5 !important;
            --bg-card: #FFFFFF !important;
            --bg-card-elevated: #EAF3ED !important;
            --bg-input: #FFFFFF !important;
            --bg-alert: #EDF7F1 !important;
            --bg-surface: #FFFFFF !important;
            --bg-secondary: #EAF3ED !important;
            --border-subtle: #DCE7DF !important;
            --border-input: #C6DCD0 !important;
            --uploader-btn-bg: #E6F4EC !important;
            --uploader-btn-text: #117A4F !important;
            --text-main: #182B22 !important;
            --text-muted: #5A7467 !important;
            --color-text: #182B22 !important;
            --color-text-muted: #5A7467 !important;
            --color-border: #DCE7DF !important;
            --card-shadow: 0 8px 24px -10px rgba(15, 61, 46, 0.12) !important;
            --desktop-sidebar-bg: #0F3D2E !important;
            --desktop-sidebar-border: rgba(15, 61, 46, 0.25) !important;
        }
        """)
    if hide_legacy_tabs:
        extra_rules.append("""
        div[data-testid="stTabs"] {
            display: none !important;
        }
        """)
    css_payload = f"<style>{UNISPEND_MOBILE_CSS}\n{''.join(extra_rules)}</style>"
    st.markdown(css_payload, unsafe_allow_html=True)
