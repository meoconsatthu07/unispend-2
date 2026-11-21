# UniSpend 2.0 — Hướng Dẫn Triển Khai Local & Truy Cập Điện Thoại Qua Wi-Fi

Tài liệu hướng dẫn cài đặt và vận hành **UniSpend 2.0 (Personal Finance Calendar + AI Receipt Scanner + Voice Assistant)** trực tiếp trên máy tính cá nhân, lưu trữ bằng SQLite cục bộ, **không cần thuê hosting, VPS hay tên miền**.

---

## 1. Kiến trúc Entry Point & Cơ sở dữ liệu

UniSpend 2.0 giữ nguyên tuyệt đối các file bị khóa (`app.py`, `main.py`, `expense_tracker/storage.py`):

- **Khởi chạy qua `main.py` / `app.py`:**
  - `python main.py --legacy` (hoặc `run_local.bat` / `.\run_local.ps1`): mở giao diện **UniSpend 2.0** với dữ liệu cá nhân tại `data/expenses.db`.
  - `python main.py --demo` (hoặc `run_local.bat --demo` / `.\run_local.ps1 -Demo`): mở giao diện **UniSpend 2.0** với dữ liệu mẫu tại `data/demo.db`.
- **Cơ sở dữ liệu SQLite:**
  - `data/expenses.db`: Lưu giao dịch thu/chi và định mức ngân sách chính (do `ExpenseStore` trong `expense_tracker/storage.py` quản lý).
  - `data/unispend_extensions.db`: Lưu dữ liệu mở rộng (Hóa đơn & ảnh OCR, Mục tiêu tiết kiệm, Giao dịch định kỳ/Khoản nợ, Cấu hình Light/Dark Mode & ngưỡng màu lịch, Lịch sử AI).
  - Khi chạy `--demo`, ứng dụng dùng `data/demo.db` và `data/unispend_extensions_demo.db` tách biệt hoàn toàn với dữ liệu người dùng.

---

## 2. Cài đặt môi trường

Yêu cầu **Python 3.10 trở lên**. Mở PowerShell tại thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Các thư viện sử dụng:
- `streamlit`, `pandas`, `altair`, `fastapi`, `uvicorn`
- `openpyxl` (Xuất báo cáo Excel `.xlsx`)
- `fpdf2` (Xuất báo cáo PDF `.pdf` tiếng Việt Unicode)
- `python-dotenv` (Đọc cấu hình `.env`)
- `google-genai` (Kết nối Google Gemini API cho AI OCR Hóa đơn, Voice STT và Financial Assistant)

---

## 3. Chạy trên máy tính cá nhân (Localhost)

### Cách 1: Dùng file chạy nhanh (Khuyên dùng)
- **Command Prompt / Double-click:**
  ```bat
  run_local.bat
  ```
- **PowerShell:**
  ```powershell
  .\run_local.ps1
  ```
- **Chạy chế độ dữ liệu mẫu:**
  ```powershell
  .\run_local.ps1 -Demo
  ```

Ứng dụng sẽ mở tại: **http://127.0.0.1:8501**

---

## 4. Truy cập bằng điện thoại qua cùng mạng Wi-Fi (Chế độ LAN)

Máy tính cá nhân đóng vai trò máy chủ lưu trữ SQLite, điện thoại kết nối chung Wi-Fi có thể truy cập trực tiếp:

1. Trên máy tính, khởi chạy chế độ LAN (`0.0.0.0:8501`):
   ```powershell
   .\run_local.ps1 -Lan
   ```
   hoặc:
   ```bat
   run_local.bat --lan
   ```
2. Màn hình Terminal sẽ in ra địa chỉ IPv4 trong mạng Wi-Fi của máy tính, ví dụ:
   ```text
   -> Truy cập trên điện thoại cùng Wi-Fi: http://192.168.1.15:8501
   ```
3. Mở trình duyệt (Safari / Chrome) trên điện thoại (đang bắt cùng Wi-Fi) và truy cập đúng địa chỉ `http://<IP-Máy-Tính>:8501`.
   *(Nếu không vào được, hãy cho phép `python.exe` qua Windows Defender Firewall ở mạng **Private**).*

### Lưu ý về Camera và Microphone trên điện thoại qua mạng LAN:
- **Qua kết nối HTTP thông thường (`http://192.168.x.x:8501`):**
  Trình duyệt di động thường chặn luồng WebRTC (`camera_input` / `audio_input` trực tiếp) trên các địa chỉ khác `localhost` nếu không có HTTPS. UniSpend 2.0 đã tích hợp sẵn:
  - **Tải ảnh hóa đơn (`📤 Tải ảnh hóa đơn JPG/PNG`)**: trên điện thoại, khi bấm nút này hệ điều hành iOS/Android sẽ cho phép chọn **"Chụp ảnh" (Take Photo)** bằng camera gốc hoặc chọn từ Thư viện ảnh.
  - **Tải file ghi âm (`Hoặc tải file ghi âm từ điện thoại`)**: cho phép ghi âm hoặc chọn file `.wav`, `.mp3`, `.m4a`, `.ogg` từ điện thoại mà không bị chặn bởi giới hạn HTTP.
- **Nếu muốn bật Camera/Microphone trực tiếp trên trình duyệt điện thoại qua HTTPS nội bộ:**
  1. Cài công cụ tạo chứng chỉ nội bộ [`mkcert`](https://github.com/FiloSottile/mkcert):
     ```powershell
     mkcert -install
     mkcert 127.0.0.1 localhost 192.168.1.15
     ```
  2. Cài file `rootCA.pem` của `mkcert` vào điện thoại và tin cậy chứng chỉ.
  3. Chạy Streamlit với tham số `--server.sslCertFile` và `--server.sslKeyFile` trỏ tới chứng chỉ vừa tạo.

---

## 5. Cấu hình AI API (OCR Hóa đơn, Giọng nói & Trợ lý tài chính)

1. Sao chép file `.env.example` thành `.env` tại thư mục gốc dự án:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Mở file `.env` và điền API key của bạn:
   ```env
   AI_PROVIDER=auto
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   ```
   *(Hoặc điền `OPENAI_API_KEY=sk-...` nếu dùng OpenAI).*
3. **Khi chưa cấu hình API key:**
   - Toàn bộ chức năng Lịch tài chính, Ngân sách, Mục tiêu tiết kiệm, Giao dịch định kỳ, Xuất Excel/PDF, Sao lưu/Khôi phục SQLite, Phân tích số liệu thật và Bộ đọc câu nói số tiền tiếng Việt (`"Tiền đổ xăng 50K"`, `"Ăn sáng 35 nghìn hôm qua"`, `"2 triệu rưỡi"`, v.v.) vẫn hoạt động đầy đủ.
   - Phần OCR từ ảnh chụp sẽ thông báo rõ trạng thái chưa có API key và tuyệt đối không giả lập hay tự bịa số tiền.
