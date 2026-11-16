param(
    [Parameter(Mandatory=$true)][string]$Python,
    [Parameter(Mandatory=$true)][string]$State
)

$ErrorActionPreference = 'Stop'
$State = [IO.Path]::GetFullPath($State)
$localRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Formika\AICQ\listener'
if ($State -ine $localRoot) { throw 'Unexpected AICQ listener state directory.' }
$config = Join-Path $State 'bindings.json'
if (-not (Test-Path -LiteralPath $config -PathType Leaf)) { throw 'AICQ bindings are missing.' }
$pythonw = Join-Path (Split-Path -Parent $Python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw -PathType Leaf)) { throw 'AICQ requires pythonw.exe.' }

Import-Module ScheduledTasks
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$name = 'Kolabse-AICQ-Listener-' + $sid
$description = 'Kolabse AICQ listener; owner SID=' + $sid
$task = Get-ScheduledTask -TaskPath '\' | Where-Object TaskName -EQ $name
if ($task -and ($task.Description -ne $description -or $task.Principal.UserId -ne $sid -or
        [string]$task.Principal.RunLevel -ne 'Limited' -or [string]$task.Principal.LogonType -ne 'Interactive')) {
    throw 'The scheduled task name is already in use.'
}

# The verified archive is temporary. Retain a versioned runtime for logon and rollback.
$files = @('room_listener.py','desktop_room.py','room_worker.py','room_client.py','room_connect.py',
    'room_invitation.py','room_join.py','room_registry.py','room_team.py','room.py','smoke_app_server.py')
$version = ($files | ForEach-Object { (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $_)).Hash }) -join ''
$sha = [Security.Cryptography.SHA256]::Create()
try { $revision = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($version))).Replace('-', '') }
finally { $sha.Dispose() }
$runtime = Join-Path $State ('runtime-' + $revision)
if (-not (Test-Path -LiteralPath $runtime)) {
    $stage = Join-Path $State ('.runtime-' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($stage) | Out-Null
    try {
        foreach ($file in $files) {
            Copy-Item -LiteralPath (Join-Path $PSScriptRoot $file) -Destination (Join-Path $stage $file)
        }
        [IO.Directory]::Move($stage, $runtime)
    } finally {
        if ([IO.Directory]::Exists($stage)) { [IO.Directory]::Delete($stage, $true) }
    }
}
for ($index = 0; $index -lt $files.Count; $index++) {
    $hash = (Get-FileHash -LiteralPath (Join-Path $runtime $files[$index])).Hash
    if ($hash -ne $version.Substring($index * 64, 64)) { throw 'AICQ runtime failed verification.' }
}

$script = Join-Path $runtime 'room_listener.py'
$db = Join-Path $State 'listener.sqlite'
$arguments = '-E -s "{0}" --config "{1}" --state "{2}"' -f $script,$config,$db
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $runtime
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $sid
$principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

if ($task) {
    Set-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
    if ($task.State -eq 'Running') {
        Stop-ScheduledTask -TaskName $name -TaskPath '\'
        $deadline = [DateTime]::UtcNow.AddSeconds(10)
        do {
            Start-Sleep -Milliseconds 200
            $running = (Get-ScheduledTask -TaskName $name -TaskPath '\').State -eq 'Running'
        } while ($running -and [DateTime]::UtcNow -lt $deadline)
        if ($running) { throw 'Previous AICQ listener did not stop.' }
    }
} else {
    $definition = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description $description
    Register-ScheduledTask -TaskName $name -TaskPath '\' -InputObject $definition | Out-Null
}
Start-ScheduledTask -TaskName $name -TaskPath '\'
