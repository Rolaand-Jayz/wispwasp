# Starts ComfyUI, waits for it to be ready, then starts the listener and
# opens the overlay. Safe to run twice - it skips anything already running.

$comfy = Join-Path $env:USERPROFILE "ComfyUI"
$here  = $PSScriptRoot

function Test-Port($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port)
        $c.Close()
        return $true
    } catch { return $false }
}

Write-Host ""
Write-Host "  Audio-driven overlay - starting up" -ForegroundColor Cyan
Write-Host "  ---------------------------------"
Write-Host ""

# --- 1. ComfyUI ------------------------------------------------------------
if (Test-Port 8188) {
    Write-Host "  [1/3] ComfyUI already running." -ForegroundColor DarkGray
} else {
    if (-not (Test-Path "$comfy\.venv\Scripts\python.exe")) {
        Write-Host "  ERROR: ComfyUI not found at $comfy" -ForegroundColor Red
        Read-Host "  Press Enter to close"
        exit 1
    }
    Write-Host "  [1/3] Starting ComfyUI..." -NoNewline
    Start-Process -FilePath "$comfy\.venv\Scripts\python.exe" `
                  -ArgumentList "main.py", "--listen", "127.0.0.1", "--port", "8188" `
                  -WorkingDirectory $comfy -WindowStyle Minimized

    $deadline = (Get-Date).AddSeconds(240)
    while ((Get-Date) -lt $deadline -and -not (Test-Port 8188)) {
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
    }
    if (Test-Port 8188) {
        Write-Host " ready." -ForegroundColor Green
    } else {
        Write-Host " timed out." -ForegroundColor Red
        Write-Host "  Check the minimised ComfyUI window for errors."
        Read-Host "  Press Enter to close"
        exit 1
    }
}

# --- 2. Checkpoint sanity check -------------------------------------------
try {
    $oi = (Invoke-WebRequest "http://127.0.0.1:8188/object_info/CheckpointLoaderSimple" `
           -UseBasicParsing -TimeoutSec 20).Content | ConvertFrom-Json
    $ckpts = $oi.CheckpointLoaderSimple.input.required.ckpt_name[0]
    if (-not $ckpts -or $ckpts.Count -eq 0) {
        Write-Host ""
        Write-Host "  No model installed." -ForegroundColor Yellow
        Write-Host "  Put a .safetensors file in:" -ForegroundColor Yellow
        Write-Host "    $comfy\models\checkpoints\" -ForegroundColor Yellow
        Write-Host "  then close both windows and run this again."
        Write-Host ""
        Read-Host "  Press Enter to close"
        exit 1
    }
    Write-Host "  [2/3] Model: $($ckpts[0])" -ForegroundColor Green
} catch {
    Write-Host "  [2/3] Could not check models: $($_.Exception.Message)" -ForegroundColor Yellow
}

# --- 3. Listener -----------------------------------------------------------
if (Test-Port 8420) {
    Write-Host "  [3/3] Listener already running." -ForegroundColor DarkGray
} else {
    Write-Host "  [3/3] Starting listener..." -NoNewline
    Start-Process -FilePath "$here\.venv\Scripts\python.exe" `
                  -ArgumentList "listener.py" `
                  -WorkingDirectory $here -WindowStyle Minimized

    $deadline = (Get-Date).AddSeconds(180)
    while ((Get-Date) -lt $deadline -and -not (Test-Port 8420)) {
        Start-Sleep -Seconds 2
        Write-Host "." -NoNewline
    }
    if (Test-Port 8420) {
        Write-Host " ready." -ForegroundColor Green
    } else {
        Write-Host " timed out." -ForegroundColor Red
        Read-Host "  Press Enter to close"
        exit 1
    }
}

Start-Process "http://localhost:8420/?bare=1"

Write-Host ""
Write-Host "  Everything is running." -ForegroundColor Cyan
Write-Host "  Overlay opened in your browser - capture that window in OBS."
Write-Host ""
Write-Host "  To stop everything, run STOP.bat"
Write-Host ""
Start-Sleep -Seconds 6
