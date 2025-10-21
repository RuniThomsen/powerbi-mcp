param(
    [switch]$SetUserEnv = $false
)

Write-Host "Installing Microsoft.AnalysisServices.AdomdClient via NuGet..." -ForegroundColor Cyan

if (-not (Get-Command dotnet -ErrorAction SilentlyContinue)) {
    Write-Error "dotnet CLI not found. Please install .NET SDK first."
    exit 1
}

$temp = New-Item -ItemType Directory -Path ([System.IO.Path]::Combine([System.IO.Path]::GetTempPath(), "adomd_setup_" + ([System.Guid]::NewGuid().ToString())))
try {
    dotnet new classlib -n temp_adomd -o $temp -f net8.0 | Out-Null
    Push-Location $temp
    dotnet add package Microsoft.AnalysisServices.AdomdClient | Out-Null
    dotnet add package System.Configuration.ConfigurationManager | Out-Null
    dotnet restore | Out-Null
} finally {
    Pop-Location
}

$nuget = Join-Path $env:USERPROFILE ".nuget\packages\microsoft.analysisservices.adomdclient"
if (-not (Test-Path $nuget)) {
    Write-Error "NuGet cache not found at $nuget"
    exit 1
}

$preferred = @('net8.0','net6.0','netstandard2.0','net48','net472','net471','net47')
$libPath = $null
Get-ChildItem -Directory $nuget | Sort-Object Name -Descending | ForEach-Object {
    $ver = $_.FullName
    foreach ($tfm in $preferred) {
        $p = Join-Path $ver ("lib\" + $tfm)
        if (Test-Path $p) { $libPath = $p; break }
    }
    if ($libPath) { break }
}

if (-not $libPath) {
    Write-Error "Failed to locate ADOMD lib path under $nuget"
    exit 1
}

Write-Host "ADOMD_LIB_DIR=$libPath" -ForegroundColor Green
if ($SetUserEnv) {
    setx ADOMD_LIB_DIR "$libPath" | Out-Null
    Write-Host "Persisted ADOMD_LIB_DIR as a user environment variable." -ForegroundColor Yellow
}

exit 0
<#
.SYNOPSIS
  Seeds local NuGet cache with ADOMD.NET and required dependencies on Windows.

.DESCRIPTION
  Creates a temporary .NET console project, adds needed packages (ADOMD.NET,
  System.Configuration.ConfigurationManager, System.Data.SqlClient), and runs restore.
  Prints the discovered ADOMD library path to set ADOMD_LIB_DIR if desired.

.USAGE
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/install_dotnet_adomd.ps1

.NOTES
  Requires .NET SDK 6+ (SDK recommended; runtime alone may not include dotnet CLI).
#>

param(
  [switch]$ForceClean
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO ] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN ] $msg" -ForegroundColor Yellow }
function Write-Err ($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

# 1) Verify dotnet CLI
try {
  $dotnetVersion = (& dotnet --version) 2>$null
  if (-not $dotnetVersion) { throw 'dotnet not found' }
  Write-Info "dotnet CLI detected: $dotnetVersion"
} catch {
  Write-Err "dotnet CLI not found. Please install .NET SDK: https://dotnet.microsoft.com/download"
  exit 1
}

function New-SeedProjectDirectory {
  param(
    [Parameter(Mandatory=$true)][string]$Root
  )
  if (-not (Test-Path -LiteralPath $Root)) {
    New-Item -ItemType Directory -Force -Path $Root | Out-Null
  }
  $timestamp = Get-Date -Format 'yyyyMMdd_HHmmssfff'
  $dir = Join-Path $Root $timestamp
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  # Resolve to a fully qualified literal path to avoid 8.3 short names and spaces issues
  $resolved = (Resolve-Path -LiteralPath $dir).Path
  return $resolved
}

# 2) Create temp project (robust to spaces/8.3 paths)
$tempBase = [System.IO.Path]::GetTempPath()
if (-not $tempBase -or $tempBase.Trim().Length -eq 0) { $tempBase = $env:TEMP }
if (-not $tempBase -or $tempBase.Trim().Length -eq 0) { throw 'TEMP directory not resolved' }

$seedRoot = Join-Path $tempBase "adomd-seed"
if ((Test-Path -LiteralPath $seedRoot) -and $ForceClean) {
  Write-Info "Removing existing seed folder: $seedRoot"
  Remove-Item -Recurse -Force -LiteralPath $seedRoot
}

$projDir = New-SeedProjectDirectory -Root $seedRoot
Write-Info "Using seed project directory: $projDir"
Push-Location -LiteralPath $projDir

Write-Info "Creating console project in $projDir"
& dotnet new console --framework net8.0 | Out-Null

# 3) Add packages (pin ADOMD; allow latest for others)
$adomdVersion = '19.103.2'
Write-Info "Adding NuGet packages"
& dotnet add package Microsoft.AnalysisServices.AdomdClient --version $adomdVersion | Out-Null
& dotnet add package System.Configuration.ConfigurationManager | Out-Null
& dotnet add package System.Data.SqlClient | Out-Null

Write-Info "Restoring packages"
& dotnet restore | Out-Null

Pop-Location

# 4) Discover ADOMD lib path from NuGet cache
$nuget = Join-Path $env:USERPROFILE ".nuget\packages"
$adomdBase = Join-Path $nuget "microsoft.analysisservices.adomdclient"
if (-not (Test-Path $adomdBase)) {
  Write-Warn "ADOMD package not found at $adomdBase. Something went wrong with restore."
  exit 2
}

# Prefer net8.0, fall back to others
$targets = @('net8.0','net6.0','netstandard2.0','net48','net472','net471','net47')
$latest = Get-ChildItem -Path $adomdBase -Directory | Sort-Object Name -Descending | Select-Object -First 1
$libPath = $null
foreach ($t in $targets) {
  $p = Join-Path $latest.FullName ("lib\" + $t)
  if (Test-Path $p) { $libPath = $p; break }
}

if (-not $libPath) {
  Write-Warn "No compatible target framework folder found under $adomdBase/$($latest.Name)"
  exit 3
}

$adomdDll = Join-Path $libPath 'Microsoft.AnalysisServices.AdomdClient.dll'
if (-not (Test-Path $adomdDll)) {
  Write-Warn "ADOMD DLL not found at $adomdDll"
  exit 4
}

Write-Host "" 
Write-Info "Seed complete. Discovered ADOMD library path:"
Write-Host "  $libPath" -ForegroundColor Green
Write-Host ""
Write-Info "Optional: set ADOMD_LIB_DIR for pythonnet to resolve assemblies:"
Write-Host "  setx ADOMD_LIB_DIR `"$libPath`"" -ForegroundColor DarkGreen
Write-Host ""
Write-Info "If running in the current shell session, also add to PATH for DLL resolution:"
Write-Host "  [System.Environment]::SetEnvironmentVariable('ADOMD_LIB_DIR', '$libPath', 'Process')" -ForegroundColor DarkGreen
Write-Host "  $([System.Environment]::SetEnvironmentVariable('PATH', "$libPath;" + [System.Environment]::GetEnvironmentVariable('PATH','Process'),'Process'))" -ForegroundColor DarkGreen
