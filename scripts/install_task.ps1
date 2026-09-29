# Register a Windows scheduled task that runs the checker every N minutes, silently
# (pythonw = no console window popping up). Run from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1 [-Minutes 10]
# Remove it again with:
#   Unregister-ScheduledTask -TaskName "YCFC Ticket Checker" -Confirm:$false
param(
    [int]$Minutes = 10,
    [string]$TaskName = "YCFC Ticket Checker"
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root "venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "venv not found - run scripts\setup.ps1 first" }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "-m ycfc_tickets" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Checks York City FC home tickets page for new fixtures" -Force | Out-Null

Write-Host "Scheduled '$TaskName' every $Minutes minutes. Logs: $root\logs\ycfc_tickets.log"
