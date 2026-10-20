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


def test_raqm_wheel_workflow_verifies_the_same_isolated_wheel_used_at_runtime():
    workflow_path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "build-windows-raqm-pillow.yml"
    workflow = workflow_path.read_text(encoding="utf-8")
    verification = workflow.split("Verify extracted wheel in an isolated runtime", 1)[1].split(
        "actions/upload-artifact@v4", 1
    )[0]

    assert "archive.extractall(test_target)" in verification
    assert '[sys.executable, "-I", "-S", "-c", probe_code]' in verification
    assert "PYTHONPATH" in verification and "PYTHONHOME" in verification
    assert "NotoSansDevanagari-Bold.ttf" in verification
    assert "NotoSansTelugu-Bold.ttf" in verification
    assert "pillow-source" not in verification
    assert "pip install --no-deps --target" not in verification
    assert "delvewheel repair --include fribidi.dll --no-mangle fribidi.dll --add-path" in workflow
    assert "raqm-wheel-raw" in workflow
    assert "winbuild\\\\build\\\\bin" in workflow or "winbuild\\build\\bin" in workflow
