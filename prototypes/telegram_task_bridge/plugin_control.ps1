# Plugin entry point. MCP startup may start an existing task, but never installs it.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('serve', 'ensure', 'start', 'stop', 'status', 'uninstall')]
    [string]$Action,
    [string]$PythonPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\venv\Scripts\python.exe'),
    [string]$ReceiverPythonPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\venv\Scripts\pythonw.exe'),
    [string]$ServerPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\runtime\server.py'),
    [string]$DatabasePath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-task-bridge\live.sqlite3'),
    [string]$ConfigPath = (Join-Path $env:LOCALAPPDATA 'codex\telegram-notify\config.json'),
    [ValidateSet('codex', 'claude-code')]
    [string]$Agent = 'codex'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$pausePath = Join-Path ([IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($DatabasePath))) 'receiver-paused'
$managerPath = Join-Path $PSScriptRoot 'manage_receiver.ps1'

function Invoke-ReceiverManager([string]$ManagerAction) {
    # A child process isolates the manager's exit statement from lifecycle cleanup.
    $shellPath = Join-Path $PSHOME 'powershell.exe'
    if (-not (Test-Path -LiteralPath $shellPath -PathType Leaf)) {
        $shellPath = Join-Path $PSHOME 'pwsh.exe'
    }
    if (-not (Test-Path -LiteralPath $managerPath -PathType Leaf)) {
        throw 'Receiver manager is missing. Run plugin setup.'
    }
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $shellPath -NoLogo -NoProfile -NonInteractive -File $managerPath `
            -Action $ManagerAction -PythonPath $ReceiverPythonPath -ServerPath $ServerPath `
            -DatabasePath $DatabasePath -ConfigPath $ConfigPath 2>&1 | Out-String
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedPreference
    }
    return [pscustomobject]@{ Code = $code; Output = $output }
}

function Write-ReceiverState([string]$State, [string]$Message, [switch]$NeedsAttention) {
    @{ state = $State; detail = $Message; needs_attention = [bool]$NeedsAttention } | ConvertTo-Json -Compress
}

function Ensure-Receiver {
    if (Test-Path -LiteralPath $pausePath) {
        Write-ReceiverState 'paused' 'Use the explicit start command to resume.'
        return
    }
    $result = Invoke-ReceiverManager 'status'
    if ($result.Code -ne 0) { throw 'Cannot inspect receiver status.' }
    $status = $result.Output | ConvertFrom-Json
    if (-not $status.installed) {
        Write-ReceiverState 'setup_needed' 'Run plugin setup to install the receiver.' -NeedsAttention
        return
    }
    if ($status.scheduler_state -in @('Running', 'Queued')) {
        # Never restart a running receiver, including while its heartbeat is starting.
        switch ([string]$status.receiver_state) {
            'ready' { Write-ReceiverState 'ready' 'Receiver is running.' }
            'retrying' { Write-ReceiverState 'retrying' 'Receiver is running and reconnecting.' }
            'failed' { Write-ReceiverState 'manual_start_needed' 'Inspect receiver status before explicitly starting it.' -NeedsAttention }
            default { Write-ReceiverState 'starting_or_unhealthy' 'Receiver is active; no restart was attempted.' }
        }
        return
    }
    $healthState = $(if ($null -ne $status.health) { [string]$status.health.state } else { '' })
    # A failed or uncertain previous run requires an explicit user start.
    # SCHED_S_TASK_HAS_NOT_RUN (267011) is safe for an installed, unused task.
    if ($status.scheduler_state -ne 'Ready' -or $status.health_error -or
        $healthState -notin @('', 'stopped') -or
        ($null -ne $status.last_task_result -and [long]$status.last_task_result -notin @(0, 267011))) {
        Write-ReceiverState 'manual_start_needed' 'Previous receiver state needs inspection; use explicit start when ready.' -NeedsAttention
        return
    }
    $result = Invoke-ReceiverManager 'start'
    if ($result.Code -ne 0) { throw 'Cannot start existing receiver.' }
    Write-ReceiverState 'starting' 'Started the existing receiver task.'
}

$mutex = $null
$lockTaken = $false
$exitCode = 0
try {
    if ($Action -eq 'serve') {
        foreach ($path in @($PythonPath, $ServerPath, $ConfigPath)) {
            if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
                throw 'Bridge runtime or configuration is missing. Run plugin setup.'
            }
        }
        # Reuse the serialized lifecycle check in a short-lived child. Its output
        # must never enter stdout, which belongs exclusively to the MCP protocol.
        $bootstrapShell = Join-Path $PSHOME 'powershell.exe'
        if (-not (Test-Path -LiteralPath $bootstrapShell)) { $bootstrapShell = Join-Path $PSHOME 'pwsh.exe' }
        $bootstrapOutput = & $bootstrapShell -NoProfile -NonInteractive -File $PSCommandPath ensure `
            -ReceiverPythonPath $ReceiverPythonPath -ServerPath $ServerPath `
            -DatabasePath $DatabasePath -ConfigPath $ConfigPath 2>&1 | Out-String
        [Console]::Error.Write($bootstrapOutput)
        $bootstrapState = $bootstrapOutput | ConvertFrom-Json
        if ($bootstrapState.state -eq 'unavailable') {
            throw 'Receiver lifecycle is busy or unavailable. Retry MCP connection after setup finishes.'
        }
        & $PythonPath $ServerPath serve --db $DatabasePath --config $ConfigPath --agent $Agent
        $exitCode = $LASTEXITCODE
    } else {
        if ($Action -in @('ensure', 'start', 'stop', 'uninstall')) {
            $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
            $mutex = [Threading.Mutex]::new($false, ('Global\Codex-TelegramTaskBridge-Control-' + $sid))
            try {
                $lockTaken = $mutex.WaitOne(5000)
            } catch [Threading.AbandonedMutexException] {
                $lockTaken = $true
            }
            if (-not $lockTaken) { throw 'Receiver lifecycle is busy. Try again shortly.' }
        }
        if ($Action -eq 'ensure') {
            Ensure-Receiver
        } else {
            if ($Action -in @('stop', 'uninstall')) {
                # Persist intent before any scheduler operation, even if it fails.
                [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($pausePath)) | Out-Null
                [IO.File]::WriteAllText($pausePath, 'Receiver paused by explicit user command.')
            }
            $resumePaused = $Action -eq 'start' -and (Test-Path -LiteralPath $pausePath)
            if ($resumePaused) { Remove-Item -LiteralPath $pausePath -Force }
            try {
                $result = Invoke-ReceiverManager $Action
                $exitCode = $result.Code
            } catch {
                if ($resumePaused) { [IO.File]::WriteAllText($pausePath, 'Receiver paused; resume failed.') }
                throw
            }
            if ($resumePaused -and $exitCode -ne 0) {
                [IO.File]::WriteAllText($pausePath, 'Receiver paused; resume failed.')
            }
            # In particular, status preserves the manager's JSON schema and output.
            [Console]::Out.Write($result.Output)
        }
    }
} catch {
    if ($Action -eq 'ensure') {
        # Bootstrap output must not expose configuration, tokens, paths or child errors.
        Write-ReceiverState 'unavailable' 'Check receiver status or run plugin setup; session startup can continue.' -NeedsAttention
    } else {
        Write-Error $_ -ErrorAction Continue
        $exitCode = 1
    }
} finally {
    if ($lockTaken) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}
if ($Action -eq 'ensure') { exit 0 }
exit $exitCode
