# Builds dist\VoiceTyperSetup-<version>.exe in one go (~2-4 minutes).
#
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1            # tests + build
#   powershell -ExecutionPolicy Bypass -File installer\build.ps1 -SkipTests # faster
#
# Needs: the project venv (with pyinstaller) and Inno Setup 6
#   venv\Scripts\python.exe -m pip install pyinstaller
#   winget install --id JRSoftware.InnoSetup -e --scope user
# The version comes from voice_typer/__init__.py: bump it there before a release.
#
# Optional code signing (Windows "Unknown publisher" warning): skipped unless a certificate is set up.
#   $env:VT_SIGN_PFX = "C:\chemin\certificat.pfx"; $env:VT_SIGN_PASSWORD = "..."   # certificate file
#   $env:VT_SIGN_THUMBPRINT = "AB12..."     # or: certificate in the Windows store / on a USB token
#   Microsoft Trusted Signing (cheapest): put its metadata.json at %USERPROFILE%\.voice-typer\trusted-signing.json
#   (or $env:VT_SIGN_AZURE_METADATA), install the client tools and log in once with `az login`.
# Needs signtool.exe (Windows SDK). See README → "Code signing".
param([switch]$SkipTests, [switch]$Clean)

$ErrorActionPreference = "Continue"  # native tools log to stderr; exit codes are checked instead
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
$started = Get-Date

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nERREUR : $text" -ForegroundColor Red; exit 1 }

# ---- optional code signing (only when a certificate is configured)
$signtool = $null
$azureMeta = if ($env:VT_SIGN_AZURE_METADATA) { $env:VT_SIGN_AZURE_METADATA } else { Join-Path $env:USERPROFILE ".voice-typer\trusted-signing.json" }
$azureDlib = $null
if (Test-Path $azureMeta) {
    $azureDlib = if ($env:VT_SIGN_AZURE_DLIB) { $env:VT_SIGN_AZURE_DLIB } else {
        @("$env:LOCALAPPDATA\Microsoft", "$env:ProgramFiles", "${env:ProgramFiles(x86)}") |
            ForEach-Object { Get-ChildItem $_ -Recurse -Filter "Azure.CodeSigning.Dlib.dll" -ErrorAction SilentlyContinue } |
            Where-Object { $_.FullName -match "x64" } | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $azureDlib) { Fail "Trusted Signing configuré mais Azure.CodeSigning.Dlib.dll introuvable : winget install -e --id Microsoft.Azure.TrustedSigningClientTools" }
}
if ($env:VT_SIGN_PFX -or $env:VT_SIGN_THUMBPRINT -or $azureDlib) {
    $signtool = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if (-not $signtool) { Fail "certificat configuré mais signtool.exe introuvable (installez le Windows SDK)." }
}
function Sign($file) {
    if (-not $signtool) { return }
    if ($azureDlib) {
        $a = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.acs.microsoft.com", "/td", "SHA256", "/d", "Voice Typer",
               "/dlib", $azureDlib, "/dmdf", $azureMeta)
    } else {
        $a = @("sign", "/fd", "SHA256", "/tr", "http://timestamp.digicert.com", "/td", "SHA256", "/d", "Voice Typer")
    }
    if (-not $azureDlib -and $env:VT_SIGN_PFX) {
        $a += @("/f", $env:VT_SIGN_PFX)
        if ($env:VT_SIGN_PASSWORD) { $a += @("/p", $env:VT_SIGN_PASSWORD) }
    } elseif (-not $azureDlib) {
        $a += @("/sha1", $env:VT_SIGN_THUMBPRINT)
    }
    & $signtool @a $file
    if ($LASTEXITCODE -ne 0) { Fail "signature de code impossible : $file" }
    Write-Host "Signé : $file" -ForegroundColor DarkGray
}

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

if ($signtool) {
    Step "Signature de code"
    Sign "dist\Voice Typer\Voice Typer.exe"
} else {
    Write-Host "`n(Signature de code : aucun certificat configuré, étape ignorée.)" -ForegroundColor DarkGray
}

Step "Version portable (zip, sans installateur ni %TEMP%)"
& $py installer\make_portable.py --src "dist\Voice Typer" --version $version --out dist
if ($LASTEXITCODE -ne 0) { Fail "make_portable.py a échoué." }

Step "Installateur (Inno Setup)"
& $iscc /Qp "/DAppVersion=$version" installer\VoiceTyper.iss
if ($LASTEXITCODE -ne 0) { Fail "Inno Setup a échoué." }

Sign "dist\VoiceTyperSetup-$version.exe"
$setup = Get-Item "dist\VoiceTyperSetup-$version.exe"
$mins = [math]::Round(((Get-Date) - $started).TotalMinutes, 1)
Write-Host "`nOK : $($setup.FullName)  ($([math]::Round($setup.Length / 1MB)) Mo, $mins min)" -ForegroundColor Green
Write-Host "     dist\VoiceTyper-portable-$version.zip (version portable)" -ForegroundColor Green
