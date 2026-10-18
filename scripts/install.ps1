#Requires -Version 5.1
param()

$ErrorActionPreference = 'Stop'

$InstallRoot = $env:AGENTIC_ODI_INSTALL_DIR
if (-not $InstallRoot) {
  $dataHome = $env:XDG_DATA_HOME
  if (-not $dataHome) { $dataHome = Join-Path $env:LOCALAPPDATA 'agentic-odi' -ErrorAction SilentlyContinue }
  if (-not $dataHome) { $dataHome = Join-Path $env:USERPROFILE '.local\share\agentic-odi' }
  $InstallRoot = $dataHome
}
$BinDir = $env:AGENTIC_ODI_BIN_DIR
if (-not $BinDir) {
  $BinDir = Join-Path $env:LOCALAPPDATA 'agentic-odi\bin' -ErrorAction SilentlyContinue
  if (-not $BinDir) { $BinDir = Join-Path $env:USERPROFILE '.local\bin' }
}

function Detect-Arch {
  $arch = $env:PROCESSOR_ARCHITECTURE
  switch ($arch) {
    'AMD64' { return 'x86_64' }
    'ARM64' { return 'arm64' }
    default { return 'x86_64' }
  }
}

function Resolve-Version {
  if ($env:AGENTIC_ODI_VERSION) { return $env:AGENTIC_ODI_VERSION.Trim() }
  $apiBase = $env:AGENTIC_ODI_BASE_URL
  if (-not $apiBase) { $apiBase = 'https://api.github.com/repos/alehar9320/agentic-odi/releases/latest' }
  if ($apiBase -notmatch 'api\.github\.com') { return '0.1.0' }
  try {
    $resp = Invoke-RestMethod -Uri $apiBase -Method Get -UserAgent 'agentic-odi-installer'
    if ($resp.tag_name) { return $resp.tag_name.TrimStart('v') }
  } catch {}
  return '0.1.0'
}

$Os = 'windows'
$Arch = Detect-Arch
$Version = Resolve-Version
$Target = "${Os}_${Arch}"
$ArchiveName = "odi_${Version}_${Target}.zip"
$ChecksumsName = 'checksums.txt'

$Base = $env:AGENTIC_ODI_BASE_URL
if (-not $Base) { $Base = 'https://github.com/alehar9320/agentic-odi/releases' }
if ($Base -match 'api\.github\.com') { $Base = 'https://github.com/alehar9320/agentic-odi/releases' }
$DlBase = "$Base/download/v$Version"

New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot 'versions') | Out-Null
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

$tmpDir = New-Item -ItemType Directory -Path (Join-Path $env:TEMP ("odi-inst-" + [guid]::NewGuid().ToString())) -Force
try {
  $archivePath = Join-Path $tmpDir $ArchiveName
  $checksumsPath = Join-Path $tmpDir $ChecksumsName
  Invoke-WebRequest -Uri "$DlBase/$ArchiveName" -OutFile $archivePath -UserAgent 'agentic-odi-installer'
  Invoke-WebRequest -Uri "$DlBase/$ChecksumsName" -OutFile $checksumsPath -UserAgent 'agentic-odi-installer'

  $expected = $null
  foreach ($line in Get-Content $checksumsPath) {
    if ($line -match "([0-9a-fA-F]{64})\s+\*?${ArchiveName}") {
      $expected = $Matches[1].ToLower()
      break
    }
    if ($line -match "([0-9a-fA-F]{64})\s+${ArchiveName}") {
      $expected = $Matches[1].ToLower()
      break
    }
  }
  if ($expected) {
    $hash = (Get-FileHash -Algorithm SHA256 -Path $archivePath).Hash.ToLower()
    if ($hash -ne $expected) { throw "Checksum verification failed for $ArchiveName" }
  }

  $verDir = Join-Path (Join-Path $InstallRoot 'versions') $Version
  if (Test-Path $verDir) { Remove-Item $verDir -Recurse -Force }
  New-Item -ItemType Directory -Force -Path $verDir | Out-Null
  Expand-Archive -Path $archivePath -DestinationPath $verDir -Force

  $currentMarker = Join-Path $InstallRoot 'current'
  Set-Content -Path $currentMarker -Value $verDir -Force

  $names = @('odi.exe','odipm.exe','odi-cli.exe','agentic-odi.exe')
  foreach ($n in $names) {
    $src = Join-Path $verDir 'odi.exe'
    if (-not (Test-Path $src)) { $src = Join-Path $verDir 'odi' }
    $dst = Join-Path $BinDir $n
    Copy-Item -Path $src -Destination $dst -Force
  }

  if (($env:PATH -split ';') -notcontains $BinDir) {
    Write-Host "Add $BinDir to your PATH"
  }
  Write-Host "Installed odi $Version to $verDir"
} finally {
  Remove-Item $tmpDir -Recurse -Force
}
