# Explicit setup; never executed by SessionStart or MCP startup.
[CmdletBinding()]
param([Parameter(Position = 0)][ValidateSet('install','update','status','uninstall')][string]$Action = 'install')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$bridgeRoot = Join-Path $env:LOCALAPPDATA 'codex/telegram-task-bridge'
$python = Join-Path $bridgeRoot 'venv/Scripts/python.exe'
$mutex = $null
$lockTaken = $false
$exitCode = 1
try {
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $mutex = [Threading.Mutex]::new($false, ('Global\Codex-TelegramTaskBridge-Control-' + $sid))
    try { $lockTaken = $mutex.WaitOne(5000) }
    catch [Threading.AbandonedMutexException] { $lockTaken = $true }
    if (-not $lockTaken) { throw 'Receiver lifecycle is busy. Try again shortly.' }
    $config = Join-Path $env:LOCALAPPDATA 'codex/telegram-notify/config.json'
    if ($Action -eq 'install' -and -not (Test-Path -LiteralPath $config -PathType Leaf)) {
        & powershell.exe -NoProfile -File (Join-Path $PSScriptRoot 'configure_telegram.ps1')
        if ($LASTEXITCODE -ne 0) { throw 'Private Telegram configuration was not completed. Setup stopped.' }
    }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $python = $null
        foreach ($name in @('py.exe','python.exe','python3.exe')) {
            $candidate = Get-Command $name -ErrorAction SilentlyContinue
            if ($null -eq $candidate) { continue }
            $arguments = @()
            if ($name -eq 'py.exe') { $arguments += '-3' }
            $arguments += @('-c','import sys; print(sys.executable) if sys.version_info >= (3,10) else sys.exit(1)')
            $detected = & $candidate.Source @arguments 2>$null
            if ($LASTEXITCODE -eq 0 -and $detected -and (Test-Path -LiteralPath ([string]$detected) -PathType Leaf)) {
                $python = [string]$detected
                break
            }
        }
        if (-not $python) { throw 'Install Python 3.10 or newer with venv support, then rerun setup. Python is not downloaded automatically.' }
    }
    & $python (Join-Path $PSScriptRoot 'installer.py') $Action --bundle (Join-Path $PSScriptRoot 'runtime')
    $exitCode = $LASTEXITCODE
} catch {
    Write-Error $_ -ErrorAction Continue
} finally {
    if ($lockTaken) { $mutex.ReleaseMutex() }
    if ($null -ne $mutex) { $mutex.Dispose() }
}
exit $exitCode
