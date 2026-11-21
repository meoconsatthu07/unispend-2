"""Nhân vật Mascot & Logo Heo Con UniPiggy của UniSpend 2.0.

Thiết kế theo nhân vật chú heo con đeo khăn quàng cổ sọc xanh emerald – trắng.
Sử dụng màu vector phẳng + lớp sáng mềm (KHÔNG dùng url(#id) gradient) để tránh tuyệt đối
lỗi trùng ID <defs> khiến trình duyệt tô đen SVG khi hiển thị đồng thời Mobile & Desktop!
"""

from __future__ import annotations

import re


def _compact_svg(raw: str) -> str:
    """Xóa toàn bộ comment HTML và nén SVG về 1 dòng phẳng, không có khoảng trắng đầu dòng."""
    no_comments = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    compact = " ".join(line.strip() for line in no_comments.splitlines() if line.strip())
    return re.sub(r">\s+<", "><", compact).strip()


def mascot_logo_svg(size: int = 34) -> str:
    """Logo chú heo con UniPiggy đeo khăn quàng sọc xanh emerald – trắng."""
    return _compact_svg(f"""
    <svg width="{size}" height="{size}" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="UniSpend Piggy Logo" style="vertical-align:middle;flex-shrink:0;">
      <rect x="2" y="2" width="60" height="60" rx="18" fill="#122B20" stroke="#34D399" stroke-width="2.2"/>
      <!-- Tai trái & phải cụp -->
      <path d="M16 25 C12 16, 17 10, 24 14 C26 15.5, 25 22, 22 25 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.4" stroke-linejoin="round"/>
      <path d="M48 25 C52 16, 47 10, 40 14 C38 15.5, 39 22, 42 25 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.4" stroke-linejoin="round"/>
      <!-- Đầu heo tròn hồng pastel -->
      <ellipse cx="32" cy="31" rx="19" ry="16.5" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.5"/>
      <ellipse cx="27" cy="22.5" rx="8" ry="4" fill="#FFD6D9" opacity="0.55"/>
      <!-- Mắt đen tròn -->
      <circle cx="23.5" cy="27.5" r="2.6" fill="#1B2620"/>
      <circle cx="22.8" cy="26.7" r="0.85" fill="#FFFFFF"/>
      <circle cx="40.5" cy="27.5" r="2.6" fill="#1B2620"/>
      <circle cx="39.8" cy="26.7" r="0.85" fill="#FFFFFF"/>
      <!-- Má hồng -->
      <ellipse cx="18.5" cy="33" rx="3" ry="1.8" fill="#F47280" opacity="0.55"/>
      <ellipse cx="45.5" cy="33" rx="3" ry="1.8" fill="#F47280" opacity="0.55"/>
      <!-- Mũi bầu dục hồng đậm -->
      <ellipse cx="32" cy="34.5" rx="8.2" ry="5.6" fill="#F48B94" stroke="#1B2620" stroke-width="2.2"/>
      <ellipse cx="29.3" cy="34.5" rx="1.45" ry="2.5" fill="#1B2620"/>
      <ellipse cx="34.7" cy="34.5" rx="1.45" ry="2.5" fill="#1B2620"/>
      <!-- Miệng cười -->
      <path d="M29 42.3 Q32 44.6 35 42.3" stroke="#1B2620" stroke-width="2" stroke-linecap="round" fill="none"/>
      <!-- Khăn quàng cổ sọc xanh emerald & trắng -->
      <path d="M17 45.5 Q32 50 47 45.5 L32 58 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.2" stroke-linejoin="round"/>
      <path d="M22.5 49.5 L41.5 49.5" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round"/>
      <path d="M27.5 53.6 L36.5 53.6" stroke="#FFFFFF" stroke-width="2.1" stroke-linecap="round"/>
    </svg>
    """)


