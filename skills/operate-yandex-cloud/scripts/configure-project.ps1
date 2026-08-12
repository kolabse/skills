[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ProjectPath,
    [string]$CloudId,
    [string]$FolderId,
    [string]$YcProfile,
    [switch]$NonInteractive
)

$ErrorActionPreference = 'Stop'
$python = Get-Command python3, python, py -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Python 3 was not found.' }
$arguments = @((Join-Path $PSScriptRoot 'configure_project.py'), '--project-path', $ProjectPath)
if ($CloudId) { $arguments += @('--cloud-id', $CloudId) }
if ($FolderId) { $arguments += @('--folder-id', $FolderId) }
if ($YcProfile) { $arguments += @('--yc-profile', $YcProfile) }
if ($NonInteractive) { $arguments += '--non-interactive' }
if ($python.Name -eq 'py.exe') { $arguments = @('-3') + $arguments }
& $python.Source @arguments
if ($LASTEXITCODE -ne 0) { throw "Project configuration failed with exit code $LASTEXITCODE." }
