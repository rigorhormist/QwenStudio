param([switch]$AsJson, [switch]$All, [string]$Selected = "")

# Internal discovery helper bundled in the desktop EXE. Merely finding python.exe is
# insufficient: Windows Store aliases, removed installations and 32-bit Python
# must not pass the environment check.
function Invoke-PythonDiscoveryCommand([string]$Executable, [string]$Arguments) {
    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $process.StartInfo.FileName = $Executable
    $process.StartInfo.Arguments = $Arguments
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.CreateNoWindow = $true
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $process.StartInfo.StandardErrorEncoding = [System.Text.Encoding]::UTF8
    try {
        [void]$process.Start()
        $output = $process.StandardOutput.ReadToEndAsync()
        $errorOutput = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(5000)) {
            $process.Kill()
            return $null
        }
        if ($process.ExitCode -ne 0) { Write-Verbose ($Executable + ": " + $errorOutput.GetAwaiter().GetResult()); return $null }
        return $output.GetAwaiter().GetResult()
    } catch { Write-Verbose ($Executable + ": " + $_.Exception.Message); return $null } finally { $process.Dispose() }
}

function Test-StudioPython([string]$Executable) {
    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { return $null }
    # Skip the App Installer aliases, which can open the Store instead of Python.
    if ($Executable -match '(?i)\\Microsoft\\WindowsApps\\python(?:3)?\.exe$') { return $null }
    $code = "import json,sys;print(json.dumps(dict(executable=sys.executable,version=list(sys.version_info[:3]),bits=64 if sys.maxsize>2**32 else 32,virtual=sys.prefix!=sys.base_prefix)))"
    $raw = Invoke-PythonDiscoveryCommand $Executable ('-I -B -X utf8 -c "' + $code + '"')
    try {
        $result = $raw | ConvertFrom-Json -ErrorAction Stop
        if (-not $result.executable -or $result.version.Count -ne 3) { return $null }
        return [pscustomobject]@{
            executable = [string]$result.executable
            version = ($result.version -join '.')
            bits = [int]$result.bits
            virtual = [bool]$result.virtual
            compatible = $result.version[0] -eq 3 -and $result.version[1] -ge 10 -and $result.version[1] -lt 14 -and $result.bits -eq 64
        }
    } catch { Write-Verbose ($Executable + ": " + $_.Exception.Message); return $null }
}

function Get-StudioPythonCandidates {
    $paths = @($env:PATH, [Environment]::GetEnvironmentVariable('Path','User'), [Environment]::GetEnvironmentVariable('Path','Machine'))
    $directories = @($paths | Where-Object { $_ } | ForEach-Object { $_ -split ';' } | Where-Object { $_ } | Select-Object -Unique)
    $launchers = @((Get-Command py.exe -CommandType Application -All -ErrorAction SilentlyContinue).Source)
    foreach ($directory in $directories) {
        $directory = [Environment]::ExpandEnvironmentVariables($directory.Trim('"'))
        $launchers += Join-Path $directory 'py.exe'
    }
    foreach ($launcher in ($launchers | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $launcher -PathType Leaf)) { continue }
        $listing = Invoke-PythonDiscoveryCommand $launcher '-0p'
        foreach ($line in ($listing -split "`r?`n")) {
            if ($line -match '(?i)((?:[A-Z]:\\|\\\\).+?python(?:[0-9.]+)?\.exe)\s*$') { $Matches[1] }
        }
    }
    # PEP 514 registrations also find python.org installs without an entry in PATH.
    foreach ($registry in @('HKCU:\Software\Python','HKLM:\Software\Python','HKLM:\Software\WOW6432Node\Python')) {
        foreach ($company in (Get-ChildItem -LiteralPath $registry -ErrorAction SilentlyContinue)) {
            foreach ($tag in (Get-ChildItem -LiteralPath $company.PSPath -ErrorAction SilentlyContinue)) {
                $install = Get-Item -LiteralPath ($tag.PSPath + '\InstallPath') -ErrorAction SilentlyContinue
                if ($install) {
                    $exe = $install.GetValue('ExecutablePath')
                    if ($exe) { [string]$exe }
                    $base = $install.GetValue('')
                    if ($base) { Join-Path ([string]$base) 'python.exe' }
                }
            }
        }
    }
    foreach ($parent in @("$env:USERPROFILE\miniconda3", "$env:USERPROFILE\anaconda3", "$env:LOCALAPPDATA\miniconda3", "$env:USERPROFILE\.pyenv\pyenv-win\versions")) {
        if (-not (Test-Path -LiteralPath $parent)) { continue }
        Join-Path $parent 'python.exe'
        Get-ChildItem -LiteralPath $parent -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'python.exe' }
        $envs = Join-Path $parent 'envs'
        if (Test-Path -LiteralPath $envs) { Get-ChildItem -LiteralPath $envs -Directory | ForEach-Object { Join-Path $_.FullName 'python.exe' } }
    }
    # Real Store Python packages are separate from the zero-byte App Installer aliases.
    if (Get-Command Get-AppxPackage -ErrorAction SilentlyContinue) {
        try {
            foreach ($package in (Get-AppxPackage -Name 'PythonSoftwareFoundation.Python*' -ErrorAction SilentlyContinue)) {
                if ($package.InstallLocation) {
                    Join-Path $package.InstallLocation 'python.exe'
                    Join-Path $package.InstallLocation 'python3.exe'
                }
            }
        } catch { Write-Verbose $_.Exception.Message }
    }
    foreach ($directory in $directories) {
        $directory = [Environment]::ExpandEnvironmentVariables($directory.Trim('"'))
        foreach ($name in @('python.exe','python3.exe')) { Join-Path $directory $name }
    }
    foreach ($parent in @("$env:LOCALAPPDATA\Programs\Python", $env:ProgramFiles, "$env:SystemDrive\")) {
        if (-not $parent -or -not (Test-Path -LiteralPath $parent)) { continue }
        Get-ChildItem -LiteralPath $parent -Directory -Filter 'Python*' -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'python.exe' }
    }
}

