# A current-user logon task; no password, elevation, or Desktop process dependency.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('install', 'start', 'stop', 'status', 'uninstall')]
    [string]$Action,
    [string]$PythonPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\venv\Scripts\pythonw.exe'),
    [string]$ServerPath = '',
    [string]$DatabasePath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\live.sqlite3'),
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-notify\config.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrEmpty($ServerPath)) { $ServerPath = Join-Path $PSScriptRoot 'server.py' }

function Get-AbsoluteFilePath([string]$Value, [string]$Label, [bool]$MustExist) {
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value -match '["\r\n]' -or $Value -match '[\\/]$' -or
        $Value -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+\\)') {
        throw "$Label must be an absolute file path without quotes or newlines."
    }
    $full = [IO.Path]::GetFullPath($Value)
    if ($MustExist -and -not (Test-Path -LiteralPath $full -PathType Leaf)) {
        throw "$Label does not exist as a file: $full"
    }
    if (Test-Path -LiteralPath $full -PathType Container) {
        throw "$Label must name a file: $full"
    }
    return $full
}

function Get-PrincipalSid([string]$UserId) {
    if ($UserId -match '^S-1-') { return $UserId }
    return ([Security.Principal.NTAccount]::new($UserId)).Translate([Security.Principal.SecurityIdentifier]).Value
}

function Assert-OwnedTask($Task) {
    if ($Task.Description -cne $script:ownerMarker -or @($Task.Actions).Count -ne 1) {
        throw 'Conflicting scheduled task: ownership marker or action count differs. No changes made.'
    }
    $taskAction = @($Task.Actions)[0]
    if ($taskAction.Execute -ine $script:PythonPath -or
        $taskAction.Arguments -cne $script:receiverArguments -or
        $taskAction.WorkingDirectory -ine $script:workingDirectory -or
        (Get-PrincipalSid $Task.Principal.UserId) -ne $script:userSid -or
        [string]$Task.Principal.LogonType -ne 'Interactive' -or
        [string]$Task.Principal.RunLevel -ne 'Limited') {
        throw 'Conflicting scheduled task configuration. Supply its exact original paths; no changes made.'
    }
}

function Assert-InstallSettings($Task) {
    $triggers = @($Task.Triggers)
    if ($triggers.Count -ne 1 -or $triggers[0].CimClass.CimClassName -ne 'MSFT_TaskLogonTrigger' -or
        (Get-PrincipalSid $triggers[0].UserId) -ne $script:userSid -or -not $triggers[0].Enabled -or
        -not $Task.Settings.Enabled -or [string]$Task.Settings.MultipleInstances -ne 'IgnoreNew' -or
        $Task.Settings.DisallowStartIfOnBatteries -or $Task.Settings.StopIfGoingOnBatteries -or
        $Task.Settings.ExecutionTimeLimit -ne 'PT0S' -or $Task.Settings.RestartCount -ne 0) {
        throw 'Existing receiver task has conflicting lifecycle settings. No changes made.'
    }
}

function Write-ReceiverStatus($Task) {
    $health = $null
    $healthError = $null
    $age = $null
    $info = $null
    $effective = 'not_installed'
    if ($Task) {
        $info = Get-ScheduledTaskInfo -TaskName $script:taskName -TaskPath '\'
        $effective = 'stopped'
    }
    if (Test-Path -LiteralPath $script:healthPath -PathType Leaf) {
        try {
            $health = Get-Content -LiteralPath $script:healthPath -Raw | ConvertFrom-Json
            if ($null -eq $health.updated_at -or [string]$health.state -notin @('starting', 'ready', 'retrying', 'failed', 'stopped', 'paused')) {
                throw 'Invalid health schema.'
            }
            $age = [Math]::Round([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() / 1000.0 - [double]$health.updated_at, 1)
        } catch {
            $health = $null
            $healthError = 'Health file is unreadable or invalid.'
        }
    }
    if ($Task -and [string]$Task.State -eq 'Running') {
        $effective = 'starting_or_unhealthy'
        # An old heartbeat cannot make a newly started or stopped task look healthy.
        $runEpoch = ([DateTimeOffset]$info.LastRunTime).ToUnixTimeSeconds()
        if ($health -and $age -ge -5 -and $age -le 120 -and
            [double]$health.updated_at -ge $runEpoch -and
            [string]$health.state -in @('starting', 'ready', 'retrying', 'failed', 'stopped', 'paused')) {
            $effective = [string]$health.state
        }
    }
    [ordered]@{
        task_name = $script:taskName
        installed = [bool]$Task
        scheduler_state = $(if ($Task) { [string]$Task.State } else { $null })
        last_task_result = $(if ($info) { $info.LastTaskResult } else { $null })
        last_run_time = $(if ($info) { $info.LastRunTime.ToString('o') } else { $null })
        receiver_state = $effective
        paused_by_user = (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetDirectoryName($script:DatabasePath)) 'receiver-paused'))
        health_path = $script:healthPath
        health_age_seconds = $age
        health = $health
        health_error = $healthError
    } | ConvertTo-Json -Depth 8
}

