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

function Import-LocalEnvFile {
  param([string]$Path)

  if (-not (Test-Path $Path)) { return }

  Get-Content -Path $Path -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }

    $idx = $line.IndexOf('=')
    if ($idx -lt 1) { return }

    $name = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "Env:$name" -Value $value
  }
}

Import-LocalEnvFile (Join-Path $PSScriptRoot ".env.local")

$lines = Get-Content -Path $pubspecPath -Encoding UTF8

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

  $defines = @()
  if ($env:SUPABASE_URL) { $defines += "--dart-define=SUPABASE_URL=$($env:SUPABASE_URL)" }
  if ($env:SUPABASE_ANON_KEY) { $defines += "--dart-define=SUPABASE_ANON_KEY=$($env:SUPABASE_ANON_KEY)" }
  if ($env:API_BASE_URL) { $defines += "--dart-define=API_BASE_URL=$($env:API_BASE_URL)" }
  if ($env:WS_URL) { $defines += "--dart-define=WS_URL=$($env:WS_URL)" }
  if ($env:MEDIA_BASE_URL) { $defines += "--dart-define=MEDIA_BASE_URL=$($env:MEDIA_BASE_URL)" }
  if ($env:SPOTIFY_CLIENT_ID) { $defines += "--dart-define=SPOTIFY_CLIENT_ID=$($env:SPOTIFY_CLIENT_ID)" }
  if ($env:SPOTIFY_REDIRECT_URI) { $defines += "--dart-define=SPOTIFY_REDIRECT_URI=$($env:SPOTIFY_REDIRECT_URI)" }

  flutter build apk --release @defines
  if ($LASTEXITCODE -ne 0) { throw "flutter build apk --release failed" }

  $apk = Join-Path $PSScriptRoot "build\app\outputs\flutter-apk\app-release.apk"
  if (Test-Path $apk) {
    Write-Host "APK: $apk" -ForegroundColor Cyan
  }
} finally {
  Pop-Location
}
