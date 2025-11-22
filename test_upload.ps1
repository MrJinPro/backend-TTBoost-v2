
$mp3Header = @(
    0x49, 0x44, 0x33, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xFF, 0xFB, 0x90, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
) * 50

[System.IO.File]::WriteAllBytes("$PSScriptRoot\test_sound.mp3", [byte[]]$mp3Header)

# Загружаем звук
$token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI3ODQxOGRhYy04N2I4LTRkZTMtOTVlNi1kNDlkMzk2MWZhOGUiLCJpYXQiOjE3NjM0ODcyNjcsImV4cCI6MTc2MzU3MzY2N30.jiQRkeZKEFAuTQx6IQ4WDJerQN6-fb4ZjZYOc9CPRk4"

try {
    $response = Invoke-RestMethod -Method POST "https://api.ttboost.pro/v2/sounds/upload" `
        -Headers @{ "Authorization" = "Bearer $token" } `
        -Form @{ file = Get-Item "$PSScriptRoot\test_sound.mp3" }
    
    Write-Host "✅ Sound uploaded successfully!" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "❌ Upload failed: $_" -ForegroundColor Red
    $_.Exception.Response.StatusCode
}

Remove-Item "$PSScriptRoot\test_sound.mp3" -ErrorAction SilentlyContinue
