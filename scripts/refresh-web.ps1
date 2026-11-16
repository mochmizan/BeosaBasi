# BeosaBasi: rebuild + redeploy web after a tunnel refresh (TK-004 interim).
# Usage: .\scripts\refresh-web.ps1
# Reads the API URL from /opt/beosabasi/api-url.txt on the VPS, rebuilds
# apps/web with it baked in, and deploys to /opt/beosabasi/app.
$ErrorActionPreference = "Stop"
$Vps = "ubuntu@43.173.11.117"

$apiUrl = ssh -o BatchMode=yes $Vps `
  "sudo -u beosabasi cat /opt/beosabasi/api-url.txt" | Select-Object -First 1
$apiUrl = $apiUrl.Trim()
if (-not $apiUrl.StartsWith("https://")) { throw "API URL invalid: $apiUrl" }
Write-Host "API_URL=$apiUrl"

$env:VITE_API_BASE_URL = $apiUrl
npm run build --prefix apps/web | Select-Object -Last 3

$tar = "$env:TEMP\webdist.tar"
if (Test-Path $tar) { Remove-Item $tar }
tar -cf $tar -C apps/web/dist .
scp $tar "${Vps}:/tmp/webdist.tar"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes(
  "sudo -u beosabasi tar -xf /tmp/webdist.tar -C /opt/beosabasi/app && rm /tmp/webdist.tar"))
ssh -o BatchMode=yes $Vps "echo $b64 | base64 -d | bash"

$webUrl = (ssh -o BatchMode=yes $Vps "sudo -u beosabasi cat /opt/beosabasi/web-url.txt" | Select-Object -First 1).Trim()
Write-Host "Checking $webUrl ..."
python -c "import httpx; print('web:', httpx.get('$webUrl'.strip(), timeout=60).status_code)"
Write-Host "REFRESH-WEB-OK"