function Find-StudioPython([string[]]$Preferred = @(), [string]$Explicit = '') {
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $rejected = @()
    # Explicit overrides are never silently replaced with an unrelated environment.
    $candidates = if ($Explicit) { @($Explicit) } else { @($Preferred) }
    foreach ($stage in 0,1) {
        foreach ($candidate in $candidates) {
            if (-not $candidate -or -not $seen.Add($candidate)) { continue }
            $result = Test-StudioPython $candidate
            if ($result -and $result.compatible) { return [pscustomobject]@{found=$true;python=$result;rejected=$rejected} }
            if ($result) { $rejected += $result }
        }
        if ($Explicit -or $stage -eq 1) { break }
        $candidates = @(Get-StudioPythonCandidates)
    }
    return [pscustomobject]@{found=$false;python=$null;rejected=$rejected}
}

function Get-StudioDataPath {
    if ($env:QWEN_STUDIO_DATA) { return $env:QWEN_STUDIO_DATA }
    foreach ($file in @((Join-Path $PSScriptRoot 'settings.local.json'), (Join-Path $env:LOCALAPPDATA 'QwenStudio\locations.json'))) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { continue }
        $settings = Get-Content -LiteralPath $file -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        if ($settings.data -is [string] -and $settings.data.Trim()) { return [string]$settings.data }
    }
    return (Join-Path $env:LOCALAPPDATA 'QwenStudio')
}

function Get-StudioRuntimeCandidates {
    # Per-user selection survives extracting a newer release to another folder.
    foreach ($directory in @((Get-StudioDataPath), $PSScriptRoot)) {
        try {
            $value = (Get-Content -LiteralPath (Join-Path $directory 'runtime-path.json') -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json).python
            if ($value -is [string] -and $value.Trim()) {
                if ([IO.Path]::IsPathRooted($value)) { $value } else { Join-Path $directory $value }
            }
        } catch { Write-Verbose $_.Exception.Message }
    }
    Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    # Older folder-based releases keep their runtime next to the EXE's parent.
    foreach ($directory in @($env:QWEN_STUDIO_LAUNCH_DIR, $(if ($env:QWEN_STUDIO_LAUNCH_DIR) { Split-Path $env:QWEN_STUDIO_LAUNCH_DIR -Parent }))) {
        if (-not $directory) { continue }
        Join-Path $directory '.venv\Scripts\python.exe'
        try {
            $value = (Get-Content -LiteralPath (Join-Path $directory 'runtime-path.json') -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json).python
            if ($value -is [string] -and $value.Trim()) { if ([IO.Path]::IsPathRooted($value)) { $value } else { Join-Path $directory $value } }
        } catch { Write-Verbose $_.Exception.Message }
    }
}

function Get-StudioPythonList([string]$Selected = '') {
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $executables = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $items = @()
    $explicit = if ($env:QWEN_STUDIO_PYTHON) { $env:QWEN_STUDIO_PYTHON } else { $Selected }
    $paths = @($explicit) + @(Get-StudioRuntimeCandidates) + @(Get-StudioPythonCandidates)
    foreach ($candidate in $paths) {
        if (-not $candidate -or -not $seen.Add($candidate)) { continue }
        $result = Test-StudioPython $candidate
        if ($result -and $executables.Add($result.executable)) { $items += $result }
        if ($result -and $explicit -and $candidate -eq $explicit) { $explicit = $result.executable }
    }
    # PowerShell 5.1 does not expose .Count on a single PSCustomObject.
    # Select directly so a one-element result cannot disappear as an empty list.
    $python = $items | Where-Object { $_.compatible -and ((-not $explicit) -or $_.executable -eq $explicit) } | Select-Object -First 1
    [pscustomobject]@{found=($null -ne $python);python=$python;candidates=@($items);rejected=@($items | Where-Object { -not $_.compatible });selected=$explicit}
}

if ($AsJson) {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    if ($All) { Get-StudioPythonList -Selected $Selected | ConvertTo-Json -Depth 5 -Compress }
    else { Find-StudioPython -Preferred @(Get-StudioRuntimeCandidates) -Explicit $env:QWEN_STUDIO_PYTHON | ConvertTo-Json -Depth 5 -Compress }
}
