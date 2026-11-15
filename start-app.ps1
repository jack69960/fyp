param([switch]$Quiet)

$ErrorActionPreference = 'Stop'

$AppDir   = 'C:\Users\jack\Desktop\fyp'
$PythonW  = Join-Path $AppDir '.venv\Scripts\pythonw.exe'
$Neo4jBat = 'C:\Users\jack\neo4j\start-neo4j.bat'

function Test-Port {
    param([int]$Port)
    $client = New-Object Net.Sockets.TcpClient
    try {
        $client.Connect('127.0.0.1', $Port)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port {
    param([int]$Port, [int]$TimeoutSeconds = 120)
    for ($i = 0; $i -lt $TimeoutSeconds; $i += 2) {
        if (Test-Port -Port $Port) { return $true }
        Start-Sleep -Seconds 2
    }
    return $false
}

# ---------- 1. Neo4j ----------
if (-not (Test-Port -Port 7687)) {
    Write-Host 'Neo4j is not running, starting it...'
    $windowStyle = if ($Quiet) { 'Hidden' } else { 'Minimized' }
    Start-Process -FilePath $Neo4jBat -WindowStyle $windowStyle | Out-Null
    if (Wait-Port -Port 7687 -TimeoutSeconds 120) {
        Write-Host 'Neo4j is ready on localhost:7687'
    } else {
        Write-Host 'WARNING: Neo4j did not come up within 120s. Check C:\Users\jack\neo4j\neo4j-community-5.26.0\logs\neo4j.log'
        exit 1
    }
} else {
    Write-Host 'Neo4j already running on localhost:7687'
}

# ---------- 2. Streamlit ----------
if (-not (Test-Port -Port 8501)) {
    Write-Host 'Starting Streamlit...'
    Start-Process -FilePath $PythonW `
        -ArgumentList @('-m', 'streamlit', 'run', 'app.py', '--server.headless', 'true', '--server.port', '8501') `
        -WorkingDirectory $AppDir -WindowStyle Hidden | Out-Null
    if (Wait-Port -Port 8501 -TimeoutSeconds 90) {
        Write-Host 'Streamlit is ready on http://localhost:8501'
    } else {
        Write-Host 'WARNING: Streamlit did not come up within 90s.'
        exit 1
    }
} else {
    Write-Host 'Streamlit already running on http://localhost:8501'
}

# ---------- 3. Open browser ----------
if (-not $Quiet) {
    Start-Process 'http://localhost:8501'
}
Write-Host 'Done.'
