# Альтернативный способ установки Flutter

Write-Host "`n=== Установка Flutter ===" -ForegroundColor Cyan
Write-Host "Автоматическая установка не сработала." -ForegroundColor Yellow
Write-Host "`nВыберите вариант:`n" -ForegroundColor Cyan

Write-Host "1. Открыть официальную страницу загрузки (РЕКОМЕНДУЕТСЯ)" -ForegroundColor Green
Write-Host "2. Скачать напрямую (300+ МБ)" -ForegroundColor Yellow
Write-Host "3. Использовать Git clone (требуется Git)" -ForegroundColor Yellow

$choice = Read-Host "`nВведите номер (1-3)"

switch ($choice) {
    "1" {
        Write-Host "`nОткрываю браузер..." -ForegroundColor Cyan
        Start-Process "https://docs.flutter.dev/get-started/install/windows"
        
        Write-Host "`n📋 Инструкция:" -ForegroundColor Cyan
        Write-Host "1. Скачайте Flutter SDK ZIP"
        Write-Host "2. Распакуйте в C:\flutter"
        Write-Host "3. Добавьте C:\flutter\bin в PATH"
        Write-Host "4. Перезапустите PowerShell"
        Write-Host "5. Выполните: flutter doctor`n"
    }
    
    "2" {
        Write-Host "`nСкачивание начнётся в браузере..." -ForegroundColor Cyan
        Start-Process "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.5-stable.zip"
        
        Write-Host "`n📋 После скачивания:" -ForegroundColor Cyan
        Write-Host "1. Распакуйте ZIP в C:\"
        Write-Host "2. Выполните: setx PATH `"%PATH%;C:\flutter\bin`""
        Write-Host "3. Перезапустите PowerShell"
        Write-Host "4. Выполните: flutter doctor`n"
    }
    
    "3" {
        Write-Host "`nКлонирование через Git..." -ForegroundColor Cyan
        $hasGit = Get-Command git -ErrorAction SilentlyContinue
        
        if ($hasGit) {
            Set-Location C:\
            git clone https://github.com/flutter/flutter.git -b stable
            
            Write-Host "`nДобавление в PATH..." -ForegroundColor Cyan
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;C:\flutter\bin", "User")
            
            Write-Host "✅ Готово! Перезапустите PowerShell и выполните: flutter doctor" -ForegroundColor Green
        } else {
            Write-Host "❌ Git не найден. Установите Git или выберите вариант 1 или 2" -ForegroundColor Red
        }
    }
    
    default {
        Write-Host "❌ Неверный выбор" -ForegroundColor Red
    }
}

Write-Host "`n💡 После установки Flutter:" -ForegroundColor Cyan
Write-Host "   cd D:\Projects\ttboost-mobile\mobile"
Write-Host "   flutter pub get"
Write-Host "   flutter run -d chrome`n"
