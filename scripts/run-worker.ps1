# Jalankan worker GPU laptop melawan API VPS terkini (TK-034 operasional).
# Membaca URL API aktif dari VPS, jadi tahan terhadap rotasi tunnel.
# Butuh WORKER_TOKEN di environment. Hentikan dengan Ctrl+C.
$ErrorActionPreference = "Stop"
if (-not $env:WORKER_TOKEN) {
  Write-Host "Set WORKER_TOKEN dulu: $env:WORKER_TOKEN='<isi-token>'"
  exit 1
}
$Vps = "ubuntu@43.173.11.117"
$apiUrl = (ssh -o BatchMode=yes $Vps "sudo -u beosabasi cat /opt/beosabasi/api-url.txt" | Select-Object -First 1).Trim()
if (-not $apiUrl.StartsWith("https://")) { throw "URL API VPS tidak terbaca: $apiUrl" }
Write-Host "API: $apiUrl"
& "$PSScriptRoot/../apps/worker/.venv/Scripts/worker.exe" run --api-url $apiUrl
