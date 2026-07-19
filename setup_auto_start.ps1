# Setup Attention Tracker Server to start automatically with Windows
# Run this script as Administrator

$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = "python"
$ServerScript = Join-Path $ScriptPath "attention_tracker\flask_server.py"
$TaskName = "منصة رفيق Attention Tracker Server"

Write-Host "Setting up auto-start for Attention Tracker Server..." -ForegroundColor Green

# Check if task already exists
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    Write-Host "Task already exists. Removing old task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create new scheduled task
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $ServerScript `
    -WorkingDirectory $ScriptPath

$Trigger = New-ScheduledTaskTrigger -AtLogon

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Force

Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host "The Attention Tracker Server will now start automatically when you log in." -ForegroundColor Cyan
Write-Host "To start it now manually, run: start_attention_server.bat" -ForegroundColor Cyan
