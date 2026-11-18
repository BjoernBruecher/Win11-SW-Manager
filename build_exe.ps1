param(
    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot
$entryPoint = Join-Path $projectRoot "Win11-SW-Manager.py"
$buildDirectory = Join-Path $projectRoot "build"
$distDirectory = Join-Path $projectRoot "dist"
$executablePath = Join-Path $distDirectory "Win11-SW-Manager.exe"

if (-not (Get-Command $PythonCommand -ErrorAction SilentlyContinue)) {
    throw "Python command '$PythonCommand' was not found."
}

if (-not (Test-Path -LiteralPath $entryPoint -PathType Leaf)) {
    throw "Application entry point not found: $entryPoint"
}

& $PythonCommand -c "import PyInstaller"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is required. Install it with: $PythonCommand -m pip install pyinstaller"
}

$arguments = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "Win11-SW-Manager",
    "--add-data",
    ("{0};src\locales" -f (Join-Path $projectRoot "src\locales")),
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
