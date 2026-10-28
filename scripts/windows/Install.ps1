[CmdletBinding()]
param([string]$RouterUrl, [string]$SttModel, [switch]$UseLocalWhisper)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $root
if ($SttModel -and $UseLocalWhisper) { throw 'Choose -SttModel or -UseLocalWhisper, not both.' }
function Invoke-Checked([scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" }
}
foreach ($tool in @('node', 'npm.cmd', 'uv', 'ffmpeg', 'ffprobe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Missing $tool. Install Node.js LTS, uv and FFmpeg (with libass), then retry. See docs/windows-native.md."
    }
}
if ((Test-Path -LiteralPath '.local\processes.json') -and (Test-Path -LiteralPath 'backend\.venv\Scripts\python.exe')) {
    Invoke-Checked { & '.\backend\.venv\Scripts\python.exe' 'scripts\windows\manage.py' 'stop' }
}
New-Item -ItemType Directory -Force '.local\tools', '.local\logs', '.local\validation' | Out-Null
$tesseract = Join-Path $env:ProgramFiles 'Tesseract-OCR\tesseract.exe'
if (-not (Get-Command tesseract -ErrorAction SilentlyContinue) -and -not (Test-Path -LiteralPath $tesseract)) {
    Invoke-Checked { winget install --id UB-Mannheim.TesseractOCR -e --silent --accept-package-agreements --accept-source-agreements --disable-interactivity }
}
Push-Location backend
try { Invoke-Checked { uv sync --frozen --python 3.12 --extra cpu --group dev } } finally { Pop-Location }
Push-Location frontend
try { Invoke-Checked { npm.cmd exec --yes --package=pnpm@10.27.0 -- pnpm install --frozen-lockfile } } finally { Pop-Location }
$setupArgs = @('scripts\windows\setup.py')
if ($RouterUrl) { $setupArgs += @('--router-url', $RouterUrl) }
if ($SttModel) { $setupArgs += @('--stt-model', $SttModel) }
if ($UseLocalWhisper) { $setupArgs += '--local-whisper' }
Invoke-Checked { & '.\backend\.venv\Scripts\python.exe' @setupArgs }
Push-Location frontend
try {
    $previousNodeOptions = $env:NODE_OPTIONS
    $env:NODE_OPTIONS = '--max-old-space-size=1536'
    $env:NEXT_TELEMETRY_DISABLED = '1'
    Invoke-Checked { npm.cmd exec --yes --package=pnpm@10.27.0 -- pnpm run build }
} finally {
    $env:NODE_OPTIONS = $previousNodeOptions
    Pop-Location
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'SupoClip.lnk'))
$shortcut.TargetPath = 'powershell.exe'
$shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $PSScriptRoot 'Start.ps1') + '"'
$shortcut.WorkingDirectory = $root
$shortcut.WindowStyle = 7
$shortcut.Description = 'Start local SupoClip, PostgreSQL, Redis, API and worker'
$shortcut.Save()
Write-Host 'Installed. Start with the SupoClip desktop shortcut. Logs: .local\logs'
