# TTBoost Production Test Suite
# Тестирование всех основных функций API

$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ODQxOGRhYy04N2I4LTRkZTMtOTVlNi1kNDlkMzk2MWZhOGUiLCJpYXQiOjE3NjM0ODcyNjcsImV4cCI6MTc2MzU3MzY2N30.jiQRkeZKEFAuTQx6IQ4WDJerQN6-fb4ZjZYOc9CPRk4"
$apiBase = "https://api.ttboost.pro"

Write-Host "`n=== TTBoost v2 Production Tests ===" -ForegroundColor Cyan
Write-Host "API: $apiBase" -ForegroundColor Cyan
Write-Host "Date: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n" -ForegroundColor Cyan

# Test 1: Health Check
Write-Host "[1/6] Health Check..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod "$apiBase/"
    Write-Host "  ✅ Status: $($health.status)" -ForegroundColor Green
    Write-Host "  ✅ Environment: $($health.env)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed: $_" -ForegroundColor Red
}

# Test 2: Profile
Write-Host "`n[2/6] Get Profile..." -ForegroundColor Yellow
try {
    $profile = Invoke-RestMethod "$apiBase/v2/auth/me" `
        -Headers @{ "Authorization" = "Bearer $token" }
    Write-Host "  ✅ User: $($profile.username)" -ForegroundColor Green
    Write-Host "  ✅ Voice: $($profile.voice_id)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed: $_" -ForegroundColor Red
}

# Test 3: List Sounds
Write-Host "`n[3/6] List Sounds..." -ForegroundColor Yellow
try {
    $sounds = Invoke-RestMethod "$apiBase/v2/sounds/list" `
        -Headers @{ "Authorization" = "Bearer $token" }
    Write-Host "  ✅ Total sounds: $($sounds.sounds.Count)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed: $_" -ForegroundColor Red
}

# Test 4: List Triggers
Write-Host "`n[4/6] List Triggers..." -ForegroundColor Yellow
try {
    $triggers = Invoke-RestMethod "$apiBase/v2/triggers/list" `
        -Headers @{ "Authorization" = "Bearer $token" }
    Write-Host "  ✅ Total triggers: $($triggers.triggers.Count)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed: $_" -ForegroundColor Red
}

# Test 5: Create Trigger
Write-Host "`n[5/6] Create Trigger..." -ForegroundColor Yellow
try {
    $triggerData = @{
        event_type = "gift"
        condition_key = "gift_name"
        condition_value = "Rose"
        action = "tts"
        action_params = @{
            text_template = "{user} подарил розу!"
        }
    } | ConvertTo-Json

    $newTrigger = Invoke-RestMethod -Method POST "$apiBase/v2/triggers/set" `
        -Headers @{ 
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $triggerData
    
    Write-Host "  ✅ Trigger created: $($newTrigger.id)" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Trigger may already exist or validation failed" -ForegroundColor Yellow
}

# Test 6: Update Settings
Write-Host "`n[6/6] Update Settings..." -ForegroundColor Yellow
try {
    $settingsData = @{
        tts_volume = 80
        gifts_volume = 90
    } | ConvertTo-Json

    $updated = Invoke-RestMethod -Method POST "$apiBase/v2/settings/update" `
        -Headers @{ 
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        } `
        -Body $settingsData
    
    Write-Host "  ✅ Settings updated" -ForegroundColor Green
    Write-Host "  ✅ TTS Volume: $($updated.tts_volume)" -ForegroundColor Green
    Write-Host "  ✅ Gifts Volume: $($updated.gifts_volume)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed: $_" -ForegroundColor Red
}

Write-Host "`n=== Tests Completed ===" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor White
Write-Host "  • Test WebSocket: wscat -c 'wss://api.ttboost.pro/v2/ws?token=$token'" -ForegroundColor Gray
Write-Host "  • Upload sound: Run test_upload.ps1" -ForegroundColor Gray
Write-Host "  • Connect mobile app to https://api.ttboost.pro" -ForegroundColor Gray
