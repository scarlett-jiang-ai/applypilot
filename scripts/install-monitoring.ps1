[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Python,
    [Parameter(Mandatory)][string]$State
)
$ErrorActionPreference = 'Stop'
$interpreter = (Resolve-Path -LiteralPath $Python).Path
$statePath = (Resolve-Path -LiteralPath $State).Path
if ($interpreter.Contains('"') -or $statePath.Contains('"')) { throw 'Invalid path' }
$watchlist = Get-Content -LiteralPath (Join-Path $statePath 'watchlist.json') -Raw | ConvertFrom-Json
if (-not $watchlist.companies -or $watchlist.companies.Count -eq 0) { throw 'Configure a non-empty company watchlist first.' }
& $interpreter -c 'import applypilot'
if ($LASTEXITCODE -ne 0) { throw 'Install ApplyPilot into the selected Python environment first.' }
$schedules = @{
    Breaking = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 3)
    Daily = New-ScheduledTaskTrigger -Daily -At '08:15'
    Weekly = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At '09:30'
}
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
foreach ($name in $schedules.Keys) {
    $arguments = '-m applypilot --state "{0}" cycle --kind {1}' -f $statePath, $name.ToLowerInvariant()
    $action = New-ScheduledTaskAction -Execute $interpreter -Argument $arguments
    if ($PSCmdlet.ShouldProcess("ApplyPilot-$name", 'Register private discovery schedule')) {
        Register-ScheduledTask -TaskName "ApplyPilot-$name" -Action $action -Trigger $schedules[$name] -Settings $settings -Description 'Private job discovery only; no applications' | Out-Null
        Get-ScheduledTask -TaskName "ApplyPilot-$name" | Select-Object TaskName, State, Triggers
    }
}
