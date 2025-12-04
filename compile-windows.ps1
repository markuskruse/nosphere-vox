$ErrorActionPreference = "Stop"

# Build Windows binaries for all Python scripts using PyInstaller.
# Run from the repo root on Windows with Python and PyInstaller installed.

$dist = "dist\windows"
$build = "build\windows"
$targets = Get-ChildItem -Path . -Filter "*.py" | ForEach-Object { $_.Name }

if (Test-Path $dist) { Remove-Item -Recurse -Force $dist }
if (Test-Path $build) { Remove-Item -Recurse -Force $build }
New-Item -ItemType Directory -Force -Path $dist | Out-Null

foreach ($target in $targets) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($target)
    $targetBuild = Join-Path $build $name
    New-Item -ItemType Directory -Force -Path $targetBuild | Out-Null

    python -m PyInstaller `
        --onefile `
        --windowed `
        --name $name `
        --distpath $dist `
        --workpath $targetBuild `
        --specpath $targetBuild `
        --clean `
        $target
}
