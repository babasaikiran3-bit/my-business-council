<#
.SYNOPSIS
    Convenience wrapper for LLM Council: starts/stops the backend and frontend together.

.EXAMPLE
    .\run.ps1          # start backend (8001) and frontend (5173) if not already running, open the browser
.EXAMPLE
    .\run.ps1 -Stop    # stop both
#>
param(
    [switch]$Stop
)

$ErrorActionPreference = "Stop"

function Get-PortPid($port) {
    $line = netstat -ano | Select-String "[:.]$port\s.*LISTENING"
    if ($line) {
        return ($line -split "\s+")[-1] | Select-Object -First 1
    }
    return $null
}

Push-Location $PSScriptRoot
try {
    $backendPid = Get-PortPid 8001
    $frontendPid = Get-PortPid 5173

    if ($Stop) {
        if ($backendPid) { Stop-Process -Id $backendPid -Force; Write-Host "Backend stopped." }
        else { Write-Host "Backend was not running." }
        if ($frontendPid) { Stop-Process -Id $frontendPid -Force; Write-Host "Frontend stopped." }
        else { Write-Host "Frontend was not running." }
        return
    }

    if (-not (Test-Path ".env")) {
        Write-Error "No .env file found. Create one with OPENROUTER_API_KEY=... before running."
        return
    }

    if (-not $backendPid) {
        Write-Host "Starting backend on http://localhost:8001..."
        Start-Process -WindowStyle Hidden -FilePath "uv" -ArgumentList "run","python","-m","backend.main" -WorkingDirectory $PSScriptRoot
    } else {
        Write-Host "Backend already running."
    }

    if (-not $frontendPid) {
        Write-Host "Starting frontend on http://localhost:5173..."
        Start-Process -WindowStyle Hidden -FilePath "npm.cmd" -ArgumentList "run","dev" -WorkingDirectory (Join-Path $PSScriptRoot "frontend")
        Start-Sleep -Seconds 3
    } else {
        Write-Host "Frontend already running."
    }

    Start-Process "http://localhost:5173"
}
finally {
    Pop-Location
}