try {
    Import-Module ScheduledTasks -ErrorAction Stop
    $requireInputs = $Action -in @('install', 'start')
    $PythonPath = Get-AbsoluteFilePath $PythonPath 'PythonPath' $requireInputs
    $ServerPath = Get-AbsoluteFilePath $ServerPath 'ServerPath' $requireInputs
    $DatabasePath = Get-AbsoluteFilePath $DatabasePath 'DatabasePath' $false
    $ConfigPath = Get-AbsoluteFilePath $ConfigPath 'ConfigPath' $requireInputs
    if ([IO.Path]::GetFileName($PythonPath) -ine 'pythonw.exe') {
        throw 'PythonPath must name pythonw.exe so the receiver has no console window.'
    }
    $workingDirectory = [IO.Path]::GetDirectoryName($ServerPath)
    $healthPath = $DatabasePath + '.receiver-health.json'
    $userSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $taskName = 'Codex-TelegramTaskBridge-Receiver-' + $userSid
    $ownerMarker = 'Codex Telegram task bridge receiver v1; owner SID=' + $userSid
    # File arguments cannot contain quotes/newlines or end in a directory separator.
    # Quoting each complete file path preserves spaces, Unicode and shell metacharacters.
    $receiverArguments = '"{0}" receive --db "{1}" --config "{2}" --health-file "{3}"' -f $ServerPath, $DatabasePath, $ConfigPath, $healthPath
    if ($requireInputs -and -not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($DatabasePath)) -PathType Container)) {
        throw 'DatabasePath parent directory must already exist. Run the bridge setup first.'
    }
    # Enumerate to distinguish absence from scheduler access failures.
    $existing = @(Get-ScheduledTask -TaskPath '\' | Where-Object TaskName -EQ $taskName)
    $task = $(if ($existing.Count) { $existing[0] } else { $null })
    if ($task) { Assert-OwnedTask $task }
    switch ($Action) {
        'install' {
            if ($task) {
                Assert-InstallSettings $task
            } else {
                $taskAction = New-ScheduledTaskAction -Execute $PythonPath -Argument $receiverArguments -WorkingDirectory $workingDirectory
                $trigger = New-ScheduledTaskTrigger -AtLogOn -User $userSid
                $principal = New-ScheduledTaskPrincipal -UserId $userSid -LogonType Interactive -RunLevel Limited
                $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
                $definition = New-ScheduledTask -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description $ownerMarker
                try {
                    # Deliberately no -Force: a concurrently created task must not be replaced.
                    $task = Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $definition
                } catch {
                    throw 'Could not register the current-user task. Check Task Scheduler permissions/policy or a conflicting task; no elevation or password was requested.'
                }
            }
        }
        'start' {
            if (-not $task) { throw 'Receiver task is not installed. Run install first.' }
            Assert-InstallSettings $task
            Start-ScheduledTask -TaskName $taskName -TaskPath '\'
        }
        'stop' {
            if ($task) { Stop-ScheduledTask -TaskName $taskName -TaskPath '\' }
        }
        'uninstall' {
            if ($task) {
                Stop-ScheduledTask -TaskName $taskName -TaskPath '\'
                Unregister-ScheduledTask -TaskName $taskName -TaskPath '\' -Confirm:$false
                $task = $null
            }
        }
    }
    if ($task) { $task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' }
    Write-ReceiverStatus $task
} catch {
    Write-Error $_ -ErrorAction Continue
    exit 1
}
