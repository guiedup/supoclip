[CmdletBinding()]
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
$argsList = @('scripts\windows\manage.py', 'start')
if ($NoBrowser) { $argsList += '--no-browser' }
& '.\backend\.venv\Scripts\python.exe' @argsList
if ($LASTEXITCODE -ne 0) { throw 'Startup failed. Check .local\logs.' }
