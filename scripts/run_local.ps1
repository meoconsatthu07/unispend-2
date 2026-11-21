<#
.SYNOPSIS
    Khởi chạy UniSpend 2.0 (Lịch Tài Chính Cá Nhân + AI OCR Hóa Đơn + Giọng Nói Tiếng Việt) trên máy tính cá nhân.
.DESCRIPTION
    Sử dụng đúng entry point có sẵn của repository (main.py và app.py), không sửa file bị khóa.
    - Mặc định: chạy cục bộ tại http://127.0.0.1:8501
    - Tùy chọn -Lan: chạy tại 0.0.0.0:8501 để điện thoại cùng mạng Wi-Fi truy cập.
    - Tùy chọn -Demo: chạy với cơ sở dữ liệu mẫu tách riêng (data/demo.db).
#>
param(
    [switch]$Lan,
    [switch]$Demo,
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -Path $ProjectRoot

$PythonExe = "python"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
}

$HostAddr = if ($Lan) { "0.0.0.0" } else { "127.0.0.1" }
$AppArgs = if ($Demo) { @("--demo") } else { @("--db", "data/expenses.db") }

Write-Host "============================================================================" -ForegroundColor DarkGreen
Write-Host "  UNISPEND 2.0 — PERSONAL FINANCE CALENDAR + AI OCR + VOICE ASSISTANT" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor DarkGreen

if ($Lan) {
    Write-Host "[CHẾ ĐỘ MẠNG NỘI BỘ WI-FI (LAN)]" -ForegroundColor Cyan
    Write-Host "  Máy tính lắng nghe tại: ${HostAddr}:${Port}"
    try {
        $Ips = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -ExpandProperty IPAddress
        foreach ($ip in $Ips) {
            Write-Host "  -> Truy cập trên điện thoại cùng Wi-Fi: http://${ip}:${Port}" -ForegroundColor Yellow
        }
    } catch {}
    Write-Host "----------------------------------------------------------------------------"
    & $PythonExe -m streamlit run app.py "--server.address=$HostAddr" "--server.port=$Port" "--browser.gatherUsageStats=false" -- @AppArgs
} else {
    Write-Host "[CHẾ ĐỘ MÁY TÍNH CÁ NHÂN (LOCALHOST)]" -ForegroundColor Cyan
    Write-Host "  -> Mở trình duyệt tại: http://127.0.0.1:${Port}" -ForegroundColor Yellow
    Write-Host "  -> Mở cho điện thoại cùng Wi-Fi: .\run_local.ps1 -Lan"
    Write-Host "  -> Mở dữ liệu mẫu:              .\run_local.ps1 -Demo"
    Write-Host "----------------------------------------------------------------------------"
    if ($Port -eq 8501) {
        if ($Demo) {
            & $PythonExe main.py --demo
        } else {
            & $PythonExe main.py --legacy
        }
    } else {
        & $PythonExe -m streamlit run app.py "--server.address=127.0.0.1" "--server.port=$Port" "--browser.gatherUsageStats=false" -- @AppArgs
    }
}
