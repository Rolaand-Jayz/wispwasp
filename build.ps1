# Builds the app and then the installer, in that order.
#
# Compiling the installer on its own is the dangerous move: Inno packages
# whatever happens to be in dist\, so a stale build gets shipped without
# any warning. This script always rebuilds first, and refuses to package a
# dist folder older than the source.
#
#   .\build.ps1            build everything
#   .\build.ps1 -SkipApp   only repackage (it will still check freshness)

param([switch]$SkipApp, [switch]$SkipTests, [switch]$SkipSelfTest)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$python = ".\.venv\Scripts\python.exe"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"

function Step($msg) { Write-Host "`n=== $msg ===" -ForegroundColor Cyan }

if (-not $SkipTests) {
    Step "Tests"
    $suites = @("test_wav.py", "test_core2.py", "test_engine.py",
                "test_server.py", "test_layouts.py", "test_setup.py",
                "test_install.py", "test_mic.py", "test_process_audio.py", "test_clear.py", "test_catalog.py", "test_models.py", "test_recovery.py", "test_activation.py", "test_options.py", "test_sync.py", "test_favourites.py", "test_confirm.py", "test_customize.py", "test_docs.py")
    foreach ($t in $suites) {
        if (-not (Test-Path $t)) { continue }
        # A suite is judged by its exit code, not by whether it wrote to
        # stderr. With ErrorActionPreference set to Stop, a single Qt
        # warning from a passing test was enough to kill the whole build
        # with no explanation of which test or why.
        $ErrorActionPreference = "Continue"
        $out = & $python $t 2>&1
        $code = $LASTEXITCODE
        $ErrorActionPreference = "Stop"
        $line = $out | Select-String -Pattern '^\d+/\d+ passed|all checks passed'
        if ($code -ne 0) {
            Write-Host "  $t FAILED" -ForegroundColor Red
            $out | Select-Object -Last 12
            exit 1
        }
        Write-Host ("  {0,-20} {1}" -f $t, ($line -join ' '))
    }
}

if (-not $SkipApp) {
    Step "Building the app"
    Get-Process WispWasp -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 1
    & ".\.venv\Scripts\pyinstaller.exe" wispwasp.spec --noconfirm --log-level WARN
    if ($LASTEXITCODE -ne 0) { Write-Host "build failed" -ForegroundColor Red; exit 1 }
}

Step "Checking the build is not stale"
$exe = Get-Item "dist\WispWasp\WispWasp.exe" -ErrorAction SilentlyContinue
if (-not $exe) { Write-Host "no build in dist\" -ForegroundColor Red; exit 1 }

# Any source file newer than the executable means dist\ does not match the
# code, which is the exact situation that ships stale behaviour.
$sources = Get-ChildItem -Recurse -Include *.py, *.html, *.spec `
    -Path "avcore", "avgui", "hooks", "app.py", "selftest.py", "overlay.html", "wispwasp.spec" `
    -ErrorAction SilentlyContinue
$newer = $sources | Where-Object { $_.LastWriteTime -gt $exe.LastWriteTime }
if ($newer) {
    Write-Host "  These are newer than the build:" -ForegroundColor Red
    $newer | ForEach-Object { Write-Host "    $($_.Name)" }
    Write-Host "  Rebuild before packaging." -ForegroundColor Red
    exit 1
}
Write-Host "  dist\ is current"

if ($SkipSelfTest) {
    Write-Host "`n=== Self-test SKIPPED ===" -ForegroundColor Yellow
    Write-Host "  The packaged app was NOT verified. Use this only when" `
        -ForegroundColor Yellow
    Write-Host "  Smart App Control is blocking the fresh binary." `
        -ForegroundColor Yellow
} else {
Step "Self-test on the built app"
Remove-Item "$env:USERPROFILE\WispWasp\selftest.log" -Force -ErrorAction SilentlyContinue
Start-Process -FilePath "dist\WispWasp\WispWasp.exe" -ArgumentList "--selftest" `
    -WorkingDirectory "$PSScriptRoot\dist\WispWasp" | Out-Null
$deadline = (Get-Date).AddSeconds(120)
while ((Get-Date) -lt $deadline -and -not (Test-Path "$env:USERPROFILE\WispWasp\selftest.log")) {
    Start-Sleep -Seconds 2
}
Get-Process WispWasp -ErrorAction SilentlyContinue | Stop-Process -Force
$log = Get-Content "$env:USERPROFILE\WispWasp\selftest.log" -ErrorAction SilentlyContinue
if (-not $log) { Write-Host "  self-test produced nothing" -ForegroundColor Red; exit 1 }
$log | Select-String -Pattern '^\[FAIL\]' | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
if ($log -match 'RESULT: everything passed') {
    Write-Host "  self-test passed"
} else {
    Write-Host "  self-test failed - see $env:USERPROFILE\WispWasp\selftest.log" -ForegroundColor Red
    exit 1
}

}

Step "Building the installer"
# The version comes from avcore/version.py so there is one place to
# change it. Passed in rather than kept here, where a copy would drift.
$verLine = Select-String -Path avcore\version.py -Pattern '^__version__' | Select-Object -First 1
$appVersion = ($verLine.Line -split '"')[1]
if (-not $appVersion) {
    Write-Host "  could not read the version from avcore\version.py" -ForegroundColor Red
    exit 1
}
Write-Host "  version $appVersion"
& $iscc "/DAppVersion=$appVersion" installer.iss | Select-String -Pattern 'Successful compile|Error'
$setup = Get-Item "installer\WispWasp-$appVersion-setup.exe"
Write-Host ("`nDone. {0} ({1:N0} MB)" -f $setup.Name, ($setup.Length / 1MB)) -ForegroundColor Green
