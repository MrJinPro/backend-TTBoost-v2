$zipPath = "$env:USERPROFILE\Downloads\flutter_windows.zip"

if (-not (Test-Path $zipPath)) {
    Write-Host "ZIP file not found. Downloading..." -ForegroundColor Yellow
    $url = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.5-stable.zip"
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $zipPath
    $ProgressPreference = 'Continue'
}

$zipSize = (Get-Item $zipPath).Length / 1MB
Write-Host "ZIP size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Cyan

Write-Host "Extracting with tar..." -ForegroundColor Green
tar -xf $zipPath -C C:\

if (Test-Path "C:\flutter\bin\flutter.bat") {
    Write-Host "`nSUCCESS! Flutter installed to C:\flutter" -ForegroundColor Green
    
    # Add to PATH
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ($userPath -notlike "*C:\flutter\bin*") {
        [Environment]::SetEnvironmentVariable("Path", "$userPath;C:\flutter\bin", "User")
        Write-Host "Added C:\flutter\bin to PATH" -ForegroundColor Green
    }
    
    Write-Host "`nNEXT STEPS:" -ForegroundColor Yellow
    Write-Host "1. RESTART this PowerShell window" -ForegroundColor White
    Write-Host "2. Run: flutter doctor" -ForegroundColor White
    Write-Host "3. Run: cd mobile" -ForegroundColor White
    Write-Host "4. Run: flutter pub get" -ForegroundColor White
    Write-Host "5. Run: flutter run -d chrome" -ForegroundColor White
} else {
    Write-Host "`nERROR: Flutter installation failed!" -ForegroundColor Red
    Write-Host "Check C:\flutter folder manually" -ForegroundColor Yellow
}
