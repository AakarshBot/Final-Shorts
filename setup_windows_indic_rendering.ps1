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

    # Prefer the Windows-provided tar tool. Older Windows tar/libarchive builds
    # cannot read .tar.zst, so fall back to a checksum-pinned official Zstandard
    # CLI downloaded to TEMP; never require pip, MSYS2, or a user-installed tool.
    $SourceDll = Join-Path $ExtractRoot "ucrt64/bin/libfribidi-0.dll"
    $SourceLicense = Join-Path $ExtractRoot "ucrt64/share/licenses/fribidi/COPYING"
    $Extracted = $false
    $Tar = Get-Command tar.exe -ErrorAction SilentlyContinue

    if ($Tar) {
        Write-Host "Extracting the verified FriBiDi package with Windows tar..."
        & $Tar.Source -xf $PackagePath -C $ExtractRoot "ucrt64/bin/libfribidi-0.dll" "ucrt64/share/licenses/fribidi/COPYING"
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $SourceDll -PathType Leaf) -and (Test-Path -LiteralPath $SourceLicense -PathType Leaf)) {
            $Extracted = $true
        } else {
            Write-Warning "This Windows tar build cannot fully extract .tar.zst; trying the verified Zstandard fallback."
            Remove-Item -LiteralPath $SourceDll, $SourceLicense -Force -ErrorAction SilentlyContinue
        }
    }

    if (-not $Extracted) {
        $ZstdZipName = "zstd-v1.5.7-win64.zip"
        $ZstdZipUrl = "https://github.com/facebook/zstd/releases/download/v1.5.7/$ZstdZipName"
        $ZstdZipSha512 = "a96dc5417943c03fa231bf2d6a586b7ae7254fa52fdc15d302f296b5ff88e1ff0f07120a720149eb82ea0f0c65444393ebf05d2ee1bd1db341b803ff65a2e675"
        $ZstdZipPath = Join-Path $TemporaryRoot $ZstdZipName
        $ZstdOuterRoot = Join-Path $TemporaryRoot "zstd-outer"
        $ZstdInnerRoot = Join-Path $TemporaryRoot "zstd-inner"
        $TarPath = Join-Path $TemporaryRoot "fribidi-package.tar"
        New-Item -ItemType Directory -Force -Path $ZstdOuterRoot, $ZstdInnerRoot | Out-Null

        Write-Host "Downloading the official Zstandard fallback and verifying its SHA-512..."
        Invoke-WebRequest -Uri $ZstdZipUrl -OutFile $ZstdZipPath
        $ActualZstdSha512 = (Get-FileHash -Path $ZstdZipPath -Algorithm SHA512).Hash.ToLowerInvariant()
        if ($ActualZstdSha512 -ne $ZstdZipSha512) {
            throw "The Zstandard fallback checksum did not match the pinned official release. Nothing unverified was executed."
        }

        # The official 1.5.7 Windows release is a ZIP containing a second ZIP.
        Expand-Archive -LiteralPath $ZstdZipPath -DestinationPath $ZstdOuterRoot -Force
        $NestedZip = Get-ChildItem -LiteralPath $ZstdOuterRoot -Filter "*.zip" -File -Recurse | Select-Object -First 1
        if (-not $NestedZip) { throw "The verified Zstandard release did not contain its expected nested ZIP." }
        Expand-Archive -LiteralPath $NestedZip.FullName -DestinationPath $ZstdInnerRoot -Force
        $ZstdExe = Get-ChildItem -LiteralPath $ZstdInnerRoot -Filter "zstd.exe" -File -Recurse | Select-Object -First 1
        if (-not $ZstdExe) { throw "The verified Zstandard release did not contain zstd.exe." }

        Write-Host "Decompressing the verified FriBiDi archive..."
        & $ZstdExe.FullName -d -q -f -o $TarPath $PackagePath
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $TarPath -PathType Leaf)) {
            throw "The verified Zstandard executable could not decompress the FriBiDi package."
        }

        if ($Tar) {
            & $Tar.Source -xf $TarPath -C $ExtractRoot "ucrt64/bin/libfribidi-0.dll" "ucrt64/share/licenses/fribidi/COPYING"
            if ($LASTEXITCODE -ne 0) {
                throw "Windows tar could not extract the decompressed FriBiDi tar archive."
            }
        } else {
            throw "Windows tar.exe is unavailable after verified Zstandard decompression. No Python packages were installed."
        }

        if (-not (Test-Path -LiteralPath $SourceDll -PathType Leaf) -or -not (Test-Path -LiteralPath $SourceLicense -PathType Leaf)) {
            throw "The decompressed official package did not yield the expected FriBiDi DLL and licence."
        }
        $Extracted = $true
    }

    if (-not $Extracted) { throw "The verified FriBiDi package could not be extracted." }
    if (-not (Test-Path -LiteralPath $SourceDll -PathType Leaf)) { throw "The verified archive did not contain the expected FriBiDi DLL." }
    if (-not (Test-Path -LiteralPath $SourceLicense -PathType Leaf)) { throw "The verified archive did not contain the FriBiDi license." }

    New-Item -ItemType Directory -Force -Path $DllDirectory | Out-Null
    $TargetDll = Join-Path $DllDirectory "libfribidi-0.dll"
    $SourceDllHash = (Get-FileHash -Path $SourceDll -Algorithm SHA256).Hash.ToLowerInvariant()
    $CopyDll = $true

    if (Test-Path -LiteralPath $TargetDll -PathType Leaf) {
        try {
            $TargetDllHash = (Get-FileHash -Path $TargetDll -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($TargetDllHash -eq $SourceDllHash) {
                Write-Host "The existing factory FriBiDi DLL matches the checksum-verified package; leaving it in place."
                $CopyDll = $false
            }
        } catch {
            Write-Warning "Could not hash the existing FriBiDi DLL while it is in use; attempting a verified replacement."
        }
    }

    if ($CopyDll) {
        try {
            Copy-Item -LiteralPath $SourceDll -Destination $TargetDll -Force
        } catch {
            throw (
                "Could not replace dlls\\libfribidi-0.dll. It may be loaded by another running Final-Shorts process. " +
                "Close every Final-Shorts / Streamlit process and restart the factory, then retry. " +
                "Original error: $($_.Exception.Message)"
            )
        }
    }

    $TargetLicense = Join-Path $DllDirectory "FRIBIDI-COPYING.txt"
    if (-not (Test-Path -LiteralPath $TargetLicense -PathType Leaf)) {
        Copy-Item -LiteralPath $SourceLicense -Destination $TargetLicense -Force
    }
    Write-Host ""
    Write-Host "Finished. Close Final-Shorts / Streamlit, then restart the factory."
    Write-Host "The renderer will find dlls\libfribidi-0.dll automatically."
} finally {
    Remove-Item -LiteralPath $TemporaryRoot -Recurse -Force -ErrorAction SilentlyContinue
}