def mascot_calendar_svg(width: int = 128, height: int = 128) -> str:
    """Mascot Heo Con UniPiggy đeo khăn sọc xanh-trắng, vẫy tay chào bên cuốn lịch & đồng xu vàng."""
    return _compact_svg(f"""
    <svg width="{width}" height="{height}" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="UniSpend Piggy Calendar Mascot">
      <!-- Ngôi sao lấp lánh -->
      <path d="M22 30 L25 37 L32 40 L25 43 L22 50 L19 43 L12 40 L19 37 Z" fill="#FBBF24"/>
      <circle cx="140" cy="28" r="3.2" fill="#34D399"/>
      <!-- Nút thắt khăn quàng bên trái -->
      <path d="M40 84 L22 76 L26 88 L20 97 L41 93 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.6" stroke-linejoin="round"/>
      <path d="M25 82 L37 86" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round"/>
      <!-- Tay phải vẫy chào dễ thương -->
      <path d="M108 86 C120 79, 129 70, 134 65 C139 69, 138 77, 131 84 C124 91, 114 96, 106 96 Z" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.8" stroke-linejoin="round"/>
      <path d="M128 69 L134 65 L136 73 L130 74 Z" fill="#D8838B" stroke="#1B2620" stroke-width="2" stroke-linejoin="round"/>
      <!-- Thân heo -->
      <ellipse cx="76" cy="102" rx="34" ry="30" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.8"/>
      <!-- Tai trái & phải cụp -->
      <path d="M44 42 C36 22, 47 12, 60 21 C63 24, 61 36, 55 42 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.8" stroke-linejoin="round"/>
      <path d="M108 42 C116 22, 105 12, 92 21 C89 24, 91 36, 97 42 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.8" stroke-linejoin="round"/>
      <!-- Đầu heo tròn hồng pastel -->
      <ellipse cx="76" cy="54" rx="37" ry="31" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.8"/>
      <ellipse cx="66" cy="36" rx="16" ry="7" fill="#FFD9DC" opacity="0.55"/>
      <!-- Mắt đen tròn -->
      <circle cx="59" cy="48" r="4.3" fill="#1B2620"/>
      <circle cx="57.7" cy="46.6" r="1.4" fill="#FFFFFF"/>
      <circle cx="93" cy="48" r="4.3" fill="#1B2620"/>
      <circle cx="91.7" cy="46.6" r="1.4" fill="#FFFFFF"/>
      <!-- Má hồng -->
      <ellipse cx="49" cy="58" rx="5.5" ry="3.2" fill="#F47280" opacity="0.55"/>
      <ellipse cx="103" cy="58" rx="5.5" ry="3.2" fill="#F47280" opacity="0.55"/>
      <!-- Mũi bầu dục -->
      <ellipse cx="76" cy="60" rx="15" ry="10.2" fill="#F48B94" stroke="#1B2620" stroke-width="2.6"/>
      <ellipse cx="70.8" cy="60" rx="2.6" ry="4.5" fill="#1B2620"/>
      <ellipse cx="81.2" cy="60" rx="2.6" ry="4.5" fill="#1B2620"/>
      <!-- Miệng cười -->
      <path d="M70.5 74 Q76 78.2 81.5 74" stroke="#1B2620" stroke-width="2.5" stroke-linecap="round" fill="none"/>
      <!-- Khăn quàng cổ tam giác sọc xanh emerald & trắng -->
      <path d="M44 82 Q76 90 108 82 L76 106 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.6" stroke-linejoin="round"/>
      <path d="M54 88.5 L98 88.5" stroke="#FFFFFF" stroke-width="3.2" stroke-linecap="round"/>
      <path d="M64 95.8 L88 95.8" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>
      <!-- Cuốn lịch tài chính phía trước -->
      <rect x="34" y="102" width="76" height="46" rx="10" fill="#FFFDF9" stroke="#1B2620" stroke-width="2.2"/>
      <path d="M34 111 C34 106 38 102 43 102 H101 C106 102 110 106 110 111 V116 H34 V111 Z" fill="#16A36A"/>
      <rect x="49" y="97" width="5" height="11" rx="2.5" fill="#1B2620"/>
      <rect x="69" y="97" width="5" height="11" rx="2.5" fill="#1B2620"/>
      <rect x="89" y="97" width="5" height="11" rx="2.5" fill="#1B2620"/>
      <rect x="43" y="122" width="11" height="8" rx="2" fill="#DCE9E1"/>
      <rect x="59" y="122" width="11" height="8" rx="2" fill="#DCE9E1"/>
      <rect x="75" y="122" width="11" height="8" rx="2" fill="#34D399"/>
      <rect x="91" y="122" width="11" height="8" rx="2" fill="#DCE9E1"/>
      <rect x="43" y="134" width="11" height="8" rx="2" fill="#DCE9E1"/>
      <rect x="59" y="134" width="11" height="8" rx="2" fill="#F59E0B"/>
      <rect x="75" y="134" width="11" height="8" rx="2" fill="#DCE9E1"/>
      <!-- Đồng xu vàng góc phải dưới -->
      <circle cx="122" cy="126" r="20" fill="#F59E0B" stroke="#FDE68A" stroke-width="2.4"/>
      <circle cx="122" cy="126" r="15" stroke="#B45309" stroke-width="1.2" stroke-dasharray="3 2" fill="none"/>
      <text x="122" y="133" text-anchor="middle" fill="#FFFBEB" font-size="20" font-weight="800" font-family="Segoe UI, sans-serif">$</text>
    </svg>
    """)


