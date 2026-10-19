# Developer tool: publish the built T9 dictionaries (dist/dicts) to a GitHub Release.
# Requires GitHub CLI: https://cli.github.com  (once: gh auth login)
#
#   powershell -ExecutionPolicy Bypass -File tools\publish_dicts.ps1 -Repo <user>/TextFixer
#
# The tag is taken from textfixer/languages.py (DICT_TAG). The app downloads dictionaries from:
#   https://github.com/<user>/TextFixer/releases/download/<DICT_TAG>/<lang>.pkl.gz
param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$Tag = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $root "dist\dicts"
if (-not $Tag) {
    $Tag = (Select-String -Path (Join-Path $root "textfixer\languages.py") -Pattern 'DICT_TAG = "(.+)"').Matches[0].Groups[1].Value
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is required: https://cli.github.com" }
if (-not (Test-Path (Join-Path $dist "manifest.json"))) { throw "No $dist\manifest.json - run tools\build_all.py first" }

$files = @(Get-ChildItem $dist -Filter *.pkl.gz | ForEach-Object FullName) + (Join-Path $dist "manifest.json")
$notes = Join-Path $root "THIRD_PARTY_NOTICES.md"
Write-Host "Release $Tag in $Repo : $($files.Count) files"

gh release view $Tag --repo $Repo *> $null
if ($LASTEXITCODE -ne 0) {
    gh release create $Tag --repo $Repo --title "T9 dictionaries ($Tag)" `
        --notes "T9 dictionaries for TextFixer. The app downloads them automatically on first run. Sources and licenses: THIRD_PARTY_NOTICES.md"
}
# 10 files at a time, replacing already uploaded ones
for ($i = 0; $i -lt $files.Count; $i += 10) {
    $chunk = $files[$i..([Math]::Min($i + 9, $files.Count - 1))]
    gh release upload $Tag @chunk --repo $Repo --clobber
}
Write-Host "Done. Don't forget: DICT_REPO = `"$Repo`" in textfixer/languages.py"
