# Запуск NovaBoost Mobile (Web версия)

Write-Host "🌐 NovaBoost Mobile - Запуск Web версии" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

$webPath = "D:\Projects\ttboost-mobile\mobile\build\web"

if (-not (Test-Path "$webPath\index.html")) {
    Write-Host "❌ Web версия не найдена" -ForegroundColor Red
    Write-Host "Соберите приложение с помощью Flutter или используйте готовую сборку`n"
    exit 1
}

Write-Host "✅ Web версия найдена: $webPath" -ForegroundColor Green

# Запуск простого HTTP сервера на Python
$pythonInstalled = Get-Command python -ErrorAction SilentlyContinue

if ($pythonInstalled) {
    Write-Host "`n🚀 Запуск на http://localhost:8080" -ForegroundColor Cyan
    Write-Host "Нажмите Ctrl+C для остановки`n" -ForegroundColor Yellow
    
    Set-Location $webPath
    Start-Process "http://localhost:8080"
    python -m http.server 8080
} else {
    Write-Host "`n⚠️  Python не найден. Альтернативные варианты:" -ForegroundColor Yellow
    Write-Host "`n1. Откройте файл напрямую в браузере:"
    Write-Host "   $webPath\index.html`n" -ForegroundColor White
    
    Write-Host "2. Используйте любой другой веб-сервер"
    Write-Host "   (например, VS Code Live Server расширение)`n"
    
    # Открываем файл напрямую
    Start-Process "$webPath\index.html"
}
