# 🧪 Тестирование TTBoost v2 API (без Flutter)

## Быстрый тест через PowerShell

### 1. Активация лицензии (первый раз)

```powershell
$license = "TTB-9E2E-5DE1-A3FC"
$username = "myuser123"
$password = "MyPass123!"

$body = @{
    license_key = $license
    username = $username
    password = $password
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/auth/redeem-license" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$token = $response.access_token
Write-Host "✅ JWT Token: $token"
Write-Host "✅ User ID: $($response.user_id)"
```

### 2. Вход (повторный)

```powershell
$username = "streamer123"
$password = "Test123!"

$body = @{
    username = $username
    password = $password
} | ConvertTo-Json

$response = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/auth/login" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

$token = $response.access_token
Write-Host "✅ JWT Token: $token"
```

### 3. Получение профиля

```powershell
$headers = @{
    Authorization = "Bearer $token"
}

$profile = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/auth/me" `
    -Headers $headers

Write-Host "✅ Профиль:"
$profile | Format-List
```

### 4. Настройка TikTok username

```powershell
$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}

$body = @{
    tiktok_username = "your_tiktok_name"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/settings/update" `
    -Method POST `
    -Headers $headers `
    -Body $body

Write-Host "✅ TikTok username обновлен"
```

### 5. Загрузка звука

```powershell
# Создаем тестовый MP3
$mp3Bytes = [byte[]](0xFF, 0xFB, 0x90, 0x00) * 100  # Минимальный MP3 заголовок

$boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "multipart/form-data; boundary=$boundary"
}

# Формирование multipart/form-data
$bodyLines = @(
    "--$boundary",
    'Content-Disposition: form-data; name="file"; filename="test.mp3"',
    'Content-Type: audio/mpeg',
    '',
    [System.Text.Encoding]::Latin1.GetString($mp3Bytes),
    "--$boundary--"
)

$bodyContent = $bodyLines -join "`r`n"

Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/sounds/upload" `
    -Method POST `
    -Headers $headers `
    -Body $bodyContent

Write-Host "✅ Звук загружен"
```

### 6. Список звуков

```powershell
$sounds = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/sounds/list" `
    -Headers @{ Authorization = "Bearer $token" }

Write-Host "✅ Загруженные звуки:"
$sounds.sounds | Format-Table
```

### 7. Создание триггера

```powershell
$headers = @{
    Authorization = "Bearer $token"
    "Content-Type" = "application/json"
}

$body = @{
    event_type = "gift"
    condition_key = "gift_name"
    condition_value = "Rose"
    action = "play_sound"
    action_params = @{
        sound_filename = "test.mp3"
    }
    enabled = $true
    priority = 0
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/triggers/set" `
    -Method POST `
    -Headers $headers `
    -Body $body

Write-Host "✅ Триггер создан"
```

### 8. Список триггеров

```powershell
$triggers = Invoke-RestMethod -Uri "https://api.ttboost.pro/v2/triggers/list" `
    -Headers @{ Authorization = "Bearer $token" }

Write-Host "✅ Триггеры:"
$triggers.triggers | Format-Table
```

## Полный тестовый скрипт

Сохраните как `test_mobile_api.ps1` и запустите:

```powershell
powershell -ExecutionPolicy Bypass -File test_mobile_api.ps1
```
