from pathlib import Path


def test_windows_indic_setup_retries_official_mirrors_without_bypassing_checksum():
    setup_path = Path(__file__).resolve().parents[1] / "setup_windows_indic_rendering.ps1"
    source = setup_path.read_text(encoding="utf-8")

    # Keep the checksum pinned to the value published by the official MSYS2
    # package metadata; mirrors are fallbacks, not a reason to weaken integrity.
    assert '3581ee03cf83a9bb0e98bf688c4f532a29553500e317532d90746de295b0f8a8' in source
    assert "https://repo.msys2.org/mingw/ucrt64/" in source
    assert "https://mirror.msys2.org/mingw/ucrt64/" in source
    assert "https://ftp.nluug.nl/pub/os/windows/msys2/builds/mingw/ucrt64/" in source
    assert "https://mirror.accum.se/mirror/msys2.org/mingw/ucrt64/" in source
    assert "$ActualSha256 -eq $ExpectedSha256" in source
    assert "if (-not $VerifiedPackage)" in source
    assert "Nothing was installed." in source
