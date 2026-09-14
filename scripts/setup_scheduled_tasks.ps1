# ==============================================================================
# Destek Talep Sistemi - Windows Görev Zamanlayıcısı (Task Scheduler) Kurulum Betiği
# Yönetici olarak PowerShell konsolunda çalıştırınız.
# ==============================================================================

$ProjectDir = (Get-Item -Path $PSScriptRoot\..).FullName
$PythonExe = Join-Path $ProjectDir "venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "HATA: Python sanal ortamı bulunamadı: $PythonExe" -ForegroundColor Red
    exit 1
}

Write-Host "Destek Talep Sistemi görevleri Windows Görev Zamanlayıcısına kaydediliyor..." -ForegroundColor Cyan
Write-Host "Proje Dizini: $ProjectDir"
Write-Host "Python Yolu: $PythonExe"

# 1. Görev: Her 15 dakikada bir SLA Denetimi
$SlaAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py check_sla_breaches" -WorkingDirectory $ProjectDir
$SlaTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
Register-ScheduledTask -TaskName "SupportTicket_CheckSLA" -Action $SlaAction -Trigger $SlaTrigger -Description "Destek Talep Sistemi 15 dakikalık SLA ihlal kontrolü" -Force

# 2. Görev: Haftalık Pasif Hesap Temizliği (Her Pazar 03:00)
$CleanupAction = New-ScheduledTaskAction -Execute $PythonExe -Argument "manage.py cleanup_unverified_accounts" -WorkingDirectory $ProjectDir
$CleanupTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00AM
Register-ScheduledTask -TaskName "SupportTicket_CleanupAccounts" -Action $CleanupAction -Trigger $CleanupTrigger -Description "Destek Talep Sistemi haftalık onaylanmamış hesap temizliği" -Force

Write-Host "Başarılı! Görevler Windows Görev Zamanlayıcısına (Task Scheduler) eklendi:" -ForegroundColor Green
Write-Host " - SupportTicket_CheckSLA (Her 15 dakikada bir)" -ForegroundColor Yellow
Write-Host " - SupportTicket_CleanupAccounts (Haftada bir Pazar 03:00)" -ForegroundColor Yellow
