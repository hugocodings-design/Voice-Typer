# Builds dist\VoiceTyperSetup-<version>.exe in one go (~2-4 minutes).
#
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1            # tests + build
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1 -SkipTests # faster
#
# Needs: the project venv (with pyinstaller) and Inno Setup 6
#   venv\Scripts\python.exe -m pip install pyinstaller
#   winget install --id JRSoftware.InnoSetup -e --scope user
# The version comes from voice_typer/__init__.py: bump it there before a release.
param([switch]$SkipTests, [switch]$Clean)

$ErrorActionPreference = "Continue"  # native tools log to stderr; exit codes are checked instead
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
$started = Get-Date

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nERREUR : $text" -ForegroundColor Red; exit 1 }

if (-not (Test-Path $py)) { Fail "venv introuvable ($py)." }
$iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
          "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
          "$env:ProgramFiles\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { Fail "Inno Setup 6 introuvable. Installez-le : winget install --id JRSoftware.InnoSetup -e --scope user" }
& $py -m PyInstaller --version *> $null
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller manquant : venv\Scripts\python.exe -m pip install pyinstaller" }

$version = (& $py -c "import voice_typer; print(voice_typer.__version__)").Trim()
Write-Host "Voice Typer $version" -ForegroundColor White

if (-not $SkipTests) {
    Step "Tests"
    & $py -m pytest -q
    if ($LASTEXITCODE -ne 0) { Fail "les tests ont échoué." }
}

Step "Icône et images de l'installateur"
& $py installer\make_assets.py
if ($LASTEXITCODE -ne 0) { Fail "make_assets.py" }

Step "Application autonome (PyInstaller)"
$pyiArgs = @("-m", "PyInstaller", "--noconfirm", "--log-level", "WARN", "--distpath", "dist", "--workpath", "build")
if ($Clean) { $pyiArgs += "--clean" }
& $py @pyiArgs installer\voice_typer.spec
if ($LASTEXITCODE -ne 0) { Fail "PyInstaller a échoué." }

Step "Auto-test de l'application compilée"
$testHome = Join-Path $root "build\selftest"
New-Item -ItemType Directory -Force $testHome | Out-Null
$savedAppData = $env:APPDATA
$env:APPDATA = $testHome   # never touch the real settings / log
try {
    $p = Start-Process -FilePath "dist\Voice Typer\Voice Typer.exe" -ArgumentList "--selftest" -PassThru -Wait
} finally { $env:APPDATA = $savedAppData }
$log = Get-Content (Join-Path $testHome "VoiceTyper\voice_typer.log") -Raw -ErrorAction SilentlyContinue
if ($p.ExitCode -ne 0 -or $log -notmatch "SELFTEST OK") { Write-Host $log; Fail "l'application compilée ne démarre pas correctement." }
Write-Host ($log.Trim())

Step "Installateur (Inno Setup)"
& $iscc /Qp "/DAppVersion=$version" installer\VoiceTyper.iss
if ($LASTEXITCODE -ne 0) { Fail "Inno Setup a échoué." }

$setup = Get-Item "dist\VoiceTyperSetup-$version.exe"
$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
Write-Host "`nOK : $($setup.FullName)  ($([math]::Round($setup.Length / 1MB)) Mo, $mins min)" -ForegroundColor Green
