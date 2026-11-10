# Build of PyDownloader: the version, the program, the installer (spec 7.3).
#
#   powershell -ExecutionPolicy Bypass -File build.ps1
#
# Output: dist\PyDownloader\ (the program), dist\install\PyDownloader-Setup-<version>.exe
# and the SHA-256 file next to it. Run "uv sync --extra dev" first.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- 1. the version from the git tag -----------------------------------------
# git writes to stderr when the repository has no tags; the native command must
# not stop the script, so the preference is relaxed for this call.
$version = "0.0.0-dev"
$ErrorActionPreference = "Continue"
$tag = (git describe --tags --abbrev=0) 2>$null
if ($LASTEXITCODE -eq 0 -and $tag) {
    $version = ($tag -replace "^v", "").Trim()
}
$ErrorActionPreference = "Stop"
Write-Host "Version: $version"

$versionFile = "src\pydownloader\_version.py"
$versionLines = @(
    '"""Version of the application.',
    '',
    '``build.ps1`` writes this file from ``git describe --tags``; in development',
    'it stays ``0.0.0-dev``.',
    '"""',
    '',
    "VERSION = `"$version`""
)
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $PWD $versionFile), ($versionLines -join "`n"), $utf8)

# --- 2. the version resource for the .exe ------------------------------------
$numbers = ($version -replace "[^0-9.]", ".").Split(".")
$parts = @(0, 0, 0, 0)
for ($i = 0; $i -lt 4 -and $i -lt $numbers.Length; $i++) {
    if ($numbers[$i] -match "^\d+$") { $parts[$i] = [int]$numbers[$i] }
}
$tuple = "(" + ($parts -join ", ") + ")"
$tupleText = ($parts -join ".")

New-Item -ItemType Directory -Force -Path "build" | Out-Null
$template = Get-Content "version_info.template.txt" -Raw
$filled = $template.Replace("VERSION_TUPLE", $tuple).Replace("VERSION_STRING", $version)
[System.IO.File]::WriteAllText((Join-Path $PWD "build\version_info.txt"), $filled, $utf8)

# --- 3. PyInstaller -----------------------------------------------------------
# uv and PyInstaller write progress on stderr: NativeCommandError must not stop
# the script, the exit code is the real check.
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
$ErrorActionPreference = "Continue"
uv run pyinstaller --clean --noconfirm pydownloader.spec
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) { throw "PyInstaller failed" }

# --- 3b. FFmpeg in {app}\bin -------------------------------------------------
# The binary of imageio-ffmpeg is the same build the program uses in a checkout;
# locate_ffmpeg() looks in bin first (spec 7.3).
$ErrorActionPreference = "Continue"
$ffmpeg = (uv run python -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())") 2>$null
$ErrorActionPreference = "Stop"
if (-not $ffmpeg -or -not (Test-Path $ffmpeg)) { throw "ffmpeg.exe not found in imageio-ffmpeg" }
New-Item -ItemType Directory -Force -Path "dist\PyDownloader\bin" | Out-Null
Copy-Item -Force $ffmpeg "dist\PyDownloader\bin\ffmpeg.exe"
Write-Host "FFmpeg: $ffmpeg"

# --- 3c. the ad blocker next to the program -----------------------------------
# uBlock.crx is in the repository, so GitHub Actions ships the blocker too.
# A checkout without the file simply ships no blocker.
if (Test-Path "uBlock.crx") {
    Copy-Item -Force "uBlock.crx" "dist\PyDownloader\uBlock.crx"
    Write-Host "uBlock: uBlock.crx"
} else {
    Write-Warning "uBlock.crx не найден: сборка без блокировщика рекламы"
}

# --- 4. Inno Setup ------------------------------------------------------------
$iscc = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
    # the per-user install created by winget without administrator rights
    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) { $iscc = $candidate; break }
    }
}
if (-not $iscc) {
    Write-Warning "Inno Setup не найден: установщик не собран. Установите: winget install -e --id JRSoftware.InnoSetup"
    exit 0
}

& $iscc "/DProductVersion=$version" "/DVersionTuple=$tupleText" "installer\pydownloader.iss"
$code = $LASTEXITCODE
if ($code -ne 0) { throw "Inno Setup failed" }

# --- 5. SHA-256 of the installer ---------------------------------------------
$setup = "dist\install\PyDownloader-Setup-$version.exe"
if (-not (Test-Path $setup)) { throw "installer not produced: $setup" }
$hash = (Get-FileHash -Algorithm SHA256 $setup).Hash.ToLower()
$hashFile = "$setup.sha256"
Set-Content -Path $hashFile -Value "$hash  $(Split-Path $setup -Leaf)" -Encoding utf8
Write-Host "Installer: $setup"
Write-Host "SHA-256:   $hash"
