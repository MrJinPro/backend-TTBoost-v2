Write-Host "Flutter SDK Installation" -ForegroundColor Cyan
Write-Host "======================`n" -ForegroundColor Cyan

$url = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.5-stable.zip"
$downloadPath = "$env:USERPROFILE\Downloads\flutter_windows.zip"
$extractPath = "C:\"

# Download with progress
Write-Host "Downloading Flutter SDK (300+ MB)..." -ForegroundColor Yellow
Write-Host "This may take 5-10 minutes depending on your connection`n" -ForegroundColor Gray

try {
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $downloadPath -UseBasicParsing
    $ProgressPreference = 'Continue'
    
    $fileSize = [Math]::Round((Get-Item $downloadPath).Length / 1MB, 2)
    Write-Host "Downloaded: $fileSize MB" -ForegroundColor Green
    
    if ($fileSize -lt 200) {
        Write-Host "ERROR: File too small, download incomplete" -ForegroundColor Red
        Remove-Item $downloadPath -Force
        exit 1
    }
    
} catch {
    Write-Host "Download failed: $_" -ForegroundColor Red
    Write-Host "`nPlease download manually from:" -ForegroundColor Yellow
    Write-Host "https://docs.flutter.dev/get-started/install/windows`n" -ForegroundColor White
    exit 1
}

# Extract
Write-Host "`nExtracting to C:\flutter..." -ForegroundColor Yellow
try {
    if (Test-Path "C:\flutter") {
        Write-Host "Removing old Flutter installation..." -ForegroundColor Gray
        Remove-Item "C:\flutter" -Recurse -Force -ErrorAction SilentlyContinue
    }
    
    Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
    Write-Host "Extracted successfully" -ForegroundColor Green
    
} catch {
    Write-Host "Extract failed: $_" -ForegroundColor Red
    exit 1
}

# Add to PATH
Write-Host "`nAdding to PATH..." -ForegroundColor Yellow
$flutterBin = "C:\flutter\bin"
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")

if ($currentPath -notlike "*$flutterBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$flutterBin", "User")
    Write-Host "Added to PATH" -ForegroundColor Green
} else {
    Write-Host "Already in PATH" -ForegroundColor Green
}

# Verify
Write-Host "`nVerifying installation..." -ForegroundColor Yellow
if (Test-Path "C:\flutter\bin\flutter.bat") {
    Write-Host "Flutter installed successfully!" -ForegroundColor Green
    
    Write-Host "`n" + "="*50 -ForegroundColor Cyan
    Write-Host "NEXT STEPS:" -ForegroundColor Cyan
    Write-Host "="*50 -ForegroundColor Cyan
    Write-Host "`n1. CLOSE and REOPEN PowerShell" -ForegroundColor Yellow
    Write-Host "2. Run: flutter doctor" -ForegroundColor White
    Write-Host "3. Run: cd D:\Projects\ttboost-mobile\mobile" -ForegroundColor White
    Write-Host "4. Run: flutter pub get" -ForegroundColor White
    Write-Host "5. Run: flutter run -d chrome`n" -ForegroundColor White
    
} else {
    Write-Host "Installation verification failed" -ForegroundColor Red
}

# Cleanup
Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
Write-Host "Cleaned up temporary files`n" -ForegroundColor Gray
