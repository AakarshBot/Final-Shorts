$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$PackageFileName = "mingw-w64-ucrt-x86_64-fribidi-1.0.17-1-any.pkg.tar.zst"
$ExpectedSha256 = "3581ee03cf83a9bb0e98bf688c4f532a29553500e317532d90746de295b0f8a8"
$PackageSources = @(
    [pscustomobject]@{
        Name = "MSYS2 primary repository"
        Url = "https://repo.msys2.org/mingw/ucrt64/$PackageFileName"
    },
    [pscustomobject]@{
        Name = "MSYS2 mirror redirect"
        Url = "https://mirror.msys2.org/mingw/ucrt64/$PackageFileName"
    },
    [pscustomobject]@{
        Name = "MSYS2 Tier 1 mirror (ftp.nluug.nl)"
        Url = "https://ftp.nluug.nl/pub/os/windows/msys2/builds/mingw/ucrt64/$PackageFileName"
    },
    [pscustomobject]@{
        Name = "MSYS2 Tier 1 mirror (mirror.accum.se)"
        Url = "https://mirror.accum.se/mirror/msys2.org/mingw/ucrt64/$PackageFileName"
    }
)

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DllDirectory = Join-Path $RepoRoot "dlls"
$TemporaryRoot = Join-Path $env:TEMP ("final-shorts-fribidi-" + [guid]::NewGuid().ToString("N"))
$PackagePath = Join-Path $TemporaryRoot $PackageFileName
$ExtractRoot = Join-Path $TemporaryRoot "extracted"
New-Item -ItemType Directory -Force -Path $TemporaryRoot, $ExtractRoot | Out-Null

try {
    $VerifiedPackage = $false
    $AttemptErrors = [System.Collections.Generic.List[string]]::new()

    foreach ($PackageSource in $PackageSources) {
        Remove-Item -LiteralPath $PackagePath -Force -ErrorAction SilentlyContinue
        try {
            Write-Host "Downloading the official MSYS2 FriBiDi package from $($PackageSource.Name)..."
            Invoke-WebRequest -Uri $PackageSource.Url -OutFile $PackagePath

            if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
                throw "The download did not create a package file."
            }

            $ActualSha256 = (Get-FileHash -Path $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($ActualSha256 -eq $ExpectedSha256) {
                Write-Host "FriBiDi package checksum verified."
                $VerifiedPackage = $true
                break
            }

            $AttemptErrors.Add("$($PackageSource.Name): SHA-256 mismatch ($ActualSha256).")
            Write-Warning "The downloaded package did not match the trusted SHA-256. Trying the next official MSYS2 source."
        } catch {
            $AttemptErrors.Add("$($PackageSource.Name): $($_.Exception.Message)")
            Write-Warning "Could not download and verify the package from $($PackageSource.Name). Trying the next official MSYS2 source."
        }
    }

    if (-not $VerifiedPackage) {
        throw (
            "No checksum-verified FriBiDi package was obtained. Nothing was installed. " +
            "Expected SHA-256: $ExpectedSha256. Attempts: $($AttemptErrors -join ' | ')"
        )
    }

    # Use Windows' built-in tar/libarchive instead of pip. This deliberately
    # avoids modifying or relying on the user's Python installation.
    $Tar = Get-Command tar.exe -ErrorAction SilentlyContinue
    if (-not $Tar) { throw "Windows tar.exe was not found. Install a current Windows build with tar/libarchive support, then rerun this setup file." }

    Write-Host "Extracting the verified FriBiDi package with Windows tar..."
    & $Tar.Source -xf $PackagePath -C $ExtractRoot "ucrt64/bin/libfribidi-0.dll" "ucrt64/share/licenses/fribidi/COPYING"
    if ($LASTEXITCODE -ne 0) {
        throw "Windows tar could not read the .tar.zst package. Update Windows or install 7-Zip with Zstandard support, then rerun this setup file. No Python packages were installed."
    }

    $SourceDll = Join-Path $ExtractRoot "ucrt64/bin/libfribidi-0.dll"
    $SourceLicense = Join-Path $ExtractRoot "ucrt64/share/licenses/fribidi/COPYING"
    if (-not (Test-Path -LiteralPath $SourceDll -PathType Leaf)) { throw "The verified archive did not contain the expected FriBiDi DLL." }
    if (-not (Test-Path -LiteralPath $SourceLicense -PathType Leaf)) { throw "The verified archive did not contain the FriBiDi license." }

    New-Item -ItemType Directory -Force -Path $DllDirectory | Out-Null
    Copy-Item -LiteralPath $SourceDll -Destination (Join-Path $DllDirectory "libfribidi-0.dll") -Force
    Copy-Item -LiteralPath $SourceLicense -Destination (Join-Path $DllDirectory "FRIBIDI-COPYING.txt") -Force
    Write-Host ""
    Write-Host "Finished. Close Final-Shorts / Streamlit, then restart the factory."
    Write-Host "The renderer will find dlls\libfribidi-0.dll automatically."
} finally {
    Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