def mascot_wallet_svg(width: int = 132, height: int = 132) -> str:
    """Mascot Heo Con UniPiggy đeo khăn quàng sọc xanh-trắng ôm ví xanh lá (Màn hình Thống kê)."""
    return _compact_svg(f"""
    <svg width="{width}" height="{height}" viewBox="0 0 160 160" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="UniSpend Piggy Wallet Mascot">
      <!-- Nút thắt khăn bên trái -->
      <path d="M44 82 L26 75 L30 86 L25 94 L45 90 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.5" stroke-linejoin="round"/>
      <!-- Thân & chân -->
      <ellipse cx="80" cy="106" rx="36" ry="30" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.8"/>
      <ellipse cx="62" cy="136" rx="10" ry="7" fill="#D8838B" stroke="#1B2620" stroke-width="2.4"/>
      <ellipse cx="98" cy="136" rx="10" ry="7" fill="#D8838B" stroke="#1B2620" stroke-width="2.4"/>
      <!-- Tai trái & phải -->
      <path d="M48 40 C40 20, 51 10, 64 19 C67 22, 65 34, 59 40 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.8" stroke-linejoin="round"/>
      <path d="M112 40 C120 20, 109 10, 96 19 C93 22, 95 34, 101 40 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.8" stroke-linejoin="round"/>
      <!-- Đầu heo -->
      <ellipse cx="80" cy="52" rx="37" ry="31" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.8"/>
      <ellipse cx="70" cy="34" rx="16" ry="7" fill="#FFD9DC" opacity="0.55"/>
      <!-- Mắt cười mãn nguyện -->
      <path d="M58 47 Q64 42 70 47" stroke="#1B2620" stroke-width="3.2" stroke-linecap="round" fill="none"/>
      <path d="M90 47 Q96 42 102 47" stroke="#1B2620" stroke-width="3.2" stroke-linecap="round" fill="none"/>
      <!-- Má hồng -->
      <ellipse cx="53" cy="56" rx="5.5" ry="3.2" fill="#F47280" opacity="0.55"/>
      <ellipse cx="107" cy="56" rx="5.5" ry="3.2" fill="#F47280" opacity="0.55"/>
      <!-- Mũi bầu dục -->
      <ellipse cx="80" cy="58" rx="14.5" ry="9.8" fill="#F48B94" stroke="#1B2620" stroke-width="2.5"/>
      <ellipse cx="75" cy="58" rx="2.5" ry="4.3" fill="#1B2620"/>
      <ellipse cx="85" cy="58" rx="2.5" ry="4.3" fill="#1B2620"/>
      <!-- Miệng cười -->
      <path d="M74.5 71.5 Q80 75.5 85.5 71.5" stroke="#1B2620" stroke-width="2.4" stroke-linecap="round" fill="none"/>
      <!-- Khăn quàng sọc xanh trắng -->
      <path d="M48 79 Q80 87 112 79 L80 100 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.5" stroke-linejoin="round"/>
      <path d="M58 85.5 L102 85.5" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>
      <!-- Chiếc ví xanh emerald -->
      <rect x="48" y="96" width="64" height="38" rx="10" transform="rotate(-4 80 115)" fill="#16A36A" stroke="#1B2620" stroke-width="2.4"/>
      <path d="M92 109 H112 V122 H92 C88 122 88 109 92 109 Z" transform="rotate(-4 80 115)" fill="#0F5136" stroke="#1B2620" stroke-width="1.8"/>
      <circle cx="96" cy="115.5" r="3" fill="#FBBF24"/>
      <!-- Hai tay ôm ví -->
      <ellipse cx="47" cy="112" rx="9" ry="7" transform="rotate(15 47 112)" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.4"/>
      <ellipse cx="113" cy="112" rx="9" ry="7" transform="rotate(-15 113 112)" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.4"/>
    </svg>
    """)


