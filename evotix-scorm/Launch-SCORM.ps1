# Evotix SCORM Studio launcher. No administrator rights required.
# Double-click Launch-SCORM.bat, or run this script from PowerShell.

$ErrorActionPreference = "Continue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$Drive = (Get-Item $Here).PSDrive
Write-Host "Evotix SCORM Studio"
Write-Host "Folder: $Here"
try {
    $Disk = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='$($Drive.Name):'" -ErrorAction SilentlyContinue
    if ($Disk -and $Disk.DriveType -eq 2) {
        Write-Host "Removable drive detected. Running from USB."
    }
} catch {
    Write-Host "Drive type was not checked."
}

$Script = Join-Path $Here "evotix_scorm_gui.py"
$Portable = Join-Path $Here "python-portable\python.exe"
if (Test-Path -LiteralPath $Portable) {
    & $Portable $Script
    exit $LASTEXITCODE
}
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $Script
    exit $LASTEXITCODE
}
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $Script
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Python 3 was not found. This launcher does not need an administrator."
Write-Host "Either install Python for your user, or unzip the Windows embeddable package into:"
Write-Host "  $Here\python-portable\"
Write-Host "Then run this launcher again."
exit 1
