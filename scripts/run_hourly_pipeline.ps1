# Hourly Pipeline Runner Script
# This script activates the virtual environment and runs the pipeline

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project directory
Set-Location $ProjectRoot

# Create logs directory
$LogDir = "$ProjectRoot\logs"
if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$LogFile = "$LogDir\pipeline_$(Get-Date -Format 'yyyyMMdd').log"
$Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

# Log start
"========================================" | Tee-Object -FilePath $LogFile -Append
"Pipeline Run: $Timestamp" | Tee-Object -FilePath $LogFile -Append
"========================================" | Tee-Object -FilePath $LogFile -Append

# Activate virtual environment
& "$ProjectRoot\venv\Scripts\Activate.ps1"

# Load environment variables from .env
if (Test-Path "$ProjectRoot\.env") {
    Get-Content "$ProjectRoot\.env" | ForEach-Object {
        if ($_ -match '^([^#=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
    "Loaded .env variables" | Tee-Object -FilePath $LogFile -Append
}

# Run pipeline
try {
    python -m src.flows.hourly_pipeline 2>&1 | Tee-Object -FilePath $LogFile -Append
    
    if ($LASTEXITCODE -eq 0) {
        "`nSUCCESS - Pipeline completed successfully at $(Get-Date -Format 'HH:mm:ss')" | Tee-Object -FilePath $LogFile -Append
    } else {
        "`nERROR - Pipeline failed with exit code: $LASTEXITCODE" | Tee-Object -FilePath $LogFile -Append
    }
} catch {
    "`nERROR - Pipeline error: $_" | Tee-Object -FilePath $LogFile -Append
}

"========================================`n" | Tee-Object -FilePath $LogFile -Append
