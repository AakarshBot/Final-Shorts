$ErrorActionPreference = "Stop"
$PackageUrl = "https://mirror.msys2.org/mingw/ucrt64/mingw-w64-ucrt-x86_64-fribidi-1.0.17-1-any.pkg.tar.zst"
$ExpectedSha256 = "3581ee03cf83a9bb0e98bf688c4f532a29553500e317532d90746de295b0f8a8"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DllDirectory = Join-Path $RepoRoot "dlls"
$TemporaryRoot = Join-Path $env:TEMP ("final-shorts-fribidi-" + [guid]::NewGuid().ToString("N"))
$PackagePath = Join-Path $TemporaryRoot "fribidi.pkg.tar.zst"
$ExtractorPath = Join-Path $TemporaryRoot "python-tools"
New-Item -ItemType Directory -Force -Path $TemporaryRoot | Out-Null
try {
    Write-Host "Downloading the official MSYS2 FriBiDi package..."
    Invoke-WebRequest -Uri $PackageUrl -OutFile $PackagePath
    $ActualSha256 = (Get-FileHash -Path $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($ActualSha256 -ne $ExpectedSha256) { throw "FriBiDi package checksum did not match. Nothing was installed." }

    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) { $PythonCommand = $Launcher.Source; $PythonPrefix = @("-3") }
    else {
        $Launcher = Get-Command python -ErrorAction SilentlyContinue
        if (-not $Launcher) { throw "Python 3 was not found. Install Python 3, then rerun this setup file." }
        $PythonCommand = $Launcher.Source
        $PythonPrefix = @()
    }

    Write-Host "Preparing a temporary archive reader..."
    & $PythonCommand @PythonPrefix -m pip install --disable-pip-version-check --quiet --target $ExtractorPath zstandard
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare the temporary package extractor." }
    $env:PYTHONPATH = $ExtractorPath

    $ExtractScript = @'
import pathlib, sys, tarfile, zstandard

package_path = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
destination.mkdir(parents=True, exist_ok=True)
wanted = {
    "ucrt64/bin/libfribidi-0.dll": destination / "libfribidi-0.dll",
    "ucrt64/share/licenses/fribidi/COPYING": destination / "FRIBIDI-COPYING.txt",
}
found = set()
with package_path.open("rb") as package:
    with zstandard.ZstdDecompressor().stream_reader(package) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as archive:
            for member in archive:
                name = member.name.replace("\\", "/").lstrip("./")
                for suffix, target in wanted.items():
                    if name.endswith(suffix) and member.isfile():
                        source = archive.extractfile(member)
                        if source is not None:
                            with source, target.open("wb") as output:
                                output.write(source.read())
                            found.add(suffix)
                if len(found) == len(wanted):
                    break
missing = set(wanted) - found
if missing:
    raise SystemExit("Official package is missing required file(s): " + ", ".join(sorted(missing)))
print("Installed libfribidi-0.dll and its license in " + str(destination))
'@

    New-Item -ItemType Directory -Force -Path $DllDirectory | Out-Null
    Write-Host "Installing FriBiDi into the factory's dlls folder..."
    & $PythonCommand @PythonPrefix -c $ExtractScript $PackagePath $DllDirectory
    if ($LASTEXITCODE -ne 0) { throw "Could not extract FriBiDi from the verified package." }
    Write-Host ""
    Write-Host "Finished. Close Final-Shorts / Streamlit, then restart the factory."
    Write-Host "The renderer will find dlls\libfribidi-0.dll automatically."
} finally {
    Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
