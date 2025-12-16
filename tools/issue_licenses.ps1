param(
  [Parameter(Mandatory=$false)][string]$BaseUrl = "http://127.0.0.1:8000",
  [Parameter(Mandatory=$true)][string]$AdminApiKey,
  [Parameter(Mandatory=$false)][ValidateSet("nova_streamer_one_mobile","nova_streamer_one_desktop","nova_streamer_duo")][string]$Plan = "nova_streamer_one_mobile",
  [Parameter(Mandatory=$false)][int]$TtlDays = 30,
  [Parameter(Mandatory=$false)][int]$Count = 10,
  [Parameter(Mandatory=$false)][string]$Prefix = "TTB"
)

$uri = "$BaseUrl/v2/license/issue-bulk"
$headers = @{ "Admin-Api-Key" = $AdminApiKey; "Content-Type" = "application/json" }
$body = @{ plan = $Plan; ttl_days = $TtlDays; count = $Count; prefix = $Prefix } | ConvertTo-Json

Write-Host "POST $uri" -ForegroundColor Cyan
$response = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -Body $body
$response.items | Select-Object key, plan, expires_at | Format-Table
