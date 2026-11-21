"""Sinh bộ 50 ảnh hóa đơn (bill) sinh viên Việt Nam chân thực để test OCR & Demo UniSpend 2.0.

Chạy:
    .venv/Scripts/python.exe scripts/generate_50_student_bills.py

Xuất ra thư mục: demo_bills_50/
- 50 ảnh hóa đơn nhiệt .jpg (bill_01_*.jpg .. bill_50_*.jpg) hỗ trợ tiếng Việt có dấu rõ nét
- danh_sach_50_bill.csv (bảng đối chiếu chuẩn: ngày, cửa hàng, danh mục, tổng tiền)
"""

from __future__ import annotations

import csv
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "demo_bills_50"

# 50 hóa đơn sinh viên UTH / TP.HCM đa dạng 6 danh mục chi tiêu
BILLS_DATA: list[dict] = [
    # --- Ăn uống (20 bill) ---
    {"slug": "com_tam_suon", "store": "CƠM TẤM SÀI GÒN 24H", "addr": "12 Võ Oanh, Bình Thạnh, TP.HCM", "date": "2026-11-01", "time": "11:45", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Cơm tấm sườn bì chả", 1, 38000), ("Trà đá", 1, 3000), ("Canh rong biển", 1, 5000)]},
    {"slug": "pho_bo_tai_nam", "store": "PHỞ BÒ GIA TRUYỀN HÀ NỘI", "addr": "45 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-01", "time": "07:20", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Phở bò tái nạm", 1, 45000), ("Quẩy giòn", 1, 5000)]},
    {"slug": "highlands_coffee", "store": "HIGHLANDS COFFEE - D2", "addr": "102 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-02", "time": "14:10", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Phin Sữa Đá (M)", 1, 39000), ("Bánh Mousse Đào", 1, 35000)]},
    {"slug": "banh_mi_thit_nuong", "store": "BÁNH MÌ CHẢO & THỊT NƯỚNG", "addr": "08 Đường D5, Bình Thạnh", "date": "2026-11-02", "time": "07:05", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Bánh mì thịt nướng đặc biệt", 1, 22000), ("Sữa đậu nành nóng", 1, 10000)]},
    {"slug": "bun_bo_hue", "store": "BÚN BÒ HUẾ O XUÂN", "addr": "74 Ung Văn Khiêm, Bình Thạnh", "date": "2026-11-03", "time": "12:05", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Bún bò giò chả", 1, 42000), ("Khăn lạnh", 1, 2000), ("Trà tắc", 1, 8000)]},
    {"slug": "circle_k_an_dem", "store": "CIRCLE K - NGUYỄN GIA TRÍ", "addr": "55 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-03", "time": "22:15", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Mì trộn trứng ốp la", 1, 26000), ("Nước suối Aquafina 500ml", 1, 7000), ("Xúc xích nướng", 1, 16000)]},
    {"slug": "winmart_thuc_pham", "store": "WINMART+ BÌNH THẠNH", "addr": "88 Võ Oanh, P.25, Bình Thạnh", "date": "2026-11-04", "time": "17:30", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Trứng gà vỉ 10 quả", 1, 34000), ("Sữa tươi TH True Milk 1L", 1, 36000), ("Mì gói Hảo Hảo lốc 5", 1, 22000), ("Rau cải ngọt 300g", 1, 14000)]},
    {"slug": "tra_sua_phuc_long", "store": "PHÚC LONG COFFEE & TEA", "addr": "62 Điện Biên Phủ, Bình Thạnh", "date": "2026-11-04", "time": "15:20", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Trà sữa Phúc Long (L)", 1, 55000), ("Trân châu trắng", 1, 10000)]},
    {"slug": "com_ga_xoi_mo", "store": "CƠM GÀ XỐI MỠ SINH VIÊN", "addr": "19 Đường D3, Bình Thạnh", "date": "2026-11-05", "time": "11:50", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Cơm gà đùi xối mỡ", 1, 40000), ("Nước sâm lạnh", 1, 10000)]},
    {"slug": "bach_hoa_xanh", "store": "BÁCH HÓA XANH - UNG VĂN KHIÊM", "addr": "140 Ung Văn Khiêm, Bình Thạnh", "date": "2026-11-06", "time": "18:10", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Ức gà phi lê 500g", 1, 48000), ("Gạo ST25 túi 2kg", 1, 68000), ("Chuối sứ 1 nải", 1, 24000)]},
    {"slug": "bun_dau_mam_tom", "store": "BÚN ĐẬU MẮM TÔM PHỐ CỔ", "addr": "33 Đường D2, Bình Thạnh", "date": "2026-11-07", "time": "19:00", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Mẹt bún đậu tá lả", 1, 65000), ("Nước mơ đá", 1, 15000)]},
    {"slug": "ca_phe_muoi", "store": "CÀ PHÊ MUỐI CHÚ LONG", "addr": "21 Xô Viết Nghệ Tĩnh, Bình Thạnh", "date": "2026-11-08", "time": "08:15", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Cà phê muối đậm vị", 1, 25000)]},
    {"slug": "mi_cay_sasin", "store": "MÌ CAY SASIN - BÌNH THẠNH", "addr": "91 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-09", "time": "18:45", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Mì kim chi bò Mỹ cấp 2", 1, 59000), ("Trà đào cam sả", 1, 25000)]},
    {"slug": "hu_tieu_nam_vang", "store": "HỦ TIẾU NAM VANG THÀNH ĐẠT", "addr": "115 Bạch Đằng, Bình Thạnh", "date": "2026-11-10", "time": "07:35", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Hủ tiếu Nam Vang khô", 1, 48000), ("Trà đá", 1, 3000)]},
    {"slug": "jollibee_combo", "store": "JOLLIBEE - PEARL PLAZA", "addr": "561A Điện Biên Phủ, Bình Thạnh", "date": "2026-11-11", "time": "12:30", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Combo 2 miếng Gà Giòn + Pepsi", 1, 75000), ("Khoai tây chiên vừa", 1, 20000)]},
    {"slug": "banh_trang_tron", "store": "ĂN VẶT CỔNG TRƯỜNG UTH", "addr": "02 Võ Oanh, Bình Thạnh", "date": "2026-11-12", "time": "16:40", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Bánh tráng trộn bò khô", 1, 20000), ("Trà chanh giã tay", 1, 15000)]},
    {"slug": "bun_thit_nuong", "store": "BÚN THỊT NƯỚNG KIỀU BẢO", "addr": "67 Đường D5, Bình Thạnh", "date": "2026-11-14", "time": "12:15", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Bún thịt nướng chả giò", 1, 38000), ("Nước mía tắc", 1, 10000)]},
    {"slug": "chao_suon_dem", "store": "CHÁO SƯỜN SỤN ĐÊM", "addr": "44 Bùi Hữu Nghĩa, Bình Thạnh", "date": "2026-11-15", "time": "21:20", "cat": "Ăn uống", "pay": "Tiền mặt", "items": [("Cháo sườn trứng bắc thảo", 1, 32000), ("Quẩy nóng", 1, 6000)]},
    {"slug": "lau_sinh_vien", "store": "LẨU BÒ NHÚNG DẤM 539", "addr": "124 Nguyễn Văn Đậu, Bình Thạnh", "date": "2026-11-17", "time": "19:30", "cat": "Ăn uống", "pay": "Chuyển khoản QR", "items": [("Lẩu bò nhỏ (chia nhóm 3)", 1, 110000), ("Bún tươi + rau thêm", 1, 15000), ("Nước ngọt chai", 2, 12000)]},
    {"slug": "gs25_an_sang", "store": "GS25 - VÕ OANH UTH", "addr": "18 Võ Oanh, Bình Thạnh", "date": "2026-11-19", "time": "07:10", "cat": "Ăn uống", "pay": "Ví MoMo", "items": [("Cơm nắm cá ngừ mayo", 1, 18000), ("Sữa Milo hộp 180ml", 1, 11000), ("Bánh bao nhân thịt", 1, 16000)]},

    # --- Đi lại (8 bill) ---
    {"slug": "petrolimex_xang_1", "store": "CỬA HÀNG XĂNG DẦU PETROLIMEX SỐ 12", "addr": "210 Xô Viết Nghệ Tĩnh, Bình Thạnh", "date": "2026-11-02", "time": "07:50", "cat": "Đi lại", "pay": "Tiền mặt", "items": [("Xăng RON 95-III (3.15 lít)", 1, 70000)]},
    {"slug": "grabbike_di_hoc", "store": "GRABBIKE - CHUYẾN ĐI TP.HCM", "addr": "Bình Thạnh -> Cơ sở 1 UTH", "date": "2026-11-04", "time": "06:55", "cat": "Đi lại", "pay": "Ví MoMo", "items": [("Cước GrabBike 4.2 km", 1, 24000), ("Phí nền tảng", 1, 2000)]},
    {"slug": "ve_xe_buyt_thang", "store": "TRUNG TÂM VẬN TẢI HÀNH KHÁCH TP.HCM", "addr": "Bến xe Buýt Văn Thánh", "date": "2026-11-05", "time": "08:05", "cat": "Đi lại", "pay": "Tiền mặt", "items": [("Tập 30 vé xe buýt học sinh-SV", 1, 67500)]},
    {"slug": "gui_xe_uth", "store": "BÃI GIỮ XE SINH VIÊN UTH", "addr": "Số 2 Võ Oanh, Bình Thạnh", "date": "2026-11-06", "time": "17:15", "cat": "Đi lại", "pay": "Tiền mặt", "items": [("Vé gửi xe máy cả tuần (5 lượt)", 5, 4000)]},
    {"slug": "pvoil_xang_2", "store": "TRẠM XĂNG DẦU PVOIL HÀNG XANH", "addr": "155 Điện Biên Phủ, Bình Thạnh", "date": "2026-11-10", "time": "17:40", "cat": "Đi lại", "pay": "Chuyển khoản QR", "items": [("Xăng RON 95-III (2.7 lít)", 1, 60000)]},
    {"slug": "thay_nhot_xe_may", "store": "TIỆM SỬA XE HONDA MINH PHÁT", "addr": "98 Ung Văn Khiêm, Bình Thạnh", "date": "2026-11-13", "time": "16:20", "cat": "Đi lại", "pay": "Tiền mặt", "items": [("Nhớt Honda chính hãng 0.8L", 1, 115000), ("Tăng sên + bơm bánh", 1, 15000)]},
    {"slug": "bebike_di_lam", "store": "BEBIKE - HÓA ĐƠN ĐIỆN TỬ", "addr": "Bình Thạnh -> Quận 1", "date": "2026-11-16", "time": "17:55", "cat": "Đi lại", "pay": "Ví MoMo", "items": [("Cước BeBike 5.8 km", 1, 32000)]},
    {"slug": "ve_xe_phuong_trang", "store": "XE KHÁCH PHƯƠNG TRANG (FUTA)", "addr": "Bến xe Miền Đông Mới", "date": "2026-11-20", "time": "18:00", "cat": "Đi lại", "pay": "Chuyển khoản QR", "items": [("Vé giường nằm về quê (1 chiều)", 1, 180000)]},

    # --- Học tập (8 bill) ---
    {"slug": "photo_giao_trinh", "store": "TIỆM PHOTOCOPY CỔNG UTH", "addr": "06 Võ Oanh, Bình Thạnh", "date": "2026-11-03", "time": "08:30", "cat": "Học tập", "pay": "Tiền mặt", "items": [("Photo giáo trình Logistics (240tr)", 1, 48000), ("Đóng bìa kiếng lò xo", 1, 12000)]},
    {"slug": "fahasa_sach_python", "store": "NHÀ SÁCH FAHASA - TÂN ĐỊNH", "addr": "387 Hai Bà Trưng, Q.3, TP.HCM", "date": "2026-11-05", "time": "16:00", "cat": "Học tập", "pay": "Chuyển khoản QR", "items": [("Sách Lập trình Python thực chiến", 1, 145000), ("Bút highlight Pastel bộ 4", 1, 32000)]},
    {"slug": "in_mau_do_an", "store": "IN ẤN KỸ THUẬT SỐ D2", "addr": "41 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-08", "time": "10:20", "cat": "Học tập", "pay": "Ví MoMo", "items": [("In màu báo cáo đồ án (35 trang)", 35, 2000), ("Bìa mạ chữ vàng", 1, 25000)]},
    {"slug": "van_phong_pham", "store": "VĂN PHÒNG PHẨM THIÊN LONG", "addr": "52 Đường D5, Bình Thạnh", "date": "2026-11-09", "time": "09:15", "cat": "Học tập", "pay": "Tiền mặt", "items": [("Tập vở 200 trang Campus", 3, 14000), ("Bút bi TL-027 xanh", 5, 4000), ("Bìa nút đựng hồ sơ", 2, 7000)]},
    {"slug": "luyen_thi_toeic", "store": "ANH NGỮ TOEIC SINH VIÊN", "addr": "80 Điện Biên Phủ, Bình Thạnh", "date": "2026-11-11", "time": "18:30", "cat": "Học tập", "pay": "Chuyển khoản QR", "items": [("Lệ phí thi thử TOEIC 4 kỹ năng", 1, 120000), ("Bộ đề ETS 2026 in sẵn", 1, 65000)]},
    {"slug": "usb_luu_bai", "store": "CELLPHONES - BÌNH THẠNH", "addr": "159 Xô Viết Nghệ Tĩnh", "date": "2026-11-14", "time": "15:10", "cat": "Học tập", "pay": "Chuyển khoản QR", "items": [("USB SanDisk 64GB USB 3.2", 1, 159000)]},
    {"slug": "khoa_hoc_excel", "store": "NỀN TẢNG HỌC TRỰC TUYẾN UNICA", "addr": "Hóa đơn điện tử Online", "date": "2026-11-16", "time": "20:05", "cat": "Học tập", "pay": "Ví MoMo", "items": [("Khóa học Excel & PowerBI cơ bản", 1, 199000)]},
    {"slug": "photo_de_cuong", "store": "PHOTOCOPY SINH VIÊN D3", "addr": "14 Đường D3, Bình Thạnh", "date": "2026-11-19", "time": "13:20", "cat": "Học tập", "pay": "Tiền mặt", "items": [("In đề cương ôn thi cuối kỳ", 1, 28000)]},

    # --- Tiền trọ & Sinh hoạt (6 bill) ---
    {"slug": "tien_tro_thang_11", "store": "NHÀ TRỌ SINH VIÊN AN KHANG", "addr": "Hẻm 69 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-01", "time": "09:00", "cat": "Tiền trọ", "pay": "Chuyển khoản QR", "items": [("Tiền thuê phòng 304 (chia đôi)", 1, 1650000), ("Phí rác + vệ sinh hành lang", 1, 30000)]},
    {"slug": "tien_dien_nuoc", "store": "PHIẾU THU ĐIỆN NƯỚC PHÒNG 304", "addr": "Hẻm 69 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-01", "time": "09:05", "cat": "Tiền trọ", "pay": "Chuyển khoản QR", "items": [("Tiền điện (55 kWh x 3.800đ)", 1, 209000), ("Tiền nước sinh hoạt (1 người)", 1, 80000)]},
    {"slug": "internet_wifi_fpt", "store": "FPT TELECOM - CƯỚC INTERNET", "addr": "Hóa đơn điện tử tháng 11/2026", "date": "2026-11-05", "time": "10:00", "cat": "Tiền trọ", "pay": "Ví MoMo", "items": [("Cước Internet Wi-Fi (chia phòng)", 1, 110000)]},
    {"slug": "giat_ui_tu_dong", "store": "GIẶT SẤY TỰ ĐỘNG WASH & GO", "addr": "27 Đường D5, Bình Thạnh", "date": "2026-11-09", "time": "19:40", "cat": "Tiền trọ", "pay": "Tiền mặt", "items": [("Giặt + sấy 6kg quần áo", 1, 45000), ("Nước xả vải thơm", 1, 5000)]},
    {"slug": "nuoc_uong_binh_20l", "store": "ĐẠI LÝ NƯỚC UỐNG LAVIE - VĨNH HẢO", "addr": "105 Ung Văn Khiêm, Bình Thạnh", "date": "2026-11-12", "time": "14:30", "cat": "Tiền trọ", "pay": "Tiền mặt", "items": [("Nước tinh khiết Vihawa bình 20L", 2, 26000)]},
    {"slug": "coopmart_do_sinh_hoat", "store": "CO.OPMART RẠCH MIỄU", "addr": "48 Hoa Sứ, Phú Nhuận", "date": "2026-11-15", "time": "17:05", "cat": "Tiền trọ", "pay": "Chuyển khoản QR", "items": [("Nước giặt OMO 1.8kg", 1, 95000), ("Kem đánh răng P/S", 1, 29000), ("Giấy vệ sinh lốc 6 cuộn", 1, 38000)]},

    # --- Giải trí (5 bill) ---
    {"slug": "cgv_ve_xem_phim", "store": "CGV CINEMAS - PEARL PLAZA", "addr": "561A Điện Biên Phủ, Bình Thạnh", "date": "2026-11-07", "time": "20:15", "cat": "Giải trí", "pay": "Ví MoMo", "items": [("Vé 2D U22 Sinh viên", 1, 65000), ("Bắp rang caramel nhỏ", 1, 45000)]},
    {"slug": "cyber_game", "store": "CYBERCORE GAMING BÌNH THẠNH", "addr": "84 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-10", "time": "21:00", "cat": "Giải trí", "pay": "Tiền mặt", "items": [("Nạp giờ chơi VIP (4 giờ)", 4, 12000), ("Sting dâu lon", 1, 14000)]},
    {"slug": "bida_cung_ban", "store": "CLB BIDA PHỐ SINH VIÊN", "addr": "132 Ung Văn Khiêm, Bình Thạnh", "date": "2026-11-13", "time": "20:30", "cat": "Giải trí", "pay": "Chuyển khoản QR", "items": [("Tiền bàn bida lỗ (chia 2 người)", 1, 55000), ("Nước suối lạnh", 1, 10000)]},
    {"slug": "cafe_boardgame", "store": "BOARDGAME STATION CAFE", "addr": "39 Đường D2, Bình Thạnh", "date": "2026-11-16", "time": "15:30", "cat": "Giải trí", "pay": "Ví MoMo", "items": [("Phụ thu chơi Boardgame + Nước", 1, 69000)]},
    {"slug": "san_cau_long", "store": "SÂN CẦU LÔNG VĂN THÁNH", "addr": "48/10 Điện Biên Phủ, Bình Thạnh", "date": "2026-11-18", "time": "18:00", "cat": "Giải trí", "pay": "Tiền mặt", "items": [("Tiền sân cầu lông (chia nhóm)", 1, 45000), ("Ống cầu đóng góp", 1, 20000)]},

    # --- Khác / Sức khỏe / Mua sắm (3 bill) ---
    {"slug": "nha_thuoc_long_chau", "store": "NHÀ THUỐC FPT LONG CHÂU", "addr": "72 Xô Viết Nghệ Tĩnh, Bình Thạnh", "date": "2026-11-06", "time": "19:15", "cat": "Khác", "pay": "Chuyển khoản QR", "items": [("Thuốc cảm cúm Panadol Extra", 1, 28000), ("Viên sủi Vitamin C Berocca", 1, 64000)]},
    {"slug": "cat_toc_30shine", "store": "30SHINE HAIR SALON", "addr": "150 Nguyễn Gia Trí, Bình Thạnh", "date": "2026-11-12", "time": "17:10", "cat": "Khác", "pay": "Ví MoMo", "items": [("Combo cắt gội sinh viên", 1, 90000)]},
    {"slug": "mua_ao_thun_sv", "store": "SHOP THỜI TRANG YAME BÌNH THẠNH", "addr": "200 Lê Quang Định, Bình Thạnh", "date": "2026-11-18", "time": "16:25", "cat": "Khác", "pay": "Chuyển khoản QR", "items": [("Áo thun cotton basic trơn", 1, 155000), ("Vớ cổ ngắn đôi", 2, 18000)]},
]


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\tahomabd.ttf"]
        if bold
        else [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\tahoma.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fmt_vnd(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _render_bill_image(idx: int, bill: dict, out_path: Path) -> int:
    rng = random.Random(1000 + idx)
    items = bill["items"]
    subtotal = sum(q * p for _, q, p in items)
    discount = 0
    total = subtotal - discount

    w = 640
    h = 430 + len(items) * 56
    paper_tone = rng.randint(248, 254)
    img = Image.new("RGB", (w, h), (paper_tone, paper_tone, paper_tone - 2))
    draw = ImageDraw.Draw(img)

    f_title = _load_font(26, bold=True)
    f_sub = _load_font(18, bold=False)
    f_head = _load_font(22, bold=True)
    f_body = _load_font(19, bold=False)
    f_bold = _load_font(20, bold=True)
    f_total = _load_font(28, bold=True)
    ink = (25, 28, 30)
    muted = (90, 95, 100)

    y = 26
    # Header cửa hàng
    draw.text((w // 2, y), bill["store"], fill=ink, font=f_title, anchor="ma")
    y += 34
    draw.text((w // 2, y), bill["addr"], fill=muted, font=f_sub, anchor="ma")
    y += 28
    draw.text((w // 2, y), f"SĐT: 090{rng.randint(1000000, 9999999)}", fill=muted, font=f_sub, anchor="ma")
    y += 32

    draw.line([(36, y), (w - 36, y)], fill=(150, 150, 150), width=2)
    y += 18
    draw.text((w // 2, y), "HÓA ĐƠN THANH TOÁN", fill=ink, font=f_head, anchor="ma")
    y += 34

    d_parts = bill["date"].split("-")
    vn_date = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]}"
    bill_code = f"HD2611{idx:03d}"
    draw.text((38, y), f"Số HĐ: {bill_code}", fill=ink, font=f_body)
    draw.text((w - 38, y), f"Ngày: {vn_date} {bill['time']}", fill=ink, font=f_body, anchor="ra")
    y += 32

    draw.line([(36, y), (w - 36, y)], fill=(170, 170, 170), width=1)
    y += 12
    draw.text((38, y), "Mặt hàng", fill=ink, font=f_bold)
    draw.text((405, y), "SL", fill=ink, font=f_bold, anchor="ma")
    draw.text((w - 38, y), "Thành tiền", fill=ink, font=f_bold, anchor="ra")
    y += 30
    draw.line([(36, y), (w - 36, y)], fill=(170, 170, 170), width=1)
    y += 14

    for name, qty, unit_price in items:
        line_total = qty * unit_price
        draw.text((38, y), name, fill=ink, font=f_body)
        draw.text((405, y), str(qty), fill=ink, font=f_body, anchor="ma")
        draw.text((w - 38, y), f"{_fmt_vnd(line_total)} đ", fill=ink, font=f_body, anchor="ra")
        y += 24
        draw.text((52, y), f"Đơn giá: {_fmt_vnd(unit_price)} đ", fill=muted, font=f_sub)
        y += 30

    draw.line([(36, y), (w - 36, y)], fill=(140, 140, 140), width=2)
    y += 16
    draw.text((38, y), "Tạm tính:", fill=ink, font=f_body)
    draw.text((w - 38, y), f"{_fmt_vnd(subtotal)} đ", fill=ink, font=f_body, anchor="ra")
    y += 32

    draw.text((38, y), "TỔNG THANH TOÁN:", fill=ink, font=f_bold)
    draw.text((w - 38, y - 4), f"{_fmt_vnd(total)} đ", fill=(15, 23, 20), font=f_total, anchor="ra")
    y += 42

    draw.text((38, y), f"Phương thức: {bill['pay']}", fill=muted, font=f_body)
    y += 34
    draw.line([(36, y), (w - 36, y)], fill=(190, 190, 190), width=1)
    y += 18
    draw.text((w // 2, y), "Cảm ơn quý khách & Hẹn gặp lại!", fill=muted, font=f_sub, anchor="ma")

    img.save(out_path, format="JPEG", quality=92)
    return total


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUT_DIR / "danh_sach_50_bill.csv"
    rows = []
    grand_total = 0

    for idx, bill in enumerate(BILLS_DATA, start=1):
        fname = f"bill_{idx:02d}_{bill['slug']}.jpg"
        out_path = OUT_DIR / fname
        total = _render_bill_image(idx, bill, out_path)
        grand_total += total
        rows.append({
            "STT": idx,
            "File ảnh": fname,
            "Ngày": bill["date"],
            "Giờ": bill["time"],
            "Cửa hàng": bill["store"],
            "Danh mục": bill["cat"],
            "Tổng tiền (VNĐ)": total,
            "Thanh toán": bill["pay"],
        })

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"GENERATED={len(rows)} TOTAL_VND={grand_total} DIR={OUT_DIR}")


if __name__ == "__main__":
    main()
