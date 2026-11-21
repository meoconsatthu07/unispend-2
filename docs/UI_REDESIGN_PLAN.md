# UI_REDESIGN_PLAN.md — KẾ HOẠCH AUDIT & REDESIGN TOÀN DIỆN UNISPEND 2.0 (MONII MONEY CALENDAR INSPIRED)

## 1. Kết Quả Audit Hệ Thống Hiện Tại

- **Framework & Ngôn ngữ:** Python 3.13 + Streamlit + Altair + SQLite (`data/expenses.db` & `data/unispend_extensions.db`) + OpenCV + Tesseract OCR 5.x + Google Gemini API (`google-genai` SDK) + Pydantic.
- **File khởi chạy giao diện:** `main.py --legacy` / `main.py --demo` $\rightarrow$ `app.py` $\rightarrow$ `expense_tracker/ui.py` (`run_app()`).
- **Các file bị khóa (Chỉ đọc — Tuyệt đối không sửa):**
  - `main.py` (0 thay đổi)
  - `app.py` (0 thay đổi)
  - `expense_tracker/storage.py` (0 thay đổi)
  - Thư mục `unispend_3d/` (0 thay đổi)
- **Các file giao diện & module mở rộng được phép thiết kế lại:**
  - `expense_tracker/ui.py`
  - `expense_tracker/theme.css`
  - `expense_tracker/charts.py`
  - `expense_tracker/lucide_icons.py`
  - `expense_tracker/mascot.py`
  - `expense_tracker/ai_service.py`
  - `expense_tracker/ocr_pipeline.py`
  - `expense_tracker/extensions_db.py`
  - `DESIGN.md` & `UI_REDESIGN_PLAN.md`

---

## 2. Bảng Đối Chiếu Toàn Bộ Ảnh Tham Khảo & Chức Năng Redesign

