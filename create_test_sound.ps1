# Генерация тестового MP3 файла

# Минимальный валидный MP3 заголовок
$mp3Header = @(
    0xFF, 0xFB, 0x90, 0x00,  # MPEG Audio Layer 3 header
    0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00
)

# Повторяем для создания файла ~5KB
$mp3Data = $mp3Header * 400

# Сохраняем
$outputPath = "D:\Projects\ttboost-mobile\test_sound.mp3"
[System.IO.File]::WriteAllBytes($outputPath, [byte[]]$mp3Data)

Write-Host "Test MP3 created: $outputPath" -ForegroundColor Green
Write-Host "Size: $([Math]::Round((Get-Item $outputPath).Length / 1KB, 2)) KB" -ForegroundColor Gray

# Также создаём JSON с информацией
@{
    filename = "test_sound.mp3"
    path = $outputPath
    size_bytes = (Get-Item $outputPath).Length
    size_kb = [Math]::Round((Get-Item $outputPath).Length / 1KB, 2)
    created = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    note = "Minimal valid MP3 file for testing upload"
} | ConvertTo-Json | Out-File "D:\Projects\ttboost-mobile\test_sound_info.json"

Write-Host "`nUse this file to test sound upload in the mobile app"
