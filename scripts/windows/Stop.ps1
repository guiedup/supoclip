[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& '.\backend\.venv\Scripts\python.exe' 'scripts\windows\manage.py' 'stop'
if ($LASTEXITCODE -ne 0) { throw 'Stop failed. Active tasks are protected; check the message above.' }