def mascot_question_svg(width: int = 108, height: int = 108) -> str:
    """Mascot Heo Con UniPiggy nghiêng đầu dễ thương với dấu hỏi '?' (Trạng thái trống Hóa đơn)."""
    return _compact_svg(f"""
    <svg width="{width}" height="{height}" viewBox="0 0 150 150" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="UniSpend Piggy Empty State">
      <!-- Dấu hỏi chấm nổi bật -->
      <text x="112" y="44" fill="#34D399" font-size="32" font-weight="900" font-family="Segoe UI, sans-serif">?</text>
      <!-- Thân & chân -->
      <ellipse cx="72" cy="102" rx="31" ry="27" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.6"/>
      <ellipse cx="56" cy="128" rx="9" ry="6.5" fill="#D8838B" stroke="#1B2620" stroke-width="2.2"/>
      <ellipse cx="88" cy="128" rx="9" ry="6.5" fill="#D8838B" stroke="#1B2620" stroke-width="2.2"/>
      <!-- Tai trái & phải -->
      <path d="M42 42 C34 24, 44 15, 56 23 C59 26, 57 37, 52 42 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.6" stroke-linejoin="round"/>
      <path d="M102 42 C110 24, 100 15, 88 23 C85 26, 87 37, 92 42 Z" fill="#FBB4B9" stroke="#1B2620" stroke-width="2.6" stroke-linejoin="round"/>
      <!-- Đầu heo -->
      <ellipse cx="72" cy="54" rx="34" ry="29" fill="#FBB8BD" stroke="#1B2620" stroke-width="2.6"/>
      <ellipse cx="63" cy="37" rx="14" ry="6" fill="#FFD9DC" opacity="0.55"/>
      <!-- Mắt tò mò -->
      <circle cx="57" cy="49" r="3.9" fill="#1B2620"/>
      <circle cx="55.8" cy="47.7" r="1.2" fill="#FFFFFF"/>
      <circle cx="87" cy="49" r="3.9" fill="#1B2620"/>
      <circle cx="85.8" cy="47.7" r="1.2" fill="#FFFFFF"/>
      <!-- Má hồng -->
      <ellipse cx="48" cy="57" rx="5" ry="3" fill="#F47280" opacity="0.55"/>
      <ellipse cx="96" cy="57" rx="5" ry="3" fill="#F47280" opacity="0.55"/>
      <!-- Mũi bầu dục -->
      <ellipse cx="72" cy="60" rx="13.5" ry="9" fill="#F48B94" stroke="#1B2620" stroke-width="2.4"/>
      <ellipse cx="67.5" cy="60" rx="2.3" ry="4" fill="#1B2620"/>
      <ellipse cx="76.5" cy="60" rx="2.3" ry="4" fill="#1B2620"/>
      <!-- Miệng nhỏ -->
      <path d="M68 72.5 Q72 75 76 72.5" stroke="#1B2620" stroke-width="2.3" stroke-linecap="round" fill="none"/>
      <!-- Khăn quàng sọc xanh trắng -->
      <path d="M43 80 Q72 88 101 80 L72 102 Z" fill="#16A36A" stroke="#1B2620" stroke-width="2.4" stroke-linejoin="round"/>
      <path d="M52 86 L92 86" stroke="#FFFFFF" stroke-width="2.8" stroke-linecap="round"/>
      <path d="M61 93 L83 93" stroke="#FFFFFF" stroke-width="2.6" stroke-linecap="round"/>
    </svg>
    """)
