# Build release APK with auto-incremented build number in pubspec.yaml
# Usage:
#   .\build_apk_release.ps1
#   .\build_apk_release.ps1 -BuildName 0.1.1

param(
  [string]$BuildName = ""
)

$ErrorActionPreference = "Stop"

$pubspecPath = Join-Path $PSScriptRoot "pubspec.yaml"
if (-not (Test-Path $pubspecPath)) {
  throw "pubspec.yaml not found at: $pubspecPath"
}

$lines = Get-Content -Path $pubspecPath -Encoding UTF8
$idx = ($lines | ForEach-Object { $_ }) | Select-Object -Index (0..($lines.Count-1)) -ErrorAction SilentlyContinue | Out-Null

$versionLineIndex = -1
for ($i = 0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '^version:\s*(.+)\s*$') {
    $versionLineIndex = $i
    break
  }
}
if ($versionLineIndex -lt 0) {
  throw "version: line not found in pubspec.yaml"
}

$current = ($lines[$versionLineIndex] -replace '^version:\s*', '').Trim()

# Expected: name+build (e.g. 0.1.0+1)
$name = $current
$build = 1
if ($current -match '^([^\+]+)\+(\d+)$') {
  $name = $Matches[1]
  $build = [int]$Matches[2]
}

if (-not [string]::IsNullOrWhiteSpace($BuildName)) {
  $name = $BuildName.Trim()
}

$newBuild = $build + 1
$newVersion = "$name+$newBuild"
$lines[$versionLineIndex] = "version: $newVersion"

# Write back
Set-Content -Path $pubspecPath -Value $lines -Encoding UTF8

Write-Host "Updated pubspec version: $current -> $newVersion" -ForegroundColor Green

Push-Location $PSScriptRoot
try {
  flutter pub get
  if ($LASTEXITCODE -ne 0) { throw "flutter pub get failed" }

  flutter build apk --release
  if ($LASTEXITCODE -ne 0) { throw "flutter build apk --release failed" }

  $apk = Join-Path $PSScriptRoot "build\app\outputs\flutter-apk\app-release.apk"
  if (Test-Path $apk) {
    Write-Host "APK: $apk" -ForegroundColor Cyan
  }
} finally {
  Pop-Location
}
