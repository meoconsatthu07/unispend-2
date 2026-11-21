# -*- coding: utf-8 -*-
"""Tạo Báo cáo Bài tập lớn (.docx) — THU CHI UTH với văn phong tự nhiên, mạch lạc chuẩn sinh viên kỹ thuật."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

BASE_DIR = Path(__file__).resolve().parent.parent
FIG_DIR = BASE_DIR / "docs" / "figures"
OUT_DOCX = BASE_DIR / "docs" / "BAO_CAO_THU_CHI_UTH.docx"

NAVY = RGBColor(0x16, 0x3A, 0x5F)
GREEN = RGBColor(0x1E, 0x4D, 0x3B)
DARK = RGBColor(0x1F, 0x29, 0x37)
MUTED = RGBColor(0x4B, 0x55, 0x63)


def set_cell_bg(cell, hex_color: str) -> None:
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        '<w:top w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        '<w:left w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        '<w:bottom w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        '<w:right w:val="single" w:sz="6" w:space="0" w:color="CBD5E1"/>'
        '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
        '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
        '</w:tblBorders>'
    )
    tbl_pr.append(borders)


def add_page_number_footer(section) -> None:
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run("Báo cáo BTL Ngôn ngữ lập trình Python - THU CHI UTH   |   Trang ")
    r.font.name = "Times New Roman"
    r.font.size = Pt(10)
    r.font.color.rgb = MUTED
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    p._p.append(fld)


def add_h1(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(15)
    r.font.color.rgb = NAVY


def add_h2(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(13.5)
    r.font.color.rgb = GREEN


def add_h3(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.bold = True
    r.font.name = "Times New Roman"
    r.font.size = Pt(12.5)
    r.font.color.rgb = DARK


def add_p(doc: Document, text: str, *, space_after: float = 5) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.25
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(13)
    r.font.color.rgb = DARK


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.line_spacing = 1.2
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r.font.size = Pt(12.5)
    r.font.color.rgb = DARK


def add_code_block(doc: Document, code: str, title: str = "") -> None:
    if title:
        pt = doc.add_paragraph()
        pt.paragraph_format.space_before = Pt(4)
        pt.paragraph_format.space_after = Pt(2)
        pt.paragraph_format.keep_with_next = True
        rt = pt.add_run(title)
        rt.bold = True
        rt.font.name = "Times New Roman"
        rt.font.size = Pt(11.5)
        rt.font.color.rgb = NAVY

    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.cell(0, 0)
    set_cell_bg(cell, "F1F5F9")
    set_table_borders(table)
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.12
    r = p.add_run(code.strip("\n"))
    r.font.name = "Consolas"
    r.font.size = Pt(9.0)
    r.font.color.rgb = DARK
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_figure(doc: Document, filename: str, caption: str, width_cm: float = 15.6) -> None:
    img_path = FIG_DIR / filename
    if not img_path.is_file():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(img_path), width=Cm(width_cm))

    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.space_after = Pt(7)
    rc = cap.add_run(caption)
    rc.italic = True
    rc.font.name = "Times New Roman"
    rc.font.size = Pt(11)
    rc.font.color.rgb = MUTED


def add_styled_table(doc: Document, headers: list[str], rows: list[list[str]], col_widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        set_cell_bg(hdr_cells[i], "1E4D3B")
        hdr_cells[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after = Pt(4)
        r = p.add_run(h)
        r.bold = True
        r.font.name = "Times New Roman"
        r.font.size = Pt(11)
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    for r_idx, row_data in enumerate(rows):
        cells = table.rows[r_idx + 1].cells
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_data):
            set_cell_bg(cells[c_idx], bg)
            cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cells[c_idx].paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.15
            r = p.add_run(str(val))
            r.font.name = "Times New Roman"
            r.font.size = Pt(10.5)
            r.font.color.rgb = DARK

    if col_widths:
        for row in table.rows:
            for i, w in enumerate(col_widths):
                row.cells[i].width = Cm(w)

    doc.add_paragraph().paragraph_format.space_after = Pt(3)


def build_report() -> Path:
    stats = json.loads((FIG_DIR / "report_stats.json").read_text(encoding="utf-8"))

    c_uth = sqlite3.connect(str(BASE_DIR / "data" / "clean_dataset" / "THU_CHI_UTH_Tai_Khoan_Sach_v2.db"))
    monthly_uth = c_uth.execute(
        """
        SELECT substr(date,1,7), COUNT(*),
               SUM(CASE WHEN kind='income' THEN amount ELSE 0 END),
               SUM(CASE WHEN kind='expense' THEN amount ELSE 0 END)
        FROM transactions GROUP BY substr(date,1,7) ORDER BY 1
        """
    ).fetchall()
    c_uth.close()

    doc = Document()
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(3.0)
        section.right_margin = Cm(2.0)
        section.different_first_page_header_footer = True
        add_page_number_footer(section)

    doc.styles["Normal"].font.name = "Times New Roman"
    doc.styles["Normal"].font.size = Pt(13)

    # =========================================================================
    # TRANG BÌA
    # =========================================================================
    def center_line(text: str, size: float, bold: bool = False, color=DARK, space_after: float = 4):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(space_after)
        r = p.add_run(text)
        r.bold = bold
        r.font.name = "Times New Roman"
        r.font.size = Pt(size)
        r.font.color.rgb = color

    center_line("BỘ GIAO THÔNG VẬN TẢI", 13, bold=True)
    center_line("TRƯỜNG ĐẠI HỌC GIAO THÔNG VẬN TẢI TP. HỒ CHÍ MINH", 14, bold=True, color=NAVY)
    center_line("KHOA CÔNG NGHỆ THÔNG TIN", 13, bold=True, space_after=24)

    center_line("BÁO CÁO BÀI TẬP LỚN CUỐI KỲ", 20, bold=True, color=NAVY, space_after=6)
    center_line("HỌC PHẦN: NGÔN NGỮ LẬP TRÌNH PYTHON", 14, bold=True, color=GREEN, space_after=22)

    title_tbl = doc.add_table(rows=1, cols=1)
    title_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = title_tbl.cell(0, 0)
    set_cell_bg(c, "EDF7F2")
    set_table_borders(title_tbl)
    tp = c.paragraphs[0]
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp.paragraph_format.space_before = Pt(12)
    tp.paragraph_format.space_after = Pt(12)
    r_sub = tp.add_run("ĐỀ TÀI:\n")
    r_sub.bold = True
    r_sub.font.name, r_sub.font.size, r_sub.font.color.rgb = "Times New Roman", Pt(13), GREEN
    r_main = tp.add_run(
        "XÂY DỰNG ỨNG DỤNG THU CHI UTH: PHÂN TÍCH, LÀM SẠCH DỮ LIỆU THU CHI "
        "VÀ QUẢN LÝ CHI TIÊU SINH VIÊN BẰNG PYTHON"
    )
    r_main.bold = True
    r_main.font.name, r_main.font.size, r_main.font.color.rgb = "Times New Roman", Pt(14.5), NAVY

    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    info_tbl = doc.add_table(rows=5, cols=2)
    info_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    info_rows = [
        ("Giảng viên hướng dẫn:", "[Điền họ tên Giảng viên]"),
        ("Lớp học phần:", "[Điền mã lớp học phần]"),
        ("Nhóm thực hiện:", "Nhóm [Điền số nhóm]"),
        ("Thành viên nhóm:", "1. [Họ tên SV 1] - MSSV: [........]\n2. [Họ tên SV 2] - MSSV: [........]\n3. [Họ tên SV 3] - MSSV: [........]\n4. [Họ tên SV 4] - MSSV: [........]\n5. [Họ tên SV 5] - MSSV: [........]"),
        ("Ngôn ngữ / Công cụ:", "Python 3.13, Pandas, Matplotlib, Altair, Streamlit, SQLite3, Gemini API"),
    ]
    for idx, (k, v) in enumerate(info_rows):
        cells = info_tbl.rows[idx].cells
        cells[0].width, cells[1].width = Cm(5.5), Cm(10.5)
        r0 = cells[0].paragraphs[0].add_run(k)
        r0.bold = True
        r0.font.name, r0.font.size = "Times New Roman", Pt(12.5)
        r1 = cells[1].paragraphs[0].add_run(v)
        r1.font.name, r1.font.size = "Times New Roman", Pt(12.5)

    doc.add_paragraph().paragraph_format.space_after = Pt(28)
    center_line("TP. Hồ Chí Minh, tháng 11 năm 2026", 12.5, bold=True, color=MUTED)
    doc.add_page_break()

    # =========================================================================
    # MỤC LỤC & DANH MỤC HÌNH
    # =========================================================================
    add_h1(doc, "MỤC LỤC")
    toc = [
        "CHƯƠNG 1: TỔNG QUAN ĐỀ TÀI VÀ PHÂN TÍCH BÀI TOÁN (Mục 4.1)",
        "    1.1. Lý do chọn đề tài",
        "    1.2. Mục tiêu và bài toán thực tế cần giải quyết",
        "    1.3. Đối tượng sử dụng và các chức năng chính",
        "    1.4. Tổng quan về dữ liệu đầu vào và đầu ra",
        "    1.5. Kỹ thuật và thư viện Python sử dụng",
        "CHƯƠNG 2: XỬ LÝ DỮ LIỆU, LƯU TRỮ CSDL VÀ TRỰC QUAN HÓA",
        "    2.1. Khám phá dữ liệu ban đầu",
        "    2.2. Tiền xử lý và làm sạch dữ liệu (2.2.1 - 2.2.3)",
        "    2.3. Lưu dữ liệu sạch vào SQLite và tách tài khoản theo file .db",
        "    2.4. Trực quan hóa và phân tích dữ liệu (2.4.1 - 2.4.11)",
        "CHƯƠNG 3: THIẾT KẾ, CÀI ĐẶT ỨNG DỤNG VÀ KIỂM THỬ ĐÁNH GIÁ (Mục 4.2 - 4.4)",
        "    3.1. Sơ đồ luồng xử lý, cấu trúc thư mục và thiết kế OOP (Mục 4.2)",
        "    3.2. Cài đặt kiểm tra lỗi, chú thích mã nguồn và cách chạy (Mục 4.3)",
        "    3.3. Kiểm thử chương trình (71 ca kiểm thử tự động) (Mục 4.4)",
        "    3.4. Đánh giá kết quả, ưu điểm, hạn chế và hướng phát triển (Mục 4.4)",
        "CHƯƠNG 4: GIAO DIỆN WEB VÀ MÔ TẢ CHI TIẾT CÁC CHỨC NĂNG (14 MÀN HÌNH THỰC TẾ)",
        "    4.1. Màn hình Tổng quan tài chính và Lịch tài chính theo ngày",
        "    4.2. Màn hình Theo dõi 3 khoản chi thiết yếu và 4 tab nghiệp vụ",
        "    4.3. Màn hình Quản lý đa tài khoản dữ liệu (Mỗi file .db là 1 tài khoản riêng)",
        "    4.4. Màn hình AI Làm sạch và Chuẩn hóa dữ liệu thô",
        "    4.5. Màn hình Thống kê chi tiêu, Cảnh báo ngân sách và Xuất báo cáo Excel/PDF",
        "    4.6. Màn hình Phân tích tỷ trọng hạng mục chi tiêu có tìm kiếm nhanh",
        "    4.7. Màn hình Hóa đơn định kỳ, Sổ nợ và Kho ảnh hóa đơn lưu trữ",
        "    4.8. Màn hình Quét hóa đơn AI (Tesseract OCR 5.5 + OpenCV + Gemini Vision)",
        "    4.9. Màn hình Nhập chi tiêu bằng giọng nói tiếng Việt tự nhiên",
        "    4.10. Màn hình Tìm kiếm giao dịch và Trợ lý AI Phân tích chi tiêu",
        "    4.11. Khung Quick Add — Ghi nhanh giao dịch theo ngày trên Lịch",
        "    4.12. Hộp Chi tiêu an toàn mỗi ngày và Báo cáo cảnh báo vượt định mức",
        "    4.13. Khung Xem trước báo cáo Excel 3 Sheet trực tiếp trên trình duyệt",
        "    4.14. Tệp Báo cáo tài chính Excel (.xlsx) thực tế khi mở trên Microsoft Excel",
        "KẾT LUẬN VÀ TÀI LIỆU THAM KHẢO",
    ]
    for line in toc:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(line)
        r.font.name, r.font.size = "Times New Roman", Pt(11.5)
        r.bold = not line.startswith("    ")

    add_h2(doc, "Danh mục hình ảnh và biểu đồ")
    for ft in [
        "Hình 1. Kết quả kiểm tra kích thước và kiểu dữ liệu ban đầu (2.461 dòng, 8 cột).",
        "Hình 2. Kết quả kiểm tra giá trị thiếu, dòng trùng lặp và Transfer-Out.",
        "Hình 3. Kết quả chuẩn hóa ngày tháng và kiểm tra ngoại lai theo IQR.",
        "Hình 4. Truy vấn kiểm tra 2.298 bản ghi sạch đã lưu trong SQLite.",
        "Hình 4a. Kiểm tra bảng transactions (139 bản ghi) của 1_THU_CHI_UTH_Demo_139_GD.db trên SQLite Viewer.",
        "Hình 4b. Kiểm tra bảng receipts (51 hóa đơn OCR) của 1b_THU_CHI_UTH_51_Hoa_Don_OCR.db trên SQLite Viewer.",
        "Hình 4c. Kiểm tra bảng transactions (151 bản ghi sạch) của 2_THU_CHI_UTH_Sinh_Vien_Sach_151_GD.db trên SQLite Viewer.",
        "Hình 5. Biểu đồ tròn tỷ trọng Thu nhập và Chi tiêu tổng quan.",
        "Hình 6. Biểu đồ tỷ trọng giá trị chi tiêu theo 6 danh mục.",
        "Hình 7. Biểu đồ tần suất số lần chi tiêu theo danh mục.",
        "Hình 8. Biểu đồ cơ cấu nguồn thu nhập.",
        "Hình 9. Biểu đồ phân bố chi tiêu theo phương thức thanh toán.",
        "Hình 10. Biểu đồ diễn biến thu chi theo từng năm (2015 - 2018).",
        "Hình 11. Biểu đồ tổng chi tiêu cộng dồn theo 12 tháng.",
        "Hình 12. Biểu đồ chi tiêu theo ngày trong tuần (Thứ 2 - Chủ nhật).",
        "Hình 13. Biểu đồ chi tiêu theo 4 mùa trong năm.",
        "Hình 14. So sánh tỷ trọng chi tiêu giữa tài khoản SV UTH và dữ liệu thật Kaggle.",
        "Hình 15. Biểu đồ thu nhập, chi tiêu và tiết kiệm 6 tháng của sinh viên UTH.",
        "Hình 16. Sơ đồ chức năng và luồng xử lý của ứng dụng THU CHI UTH.",
        "Hình 17. Giao diện Tổng quan tài chính và Lịch tài chính theo ngày.",
        "Hình 18. Giao diện Theo dõi 3 khoản chi thiết yếu (Tiền ăn, Tiền trọ, Đi lại) và 4 tab dưới.",
        "Hình 19. Giao diện Quản lý đa tài khoản dữ liệu (Mỗi file .db = 1 tài khoản riêng).",
        "Hình 20. Giao diện AI Làm sạch và Chuẩn hóa dữ liệu thô (CSV/Excel/Văn bản).",
        "Hình 21. Giao diện Thống kê chi tiêu, Cảnh báo vượt định mức và Xuất Excel/PDF.",
        "Hình 22. Giao diện Tỷ trọng hạng mục chi tiêu kèm thanh tìm kiếm nhanh.",
        "Hình 23. Giao diện Hóa đơn và Kho ảnh hóa đơn đã lưu (51 hóa đơn).",
        "Hình 24. Giao diện Quét hóa đơn AI (Tesseract OCR 5.5.0 + Tiền xử lý OpenCV + Gemini).",
        "Hình 25. Giao diện Nhập chi tiêu bằng giọng nói tiếng Việt tự nhiên.",
        "Hình 26. Giao diện Tìm kiếm giao dịch và Trợ lý AI Phân tích chi tiêu.",
        "Hình 27. Khung Quick Add - Ghi nhanh giao dịch theo ngày đang chọn trên lịch.",
        "Hình 28. Hộp Chi tiêu an toàn mỗi ngày và Báo cáo cảnh báo vượt định mức.",
        "Hình 29. Khung Xem trước báo cáo Excel 3 Sheet trực tiếp trên giao diện Web.",
        "Hình 30. Tệp Báo cáo tài chính Excel (.xlsx) thực tế khi mở trên Microsoft Excel.",
    ]:
        add_bullet(doc, ft)
    doc.add_page_break()

    # =========================================================================
    # CHƯƠNG 1: TỔNG QUAN ĐỀ TÀI VÀ PHÂN TÍCH BÀI TOÁN
    # =========================================================================
    add_h1(doc, "CHƯƠNG 1: TỔNG QUAN ĐỀ TÀI VÀ PHÂN TÍCH BÀI TOÁN (MỤC 4.1)")

    add_h2(doc, "1.1. Lý do chọn đề tài")
    add_p(
        doc,
        "Với sinh viên ở trọ tại TP.HCM, đặc biệt là sinh viên Trường Đại học Giao thông Vận tải TP.HCM (UTH), "
        "chuyện chi tiêu hằng tháng rất dễ bị lố tay nếu không ghi chép lại. Tiền gia đình gửi hoặc lương làm thêm "
        "thường nhận một lần vào đầu tháng, nhưng các khoản chi như cơm trưa, xăng xe, tiền trọ, in tài liệu lại "
        "rải rác mỗi ngày. Đến cuối tháng nhiều bạn không nhớ mình đã tiêu vào đâu mà hết tiền."
    )
    add_p(
        doc,
        "Khi bắt tay làm đề tài, nhóm còn gặp thêm một vấn đề khác khá thực tế. Nếu lấy dữ liệu thu chi có sẵn từ "
        "file Excel tự ghi, sao kê ngân hàng hay bộ dữ liệu công khai trên mạng (như Kaggle) để đưa vào phần mềm "
        "phân tích thì dữ liệu gốc thường khá lộn xộn. Ngày tháng lúc có giờ lúc không, nhiều dòng bị trống ghi chú, "
        "có dòng bị lặp lại hoặc lẫn cả giao dịch chuyển tiền qua lại giữa các tài khoản. Nếu nạp thẳng vào ứng dụng "
        "thì các con số thống kê sẽ bị sai ngay."
    )
    add_p(
        doc,
        "Vì vậy, nhóm chọn xây dựng ứng dụng THU CHI UTH bằng Python. Ứng dụng không chỉ để ghi chép thu chi hằng "
        "ngày mà còn xử lý luôn phần làm sạch dữ liệu thô, tách mỗi bộ dữ liệu thành một file SQLite riêng để tiện "
        "quản lý và vẽ biểu đồ theo dõi."
    )

    add_h2(doc, "1.2. Mục tiêu và bài toán thực tế cần giải quyết")
    add_p(doc, "Khi thực hiện bài tập lớn này, nhóm đặt ra các mục tiêu cụ thể sau:")
    add_bullet(doc, "Kiểm tra và làm sạch dữ liệu thu chi thô: xử lý ô bị trống, bỏ dòng trùng lặp, loại bỏ giao dịch chuyển khoản nội bộ, chuẩn hóa lại ngày tháng và đơn vị tiền tệ.")
    add_bullet(doc, "Phân tích thói quen thu chi từ dữ liệu thực tế: xem danh mục nào tốn tiền nhất, danh mục nào hay chi nhiều lần nhất, biến động theo tháng, theo thứ trong tuần và theo mùa ra sao.")
    add_bullet(doc, "Vẽ các biểu đồ trực quan bằng Matplotlib và Altair để nhìn ra ngay sự khác nhau giữa dữ liệu thật từ Kaggle và dữ liệu sinh hoạt 6 tháng của sinh viên UTH.")
    add_bullet(doc, "Tích hợp AI (Gemini API, có sẵn bản chạy offline dự phòng) giúp người dùng tải file CSV/Excel thô hoặc dán vài dòng ghi chú lộn xộn để phần mềm tự làm sạch rồi lưu thành một tài khoản riêng.")
    add_bullet(doc, "Hoàn thiện ứng dụng web chạy trực tiếp trên máy cá nhân bằng Streamlit, có thêm quét hóa đơn OCR, nhập giọng nói tiếng Việt, xuất báo cáo Excel/PDF và kiểm thử tự động.")

    add_h2(doc, "1.3. Đối tượng sử dụng và các chức năng chính")
    add_p(
        doc,
        "Sản phẩm hướng tới sinh viên UTH cần một công cụ gọn nhẹ để theo dõi thu chi hằng tháng ngay trên máy tính "
        "cá nhân mà không cần cài đặt phần mềm phức tạp. Ngoài ra, bất kỳ bạn sinh viên nào đang học Python cũng có "
        "thể dùng chức năng làm sạch dữ liệu để xử lý nhanh file CSV/Excel thô."
    )
    add_styled_table(
        doc,
        ["Mã CN", "Chức năng", "Mô tả cách hoạt động"],
        [
            ["CN-01", "Quản lý thu chi (CRUD)", "Thêm, xem, sửa, xóa từng khoản thu/chi; lọc theo tháng, loại giao dịch, danh mục và tìm kiếm theo từ khóa tiếng Việt."],
            ["CN-02", "Lịch tài chính theo ngày", "Hiển thị tổng thu, tổng chi trên từng ngày của lịch tháng; tính số dư và mức chi an toàn mỗi ngày."],
            ["CN-03", "Ngân sách và cảnh báo", "Đặt hạn mức chi tổng và từng danh mục trong tháng; hiện cảnh báo khi dùng từ 80% trở lên hoặc vượt 100%."],
            ["CN-04", "Quản lý đa tài khoản (.db)", "Mỗi file SQLite (.db) là một tài khoản độc lập; cho phép đổi tài khoản, tạo mới, đổi tên, xóa và nhập file .db/.csv."],
            ["CN-05", "AI làm sạch dữ liệu thô", "Tải file CSV/Excel thô hoặc dán ghi chú tự do để AI nhận diện cột, chuẩn hóa ngày/tiền/danh mục rồi lưu thành tài khoản .db mới."],
            ["CN-06", "Quét hóa đơn OCR & Giọng nói", "Đọc ảnh hóa đơn bằng OpenCV + Tesseract/Gemini và tách số tiền từ câu nói tiếng Việt (45k, 1tr5, hai trăm nghìn)."],
            ["CN-07", "Xuất báo cáo & Sao lưu", "Xuất báo cáo ra Excel (.xlsx), PDF (.pdf) có dấu tiếng Việt, CSV và sao lưu/khôi phục file SQLite."],
        ],
        col_widths=[1.6, 4.2, 10.2],
    )

    add_h2(doc, "1.4. Tổng quan về dữ liệu đầu vào và đầu ra")
    add_p(
        doc,
        "Để kiểm chứng phần làm sạch và phân tích dữ liệu trên số liệu thật, nhóm sử dụng bộ dữ liệu công khai "
        "Daily Household Transactions của tác giả Prasad Patil (nguồn Kaggle, bản tải CSV tại GitHub: "
        "https://github.com/Mahesh1827/Daily_Transactions). File gốc có 2.461 dòng và 8 cột, ghi lại các khoản "
        "thu chi hằng ngày từ 01/01/2015 đến 20/09/2018. Bên cạnh đó, nhóm chuẩn bị thêm bộ dữ liệu 6 tháng "
        "(06/2026 - 11/2026, 151 giao dịch) sát với chi tiêu sinh viên UTH để so sánh."
    )
    add_styled_table(
        doc,
        ["Tên cột gốc", "Ý nghĩa", "Kiểu dữ liệu", "Ghi nhận ban đầu"],
        [
            ["Date", "Ngày giờ phát sinh giao dịch", "object (str)", "Có dòng kèm giờ phút (DD-MM-YYYY HH:MM), có dòng chỉ có ngày"],
            ["Mode", "Phương thức thanh toán (Cash, Saving Bank...)", "object (str)", "Đủ 2.461 giá trị"],
            ["Category", "Danh mục chính (Food, Transportation, Salary...)", "object (str)", "50 nhãn tiếng Anh viết hoa thường chưa đều"],
            ["Subcategory", "Danh mục phụ chi tiết (Train, snacks, Netflix...)", "object (str)", "Trống 635 dòng (25,8%)"],
            ["Note", "Ghi chú giao dịch", "object (str)", "Trống 521 dòng (21,2%)"],
            ["Amount", "Số tiền giao dịch", "float64", "Tính bằng INR, nhỏ nhất 2.0, lớn nhất 250.000.0"],
            ["Income/Expense", "Phân loại thu, chi hoặc chuyển khoản", "object (str)", "Expense: 2.176, Transfer-Out: 160, Income: 125"],
            ["Currency", "Đơn vị tiền tệ", "object (str)", "Toàn bộ là INR"],
        ],
        col_widths=[3.2, 5.2, 2.8, 4.8],
    )
    add_p(
        doc,
        "Đầu ra của chương trình gồm file cơ sở dữ liệu SQLite (.db) đã kiểm định sạch 100%, giao diện web hiển thị "
        "lịch và biểu đồ thống kê, cùng các file báo cáo Excel (.xlsx), PDF (.pdf) và CSV (.csv) để lưu trữ hoặc nộp báo cáo."
    )

    add_h2(doc, "1.5. Kỹ thuật và thư viện Python sử dụng")
    add_p(
        doc,
        "Nhóm viết toàn bộ chương trình bằng Python 3.13 trên Visual Studio Code. Thay vì dùng một file script dài, "
        "mã nguồn được tách thành nhiều module rõ ràng theo từng nhiệm vụ như đọc ghi SQLite, làm sạch dữ liệu, "
        "vẽ biểu đồ và hiển thị giao diện web."
    )
    add_styled_table(
        doc,
        ["Nhóm công việc", "Thư viện Python", "Mục đích sử dụng"],
        [
            ["Đọc và xử lý bảng dữ liệu", "pandas, numpy", "Đọc CSV/Excel thô, kiểm tra null, bỏ trùng, chuẩn hóa ngày và tính IQR."],
            ["Vẽ biểu đồ", "matplotlib, altair, Pillow", "Vẽ các biểu đồ phân tích và sơ đồ luồng xử lý."],
            ["Cơ sở dữ liệu & Web", "sqlite3, streamlit, fastapi", "Lưu trữ tài khoản .db có ràng buộc CHECK, làm giao diện web và API."],
            ["AI và xử lý ảnh OCR", "google-genai, pydantic, opencv-python, pytesseract", "Hỗ trợ phân loại dữ liệu thô, đọc ảnh hóa đơn và kiểm tra JSON."],
            ["Xuất file và kiểm thử", "openpyxl, fpdf2, python-docx, unittest", "Xuất Excel, PDF, Word và chạy bộ 71 ca kiểm thử tự động."],
        ],
        col_widths=[4.2, 4.6, 7.2],
    )
    doc.add_page_break()

    # =========================================================================
    # CHƯƠNG 2: XỬ LÝ DỮ LIỆU, LƯU TRỮ CSDL VÀ TRỰC QUAN HÓA
    # =========================================================================
    add_h1(doc, "CHƯƠNG 2: XỬ LÝ DỮ LIỆU, LƯU TRỮ CSDL VÀ TRỰC QUAN HÓA")

    add_h2(doc, "2.1. Khám phá dữ liệu ban đầu")
    add_p(
        doc,
        "Đầu tiên nhóm dùng Pandas đọc file THU_CHI_UTH_Du_Lieu_Tho_Kaggle.csv để xem tổng số dòng, số cột và kiểu "
        "dữ liệu hiện tại của từng thuộc tính trước khi sửa."
    )
    add_figure(doc, "step_01_explore_info.png", "Hình 1. Kết quả kiểm tra kích thước và kiểu dữ liệu ban đầu (2.461 dòng, 8 cột).")
    add_p(
        doc,
        "Nhìn vào kết quả in ra, bảng dữ liệu gốc có 2.461 dòng và 8 cột. Ngay ở bước đầu đã thấy mấy điểm cần xử lý: "
        "cột Date đang lưu kiểu chuỗi object, hai cột Subcategory và Note bị thiếu dữ liệu khá nhiều, cột Income/Expense "
        "có lẫn 160 dòng Transfer-Out, còn cột Category thì dùng nhiều nhãn tiếng Anh rời rạc."
    )

    add_h2(doc, "2.2. Tiền xử lý và làm sạch dữ liệu")

    add_h3(doc, "2.2.1. Kiểm tra giá trị thiếu, dòng trùng lặp và chuyển khoản nội bộ")
    add_p(
        doc,
        "Nếu để nguyên các dòng Transfer-Out (chuyển tiền từ ví này sang ví khác của cùng một người) thì tổng chi "
        "sẽ bị cộng dư lên. Tương tự, các dòng trùng lặp cũng làm sai số liệu thống kê. Nhóm kiểm tra cụ thể số lượng "
        "từng loại lỗi bằng các lệnh Pandas cơ bản."
    )
    add_figure(doc, "step_02_missing_dup.png", "Hình 2. Kết quả kiểm tra giá trị thiếu, dòng trùng lặp và Transfer-Out.")
    add_p(
        doc,
        "Từ kết quả đo được, nhóm xử lý theo 3 bước: lọc bỏ toàn bộ 160 dòng Transfer-Out, xóa 9 dòng bị lặp hoàn toàn "
        "bằng drop_duplicates(), và tự động điền lại phần ghi chú cho 521 dòng bị thiếu Note bằng cách ghép tên Category, "
        "Subcategory và Mode (ví dụ 'Food - snacks (Cash)') để giữ nguyên giá trị tiền mà không làm mất bản ghi."
    )

    add_h3(doc, "2.2.2. Chuẩn hóa ngày tháng và kiểm tra ngoại lai theo IQR")
    add_p(
        doc,
        "Cột Date trong file gốc trộn lẫn cả kiểu 'DD-MM-YYYY HH:MM' và 'DD-MM-YYYY'. Nhóm dùng hàm pd.to_datetime "
        "với tham số dayfirst=True và format='mixed' để chuyển về định dạng ngày chuẩn ISO YYYY-MM-DD, kiểm tra lại "
        "không có dòng nào bị lỗi ngày. Sau khi quy đổi tiền tệ từ INR sang VNĐ theo tỷ giá cố định 1 INR = 300 VNĐ "
        "(làm tròn 1.000đ), nhóm chạy kiểm tra ngoại lai bằng khoảng tứ phân vị IQR."
    )
    add_figure(doc, "step_03_date_iqr.png", "Hình 3. Kết quả chuẩn hóa ngày tháng và kiểm tra ngoại lai theo IQR.")
    add_p(
        doc,
        f"Kết quả tính IQR trên tập giao dịch chi tiêu cho thấy Q1 = {stats['q1']:,.0f}đ, Q3 = {stats['q3']:,.0f}đ, "
        f"IQR = {stats['iqr']:,.0f}đ và ngưỡng trên Q3 + 1,5*IQR = {stats['upper_iqr']:,.0f}đ. Có {stats['iqr_outliers']} "
        "giao dịch nằm trên mức này. Khi mở kiểm tra lại từng dòng thì đây không phải dữ liệu nhập sai mà là những "
        "khoản chi lớn có thật như đóng quỹ đầu tư, gửi tiết kiệm định kỳ hoặc chi phí lớn cho gia đình. Do đó nhóm "
        "giữ lại các dòng này thay vì xóa tự động."
    )

    add_h3(doc, "2.2.3. Chuẩn hóa danh mục và bảng đối chiếu trước/sau làm sạch")
    add_p(
        doc,
        "Các nhãn danh mục tiếng Anh trong file gốc được ánh xạ về đúng 6 danh mục chi tiêu và 4 danh mục thu nhập "
        "tiếng Việt của web THU CHI UTH. Bảng dưới đây tóm tắt lại số liệu trước và sau khi chạy pipeline làm sạch:"
    )
    add_styled_table(
        doc,
        ["Hạng mục kiểm tra", "Trước khi làm sạch", "Sau khi làm sạch", "Cách xử lý"],
        [
            ["Tổng số dòng", "2.461 dòng", "2.298 dòng (2015-2018)", "Giữ lại các dòng Thu/Chi hợp lệ"],
            ["Dòng Transfer-Out", "160 dòng", "0 dòng", "Lọc bỏ để không tính nhầm vào chi tiêu"],
            ["Dòng trùng lặp", "9 dòng", "0 dòng", "Xóa bằng df.drop_duplicates()"],
            ["Ô thiếu ở cột Note", "521 dòng (21,2%)", "0 dòng", "Bù tự động từ Category/Subcategory/Mode"],
            ["Định dạng ngày", "Chuỗi hỗn hợp", "100% YYYY-MM-DD", "Chuyển đổi bằng pd.to_datetime()"],
            ["Danh mục & Tiền tệ", "38 nhãn tiếng Anh / INR", "6 mục chi, 4 mục thu / VNĐ", "Ánh xạ danh mục + quy đổi 1 INR = 300đ"],
        ],
        col_widths=[4.0, 3.6, 3.8, 4.6],
    )

    add_h2(doc, "2.3. Lưu dữ liệu sạch vào SQLite và tách tài khoản theo file .db")
    add_p(
        doc,
        "Dữ liệu sau khi làm sạch được xuất ra file CSV (THU_CHI_UTH_Du_Lieu_That_Kaggle_v2.csv) và nạp vào cơ sở "
        "dữ liệu SQLite3 (THU_CHI_UTH_Tai_Khoan_Kaggle_v2.db) bằng executemany(). Bảng transactions có sẵn ràng buộc "
        "CHECK để chặn ngày sai định dạng, số tiền nhỏ hơn hoặc bằng 0 và danh mục không hợp lệ. Hình 4 cho thấy kết "
        "quả truy vấn kiểm tra lại trực tiếp trong SQLite."
    )
    add_figure(doc, "step_04_sqlite_verify.png", "Hình 4. Truy vấn kiểm tra 2.298 bản ghi sạch đã lưu trong SQLite.")
    add_p(
        doc,
        "Thay vì gộp chung mọi thứ vào một file duy nhất, nhóm thiết kế mỗi file .db là một tài khoản riêng "
        "(xử lý trong accounts.py). Khi người dùng đổi tài khoản trên web, hệ thống tự đóng file cũ, mở file .db mới "
        "và lưu đường dẫn vào .active_account.json nên chuyển qua Lịch hay Thống kê đều cập nhật đúng dữ liệu của "
        "tài khoản đang chọn."
    )

    add_h3(doc, "2.3.1. Kiểm tra trực tiếp các tệp cơ sở dữ liệu SQLite (.db) trên SQLite Viewer")
    add_p(
        doc,
        "Sau khi xuất và lưu các bộ dữ liệu vào SQLite, nhóm mở trực tiếp các tệp .db trên công cụ SQLite Viewer "
        "để kiểm tra cấu trúc bảng, số lượng bản ghi và đối chiếu giá trị thực tế trong từng tài khoản:"
    )
    add_figure(
        doc,
        "db_01_sqlite_demo_139.png",
        "Hình 4a. Kiểm tra tệp 1_THU_CHI_UTH_Demo_139_GD.db trên SQLite Viewer (3 bảng: transactions, sqlite_sequence, budgets; 139 bản ghi giao dịch).",
    )
    add_p(
        doc,
        "1) Tệp 1_THU_CHI_UTH_Demo_139_GD.db (Hình 4a): Gồm 3 bảng (transactions, sqlite_sequence, budgets). Bảng "
        "transactions chứa đúng 139 bản ghi thu chi từ tháng 06/2026 đến tháng 11/2026 (Tổng thu 36.000.000 VNĐ, "
        "Tổng chi 31.082.500 VNĐ; riêng tháng 11/2026 có 68 giao dịch khớp với giao diện web). Các cột date, kind, "
        "category, amount và note hiển thị rõ ràng, số tiền được lưu nguyên vẹn dạng số nguyên dương."
    )
    add_figure(
        doc,
        "db_02_sqlite_receipts_51.png",
        "Hình 4b. Kiểm tra tệp mở rộng 1b_THU_CHI_UTH_51_Hoa_Don_OCR.db trên SQLite Viewer (6 bảng; bảng receipts lưu 51 hóa đơn OCR).",
    )
    add_p(
        doc,
        "2) Tệp mở rộng 1b_THU_CHI_UTH_51_Hoa_Don_OCR.db (Hình 4b): Gồm 6 bảng chuyên biệt (ui_settings, receipts, "
        "sqlite_sequence, savings_goals, recurring_items, ai_history). Trong đó bảng receipts lưu 51 hóa đơn mua hàng "
        "thực tế của sinh viên UTH (Tổng giá trị 6.291.500 VNĐ) với đầy đủ tên cửa hàng (Cơm tấm Sài Gòn 24h, Phở bò "
        "Gia truyền, Highlands Coffee D2, Bún bò Huế O Xuân, Circle K Nguyễn Gia Trí, WinMart+ Bình Thạnh, Phúc Long, "
        "Bách Hóa Xanh...), ngày giờ mua, chuỗi JSON danh sách món hàng (items_json) và phương thức thanh toán."
    )
    add_figure(
        doc,
        "db_03_sqlite_clean_151.png",
        "Hình 4c. Kiểm tra tệp 2_THU_CHI_UTH_Sinh_Vien_Sach_151_GD.db trên SQLite Viewer (151 bản ghi thu chi sinh viên UTH đã làm sạch 100%).",
    )
    add_p(
        doc,
        "3) Tệp 2_THU_CHI_UTH_Sinh_Vien_Sach_151_GD.db (Hình 4c): Lưu bộ dữ liệu chuẩn 6 tháng của sinh viên UTH "
        "sau khi đã kiểm định sạch 100% (Records: 151, 0 dòng trống ghi chú, 0 dòng sai năm, Tổng thu 41.180.000 VNĐ, "
        "Tổng chi 27.372.000 VNĐ, tỷ lệ tiết kiệm 33,53%). Qua bước kiểm tra trên SQLite Viewer, cả 3 tệp cơ sở dữ liệu "
        "đều đảm bảo toàn vẹn cấu trúc và sẵn sàng phục vụ truy vấn, trực quan hóa trên ứng dụng web."
    )

    # =========================================================================
    # 2.4. TRỰC QUAN HÓA VÀ PHÂN TÍCH DỮ LIỆU
    # =========================================================================
    add_h2(doc, "2.4. Trực quan hóa và phân tích dữ liệu")

    add_h3(doc, "2.4.1. Mục tiêu và các chỉ số theo dõi")
    add_p(
        doc,
        "Sau khi dữ liệu đã sạch và nằm gọn trong SQLite, nhóm vẽ các biểu đồ để xem cụ thể tiền đến từ đâu, chi "
        "vào việc gì nhiều nhất và có quy luật nào theo thời gian hay không. Ba chỉ số chính nhóm dùng để so sánh là "
        "Tỷ lệ tiết kiệm = (Tổng thu - Tổng chi) / Tổng thu * 100%, Tỷ trọng từng danh mục chi, và số lần giao dịch."
    )

    add_h3(doc, "2.4.2. Tổng quan cơ cấu Thu nhập và Chi tiêu")
    add_figure(doc, "chart_01_thu_chi_tong_quan.png", "Hình 5. Biểu đồ tròn tỷ trọng Thu nhập và Chi tiêu tổng quan (2.298 giao dịch).")
    add_p(
        doc,
        f"Trong 2.298 giao dịch sạch ({stats['inc_rows']} khoản thu và {stats['exp_rows']} khoản chi), tổng thu nhập "
        f"đạt {stats['tot_inc']:,} VNĐ (912,72 triệu) còn tổng chi tiêu là {stats['tot_exp']:,} VNĐ (586,64 triệu). "
        f"Phần chênh lệch giữ lại được là {stats['net_bal']:,} VNĐ, tương ứng tỷ lệ tiết kiệm {stats['save_rate']}%. "
        "Nhìn chung chủ tài khoản chi tiêu khá chừng mực so với thu nhập."
    )

    add_h3(doc, "2.4.3. Phân tích tỷ trọng giá trị chi tiêu theo danh mục")
    add_figure(doc, "chart_02_chi_tieu_theo_danh_muc.png", "Hình 6. Biểu đồ tỷ trọng giá trị chi tiêu theo 6 danh mục.")
    add_p(
        doc,
        f"Nhìn vào Hình 6 có thể thấy nhóm Khác chiếm tới {stats['cat_exp_pct'].get('Khác', 0)}% tổng số tiền chi ra. "
        "Sở dĩ mục này cao như vậy là vì trong bộ dữ liệu gốc của người đi làm có nhiều khoản đóng quỹ đầu tư, "
        f"gửi tiết kiệm dài hạn và chi phí y tế gia đình. Tiếp theo là Giải trí ({stats['cat_exp_pct'].get('Giải trí', 0)}%), "
        f"Tiền trọ/Nhà ở ({stats['cat_exp_pct'].get('Tiền trọ', 0)}%), Đi lại ({stats['cat_exp_pct'].get('Đi lại', 0)}%), "
        f"Ăn uống ({stats['cat_exp_pct'].get('Ăn uống', 0)}%) và Học tập ({stats['cat_exp_pct'].get('Học tập', 0)}%)."
    )

    add_h3(doc, "2.4.4. Phân tích tần suất số lần giao dịch theo danh mục")
    add_figure(doc, "chart_03_tan_suat_giao_dich.png", "Hình 7. Biểu đồ tần suất số lần chi tiêu theo danh mục.")
    add_p(
        doc,
        f"Một điểm khá thú vị là khi đếm theo số lần chi (Hình 7), Ăn uống lại đứng đầu với {stats['cat_cnt'].get('Ăn uống', 0)} "
        "lần giao dịch, chiếm khoảng 42% tổng số lần quẹt tiền và cao gấp 2,5 lần mức trung bình (362 lần/danh mục), "
        "dù tổng tiền chỉ bằng 5,6%. Theo sau là Khác "
        f"({stats['cat_cnt'].get('Khác', 0)} lần) và Đi lại ({stats['cat_cnt'].get('Đi lại', 0)} lần). "
        "Điều này cho thấy tiền ăn tuy mỗi bữa không lớn nhưng phát sinh liên tục hằng ngày."
    )

    add_h3(doc, "2.4.5. Phân tích cơ cấu nguồn Thu nhập")
    add_figure(doc, "chart_04_nguon_thu_nhap.png", "Hình 8. Biểu đồ cơ cấu nguồn thu nhập.")
    add_p(
        doc,
        f"Về nguồn thu, tiền lương từ công việc (nhóm Làm thêm) chiếm tỷ lệ lớn nhất với {stats['inc_pct'].get('Làm thêm', 0)}%. "
        f"Nhóm Khác (gồm cổ tức, tiền lãi ngân hàng, hoàn thuế) chiếm {stats['inc_pct'].get('Khác', 0)}%, tiếp đến là "
        f"Học bổng/Thưởng ({stats['inc_pct'].get('Học bổng', 0)}%) và Gia đình hỗ trợ ({stats['inc_pct'].get('Gia đình hỗ trợ', 0)}%)."
    )

    add_h3(doc, "2.4.6. Phân tích chi tiêu theo Phương thức thanh toán")
    add_figure(doc, "chart_05_phuong_thuc_thanh_toan.png", "Hình 9. Biểu đồ phân bố chi tiêu theo phương thức thanh toán (Top 5).")
    add_p(
        doc,
        "Dựa vào cột Mode của file gốc, hai hình thức thanh toán phổ biến nhất là Tài khoản ngân hàng 1 và Tiền mặt "
        "(Cash), cộng lại chiếm hơn 90% tổng số lần chi. Tiền mặt hay dùng cho các khoản ăn vặt, đi xe hằng ngày, còn "
        "tài khoản ngân hàng dùng cho hóa đơn định kỳ và các khoản chuyển lớn."
    )

    add_h3(doc, "2.4.7. Diễn biến Thu và Chi theo từng năm (2015 - 2018)")
    add_figure(doc, "chart_06_xu_huong_theo_nam.png", "Hình 10. Biểu đồ diễn biến tổng thu và tổng chi qua các năm (2015 - 2018).")
    add_p(
        doc,
        "Qua 4 năm ghi nhận, đường tổng thu luôn nằm cao hơn đường tổng chi nên mỗi năm đều có khoản dư. Riêng năm "
        "2018 tổng số liệu thấp hơn năm 2017 là do tập dữ liệu gốc chỉ thu thập đến hết ngày 20/09/2018 chứ chưa đủ cả năm."
    )

    add_h3(doc, "2.4.8. Biến động chi tiêu theo 12 tháng trong năm")
    add_figure(doc, "chart_07_chi_tieu_theo_thang.png", "Hình 11. Biểu đồ tổng chi tiêu cộng dồn theo 12 tháng trong năm.")
    add_p(
        doc,
        f"Tính cộng dồn theo tháng, mức chi trung bình là {stats['month_avg']} triệu VNĐ/tháng. Tháng chi nhiều nhất là "
        f"Tháng {stats['month_max'][0]} ({stats['month_max'][1]} triệu) và thấp nhất là Tháng {stats['month_min'][0]} "
        f"({stats['month_min'][1]} triệu). Một số tháng tăng vọt lên trên đường trung bình do phát sinh các khoản đóng "
        "quỹ lớn hoặc mua sắm đầu năm."
    )

    add_h3(doc, "2.4.9. Phân tích chi tiêu theo ngày trong tuần")
    add_figure(doc, "chart_08_chi_tieu_theo_thu.png", "Hình 12. Biểu đồ chi tiêu theo ngày trong tuần (Thứ 2 - Chủ nhật).")
    add_p(
        doc,
        f"Mức chi trung bình theo thứ trong tuần là {stats['wd_avg']} triệu VNĐ. Ngày chi cao nhất là {stats['wd_max'][0]} "
        f"({stats['wd_max'][1]} triệu) và thấp nhất là {stats['wd_min'][0]} ({stats['wd_min'][1]} triệu). Nhìn chung các "
        "ngày hành chính trong tuần có tổng tiền cao hơn cuối tuần vì các giao dịch ngân hàng và đóng phí thường làm vào giờ làm việc."
    )

    add_h3(doc, "2.4.10. Phân tích chi tiêu theo 4 mùa trong năm")
    add_figure(doc, "chart_09_chi_tieu_theo_mua.png", "Hình 13. Biểu đồ chi tiêu theo 4 mùa trong năm.")
    add_p(
        doc,
        f"Khi gom theo 4 mùa, mùa {stats['season_max'][0]} có mức chi cao nhất ({stats['season_max'][1]} triệu VNĐ), "
        f"còn mùa {stats['season_min'][0]} thấp nhất ({stats['season_min'][1]} triệu VNĐ). Việc chia theo mùa giúp dễ "
        "nhận ra giai đoạn nào trong năm hay tốn kém nhất để chuẩn bị tiền dự phòng trước."
    )

    add_h3(doc, "2.4.11. So sánh với Tài khoản Sinh viên UTH (6 tháng 06 - 11/2026)")
    add_p(
        doc,
        "Nhóm tiếp tục mở tài khoản dữ liệu sạch 6 tháng của sinh viên UTH (151 giao dịch) để đặt cạnh dữ liệu Kaggle "
        "xem cơ cấu chi tiêu của sinh viên khác hộ gia đình đi làm ở điểm nào."
    )
    add_figure(doc, "bieu_do_phan_tich_data.png", "Hình 14. So sánh tỷ trọng chi tiêu giữa tài khoản SV UTH và dữ liệu thật Kaggle.")
    add_styled_table(
        doc,
        ["Tháng (SV UTH)", "Số GD", "Tổng thu (VNĐ)", "Tổng chi (VNĐ)", "Tiết kiệm (VNĐ)", "Tỷ lệ tiết kiệm"],
        [
            [m, str(cnt), f"{inc:,}", f"{exp:,}", f"{inc-exp:,}", f"{(inc-exp)/inc*100:.1f}%" if inc else "0%"]
            for m, cnt, inc, exp in monthly_uth
        ],
        col_widths=[3.2, 1.6, 3.1, 3.1, 2.9, 2.1],
    )
    add_figure(doc, "bieu_do_xu_huong_thang.png", "Hình 15. Biểu đồ thu nhập, chi tiêu và tiết kiệm 6 tháng của sinh viên UTH.")
    add_p(
        doc,
        "Kết quả so sánh cho thấy sự khác biệt rất rõ. Với sinh viên UTH ở trọ, riêng Tiền trọ (49,2%) và Ăn uống "
        "(25,9%) đã chiếm 75,1% tổng chi tiêu hằng tháng. Các khoản còn lại như Đi lại (7,9%), Khác (7,3%), Học tập "
        "(5,2%) và Giải trí (4,5%) chiếm tỷ trọng nhỏ hơn nhiều. Riêng tháng 09/2026 tiền tiết kiệm tăng lên 3,86 triệu "
        "nhờ nhận thêm học bổng khuyến khích học tập 2,5 triệu VNĐ."
    )
    doc.add_page_break()

    # =========================================================================
    # CHƯƠNG 3: THIẾT KẾ, CÀI ĐẶT ỨNG DỤNG VÀ KIỂM THỬ ĐÁNH GIÁ
    # =========================================================================
    add_h1(doc, "CHƯƠNG 3: THIẾT KẾ, CÀI ĐẶT ỨNG DỤNG VÀ KIỂM THỬ ĐÁNH GIÁ (MỤC 4.2 - 4.4)")

    add_h2(doc, "3.1. Sơ đồ luồng xử lý, cấu trúc thư mục và thiết kế OOP (Mục 4.2)")
    add_p(
        doc,
        "Chương trình được chia thành 5 tầng xử lý từ lúc nhận dữ liệu đầu vào cho đến lúc xuất biểu đồ và báo cáo. "
        "Nhóm áp dụng lập trình hướng đối tượng (OOP) bằng các lớp dataclass (Transaction, BudgetStatus, AccountInfo, "
        "CleaningResult) kết hợp các lớp quản lý cơ sở dữ liệu (ExpenseStore, ExtensionsStore, ExpenseBackend)."
    )
    add_figure(doc, "so_do_luong_xu_ly.png", "Hình 16. Sơ đồ chức năng và luồng xử lý của ứng dụng THU CHI UTH.")

    add_code_block(
        doc,
        """quan-ly-chi-tieu-sinh-vien/
