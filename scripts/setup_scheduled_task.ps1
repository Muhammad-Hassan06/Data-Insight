# Setup Windows Task Scheduler for Hourly Pipeline
# Run this script as Administrator to create the scheduled task

param(
    [string]$TaskName = "HackInsight_Hourly_Pipeline",
    [string]$Description = "Runs PM2.5 forecasting pipeline every hour"
)

# Get project root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$RunnerScript = "$ProjectRoot\scripts\run_hourly_pipeline.ps1"

# Check if script exists
if (!(Test-Path $RunnerScript)) {
    Write-Error "Runner script not found: $RunnerScript"
    exit 1
}

Write-Host "Setting up scheduled task..." -ForegroundColor Cyan
Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
Write-Host "Script: $RunnerScript" -ForegroundColor Yellow
Write-Host "Schedule: Every hour at :05 minutes past the hour" -ForegroundColor Yellow
Write-Host ""

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($ExistingTask) {
    $Response = Read-Host "Task '$TaskName' already exists. Overwrite? (Y/N)"
    if ($Response -ne 'Y' -and $Response -ne 'y') {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task." -ForegroundColor Green
}

# Create action - Run PowerShell with the script
$Action = New-ScheduledTaskAction `
    -Execute "PowerShell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`"" `
    -WorkingDirectory $ProjectRoot

# Create trigger - Every hour at :05 minutes
$Trigger = New-ScheduledTaskTrigger -Daily -At "00:05" 
$Trigger.Repetition = New-ScheduledTaskTrigger -Once -At "00:05" -RepetitionInterval (New-TimeSpan -Hours 1) | Select-Object -ExpandProperty Repetition

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -MultipleInstances IgnoreNew

# Create principal (run as current user)
$Principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

# Register the task
try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Description $Description `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Force | Out-Null
    
    Write-Host "`n✓ Scheduled task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The pipeline will run:" -ForegroundColor Cyan
    Write-Host "  • Every hour at :05 minutes (e.g., 1:05, 2:05, 3:05...)" -ForegroundColor White
    Write-Host "  • Logs saved to: $ProjectRoot\logs\" -ForegroundColor White
    Write-Host ""
    Write-Host "To manage the task:" -ForegroundColor Cyan
    Write-Host "  • Open Task Scheduler: taskschd.msc" -ForegroundColor White
    Write-Host "  • Or run: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host ""
    Write-Host "To run immediately (test): " -ForegroundColor Cyan
    Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To disable:" -ForegroundColor Cyan
    Write-Host "  Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To remove:" -ForegroundColor Cyan
    Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Yellow
    
} catch {
    Write-Error "Failed to create scheduled task: $_"
    Write-Host ""
    Write-Host "If you see a permissions error, try running PowerShell as Administrator:" -ForegroundColor Yellow
    Write-Host "  Right-click PowerShell → Run as Administrator" -ForegroundColor White
    exit 1
}
