param(
    [Parameter(Mandatory = $true)]
    [string]$Version,

    [string]$PythonCommand = "python"
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$versionFile = Join-Path $projectRoot "src\version.py"
$buildScript = Join-Path $projectRoot "build_exe.ps1"
$executablePath = Join-Path $projectRoot "dist\Win11-SW-Manager.exe"
$checksumPath = "$executablePath.sha256"

if ($Version -notmatch '^\d+\.\d+$') {
    throw "Version must contain the major and minor numbers, for example 1.2."
}

foreach ($command in @("git", "gh", $PythonCommand)) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command '$command' was not found."
    }
}

if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) {
    throw "Application version file not found: $versionFile"
}

if (-not (Test-Path -LiteralPath $buildScript -PathType Leaf)) {
    throw "Build script not found: $buildScript"
}

Push-Location -LiteralPath $projectRoot
try {
    $repositoryRoot = (& git rev-parse --show-toplevel).Trim()
    if (
        $LASTEXITCODE -ne 0 -or
        [System.IO.Path]::GetFullPath($repositoryRoot) -ne $projectRoot
    ) {
        throw "The release script must run from the root of a Git repository."
    }

    $worktreeStatus = & git status --porcelain
    if ($LASTEXITCODE -ne 0) {
        throw "Could not read Git worktree status."
    }
    if ($worktreeStatus) {
        throw "Commit or stash all existing changes before creating a release."
    }

    $currentCommitCount = (& git rev-list --count HEAD).Trim()
    if (
        $LASTEXITCODE -ne 0 -or
        $currentCommitCount -notmatch '^\d+$'
    ) {
        throw "Could not determine the current Git commit count."
    }
    $commitNumber = [long]$currentCommitCount + 1
    $appVersion = "$Version.$commitNumber"
    $tag = "v$appVersion"

    $existingTag = & git tag --list $tag
    if ($LASTEXITCODE -ne 0) {
        throw "Could not check whether tag '$tag' already exists."
    }
    if ($existingTag) {
        throw "Release tag '$tag' already exists."
    }

    & gh auth status
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub CLI authentication is required. Run 'gh auth login' first."
    }

    $originalVersionContent = [System.IO.File]::ReadAllText($versionFile)
    if ($originalVersionContent -notmatch '(?m)^APP_VERSION = "[^"]+"\r?$') {
        throw "Could not find APP_VERSION in $versionFile."
    }
    $updatedVersionContent = $originalVersionContent -replace `
        '(?m)^APP_VERSION = "[^"]+"\r?$',
        "APP_VERSION = `"$appVersion`""
    $utf8WithoutBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        $versionFile,
        $updatedVersionContent,
        $utf8WithoutBom
    )

    try {
        & $buildScript -PythonCommand $PythonCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Executable build failed."
        }
        if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) {
            throw "Build completed without producing $executablePath."
        }
        $sha256 = (Get-FileHash -LiteralPath $executablePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $checksumContent = "$sha256  Win11-SW-Manager.exe$([Environment]::NewLine)"
        [System.IO.File]::WriteAllText(
            $checksumPath,
            $checksumContent,
            $utf8WithoutBom
        )
    }
    catch {
        [System.IO.File]::WriteAllText(
            $versionFile,
            $originalVersionContent,
            $utf8WithoutBom
        )
        throw
    }

    & git add -- "src/version.py"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not stage the application version change."
    }

    & git commit -m "Release $tag"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not commit the application version change."
    }

    $releasedCommitCount = (& git rev-list --count HEAD).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify the release commit count."
    }
    if ([long]$releasedCommitCount -ne $commitNumber) {
        throw "The release commit count changed unexpectedly; version $appVersion does not match HEAD."
    }

    & git tag -a $tag -m "Release $tag"
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create release tag '$tag'."
    }

    & git push origin $tag
    if ($LASTEXITCODE -ne 0) {
        throw "Could not push release tag '$tag' to origin."
    }

    & gh release create $tag $executablePath $checksumPath --title "Win11-SW-Manager $tag" --generate-notes
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub release creation failed. The local version commit and pushed tag remain."
    }

    Write-Host "Published GitHub release $tag with $executablePath"
    Write-Host "SHA-256: $sha256"
}
finally {
    Pop-Location
}
