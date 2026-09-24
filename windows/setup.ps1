param(
    [string]$Python = '',
    [ValidateSet('cu130','cu128')][string]$Cuda = 'cu130'
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
. (Join-Path $PSScriptRoot 'find-python.ps1')
$explicit = if ($env:QWEN_STUDIO_PYTHON) { $env:QWEN_STUDIO_PYTHON } else { $Python }
$discovery = Find-StudioPython -Preferred @(Get-StudioRuntimeCandidates) -Explicit $explicit
if (-not $discovery.found) {
    throw 'Install a working 64-bit Python 3.10-3.13, then retry. Existing runtime files were not changed.'
}
$studioPython = $discovery.python.executable
& $studioPython -X utf8 (Join-Path $PSScriptRoot 'backend\runtime_setup.py') --root $PSScriptRoot --data (Get-StudioDataPath) --python $studioPython --cuda $Cuda
exit $LASTEXITCODE
