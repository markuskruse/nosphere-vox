$ErrorActionPreference = "Stop"

# Build Windows binary for vox.py using PyInstaller.
# Run from the repo root on Windows with Python and PyInstaller installed.

$dist = "dist\windows"
$build = "build\windows"
$asset = Join-Path $PSScriptRoot "assets\nosphere-vox.png"
$targets = @("vox.py")

if (Test-Path $dist) { Remove-Item -Recurse -Force $dist -ErrorAction SilentlyContinue }
if (Test-Path $build) { Remove-Item -Recurse -Force $build -ErrorAction SilentlyContinue }
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
        --add-data "$asset;assets" `
        $target
}
