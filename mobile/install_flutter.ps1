Write-Host "Flutter Installer for Windows" -ForegroundColor Cyan
Write-Host "============================`n" -ForegroundColor Cyan

$flutterUrl = "https://storage.googleapis.com/flutter_infra_release/releases/stable/windows/flutter_windows_3.24.5-stable.zip"
$downloadPath = "$env:USERPROFILE\Downloads\flutter_windows.zip"

# Check existing installation
if (Test-Path "C:\flutter\bin\flutter.bat") {
    Write-Host "Flutter already installed in C:\flutter" -ForegroundColor Green
    
    $addToPath = Read-Host "`nAdd to PATH automatically? (y/n)"
    if ($addToPath -eq "y") {
        $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
        if ($currentPath -notlike "*C:\flutter\bin*") {
            [Environment]::SetEnvironmentVariable("Path", "$currentPath;C:\flutter\bin", "User")
            Write-Host "Added to PATH. RESTART PowerShell!" -ForegroundColor Green
        } else {
            Write-Host "Already in PATH" -ForegroundColor Green
        }
    }
    exit 0
}

Write-Host "Downloading Flutter SDK..." -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri $flutterUrl -OutFile $downloadPath -UseBasicParsing
    Write-Host "Downloaded: $downloadPath" -ForegroundColor Green
} catch {
    Write-Host "Download error: $_" -ForegroundColor Red
    Write-Host "`nManual download: https://docs.flutter.dev/get-started/install/windows" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nExtracting to C:\flutter..." -ForegroundColor Cyan
try {
    Expand-Archive -Path $downloadPath -DestinationPath "C:\" -Force
    Write-Host "Extracted to C:\flutter" -ForegroundColor Green
} catch {
    Write-Host "Extract error: $_" -ForegroundColor Red
    exit 1
}

Write-Host "`nAdding to PATH..." -ForegroundColor Cyan
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*C:\flutter\bin*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;C:\flutter\bin", "User")
    Write-Host "Added to PATH" -ForegroundColor Green
} else {
    Write-Host "Already in PATH" -ForegroundColor Green
}

Write-Host "`nRESTART PowerShell and run:" -ForegroundColor Yellow
Write-Host "  flutter doctor`n" -ForegroundColor White

Remove-Item $downloadPath -Force -ErrorAction SilentlyContinue
