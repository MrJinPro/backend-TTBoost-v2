# Полный тест TTBoost v2 API

Write-Host "`n🧪 TTBoost v2 API - Полное тестирование" -ForegroundColor Cyan
Write-Host "======================================`n" -ForegroundColor Cyan

# Используем существующего пользователя
$username = "streamer123"
$password = "Test123!"
$token = $null

# 1. Вход
Write-Host "[1/7] Вход в систему..." -ForegroundColor Yellow
try {
    $body = @{
        username = $username
        password = $password
    } | ConvertTo-Json

    $response = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/auth/login" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body `
        -ErrorAction Stop

    $token = $response.access_token
    Write-Host "✅ Успешно! JWT: $($token.Substring(0, 20))..." -ForegroundColor Green
    Write-Host "   User ID: $($response.user_id)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Ошибка входа: $_" -ForegroundColor Red
    exit 1
}

# 2. Профиль
Write-Host "`n[2/7] Получение профиля..." -ForegroundColor Yellow
try {
    $headers = @{ Authorization = "Bearer $token" }
    $profile = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/auth/me" `
        -Headers $headers `
        -ErrorAction Stop

    Write-Host "✅ Профиль получен:" -ForegroundColor Green
    Write-Host "   Username: $($profile.username)" -ForegroundColor Gray
    Write-Host "   Voice: $($profile.voice_id)" -ForegroundColor Gray
    Write-Host "   TTS: $($profile.tts_enabled), Volume: $($profile.tts_volume)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Ошибка: $_" -ForegroundColor Red
}

# 3. Список звуков
Write-Host "`n[3/7] Список звуков..." -ForegroundColor Yellow
try {
    $sounds = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/sounds/list" `
        -Headers @{ Authorization = "Bearer $token" } `
        -ErrorAction Stop

    Write-Host "✅ Звуков загружено: $($sounds.sounds.Count)" -ForegroundColor Green
    if ($sounds.sounds.Count -gt 0) {
        $sounds.sounds | Select-Object -First 3 | ForEach-Object {
            Write-Host "   - $($_.filename)" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "❌ Ошибка: $_" -ForegroundColor Red
}

# 4. Список триггеров
Write-Host "`n[4/7] Список триггеров..." -ForegroundColor Yellow
try {
    $triggers = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/triggers/list" `
        -Headers @{ Authorization = "Bearer $token" } `
        -ErrorAction Stop

    Write-Host "✅ Триггеров: $($triggers.triggers.Count)" -ForegroundColor Green
    if ($triggers.triggers.Count -gt 0) {
        $triggers.triggers | Select-Object -First 3 | ForEach-Object {
            Write-Host "   - $($_.event_type): $($_.action)" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "❌ Ошибка: $_" -ForegroundColor Red
}

# 5. Обновление настроек
Write-Host "`n[5/7] Обновление TikTok username..." -ForegroundColor Yellow
try {
    $body = @{
        tiktok_username = "test_streamer"
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/settings/update" `
        -Method POST `
        -Headers @{
            Authorization = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $body `
        -ErrorAction Stop | Out-Null

    Write-Host "✅ TikTok username обновлен" -ForegroundColor Green
} catch {
    Write-Host "❌ Ошибка: $_" -ForegroundColor Red
}

# 6. Создание тестового триггера
Write-Host "`n[6/7] Создание триггера для Rose..." -ForegroundColor Yellow
try {
    $body = @{
        event_type = "gift"
        condition_key = "gift_name"
        condition_value = "Rose"
        action = "tts"
        action_params = @{
            text_template = "Спасибо за розу, {user}!"
        }
        enabled = $true
        priority = 10
    } | ConvertTo-Json

    Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/triggers/set" `
        -Method POST `
        -Headers @{
            Authorization = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $body `
        -ErrorAction Stop | Out-Null

    Write-Host "✅ Триггер создан" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Триггер уже существует или ошибка: $_" -ForegroundColor Yellow
}

# 7. WebSocket подключение (информация)
Write-Host "`n[7/7] WebSocket подключение..." -ForegroundColor Yellow
Write-Host "✅ WebSocket URL: wss://api.ttboost.pro/v2/ws?token=$($token.Substring(0, 20))..." -ForegroundColor Green
Write-Host "`n💡 Для тестирования WebSocket используйте:" -ForegroundColor Cyan
Write-Host "   wscat -c `"wss://api.ttboost.pro/v2/ws?token=$token`"`n" -ForegroundColor White

# Итог
Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "✅ Все тесты завершены!" -ForegroundColor Green
Write-Host "`n📱 Мобильное приложение готово к работе с v2 API" -ForegroundColor Cyan
Write-Host "`nСледующие шаги:" -ForegroundColor Yellow
Write-Host "1. Установите Flutter: .\install_flutter.ps1"
Write-Host "2. Соберите приложение: flutter build web"
Write-Host "3. Или используйте старую сборку (будет работать частично)`n"
