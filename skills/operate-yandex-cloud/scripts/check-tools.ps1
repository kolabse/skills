[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ProjectPath,
    [string[]]$ScanPath,
    [string[]]$Toolset,
    [switch]$All,
    [switch]$Json,
    [switch]$InstallMissing,
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python3, python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Python 3 was not found.' }
$arguments = @((Join-Path $PSScriptRoot 'check_tools.py'), '--project-path', $ProjectPath)
foreach ($path in $ScanPath) { $arguments += @('--scan-path', $path) }
foreach ($name in $Toolset) { $arguments += @('--toolset', $name) }
if ($All) { $arguments += '--all' }
if ($Json) { $arguments += '--json' }
if ($InstallMissing) { $arguments += '--install-missing' }
if ($NonInteractive) { $arguments += '--non-interactive' }
if ($python.Name -eq 'py.exe') { $arguments = @('-3') + $arguments }
& $python.Source @arguments
exit $LASTEXITCODE
