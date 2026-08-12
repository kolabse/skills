[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ProjectPath,
    [string[]]$ScanPath,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python3, python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Python 3 was not found.' }
$arguments = @((Join-Path $PSScriptRoot 'preflight.py'), '--project-path', $ProjectPath)
foreach ($path in $ScanPath) { $arguments += @('--scan-path', $path) }
if ($Json) { $arguments += '--json' }
if ($python.Name -eq 'py.exe') { $arguments = @('-3') + $arguments }
& $python.Source @arguments
exit $LASTEXITCODE
