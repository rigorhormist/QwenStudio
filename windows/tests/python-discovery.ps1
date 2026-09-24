$ErrorActionPreference = 'Stop'
$VerbosePreference = 'Continue'
. (Join-Path $PSScriptRoot '..\find-python.ps1')
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
$python = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source
$actual = Test-StudioPython $python
Assert ($actual -and $actual.compatible) ('The CI Python must be supported: ' + $python + ' / ' + ($actual | ConvertTo-Json -Compress))

$temp = Join-Path ([IO.Path]::GetTempPath()) ('Qwen discovery ' + [Guid]::NewGuid())
$registry = 'HKCU:\Software\Python\QwenStudioDiscoveryTest-' + [Guid]::NewGuid()
$oldPath = $env:PATH
$oldData = $env:QWEN_STUDIO_DATA
$originalProbe = (Get-Item Function:Invoke-PythonDiscoveryCommand).ScriptBlock
try {
    # A real venv, with spaces and an apostrophe, exercises process argument handling.
    $venv = Join-Path $temp "runtime's folder"
    & $python -m venv --without-pip $venv
    Assert ($LASTEXITCODE -eq 0) 'Could not create the isolated runtime.'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    $found = Find-StudioPython -Preferred @($venvPython)
    Assert ($found.found -and $found.python.executable -eq $venvPython -and $found.python.virtual) 'Prefer an existing working app environment.'

    $env:QWEN_STUDIO_DATA = Join-Path $temp 'persistent data'
    New-Item -ItemType Directory -Path $env:QWEN_STUDIO_DATA -Force | Out-Null
    $stateFile = Join-Path $env:QWEN_STUDIO_DATA 'runtime-path.json'
    @{ python=$venvPython } | ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
    $found = Find-StudioPython -Preferred @(Get-StudioRuntimeCandidates)
    Assert ($found.python.executable -eq $venvPython) 'A new release must find the already repaired runtime.'
    '{broken pointer' | Set-Content -LiteralPath $stateFile -Encoding UTF8
    $found = Find-StudioPython -Preferred @(Get-StudioRuntimeCandidates)
    Assert $found.found 'A malformed pointer must not prevent system discovery.'

    $missing = Join-Path $temp 'missing\python.exe'
    $found = Find-StudioPython -Preferred @($missing)
    Assert $found.found 'Freshly extracted packages must find system Python.'
    $explicit = Find-StudioPython -Explicit $missing
    Assert (-not $explicit.found) 'Never replace an explicit missing override silently.'

    New-Item -Path ($registry + '\3.11\InstallPath') -Force | Out-Null
    Set-Item -LiteralPath ($registry + '\3.11\InstallPath') -Value (Split-Path $venvPython)
    New-ItemProperty -LiteralPath ($registry + '\3.11\InstallPath') -Name ExecutablePath -Value $venvPython -Force | Out-Null
    $env:PATH = ''
    Assert (@(Get-StudioPythonCandidates) -contains $venvPython) 'Find registered Python even when it is absent from PATH.'

    $env:PATH = (Split-Path $venvPython)
    Assert (@(Get-StudioPythonCandidates) -contains $venvPython) 'Find a custom environment on PATH.'
    $env:PATH = $oldPath

    function Invoke-PythonDiscoveryCommand { return '{"executable":"C:\\python.exe","version":[3,14,0],"bits":64,"virtual":false}' }
    Assert (-not (Test-StudioPython $python).compatible) 'Unsupported Python versions must not pass.'
    function Invoke-PythonDiscoveryCommand { return '{"executable":"C:\\python.exe","version":[3,11,0],"bits":32,"virtual":false}' }
    Assert (-not (Test-StudioPython $python).compatible) '32-bit Python must not pass.'
    function Invoke-PythonDiscoveryCommand { return 'not a Python response' }
    Assert ($null -eq (Test-StudioPython $python)) 'Broken executables must not pass.'
    Set-Item Function:Invoke-PythonDiscoveryCommand $originalProbe
    Write-Host 'PASS: existing runtime, fresh package, registry without PATH, explicit override, version and architecture.'
} finally {
    $env:PATH = $oldPath
    $env:QWEN_STUDIO_DATA = $oldData
    Set-Item Function:Invoke-PythonDiscoveryCommand $originalProbe
    if (Test-Path -LiteralPath $registry) { Remove-Item -LiteralPath $registry -Recurse -Force }
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Recurse -Force }
}