├── app.py / main.py              # Khởi chạy Streamlit và chọn chế độ (--demo, --db, --api)
├── MO_WEB_THU_CHI_UTH.bat        # File mở nhanh web THU CHI UTH trên Windows
├── RUN.bat / DEMO.bat            # File chạy nhanh 2 phiên bản giao diện
├── requirements.txt              # Danh sách thư viện Python cần cài đặt
├── expense_tracker/              # Gói chính của web THU CHI UTH
│   ├── storage.py                # OOP: Transaction, BudgetStatus, ExpenseStore (SQLite + CHECK)
│   ├── accounts.py               # Quản lý đa tài khoản (.db riêng + .active_account.json)
│   ├── ai_data_cleaner.py        # Làm sạch file CSV/Excel/Văn bản thô bằng AI + Pandas
│   ├── ai_service.py             # Kết nối Gemini/OpenAI, đọc số tiền tiếng Việt & tư vấn
│   ├── ocr_pipeline.py           # Tiền xử lý ảnh OpenCV + Tesseract OCR + Pydantic
│   ├── extensions_db.py          # CSDL mở rộng (*_extensions.db) cho từng tài khoản
│   ├── charts.py / reports_backup.py / ui.py / utils.py
├── unispend_3d/                  # Giao diện THU CHI UTH (bản 3D) và FastAPI
├── scripts/                      # Script xử lý dữ liệu và tạo báo cáo
├── data/                         # Chứa các file SQLite, CSV, Excel (THU_CHI_UTH_*)
└── tests/                        # Bộ 71 ca kiểm thử tự động (unittest + AppTest)""",
        title="Cấu trúc thư mục chương trình:",
    )

    add_styled_table(
        doc,
        ["Module", "Lớp / Hàm chính", "Nhiệm vụ"],
        [
            ["expense_tracker/storage.py", "Transaction, BudgetStatus, ExpenseStore", "Quản lý thêm/sửa/xóa/lọc giao dịch SQLite, tính tổng tháng và cảnh báo ngân sách."],
            ["expense_tracker/accounts.py", "AccountInfo, list_accounts(), create_account(), save_active_account()", "Tách mỗi file .db thành một tài khoản riêng và nhớ tài khoản đang mở khi chuyển tab."],
            ["expense_tracker/ai_data_cleaner.py", "CleaningResult, clean_tabular_file(), clean_raw_text()", "Đọc file CSV/Excel thô hoặc văn bản, nhờ AI ánh xạ danh mục rồi dùng Pandas làm sạch."],
            ["expense_tracker/ai_service.py & ocr_pipeline.py", "parse_vietnamese_voice_expense(), analyze_receipt_image_with_gemini()", "Tách số tiền tiếng Việt (45k, 1tr5...) và nhận diện thông tin trên ảnh hóa đơn."],
            ["expense_tracker/reports_backup.py", "export_excel_bytes(), export_pdf_bytes(), restore_sqlite_backup()", "Xuất file Excel, PDF tiếng Việt Unicode và sao lưu/khôi phục SQLite an toàn."],
            ["unispend_3d/ (models, backend, app)", "Transaction, BudgetConfig, ExpenseBackend", "Đóng gói nghiệp vụ OOP và chạy giao diện bản 3D kèm REST API."],
        ],
        col_widths=[4.0, 4.8, 7.2],
    )

    add_h2(doc, "3.2. Cài đặt kiểm tra lỗi, chú thích mã nguồn và cách chạy (Mục 4.3)")
    add_p(
        doc,
        "Mọi dữ liệu nhập vào đều được kiểm tra lỗi ở cả hai lớp: hàm kiểm tra trong Python và ràng buộc CHECK "
        "trong bảng SQLite. Các câu lệnh SQL đều dùng tham số (?) để tránh lỗi SQL Injection, còn ghi chú khi xuất "
        "CSV/Excel sẽ tự chặn các ký tự công thức (=, +, -, @). Dưới đây là đoạn mã có chú thích trích từ storage.py:"
    )
    add_code_block(
        doc,
        """# Trích expense_tracker/storage.py - Kiểm tra dữ liệu đầu vào trước khi ghi SQLite
def _transaction_values(date: str, kind: str, category: str, amount: int, note: str):
    _date(date)  # Kiểm tra đúng định dạng YYYY-MM-DD và ngày có thật trên lịch
    if kind not in TYPE_LABELS:
        raise ValueError("Loại giao dịch không hợp lệ.")
    categories = EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES
    if category not in categories:
        raise ValueError("Danh mục không phù hợp với loại giao dịch.")
    _amount(amount)  # Chỉ nhận số nguyên dương VNĐ để tránh sai số float
    note = note.strip()
    if len(note) > 200:
        raise ValueError("Ghi chú không được dài quá 200 ký tự.")
    return date, kind, category, amount, note""",
        title="Đoạn mã kiểm tra lỗi đầu vào (có chú thích trong storage.py):",
    )
    add_code_block(
        doc,
        """# Hướng dẫn cài đặt và chạy chương trình trên máy tính cá nhân
cd "quan-ly-chi-tieu-sinh-vien"
python -m venv .venv
.\\.venv\\Scripts\\activate
pip install -r requirements.txt

# Chạy ứng dụng (hoặc nhấp đúp MO_WEB_THU_CHI_UTH.bat)
python main.py --demo
# Chạy toàn bộ 71 ca kiểm thử tự động
python -m unittest discover -s tests -t .""",
        title="Các lệnh cài đặt và chạy thử:",
    )

    add_h2(doc, "3.3. Kiểm thử chương trình (71 ca kiểm thử tự động) (Mục 4.4)")
    add_p(
        doc,
        "Nhóm chạy kiểm thử tự động bằng unittest và Streamlit AppTest cho toàn bộ các chức năng chính. Kết quả "
        "ghi nhận 71/71 ca kiểm thử đều PASS, không có lỗi phát sinh."
    )
    add_styled_table(
        doc,
        ["Mã TC", "Nội dung kiểm thử", "Dữ liệu thử", "Kết quả thực tế", "Kết luận"],
        [
            ["TC-01", "Thêm/sửa/xóa giao dịch", "2026-11-10, expense, Ăn uống, 45000", "Lưu và cập nhật đúng trong SQLite.", "PASS"],
            ["TC-02", "Nhập tiền <= 0 hoặc ngày sai", "amount = 0; date = '2026-02-30'", "Báo lỗi tiếng Việt, không ghi vào DB.", "PASS"],
            ["TC-03", "Nhập sai danh mục theo loại", "kind='income', category='Tiền trọ'", "Bị chặn ở cả Python và SQLite CHECK.", "PASS"],
            ["TC-04", "Chặn công thức Excel", "note = '=SUM(A1:A5)'", "Tự xử lý an toàn khi xuất CSV/Excel.", "PASS"],
            ["TC-05", "Đổi tài khoản & chuyển tab", "Đổi sang Kaggle rồi mở Lịch, Thống kê", "Giữ đúng file .db và tự nhảy về tháng 2018-09.", "PASS"],
            ["TC-06", "AI làm sạch file thô Kaggle", "THU_CHI_UTH_Du_Lieu_Tho_Kaggle.csv (2.461 dòng)", "Tự nhận diện INR, ra 2.298 dòng sạch PASS CHECK.", "PASS"],
            ["TC-07", "AI tách văn bản thu chi thô", "3 dòng ghi chú (4.5tr, 2tr2, 40k, 70 nghìn)", "Tách đúng 4 giao dịch chuẩn VNĐ.", "PASS"],
            ["TC-08", "Chạy toàn bộ bộ test", "python -m unittest discover -s tests -t .", "71/71 ca kiểm thử đều đạt.", "PASS"],
        ],
        col_widths=[1.4, 3.8, 4.4, 4.8, 1.6],
    )

    add_h2(doc, "3.4. Đánh giá kết quả, ưu điểm, hạn chế và hướng phát triển (Mục 4.4)")
    add_styled_table(
        doc,
        ["Nội dung đánh giá", "Nhận xét thực tế của nhóm"],
        [
            ["Chương trình có chạy đúng chức năng không?", "Đạt. Các chức năng thêm/sửa/xóa, Lịch tài chính, Biểu đồ, Cảnh báo ngân sách, Đa tài khoản .db, AI làm sạch dữ liệu và Xuất Excel/PDF đều chạy ổn định (71/71 test PASS)."],
            ["Kết quả đầu ra có phù hợp yêu cầu không?", "Phù hợp. File thô 2.461 dòng được lọc sạch còn 2.298 dòng; các biểu đồ và bảng số liệu cho thấy rõ tỷ trọng chi tiêu từng nhóm để dễ điều chỉnh ngân sách."],
            ["Giao diện và cách dùng có rõ ràng không?", "Rõ ràng. Giao diện hoàn toàn bằng tiếng Việt, có chế độ sáng/tối, thanh trên cùng báo rõ đang mở tài khoản nào kèm 2 nút đổi tài khoản và làm sạch dữ liệu bằng AI."],
        ],
        col_widths=[5.2, 10.8],
    )
    add_bullet(doc, "Ưu điểm: Ứng dụng xử lý được từ khâu làm sạch file thô đến lưu SQLite tách từng tài khoản và vẽ biểu đồ trực quan; mã nguồn chia module dễ đọc; vẫn chạy bình thường khi không có API key nhờ cơ chế dự phòng offline.")
    add_bullet(doc, "Hạn chế: Dữ liệu lưu cục bộ trong máy cá nhân nên chưa tự đồng bộ qua mạng giữa điện thoại và laptop; phần quét hóa đơn OCR còn phụ thuộc ánh sáng và độ rõ của ảnh chụp; chưa có màn hình đăng nhập mật khẩu.")
    add_bullet(doc, "Hướng phát triển: Nhóm dự kiến bổ sung mô hình dự đoán chi tiêu tháng tiếp theo bằng scikit-learn, hỗ trợ đồng bộ dữ liệu lên đám mây có đăng nhập tài khoản, và tự đọc thông báo biến động số dư ngân hàng.")
    doc.add_page_break()

    # =========================================================================
    # CHƯƠNG 4: GIAO DIỆN WEB VÀ MÔ TẢ CHI TIẾT CÁC CHỨC NĂNG (10 MÀN HÌNH)
    # =========================================================================
    add_h1(doc, "CHƯƠNG 4: GIAO DIỆN WEB VÀ MÔ TẢ CHI TIẾT CÁC CHỨC NĂNG CỦA ỨNG DỤNG")
    add_p(
        doc,
        "Chương này trình bày toàn bộ giao diện web thực tế của ứng dụng sau khi khởi chạy trên máy tính cá nhân "
        "cùng mô tả chi tiết công dụng và cách thao tác của từng màn hình chức năng."
    )

    add_h2(doc, "4.1. Màn hình Tổng quan tài chính và Lịch tài chính theo ngày")
    add_figure(doc, "ui_01_tong_quan_lich.jpg", "Hình 17. Giao diện chính Tổng quan tài chính và Lịch tài chính theo ngày.")
    add_p(
        doc,
        "Đây là màn hình trung tâm khi người dùng mở ứng dụng. Bố cục được chia thành các khu vực trực quan giúp "
        "sinh viên nắm bắt toàn bộ tình hình thu chi trong tháng chỉ trong một ánh nhìn:"
    )
    add_bullet(doc, "Thanh điều hướng bên trái (Sidebar): Gồm 7 mục chức năng chính (Lịch tài chính, Hóa đơn & Sổ nợ, Kho ảnh hóa đơn, Thống kê chi tiêu, AI Làm sạch dữ liệu, Quét hóa đơn AI, Nhập giọng nói, Cá nhân & Tài khoản), thẻ gợi ý nhanh từ Uni AI và nút chuyển đổi giao diện Sáng/Tối (Light/Dark Mode).")
    add_bullet(doc, "Thanh tiêu đề & Thanh trạng thái Tài khoản trên cùng: Cho phép chuyển nhanh qua lại giữa các tháng, bấm về 'Hôm nay', mở nhanh 'Quét hóa đơn' hoặc 'Giọng nói'. Ngay bên dưới là thanh trạng thái hiển thị rõ file cơ sở dữ liệu (.db) nào đang mở, tổng số giao dịch và 2 nút thao tác nhanh 'Đổi / Tạo tài khoản' cùng 'AI Làm sạch dữ liệu thô'.")
    add_bullet(doc, "Dải 4 thẻ chỉ số KPI: Hiển thị Số dư khả dụng hiện tại, Tổng thu nhập trong tháng, Tổng chi tiêu (kèm số giao dịch đã ghi) và số tiền Có thể chi hôm nay (tự động báo đỏ khi đã vượt định mức ngân sách).")
    add_bullet(doc, "Lưới Lịch tài chính & Cột thông tin bên phải: Mỗi ô ngày trên lịch hiển thị trực tiếp tổng tiền đã chi trong ngày đó (ví dụ -456k, -161k, -754k) và đổi màu theo mức độ chi tiêu. Cột bên phải hiển thị lời nhắc từ AI, chi tiết các khoản thu chi của ngày đang chọn và danh sách giao dịch gần đây.")

    add_h2(doc, "4.2. Màn hình Theo dõi 3 khoản chi thiết yếu của sinh viên và 4 tab nghiệp vụ")
    add_figure(doc, "ui_10_ba_khoan_thiet_yeu.png", "Hình 18. Khối theo dõi 3 khoản chi thiết yếu (Tiền ăn, Tiền trọ, Đi lại) và 4 tab quản lý bên dưới.")
    add_p(
        doc,
        "Do sinh viên ở trọ chủ yếu tốn tiền vào 3 nhóm cố định là Tiền ăn, Tiền trọ và Đi lại, nhóm thiết kế riêng "
        "khối 'Theo dõi 3 khoản chi thiết yếu' nằm ngay dưới lịch tài chính:"
    )
    add_bullet(doc, "Mỗi thẻ hiển thị số tiền đã tiêu, định mức ngân sách đã đặt, tỷ trọng phần trăm so với tổng chi cả tháng và thanh tiến độ màu đỏ khi vượt ngân sách (ví dụ Tiền ăn đã chi 2.965.000 đ / định mức 1.200.000 đ, vượt 1.765.000 đ; Tiền trọ chiếm 43,2% tổng chi; Đi lại vượt 485.500 đ).")
    add_bullet(doc, "Thanh 4 tab phía dưới (Tổng quan, Biểu đồ theo tháng, Cảnh báo & Ngân sách, Sổ giao dịch): Giúp người dùng chỉnh sửa nhanh định mức ngân sách hoặc sửa/xóa trực tiếp từng dòng giao dịch trong sổ.")

    add_h2(doc, "4.3. Màn hình Quản lý đa tài khoản dữ liệu (Mỗi file .db là 1 tài khoản riêng)")
    add_figure(doc, "ui_02_quan_ly_tai_khoan.png", "Hình 19. Giao diện Quản lý đa tài khoản dữ liệu SQLite (.db).")
    add_p(
        doc,
        "Để mỗi bộ dữ liệu hoặc mỗi sinh viên có một không gian thu chi riêng biệt, mục 'Tài khoản dữ liệu' trong "
        "trang Cá nhân & Tài khoản cung cấp đầy đủ các thao tác quản lý file SQLite (.db):"
    )
    add_bullet(doc, "Chuyển sang tài khoản khác: Hộp chọn liệt kê toàn bộ các file .db hiện có kèm số lượng giao dịch (ví dụ Tài khoản Demo, Tài khoản Sinh viên UTH 6 tháng, Tài khoản Dữ liệu thật Kaggle 2.298 giao dịch). Khi chọn tài khoản nào, toàn bộ Lịch, Thống kê và Hóa đơn sẽ tự động tải đúng dữ liệu của file .db đó.")
    add_bullet(doc, "Tab Tạo tài khoản mới: Nhập tên tài khoản (ví dụ 'Nguyễn Văn A - HK1', 'Quỹ CLB UTH'), tùy chọn tích nạp sẵn dữ liệu mẫu 6 tháng rồi bấm 'Tạo tài khoản (.db riêng)' để sinh một file SQLite mới hoàn toàn.")
    add_bullet(doc, "Tab Đổi tên / Xóa và Tab Nhập file .db thành tài khoản: Cho phép đổi tên hiển thị, xóa các tài khoản tự tạo không còn dùng, hoặc tải một file .db có sẵn từ máy tính lên để biến thành một tài khoản mới trên web.")

    add_h2(doc, "4.4. Màn hình AI Làm sạch và Chuẩn hóa dữ liệu thô")
    add_figure(doc, "ui_05_ai_lam_sach_du_lieu.png", "Hình 20. Giao diện AI Làm sạch và Chuẩn hóa dữ liệu thô (CSV, Excel, Văn bản).")
    add_p(
        doc,
        "Đây là chức năng giúp người dùng đưa dữ liệu thô từ bên ngoài vào hệ thống mà không sợ lỗi định dạng:"
    )
    add_bullet(doc, "Hỗ trợ 2 chế độ nguồn dữ liệu: 'Tải file CSV / Excel thô' (nhận file .csv, .xlsx, .xls tối đa 200MB từ Kaggle, sao kê ngân hàng, khảo sát...) hoặc 'Dán văn bản / ghi chú thô' (dán trực tiếp nhiều dòng ghi chú chi tiêu tự do).")
    add_bullet(doc, "Tùy chọn bật AI (Gemini / OpenAI) để tự động nhận diện tên cột, ánh xạ các nhãn danh mục tiếng Anh/Việt lộn xộn về đúng 6 danh mục chi và 4 danh mục thu của web, đồng thời chọn đơn vị tiền tệ gốc (Tự động, VND, INR, USD, EUR) để quy đổi về số nguyên VNĐ.")
    add_bullet(doc, "Sau khi bấm 'AI Phân tích & Làm sạch file', hệ thống tự động lọc bỏ dòng trùng lặp, loại bỏ giao dịch chuyển khoản nội bộ (Transfer-Out), bù ghi chú bị trống, hiện bảng xem trước và cho phép lưu 1 chạm thành một tài khoản .db độc lập mới.")

    add_h2(doc, "4.5. Màn hình Thống kê chi tiêu, Cảnh báo ngân sách và Xuất báo cáo Excel/PDF")
    add_figure(doc, "ui_03_thong_ke_canh_bao.jpg", "Hình 21. Giao diện Thống kê chi tiêu, Cảnh báo vượt định mức và Xuất báo cáo Excel/PDF.")
    add_p(
        doc,
        "Màn hình Thống kê chi tiêu tổng hợp toàn bộ sức khỏe tài chính của tháng đang xem và hỗ trợ xuất file báo cáo:"
    )
    add_bullet(doc, "Hiển thị 4 thẻ tổng hợp kèm biểu đồ đường thu nhỏ (sparkline) cho biết xu hướng tăng/giảm của số dư, thu nhập, chi tiêu và tỷ lệ phần trăm so với hạn mức.")
    add_bullet(doc, "Khối cảnh báo đỏ tự động liệt kê chính xác từng hạng mục bị lố ngân sách và số tiền vượt cụ thể (ví dụ Tổng chi tiêu vượt định mức 6.206.500 đ; Ăn uống vượt 1.765.000 đ; Đi lại vượt 485.500 đ).")
    add_bullet(doc, "Bộ lọc chế độ xem ('Tháng này' hoặc 'Xu hướng' nhiều tháng) và 2 nút lớn 'Xuất Excel' (.xlsx nhiều sheet) cùng 'Xuất PDF' (.pdf định dạng A4 có dấu tiếng Việt) để tải ngay báo cáo về máy.")

    add_h2(doc, "4.6. Màn hình Phân tích tỷ trọng hạng mục chi tiêu")
    add_figure(doc, "ui_04_ty_trong_hang_muc.png", "Hình 22. Giao diện Tỷ trọng hạng mục chi tiêu kèm thanh tìm kiếm nhanh.")
    add_p(
        doc,
        "Ngay bên dưới phần thống kê tổng quan là bảng phân rã chi tiết tỷ trọng từng hạng mục chi tiêu trong tháng:"
    )
    add_bullet(doc, "Có ô 'Tìm kiếm hạng mục...' để lọc nhanh nhóm chi tiêu cần xem.")
    add_bullet(doc, "Mỗi hạng mục (Ăn uống, Nhà cửa, Di chuyển, Mua sắm, Giải trí, Học tập, Sức khỏe, Khác) đi kèm biểu tượng màu riêng, thanh tỷ lệ trực quan, tổng số tiền đã chi và phần trăm đóng góp trong tổng chi tiêu (ví dụ Nhà cửa 4.543.000 đ chiếm 43,2%; Ăn uống 2.965.000 đ chiếm 28,2%; Học tập 1.159.000 đ chiếm 11,0%).")

    add_h2(doc, "4.7. Màn hình Hóa đơn định kỳ, Sổ nợ và Kho ảnh hóa đơn lưu trữ")
    add_figure(doc, "ui_09_kho_anh_hoa_don.jpg", "Hình 23. Giao diện Hóa đơn và Kho lưu trữ ảnh hóa đơn (51 hóa đơn).")
    add_p(
        doc,
        "Màn hình Hóa đơn & Kho ảnh được chia làm 3 phân mục (Định kỳ, Sổ nợ, Kho ảnh) giúp sinh viên quản lý các "
        "khoản phải đóng hằng tháng cũng như lưu giữ bằng chứng thanh toán:"
    )
    add_bullet(doc, "Thống kê tổng số ảnh hóa đơn đã lưu trong tài khoản (51 hóa đơn) và tổng giá trị tiền tương ứng (6.291.500 đ).")
    add_bullet(doc, "Cho phép lọc hóa đơn theo phạm vi, theo danh mục (Đi lại, Học tập, Ăn uống...) hoặc tìm nhanh theo tên quán, món hàng, ngày mua.")
    add_bullet(doc, "Mỗi thẻ hóa đơn hiển thị tên cửa hàng (ví dụ XE KHÁCH PHƯƠNG TRANG -180.000 đ, PHOTOCOPY SINH VIÊN D3 -28.000 đ), ngày giờ, phương thức thanh toán (Chuyển khoản QR, Tiền mặt), ảnh chụp hóa đơn thu nhỏ và các nút 'Tải' ảnh về máy, 'Xóa' hoặc 'Xem chi tiết & ảnh lớn'.")

    add_h2(doc, "4.8. Màn hình Quét hóa đơn AI (Tesseract OCR 5.5 + OpenCV + Gemini Vision)")
    add_figure(doc, "ui_06_quet_hoa_don_ocr.jpg", "Hình 24. Giao diện Quét hóa đơn AI kết hợp tiền xử lý ảnh OpenCV, Tesseract OCR và Gemini.")
    add_p(
        doc,
        "Thay vì phải gõ tay từng món hàng sau khi đi siêu thị hoặc ăn uống, người dùng mở mục Quét Hóa Đơn AI:"
    )
    add_bullet(doc, "Thanh trạng thái báo rõ tình trạng kết nối của Cổng AI API (GEMINI gemini-3.5-flash-lite) và bộ đọc Tesseract OCR cục bộ (phiên bản 5.5.0 hỗ trợ tiếng Việt vie+eng), có sẵn 2 nút kiểm tra kết nối trực tiếp.")
    add_bullet(doc, "Hỗ trợ 3 nguồn đầu vào: Tải ảnh hóa đơn (JPG/PNG), Chụp ảnh trực tiếp bằng Camera, hoặc dùng Văn bản OCR thủ công / Hóa đơn mẫu.")
    add_bullet(doc, "Tích hợp bước tiền xử lý ảnh bằng OpenCV (chuyển ảnh xám Grayscale, khử nhiễu và cân bằng độ tương phản CLAHE) cùng tùy chọn xoay ảnh tự động theo EXIF giúp đọc rõ cả hóa đơn chụp thiếu sáng.")
    add_bullet(doc, "Cung cấp 3 chế độ bảo mật linh hoạt: (1) Kết hợp Gemini Vision và đối chiếu Tesseract OCR; (2) Chỉ chạy Tesseract OCR trên máy rồi gửi văn bản cho Gemini phân tích JSON; hoặc (3) Chỉ xử lý OCR cục bộ 100% trên máy tính mà không gửi dữ liệu ra ngoài.")

    add_h2(doc, "4.9. Màn hình Nhập chi tiêu bằng giọng nói tiếng Việt tự nhiên")
    add_figure(doc, "ui_07_nhap_giong_noi.png", "Hình 25. Giao diện Nhập chi tiêu nhanh bằng giọng nói tiếng Việt.")
    add_p(
        doc,
        "Chức năng Nhập bằng giọng nói giúp ghi nhanh khoản chi chỉ bằng một câu nói tự nhiên bằng tiếng Việt:"
    )
    add_bullet(doc, "Người dùng bấm nút Micro màu xanh để thu âm trực tiếp trên trình duyệt, hoặc chạm chọn nhanh các câu mẫu ('Ăn trưa phở bò 45k', 'Đổ xăng 70 ngàn'), hoặc gõ câu nói tự nhiên vào ô văn bản.")
    add_bullet(doc, "Khi bấm 'Phân tích câu nói', bộ xử lý ngôn ngữ tự nhiên tiếng Việt (kết hợp AI và tập luật số tiền Việt trong ai_service.py) tự động hiểu các cách nói thông dụng của sinh viên như '45k', '70 ngàn', 'năm chục', 'hai xị rưỡi', '1tr5' để tách ra đúng số tiền nguyên VNĐ, ngày giao dịch, loại thu/chi và tự xếp vào danh mục phù hợp.")

    add_h2(doc, "4.10. Màn hình Tìm kiếm giao dịch và Trợ lý AI Phân tích chi tiêu")
    add_figure(doc, "ui_08_tro_ly_ai_phan_tich.png", "Hình 26. Giao diện Tìm kiếm giao dịch và Trợ lý AI Phân tích chi tiêu.")
    add_p(
        doc,
        "Trong trang Cá nhân, người dùng có thể tra cứu lại lịch sử và trò chuyện trực tiếp với Trợ lý AI tài chính:"
    )
    add_bullet(doc, "Ô Tìm kiếm giao dịch: Cho phép gõ bất kỳ từ khóa ghi chú hoặc tên danh mục nào (ví dụ 'cà phê', 'xăng', 'trọ') để lọc tức thời các khoản thu chi liên quan.")
    add_bullet(doc, "Khối Trợ lý AI Phân tích Chi Tiêu: Tự động đọc số liệu thật từ SQLite của tháng đang mở để tóm tắt nhanh (Tổng thu, Tổng chi, Số dư, danh mục chi nhiều nhất như Tiền trọ chiếm 43,2%, và dự báo tổng chi cuối tháng dựa trên tốc độ chi tiêu hiện tại).")
    add_bullet(doc, "Hỗ trợ 4 nút câu hỏi nhanh 1 chạm ('Tháng này tôi tiêu bao nhiêu?', 'Tôi tiêu nhiều nhất vào danh mục nào?', 'Tháng này tôi đã vượt ngân sách chưa?', 'Tôi nên tiết kiệm bao nhiêu?'), ô đặt câu hỏi tự do bằng tiếng Việt để bấm 'Hỏi AI Assistant', cùng nút 'Kế hoạch tiết kiệm 3 bước' để AI đề xuất phương án cắt giảm chi tiêu cụ thể.")

    add_h2(doc, "4.11. Khung Quick Add — Ghi nhanh giao dịch theo ngày trên Lịch")
    add_figure(doc, "ui_14_quick_add_ghi_nhanh.png", "Hình 27. Khung Quick Add giúp ghi nhanh khoản thu/chi ngay tại ngày đang chọn trên lịch.")
    add_p(
        doc,
        "Khi người dùng bấm vào bất kỳ ngày nào trên Lịch tài chính (ví dụ ngày 21/11/2026), khung 'Quick Add — Ghi "
        "nhanh' nằm ngay bên dưới lịch cho phép thêm khoản thu chi mới mà không cần mở sang trang khác:"
    )
    add_bullet(doc, "Chọn loại giao dịch (Chi tiêu hoặc Thu nhập), chọn Danh mục (Tiền ăn, Tiền trọ, Đi lại...) và chọn loại Ví thanh toán (Ví tiền mặt, Chuyển khoản...).")
    add_bullet(doc, "Ô Số tiền (VNĐ) hỗ trợ nút cộng/trừ tăng giảm nhanh theo bội số tiền Việt, đi kèm ô Ghi chú ngắn gọn và nút '+ Lưu giao dịch (21/11/2026)' để ghi thẳng vào ngày vừa chọn trên lịch.")

    add_h2(doc, "4.12. Hộp Chi tiêu an toàn mỗi ngày và Báo cáo cảnh báo vượt định mức")
    add_figure(doc, "ui_13_chi_tieu_an_toan_canh_bao.png", "Hình 28. Hộp Chi tiêu an toàn mỗi ngày và Báo cáo cảnh báo vượt định mức chi tiết.")
    add_p(
        doc,
        "Để sinh viên biết mỗi ngày còn được phép tiêu tối đa bao nhiêu tiền mà không bị lố ngân sách tháng, ứng dụng "
        "tính toán tự động chỉ số 'Chi tiêu an toàn' và hiển thị hộp cảnh báo nổi bật:"
    )
    add_bullet(doc, "Khi tổng chi trong tháng vẫn nằm dưới định mức, hệ thống lấy phần ngân sách còn lại chia đều cho số ngày còn lại của tháng để ra số tiền an toàn được tiêu mỗi ngày.")
    add_bullet(doc, "Khi tổng chi đã vượt định mức (như trên hình: đã chi 10.506.500 đ so với định mức 4.300.000 đ, tức 244,3%), chỉ số Chi tiêu an toàn tự động hạ về 0 đ/ngày kèm nhãn đỏ 'Vượt định mức (+144.3%)'.")
    add_bullet(doc, "Khung 'BÁO CÁO CẢNH BÁO VƯỢT ĐỊNH MỨC' liệt kê rõ từng khoản bị lố (Tổng ngân sách vượt 6.206.500 đ; Tiền ăn vượt 1.765.000 đ - 247% định mức; Đi lại vượt 485.500 đ - 221% định mức) và cung cấp 2 nút tắt 'Xem báo cáo chi tiết' hoặc 'Điều chỉnh hạn mức' ngay tại chỗ.")

    add_h2(doc, "4.13. Khung Xem trước báo cáo Excel 3 Sheet trực tiếp trên trình duyệt")
    add_figure(doc, "ui_12_xem_truoc_excel_web.png", "Hình 29. Khung Xem trước báo cáo Excel (3 Sheet) ngay trên giao diện Web.")
    add_p(
        doc,
        "Trước khi bấm tải file Excel về máy, người dùng có thể mở mục 'Xem trước báo cáo Excel' ngay trên web để "
        "kiểm tra toàn bộ nội dung của cả 3 trang tính (Sheet):"
    )
    add_bullet(doc, "Hỗ trợ chuyển đổi tức thời giữa 3 nút: 'Sheet 1: Tổng quan', 'Sheet 2: Theo danh mục' và 'Sheet 3: Chi tiết giao dịch'.")
    add_bullet(doc, "Bảng xem trước hiển thị đầy đủ các cột Ngày, Loại, Danh mục, Số tiền (VNĐ) đã định dạng dấu chấm phân cách hàng nghìn và Ghi chú chi tiết (ví dụ XE KHÁCH PHƯƠNG TRANG 180.000 đ, PHOTOCOPY SINH VIÊN D3 28.000 đ, GS25 - VÕ OANH UTH 45.000 đ, SHOP THỜI TRANG YAME BÌNH THẠNH 191.000 đ...).")

    add_h2(doc, "4.14. Tệp Báo cáo tài chính Excel (.xlsx) thực tế khi mở trên Microsoft Excel")
    add_figure(doc, "ui_11_file_excel_xuat_ra.png", "Hình 30. Tệp Báo cáo tài chính (.xlsx) mở thực tế trên phần mềm Microsoft Excel.")
    add_p(
        doc,
        "Khi bấm nút 'Xuất Excel', module reports_backup.py (dùng thư viện openpyxl) tự động sinh ra file .xlsx được "
        "định dạng sẵn phông chữ, màu nền tiêu đề xanh đậm, đường viền ô và định dạng số tiền chuẩn kế toán:"
    )
    add_bullet(doc, "Khối Chỉ số tổng hợp (từ dòng 4 đến dòng 14): Tổng hợp đầy đủ Tổng thu nhập (6.000.000), Tổng chi tiêu (10.506.500), Chênh lệch thu chi (-4.506.500), Tổng số giao dịch (68), Kỳ báo cáo, Trung bình chi mỗi ngày (350.217 đ), Ngày chi tiêu cao nhất (01/11/2026 - 4.311.000 đ), Danh mục chi nhiều nhất (Nhà cửa - 4,5 tr), So với tháng trước (+146,1%) và Tỷ lệ sử dụng ngân sách (244,3%).")
    add_bullet(doc, "Khối Danh mục chi tiêu (từ dòng 16 trở đi): Thống kê từng danh mục (Ăn uống, Tiền trọ, Đi lại, Học tập, Giải trí, Khác) với 4 cột số liệu rõ ràng gồm Đã chi (VNĐ), Định mức (VNĐ), Còn lại (VNĐ) và Tỷ lệ sử dụng (%). Sinh viên có thể dùng trực tiếp file Excel này để lưu trữ cá nhân hoặc đính kèm báo cáo.")
    doc.add_page_break()

    # =========================================================================
    # KẾT LUẬN & TÀI LIỆU THAM KHẢO
    # =========================================================================
    add_h1(doc, "KẾT LUẬN")
    add_p(
        doc,
        "Qua bài tập lớn học phần Ngôn ngữ lập trình Python, nhóm đã xây dựng hoàn chỉnh ứng dụng THU CHI UTH "
        "từ bước khám phá và làm sạch dữ liệu thật đến đóng gói giao diện web đa tài khoản SQLite. Chương trình "
        "chạy ổn định trên máy tính cá nhân, vượt qua 71 ca kiểm thử tự động và có thể áp dụng ngay để sinh viên "
        "UTH theo dõi chi tiêu hằng ngày."
    )

    add_h1(doc, "TÀI LIỆU THAM KHẢO")
    add_bullet(doc, "Tài liệu chính thức Python 3.13, sqlite3 và unittest: https://docs.python.org/3/")
    add_bullet(doc, "Tài liệu thư viện Pandas và Matplotlib: https://pandas.pydata.org/ | https://matplotlib.org/")
    add_bullet(doc, "Tài liệu Streamlit và AppTest: https://docs.streamlit.io/")
    add_bullet(doc, "Tài liệu Google Gemini API (google-genai): https://ai.google.dev/gemini-api/docs")
    add_bullet(doc, "Bộ dữ liệu Daily Household Transactions (Prasad Patil - Kaggle / GitHub): https://github.com/Mahesh1827/Daily_Transactions")

    OUT_DOCX.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUT_DOCX))
    return OUT_DOCX


if __name__ == "__main__":
    out = build_report()
    print("NATURAL_DOCX_CREATED:", out)