| STT | Màn hình/chức năng | Giao diện hiện tại | Ảnh tham khảo | Giao diện cần làm | Trạng thái |
|---|---|---|---|---|---|
| 1 | **Header & Điều hướng Tổng quan (Homepage Header)** | Thanh tiêu đề cơ bản và chọn tháng rời rạc | `media_1795086162162_f478eece.jpg`, `media_1795085577965_25afb77d.jpg` | Header chuẩn Monii & Desktop Pro: Lời chào người dùng (`Xin chào, <Tên>`), Ngày hiện tại, Ô tìm kiếm giao dịch nhanh, Chuông thông báo hóa đơn sắp tới, Avatar người dùng, Công tắc Light/Dark Mode và bộ chọn tháng `< Tháng MM, YYYY >` + nút `Hôm nay`. | Hoàn thành |
| 2 | **Thẻ Tổng quan Tài chính (Financial Summary & Hero Card)** | Các hộp metric đơn lẻ | `media_1795084382345_8ae16d1a.jpg`, `media_1795086162162_f478eece.jpg` | Hero Card Khả dụng tháng kèm Mascot UniBean ôm lịch + 4 thẻ KPI chuẩn Monii Desktop (`Số dư hiện tại`, `Thu nhập`, `Chi tiêu`, `Có thể chi hôm nay`) với Lucide SVG icons, chỉ số thay đổi và biểu đồ sparkline SVG. | Hoàn thành |
| 3 | **Lịch Chi Tiêu Theo Tháng (Monii Money Calendar)** | Lưới lịch 7 cột cơ bản | `media_1795084382345_8ae16d1a.jpg`, `media_1795085577965_25afb77d.jpg`, `media_1795086162162_f478eece.jpg` | Lịch 7 cột (`T2` $\rightarrow$ `CN`), hai thẻ tổng `CHI` / `THU` phía trên, hiển thị số tiền thu/chi từng ngày, phân màu nền theo ngưỡng chi tiêu (Thấp/Trung bình/Cao), viền xanh `#16A36A` / `#38C98A` nổi bật cho ngày đang chọn, bấm chọn ngày cập nhật tức thì bảng chi tiết bên phải. | Hoàn thành |
| 4 | **Bảng Giao Dịch Trong Ngày (Daily Transaction Panel) & Quick Add** | Chỉ liệt kê văn bản và form thêm đơn giản, thiếu chọn ví và sửa/xóa tại chỗ | `media_1795086162162_f478eece.jpg`, `media_1795084687081_cd00ccfe.jpg` | Hiển thị Thứ/Ngày đang chọn, Tổng thu & Tổng chi trong ngày, danh sách thẻ giao dịch có icon Lucide theo danh mục (`coffee`, `utensils`, `car`...), nhãn Ví thanh toán, thao tác **Xem chi tiết / Sửa / Xóa ngay trong ngày** và biểu mẫu **Quick Add** (chọn Thu/Chi, chip số tiền nhanh, Danh mục, Chọn Ví, Ghi chú, Lưu). | Hoàn thành |
| 5 | **Chi Tiêu An Toàn (Safe Spending Meter)** | Chưa hiển thị đầy đủ số tiền đã chi & còn lại ngay dưới lịch | `media_1795086162162_f478eece.jpg` | Thẻ **Chi tiêu an toàn (`... ₫/ngày`)** ngay dưới lịch: hiển thị Mức chi an toàn mỗi ngày, Tổng đã chi, Số tiền ngân sách còn lại, Thanh tiến độ mượt và badge cảnh báo (`Trong giới hạn` / `Sắp chạm ngưỡng` / `Vượt hạn mức`). | Hoàn thành |
| 6 | **Hóa Đơn Sắp Tới & Quản Lý Hóa Đơn Định Kỳ / Sổ Nợ (Upcoming Bills & Subscriptions)** | Danh sách hóa đơn rời rạc | `media_1795084388164_7b0f34cd.jpg`, `media_1795086162162_f478eece.jpg` | Thẻ **Hóa đơn sắp tới** ở cột phải trang chủ + Màn hình **Hóa Đơn & Đăng Ký** chuyên biệt: chuyển đổi `Hóa đơn định kỳ` / `Sổ ghi nợ`, 2 thẻ lớn `CHƯA THANH TOÁN` & `ĐÃ THANH TOÁN`, trạng thái trống có Mascot UniBean `?`, nút xác nhận thanh toán 1 chạm ghi thẳng vào SQLite và xóa hóa đơn. | Hoàn thành |
| 7 | **Menu Nổi Radial & Nhập Chi Tiêu Bằng Giọng Nói (Voice Bottom-Sheet Modal)** | Nút bấm thường | `media_1795084471304_dc9df2f1.jpg`, `media_1795084481422_2f40af08.jpg`, `media_1795085556593_b4471d23.jpg`, `media_1795085563821_f943003b.jpg` | Cụm nút nổi Radial (`Camera`, `Thư viện ảnh`, `Đóng`, `Micro`) bằng Lucide SVG + Bottom-Sheet Modal **Nhập bằng giọng nói** (Vòng tròn mic phát sáng, 7 cột sóng âm chuyển động, hộp `LỜI BẠN NÓI`, tự động STT & phân tích NLP/Gemini, 2 nút `Sửa chi tiết` & `Lưu chi tiêu`). | Hoàn thành |
| 8 | **Quét Hóa Đơn AI (Tesseract OCR 5.x + Gemini Vision/JSON)** | Form tải ảnh cơ bản | `media_1795084687081_cd00ccfe.jpg`, `media_1795085012935_20b5e5cb.jpg` | Khung ngắm Viewfinder 4 góc xanh, tiền xử lý ảnh OpenCV (xoay ảnh, Grayscale, CLAHE), chạy Tesseract `vie+eng` kết hợp Gemini Vision/JSON 12 trường (`GeminiReceiptSchema`), bảng danh sách mặt hàng, cảnh báo trùng lặp SHA-256, chỉnh sửa & xác nhận lưu. | Hoàn thành |
| 9 | **Phân Tích & Thống Kê Chi Tiêu 8 Hạng Mục (Statistics & Trends)** | Biểu đồ mặc định | `media_1795084394629_77e265f4.jpg`, `media_1795084687081_cd00ccfe.jpg` | Tab `Tháng này` / `Xu hướng`, bộ lọc `Ngày/Tuần/Tháng/Quý/Năm/Tự chọn`, Thẻ Donut + Mascot UniBean ôm ví + Nút xuất `Excel` / `PDF`, 2 thẻ `TB MỖI NGÀY` & `CHI NHIỀU NHẤT`, danh sách **8 hạng mục tỷ trọng** dùng Lucide SVG icons kèm thanh tiến độ, cùng bộ biểu đồ xu hướng 6 tháng. | Hoàn thành |
| 10 | **Ngân Sách & Mục Tiêu Tiết Kiệm (Budgets & Savings Goals)** | Form số đơn thuần | `media_1795085012935_20b5e5cb.jpg`, `media_1795086162162_f478eece.jpg` | Thẻ tiến độ **Ngân sách tổng** & **Ngân sách từng danh mục** có cảnh báo 80%/100% + Khu vực **Mục tiêu tiết kiệm** (Tạo mục tiêu, số tiền mục tiêu, hiện có, còn thiếu, thanh tiến độ, cập nhật/sửa/xóa mục tiêu). | Hoàn thành |
| 11 | **Quản Lý Giao Dịch (Sổ Giao Dịch Monii Card List & Data Table)** | Bảng dataframe thuần túy | `media_1795085012935_20b5e5cb.jpg`, `media_1795086162162_f478eece.jpg` | Bộ lọc Loại/Danh mục/Từ khóa + Thẻ tổng hợp nhanh + Danh sách thẻ giao dịch chuẩn Monii có icon Lucide & nhãn Ví + Bảng dữ liệu chi tiết + Khu vực Sửa/Xóa giao dịch có xác nhận an toàn và xuất CSV. | Hoàn thành |
| 12 | **Trợ Lý Tài Chính AI (AI Chat & Deep Financial Review)** | Hỏi đáp đơn lẻ, chưa có khung lịch sử chat trực quan | `media_1795084687081_cd00ccfe.jpg` | Giao diện **Trợ lý AI dạng khung Chat thực tế**: hiển thị bong bóng hội thoại (Lịch sử trò chuyện từ SQLite), chip câu hỏi gợi ý, ô nhập câu hỏi, trạng thái đang xử lý và bản **Phân tích chuyên sâu + Kế hoạch tiết kiệm 3 bước** từ số liệu thật. | Hoàn thành |
| 13 | **Cài Đặt, Tài Khoản, Ví & Sao Lưu (Personal & Settings)** | Cài đặt rời rạc | `media_1795084399904_424c4987.jpg` | Màn hình **Cá nhân & Cài đặt** chuẩn Monii: Hồ sơ cá nhân (đổi tên hiển thị trên lời chào Header), Quản lý Ví thanh toán (`Tiền mặt`, `Ngân hàng`, `Ví điện tử`), Giờ nhắc nhở `20:00`, Ngưỡng màu lịch, Công tắc Light/Dark Mode, Cổng đấu nối AI API, Xuất Excel đa sheet và Sao lưu/Khôi phục SQLite. | Hoàn thành |
