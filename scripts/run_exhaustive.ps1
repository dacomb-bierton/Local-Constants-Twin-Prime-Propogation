# Windows / PowerShell version of run_exhaustive.sh
#   .\scripts\run_exhaustive.ps1            # 1e10: ~40 GB RAM for gaps, ~20 GB for propagation
#   .\scripts\run_exhaustive.ps1 1e9        # rehearsal, ~5 GB, a few minutes
param([string]$Limit = "1e10")
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path results | Out-Null

Write-Host "== gaps --limit $Limit"
python -m twinconj gaps --limit $Limit --model --out "results/gaps_$Limit.txt"

Write-Host "== propagation --limit $Limit"
python -m twinconj propagation --limit $Limit --out "results/propagation_$Limit.txt"

Write-Host "done; outputs in results/gaps_$Limit.txt and results/propagation_$Limit.txt"
