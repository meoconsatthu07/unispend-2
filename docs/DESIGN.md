# DESIGN.md — HỆ THỐNG THIẾT KẾ UNISPEND 2.0 (MODERN FINTECH – FRIENDLY MONEY CALENDAR)

## 1. Triết Lý Thiết Kế (Design Philosophy)

**UniSpend 2.0** được thiết kế theo phong cách **Modern Fintech – Friendly Money Calendar** lấy cảm hứng từ trải nghiệm của **Monii Money Calendar**, kết hợp nguyên tắc từ **UI/UX Pro Max**, **Anthropic Frontend Design**, **Emil Kowalski Motion Principles** và **Vercel Web Interface Guidelines**:

- **Rõ ràng về tài chính (Financial Clarity First):** Mọi con số tiền tệ (`VNĐ`) đều sử dụng `font-variant-numeric: tabular-nums` để căn chỉnh hàng dọc tuyệt đối trên lịch, thẻ KPI và sổ giao dịch.
- **Lịch là trung tâm (Calendar-Centric Workflow):** Người dùng nhìn vào một tháng là thấy ngay bức tranh dòng tiền theo từng ngày (màu sắc phân tầng mức chi), chạm vào ngày để xem, thêm, sửa hoặc xóa giao dịch ngay lập tức.
- **Thân thiện nhưng chuyên nghiệp (Friendly yet Commercial-Grade):** Kết hợp hệ thống **Lucide Vector Icons** sắc nét (`stroke-width: 2px`) với nhân vật đại diện riêng **UniBean** (SVG vector) để tạo cá tính riêng biệt cho UniSpend 2.0.

---

## 2. Bảng Màu Chuẩn (Color Tokens)

### Light Mode (Emerald Ivory Dashboard)
| Token | Mã màu (HEX) | Vai trò sử dụng |
|---|---|---|
| `--color-primary` | `#16A36A` | Màu xanh chính (Nút hành động chính, viền ngày chọn, thanh tiến độ an toàn, điểm nhấn thương hiệu) |
| `--bg-main` | `#F4F8F5` | Nền tổng thể của ứng dụng (Soft Mint Ivory) |
| `--bg-surface` | `#FFFFFF` | Nền thẻ (Card), Lịch, Modal, Bảng giao dịch |
| `--bg-secondary` | `#EAF3ED` | Nền thẻ phụ, pill trạng thái, ô lịch mức chi thấp |
| `--color-text` | `#182B22` | Chữ chính (Độ tương phản cao chuẩn WCAG AA/AAA) |
| `--color-text-muted` | `#87958D` | Chữ phụ, nhãn mô tả, ngày tháng phụ |
| `--color-border` | `#E5EEE8` | Đường viền thẻ, ô lịch, ô nhập liệu |
| `--color-danger` | `#D94B50` | Màu đỏ chi tiêu, cảnh báo vượt hạn mức ngân sách |
| `--color-warning` | `#E8A45B` | Màu cam cảnh báo sắp chạm ngưỡng (80%–100%) |

### Dark Mode (Monii Emerald Noir)
| Token | Mã màu (HEX) | Vai trò sử dụng |
|---|---|---|
| `--color-primary` | `#38C98A` | Màu xanh ngọc phát sáng trên nền tối (Active pill, viền ngày chọn, nút chính) |
| `--bg-main` | `#0D1B16` | Nền chính Dark Mode sâu và dịu mắt |
| `--bg-surface` | `#142820` | Nền Card chính, Khung lịch, Khung chi tiết ngày |
| `--bg-secondary` | `#1C352B` | Nền Card phụ, Hộp chọn, Pill điều hướng |
| `--color-text` | `#F2F8F4` | Chữ chính sáng rõ |
| `--color-text-muted` | `#91A69A` | Chữ phụ, nhãn phụ |
| `--color-border` | `#263C31` | Viền phân tách tinh tế trên nền tối |
| `--color-danger` | `#E05A5F` | Màu đỏ chi tiêu / chưa thanh toán |
| `--color-warning` | `#E8A45B` | Màu cam cảnh báo chi tiêu trung bình / sắp vượt ngưỡng |

---

## 3. Typography (Hệ Thống Chữ)

- **Font chữ chính:** `'Be Vietnam Pro', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` — hỗ trợ hoàn hảo dấu tiếng Việt và độ đọc cao trên mọi kích thước màn hình.
- **Số liệu tiền tệ (`VNĐ`):** Bắt buộc áp dụng `font-variant-numeric: tabular-nums` và `letter-spacing: -0.02em`.
- **Phân cấp kích thước:**
  - Số dư lớn trên Hero Card: `clamp(1.85rem, 3.2vw, 2.45rem)`, `font-weight: 900`.
  - Giá trị trên 4 thẻ KPI & Chi tiêu an toàn: `1.35rem – 1.5rem`, `font-weight: 800`.
  - Tiêu đề khu vực (Section Heading): `1.1rem – 1.35rem`, `font-weight: 800`.
  - Nội dung giao dịch & nhãn: `0.85rem – 0.95rem`, `font-weight: 500–700`.

---

## 4. Hệ Thống Icon Vector (Lucide Icon System)

- **Nguồn chuẩn:** [Lucide Icons](https://lucide.dev/) được đóng gói trực tiếp trong `expense_tracker/lucide_icons.py`.
- **Quy tắc bắt buộc:**
  - Không dùng emoji thay thế icon trong các thành phần giao diện.
  - Kích thước chuẩn: `16px` (micro badge), `18px` (button/header icon), `20px–22px` (card & category icon box `40x40px` bo góc `12px`).
  - Độ dày nét vẽ đồng nhất: `stroke-width="2"`, `stroke-linecap="round"`, `stroke-linejoin="round"`.
  - Tự động đổi màu theo ngữ cảnh (`currentColor`, `#16A36A` ở Light Mode, `#38C98A` ở Dark Mode).

---

## 5. Chuyển Động & Responsive (Motion & Responsive Rules)

- **Đường cong chuyển động (Spring Easing):** `--ease-spring: cubic-bezier(0.22, 1, 0.36, 1)` với thời lượng `180ms – 320ms`.
- **Card & Geometry:** Bo góc chuẩn `20px – 24px` cho Card lớn, `14px – 16px` cho ô lịch và ô nhập liệu, `999px` cho Pill & nút hành động.
- **Responsive Đa thiết bị:**
  - **Desktop ($\ge 1024\text{px}$):** Sidebar trái cố định + Khu vực chính 4 cột KPI + Lịch 2 cột (Lịch 7 cột bên trái, Chi tiết ngày & Hóa đơn sắp tới bên phải).
  - **Tablet ($768\text{px} - 1023\text{px}$):** Tự động co giãn lưới thẻ và giữ tỷ lệ lịch không tràn ngang.
  - **Mobile ($\le 767\text{px}$):** Tối ưu khoảng đệm ô lịch, vùng chạm nút $\ge 44\text{px}$, thanh điều hướng cố định phía dưới (Bottom Navigation Dock) và hỗ trợ `env(safe-area-inset-bottom)`.
