# Скрипт для запуска мобильного приложения NovaBoost

Write-Host "🚀 NovaBoost Mobile - Запуск приложения" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Cyan

# Проверка Flutter
$flutterInstalled = Get-Command flutter -ErrorAction SilentlyContinue
if (-not $flutterInstalled) {
    Write-Host "❌ Flutter не найден в PATH" -ForegroundColor Red
    Write-Host "`nУстановите Flutter:" -ForegroundColor Yellow
    Write-Host "1. Скачайте: https://flutter.dev/docs/get-started/install/windows"
    Write-Host "2. Распакуйте и добавьте в PATH"
    Write-Host "3. Запустите: flutter doctor`n"
    exit 1
}

Write-Host "✅ Flutter найден" -ForegroundColor Green
flutter --version

function Get-DartDefines {
    $defines = @()
    if ($env:SUPABASE_URL) { $defines += "--dart-define=SUPABASE_URL=$($env:SUPABASE_URL)" }
    if ($env:SUPABASE_ANON_KEY) { $defines += "--dart-define=SUPABASE_ANON_KEY=$($env:SUPABASE_ANON_KEY)" }
    if ($env:API_BASE_URL) { $defines += "--dart-define=API_BASE_URL=$($env:API_BASE_URL)" }
    if ($env:WS_URL) { $defines += "--dart-define=WS_URL=$($env:WS_URL)" }
    if ($env:MEDIA_BASE_URL) { $defines += "--dart-define=MEDIA_BASE_URL=$($env:MEDIA_BASE_URL)" }
    return $defines
}

$dartDefines = Get-DartDefines

# Установка зависимостей
Write-Host "`n📦 Установка зависимостей..." -ForegroundColor Cyan
flutter pub get

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка при установке зависимостей" -ForegroundColor Red
    exit 1
}

# Запуск приложения
Write-Host "`n🎮 Запуск приложения..." -ForegroundColor Cyan
Write-Host "Выберите платформу:" -ForegroundColor Yellow
Write-Host "1. Windows (desktop)"
Write-Host "2. Android (эмулятор/устройство)"
Write-Host "3. Chrome (web)"

$choice = Read-Host "`nВведите номер (1-3)"

switch ($choice) {
    "1" {
        Write-Host "`n🪟 Запуск на Windows..." -ForegroundColor Cyan
        flutter run -d windows @dartDefines
    }
    "2" {
        Write-Host "`n📱 Запуск на Android..." -ForegroundColor Cyan
        flutter run -d android @dartDefines
    }
    "3" {
        Write-Host "`n🌐 Запуск в Chrome..." -ForegroundColor Cyan
        flutter run -d chrome --web-renderer html @dartDefines
    }
    default {
        Write-Host "❌ Неверный выбор" -ForegroundColor Red
        exit 1
    }
}
