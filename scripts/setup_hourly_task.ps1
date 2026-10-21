# Setup Windows Task Scheduler for Hourly Pipeline
# Run this to create the scheduled task

$TaskName = "HackInsight_Hourly_Pipeline"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$RunnerScript = "$ProjectRoot\scripts\run_hourly_pipeline.ps1"

Write-Host ""
Write-Host "=== Setting Up Hourly Pipeline Task ===" -ForegroundColor Cyan
Write-Host "Task Name: $TaskName" -ForegroundColor Yellow
Write-Host "Script: $RunnerScript" -ForegroundColor Yellow
Write-Host "Schedule: Every hour at 05 past the hour" -ForegroundColor Yellow
Write-Host ""

# Check if task exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Task already exists. Removing..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create action
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$RunnerScript`"" -WorkingDirectory $ProjectRoot

# Create trigger - Hourly at :05 minutes
$Trigger = New-ScheduledTaskTrigger -Once -At "00:05AM" -RepetitionInterval (New-TimeSpan -Hours 1)

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew

# Principal (run as current user)
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive

# Register task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Description "Runs PM2.5 forecasting pipeline every hour" -Force | Out-Null
    
    Write-Host "SUCCESS! Task created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The pipeline will run every hour at 05 minutes past the hour" -ForegroundColor White
    Write-Host ""
    Write-Host "Commands:" -ForegroundColor Cyan
    Write-Host "  Run now:    Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Check:      Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Disable:    Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor White
    Write-Host "  Remove:     Unregister-ScheduledTask -TaskName '$TaskName' -Confirm" -ForegroundColor White
    Write-Host ""
    Write-Host "Logs will be saved to: $ProjectRoot\logs\" -ForegroundColor Yellow
    Write-Host ""
    
} catch {
    Write-Error "Failed to create task: $_"
    Write-Host ""
    Write-Host "Try running PowerShell as Administrator" -ForegroundColor Yellow
    exit 1
}
