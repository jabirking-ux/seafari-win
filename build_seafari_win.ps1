<#
.SYNOPSIS
  Builds and patches Seafari for Windows.
.DESCRIPTION
  Applies the Safari UI assets, disables telemetry/crash reporters, applies PE branding and icon resources.
.EXAMPLE
  .\build_seafari_win.ps1
.EXAMPLE
  .\build_seafari_win.ps1 -FirefoxDir "C:\path\to\firefox"
#>
param(
    [string]$FirefoxDir = "$env:LOCALAPPDATA\Programs\Seafari",
    [string]$UblockXpi = "",
    [string]$AtbcXpi = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Seafari for Windows - Build & Patch Pipeline" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

if (-not $UblockXpi) {
    $UblockXpi = Join-Path $FirefoxDir "distribution\extensions\uBlock0@raymondhill.net.xpi"
}
if (-not $AtbcXpi) {
    $AtbcXpi = Join-Path $FirefoxDir "distribution\extensions\ATBC@EasonWong.xpi"
}

python "$repoRoot\scripts\patch_windows_firefox.py" --firefox-dir "$FirefoxDir" --ublock-xpi "$UblockXpi" --atbc-xpi "$AtbcXpi"

Write-Host "`n[+] Seafari Windows build completed successfully!" -ForegroundColor Green
