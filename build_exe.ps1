param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$entryPoint = Join-Path $projectRoot "Win11-SW-Manager.py"
$iconPath = Join-Path $projectRoot "assets\program.ico"
$logoPath = Join-Path $projectRoot "assets\program.png"
$buildDirectory = Join-Path $projectRoot "build"
$distDirectory = Join-Path $projectRoot "dist"
$executablePath = Join-Path $distDirectory "Win11-SW-Manager.exe"

if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python command '$PythonCommand' was not found."
}

if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Application entry point not found: $entryPoint"
}

if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
    throw "Application icon not found: $iconPath"
}

if (-not (Test-Path -LiteralPath $logoPath -PathType Leaf)) {
    throw "Application logo not found: $logoPath"
}

& $PythonCommand -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is required. Install it with: $PythonCommand -m pip install pyinstaller"
}

$versionFile = Join-Path $projectRoot "src\version.py"
$versionInfoPath = Join-Path $buildDirectory "Win11-SW-Manager-version-info.txt"

if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
    throw "Application version file not found: $versionFile"
}

$versionContent = [System.IO.File]::ReadAllText($versionFile)
if ($versionContent -notmatch '(?m)^APP_VERSION = "(\d+)\.(\d+)\.(\d+)\.(\d+)"\r?$') {
    throw "Could not read a numeric APP_VERSION from $versionFile"
}

$majorVersion = [int]$Matches[1]
$minorVersion = [int]$Matches[2]
$patchVersion = [int]$Matches[3]
$commitVersion = [int]$Matches[4]
foreach ($component in @(
    $majorVersion,
    $minorVersion,
    $patchVersion,
    $commitVersion
)) {
    if ($component -lt 0 -or $component -gt 65535) {
        throw "APP_VERSION components must be between 0 and 65535."
    }
}
$appVersion = "$majorVersion.$minorVersion.$patchVersion.$commitVersion"
$buildVersion = $appVersion

New-Item -ItemType Directory -Path $buildDirectory -Force | Out-Null
$versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($majorVersion, $minorVersion, $patchVersion, $commitVersion),
    prodvers=($majorVersion, $minorVersion, $patchVersion, $commitVersion),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [
          StringStruct(u'CompanyName', u'Bjoern Bruecher'),
          StringStruct(u'FileDescription', u'Win11 Software Manager'),
          StringStruct(u'FileVersion', u'$buildVersion'),
          StringStruct(u'InternalName', u'Win11-SW-Manager'),
          StringStruct(u'LegalCopyright', u'Copyright (C) 2026 Bjoern Bruecher'),
          StringStruct(u'OriginalFilename', u'Win11-SW-Manager.exe'),
          StringStruct(u'ProductName', u'Win11-SW-Manager'),
          StringStruct(u'ProductVersion', u'$appVersion')
        ]
      )
    ]),
    VarFileInfo([VarStruct(u'Translation', [0x0409, 1200])])
  ]
)
"@
[System.IO.File]::WriteAllText(
    $versionInfoPath,
    $versionInfo,
    (New-Object System.Text.UTF8Encoding($false))
)

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--uac-admin",
    "--name", "Win11-SW-Manager",
    "--icon", $iconPath,
    "--version-file", $versionInfoPath,
    "--add-data",
    ("{0};src\locales" -f (Join-Path $projectRoot "src\locales")),
    "--add-data",
    ("{0};assets" -f $iconPath),
    "--add-data",
    ("{0};assets" -f $logoPath),
    "--distpath", $distDirectory,
    "--workpath", (Join-Path $buildDirectory "work"),
    "--specpath", $buildDirectory,
    $entryPoint
)

Push-Location -LiteralPath $projectRoot
try {
    & $PythonCommand @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
    throw "Build completed without producing the expected executable: $executablePath"
}

Write-Host "Created standalone executable: $executablePath"
