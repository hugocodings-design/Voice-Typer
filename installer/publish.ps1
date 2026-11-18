# Publishes dist\VoiceTyperSetup-<version>.exe as an automatic update for every installed copy.
#
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1
#   powershell -ExecutionPolicy Bypass -File installer\publish.ps1 -Notes "Corrections diverses" -NotesEn "Bug fixes"
#   … -Required    → required update: installed copies (0.11+) install it by themselves, no "Later" / "Skip"
#
# latest.json is signed with the private key in %USERPROFILE%\.voice-typer\ (installer/sign.py).
# Creates a release on the PUBLIC repository hugocodings-design/Voice-Typer-Releases (installer + latest.json,
# no source code). Installed copies read latest.json (voice_typer/updater.py) and offer the update.
# Needs the GitHub CLI logged in (gh auth status).
param([string]$Notes = "", [string]$NotesEn = "", [switch]$Draft, [switch]$Required)

$ErrorActionPreference = "Continue"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
$repo = "hugocodings-design/Voice-Typer-Releases"

function Fail($text) { Write-Host "`nERREUR : $text" -ForegroundColor Red; exit 1 }

$version = (& $py -c "import voice_typer; print(voice_typer.__version__)").Trim()
$setup = Get-Item "dist\VoiceTyperSetup-$version.exe" -ErrorAction SilentlyContinue
if (-not $setup) { Fail "dist\VoiceTyperSetup-$version.exe introuvable : lancez d'abord installer\build.ps1." }
& gh release view "v$version" --repo $repo *> $null
if ($LASTEXITCODE -eq 0) { Fail "la version $version est déjà publiée : changez le numéro dans voice_typer\__init__.py." }
if (-not $NotesEn) { $NotesEn = $Notes }

Write-Host "Empreinte SHA-256 et signature ed25519…" -ForegroundColor Cyan
$json = Join-Path $root "dist\latest.json"
$env:PYTHONIOENCODING = "utf-8"
$signArgs = @("installer\sign.py", "manifest", "--setup", $setup.FullName, "--version", $version, "--out", $json)
if ($Notes) { $signArgs += @("--notes-fr", $Notes) }     # PowerShell 5.1 drops empty arguments
if ($NotesEn) { $signArgs += @("--notes-en", $NotesEn) }
if ($Required) { $signArgs += "--required"; Write-Host "Mise à jour OBLIGATOIRE." -ForegroundColor Yellow }
& $py @signArgs
if ($LASTEXITCODE -ne 0) { Fail "signature impossible (clé privée absente ? voir README, Update signing key)." }
$sha = (Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json).sha256

$body = "Voice Typer $version`n`n$Notes`n`nSHA-256 : $sha"
Write-Host "Envoi sur GitHub ($([math]::Round($setup.Length / 1MB)) Mo, quelques minutes)…" -ForegroundColor Cyan
$ghArgs = @("release", "create", "v$version", $setup.FullName, $json, "--repo", $repo,
            "--title", "Voice Typer $version", "--notes", $body, "--latest")
if ($Draft) { $ghArgs += "--draft" }
& gh @ghArgs
if ($LASTEXITCODE -ne 0) { Fail "la publication a échoué." }
Write-Host "`nOK : Voice Typer $version publié. Les copies installées le proposeront dans les prochaines heures." -ForegroundColor Green
