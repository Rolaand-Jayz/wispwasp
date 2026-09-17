# Ensures ComfyUI is running, then opens the manual prompt tool.
$comfy = Join-Path $env:USERPROFILE "ComfyUI"
$here  = $PSScriptRoot

function Test-Port($port) {
    try {
        $c = New-Object Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $port); $c.Close(); return $true
    } catch { return $false }
}

if (Test-Port 8188) {
    Write-Host "  ComfyUI already running." -ForegroundColor DarkGray
} else {
    if (-not (Test-Path "$comfy\.venv\Scripts\python.exe")) {
        Write-Host "  ERROR: ComfyUI not found at $comfy" -ForegroundColor Red
        Read-Host "  Press Enter to close"; exit 1
    }
    Write-Host "  Starting ComfyUI..." -NoNewline
    Start-Process -FilePath "$comfy\.venv\Scripts\python.exe" `
                  -ArgumentList "main.py", "--listen", "127.0.0.1", "--port", "8188" `
                  -WorkingDirectory $comfy -WindowStyle Minimized
    $deadline = (Get-Date).AddSeconds(240)
    while ((Get-Date) -lt $deadline -and -not (Test-Port 8188)) {
        Start-Sleep -Seconds 2; Write-Host "." -NoNewline
    }
    if (Test-Port 8188) { Write-Host " ready." -ForegroundColor Green }
    else {
        Write-Host " timed out." -ForegroundColor Red
        Write-Host "  Check the minimised ComfyUI window."
        Read-Host "  Press Enter to close"; exit 1
    }
}

# Runs in this window so you can type into it.
& "$here\.venv\Scripts\python.exe" "$here\prompt_tool.py"
