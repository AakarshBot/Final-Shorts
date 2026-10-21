"""Function 06: final visual renderer preview and subtitle handoff contract."""

from __future__ import annotations

from io import BytesIO
import ctypes
import hashlib
import os
from pathlib import Path
import math
import shutil
import subprocess
import sys
import tempfile
import time
import warnings
from functools import lru_cache
from itertools import combinations
import sysconfig
import zipfile
from urllib.request import urlopen


_DLL_DIRECTORY_HANDLES = []
_FRIBIDI_DLL_HANDLES = []
_WINDOWS_FRIBIDI_INSTALL_ATTEMPTED = False
_WINDOWS_FRIBIDI_INSTALL_ERROR = ""
_WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED = False
_WINDOWS_RAQM_PILLOW_INSTALL_ERROR = ""
_WINDOWS_RAQM_PILLOW_READY_FOR_RESTART = False


def _bundled_raqm_pillow_directory(root: Path | None = None) -> Path:
    """Return the versioned, isolated Pillow build compiled with RAQM for CPython 3.11."""
    root = Path(root or Path(__file__).resolve().parent)
    return root / ".deps" / "raqm_pillow_11_3_0_cp311"


def _activate_bundled_raqm_pillow(root: Path | None = None) -> bool:
    """Prefer a prepared RAQM-enabled Pillow wheel before this process imports PIL."""
    target = _bundled_raqm_pillow_directory(root)
    package = target / "PIL"
    marker = target / "python_executable.txt"
    if not marker.is_file() or not (package / "__init__.py").is_file():
        return False
    if not any(path.is_file() and path.name.startswith("_imagingft.") for path in package.iterdir()):
        return False
    try:
        recorded_python = Path(marker.read_text(encoding="utf-8").strip()).resolve()
        if recorded_python != Path(sys.executable).resolve():
            return False
    except (OSError, ValueError):
        return False
    target_string = str(target.resolve())
    if target_string in sys.path:
        sys.path.remove(target_string)
    sys.path.insert(0, target_string)
    return True


def _windows_dll_search_directories(root: Path | None = None) -> tuple[Path, ...]:
    """Find conventional Windows dependency folders, including FriBiDi locations."""
    root = Path(root or Path(__file__).resolve().parent)
    prefix = Path(sys.prefix)
    configured = os.environ.get("FRIBIDI_DLL_PATH") or os.environ.get("FRIBIDI_DLL_DIR") or ""
    paths = []
    if configured.strip():
        configured_path = Path(configured.strip().strip('"'))
        paths.append(configured_path.parent if configured_path.suffix.casefold() == ".dll" else configured_path)
    raqm_pillow = _bundled_raqm_pillow_directory(root)
    paths.extend((
        raqm_pillow,
        raqm_pillow / "PIL",
        raqm_pillow / "pillow.libs",
        raqm_pillow / "PIL" / ".libs",
        root / "dlls",
        root / ".deps",
        root / "vendor" / "dlls",
        root / "vendor",
        root,
        prefix / "Library" / "bin",
        prefix / "DLLs",
        prefix / "Lib" / "site-packages" / "PIL",
        Path("C:/msys64/mingw64/bin"),
        Path("C:/msys64/ucrt64/bin"),
        Path("C:/msys64/usr/bin"),
    ))
    unique = []
    seen = set()
    for path in paths:
        try:
            key = str(path.resolve()).casefold()
        except OSError:
            key = str(path).casefold()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return tuple(unique)


def _register_windows_dll_paths() -> None:
    """Register known DLL folders before Pillow asks Windows to load FriBiDi."""
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    for directory in _windows_dll_search_directories():
        if not directory.is_dir():
            continue
        try:
            handle = os.add_dll_directory(str(directory))
        except (OSError, ValueError):
            continue
        _DLL_DIRECTORY_HANDLES.append(handle)


def _install_raqm_enabled_pillow(root: Path | None = None) -> Path:
    """Download and verify the factory's custom Pillow wheel built with vendored RAQM."""
    root = Path(root or Path(__file__).resolve().parent)
    if sys.version_info[:2] != (3, 11) or sysconfig.get_platform().replace("-", "_") != "win_amd64":
        raise RuntimeError(
            "The verified RAQM-enabled Pillow build currently targets 64-bit CPython 3.11 on Windows. "
            "The active interpreter is not that build target."
        )

    dependency_root = root / ".deps"
    dependency_root.mkdir(parents=True, exist_ok=True)
    target = _bundled_raqm_pillow_directory(root)
    filename = "pillow-11.3.0-cp311-cp311-win_amd64.whl"
    release_root = (
        "https://github.com/AakarshBot/Final-Shorts/releases/download/"
        "raqm-pillow-windows-v1"
    )
    wheel_url = f"{release_root}/{filename}"
    checksum_url = f"{wheel_url}.sha256"
    staging = Path(tempfile.mkdtemp(prefix="raqm-pillow-staging-", dir=str(dependency_root)))

    try:
        try:
            with urlopen(wheel_url, timeout=90) as response:
                wheel_bytes = response.read()
            with urlopen(checksum_url, timeout=30) as response:
                checksum_text = response.read().decode("ascii", errors="strict").strip()
        except Exception as exc:
            raise RuntimeError(
                "Could not download the RAQM-enabled Pillow build from the factory's verified release. "
                "Make sure the local checkout is updated to the latest main and retry."
            ) from exc

        checksum_fields = checksum_text.split()
        expected_sha256 = checksum_fields[0].casefold() if checksum_fields else ""
        actual_sha256 = hashlib.sha256(wheel_bytes).hexdigest()
        if len(expected_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_sha256):
            raise RuntimeError("The RAQM Pillow release did not provide a valid SHA-256 checksum.")
        if actual_sha256 != expected_sha256:
            raise RuntimeError(
                "The downloaded RAQM-enabled Pillow wheel failed SHA-256 verification; it was not installed."
            )

        try:
            with zipfile.ZipFile(BytesIO(wheel_bytes)) as archive:
                staging_resolved = staging.resolve()
                for member in archive.infolist():
                    extracted = (staging / member.filename).resolve()
                    if not extracted.is_relative_to(staging_resolved):
                        raise RuntimeError("The RAQM Pillow wheel contains an unsafe archive path.")
                archive.extractall(staging)
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeError("The verified Pillow wheel could not be unpacked.") from exc

        package = staging / "PIL"
        if not (package / "__init__.py").is_file() or not any(
            path.is_file() and path.name.startswith("_imagingft.") for path in package.iterdir()
        ):
            raise RuntimeError("The verified Pillow wheel did not contain the expected Windows binaries.")

        samples = (
            ("NotoSansDevanagari-Bold.ttf", "क्षेत्र की उपलब्धि"),
            ("NotoSansTelugu-Bold.ttf", "ప్రత్యేకమైన క్రీడాకారుడు"),
        )
        probe_code = "\n".join((
            "import os, sys",
            f"root = {str(root.resolve())!r}",
            f"target = {str(staging.resolve())!r}",
            "dll_dirs = [os.path.join(target, 'PIL'), os.path.join(target, 'pillow.libs'), os.path.join(target, 'PIL', '.libs')]",
            "handles = [os.add_dll_directory(p) for p in dll_dirs if os.name == 'nt' and os.path.isdir(p)]",
            "sys.path.insert(0, target)",
            "import PIL",
            "from PIL import features, ImageFont",
            "import PIL._imagingft as imagingft",
            "raqm = features.check_feature('raqm')",
            "assert raqm is True, f'Pillow was not compiled with RAQM (PIL={PIL.__file__}; _imagingft={imagingft.__file__}; RAQM={raqm})'",
            f"samples = {samples!r}",
            "for font_name, sample in samples:",
            "    font = ImageFont.truetype(os.path.join(root, 'fonts', font_name), 48, layout_engine=ImageFont.Layout.RAQM)",
            "    assert font.layout_engine == ImageFont.Layout.RAQM, f'RAQM fell back to basic layout for {font_name}'",
            "    assert font.getmask(sample).getbbox() is not None, f'Indic glyph shaping returned an empty mask for {font_name}'",
        ))
        probe_env = os.environ.copy()
        for variable in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE"):
            probe_env.pop(variable, None)
        if os.name == "nt":
            system_root = Path(probe_env.get("SystemRoot", "C:/Windows"))
            runtime_paths = (
                staging / "PIL",
                staging / "pillow.libs",
                staging / "PIL" / ".libs",
                Path(sys.executable).resolve().parent,
                system_root / "System32",
                system_root,
            )
            probe_env["PATH"] = os.pathsep.join(
                str(path) for path in runtime_paths if path.is_dir()
            )
        try:
            probe = subprocess.run(
                [sys.executable, "-I", "-S", "-c", probe_code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=45,
                check=False,
                env=probe_env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"Could not run the real RAQM/Pillow verification: {exc}") from exc
        if probe.returncode != 0:
            details = "\n".join(
                part.strip() for part in (probe.stdout, probe.stderr) if part and part.strip()
            )
            raise RuntimeError(
                "The downloaded Pillow wheel did not pass the real RAQM and Indic font-shaping test. "
                + (details or f"RAQM probe exited with code {probe.returncode}.")
            )

        sitecustomize = """import ctypes
import os
from pathlib import Path

_TARGET = Path(__file__).resolve().parent
_FACTORY_ROOT = _TARGET.parents[1]
_DLL_PATHS = (
    _FACTORY_ROOT / "dlls",
    _TARGET,
    _TARGET / "PIL",
    _TARGET / "pillow.libs",
    _TARGET / "PIL" / ".libs",
)
_DLL_HANDLES = []
_VALID_DLL_PATHS = [str(_path) for _path in _DLL_PATHS if _path.is_dir()]
if _VALID_DLL_PATHS:
    os.environ["PATH"] = os.pathsep.join(_VALID_DLL_PATHS + [os.environ.get("PATH", "")])
if os.name == "nt" and hasattr(os, "add_dll_directory"):
    for _dll_dir in _DLL_PATHS:
        if _dll_dir.is_dir():
            try:
                _DLL_HANDLES.append(os.add_dll_directory(str(_dll_dir)))
            except (OSError, ValueError):
                pass
    for _dll_name in ("libfribidi-0.dll", "fribidi-0.dll", "fribidi.dll"):
        _dll_path = _FACTORY_ROOT / "dlls" / _dll_name
        if _dll_path.is_file():
            try:
                _DLL_HANDLES.append(ctypes.WinDLL(str(_dll_path)))
                break
            except OSError:
                pass
"""
        (staging / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
        (staging / "python_executable.txt").write_text(str(sys.executable), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)
        return target
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


def _install_windows_fribidi_via_powershell(root: Path | None = None) -> None:
    """Run the repo's checksum-verified no-pip installer, then validate its DLL output."""
    root = Path(root or Path(__file__).resolve().parent)
    setup_script = root / "setup_windows_indic_rendering.ps1"
    if not setup_script.is_file():
        raise RuntimeError(
            "The factory's setup_windows_indic_rendering.ps1 file is missing; "
            "cannot install the verified FriBiDi runtime automatically."
        )

    powershell = (
        shutil.which("powershell.exe")
        or shutil.which("powershell")
        or shutil.which("pwsh.exe")
        or shutil.which("pwsh")
    )
    if not powershell:
        raise RuntimeError(
            "PowerShell was not found. The factory's automatic FriBiDi setup could not start."
        )

    try:
        process = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(setup_script),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "The automatic FriBiDi setup exceeded 180 seconds while trying the trusted mirrors."
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start the automatic FriBiDi setup: {exc}") from exc

    if process.returncode != 0:
        details = "\n".join(
            part.strip() for part in (process.stdout, process.stderr) if part and part.strip()
        )
        if len(details) > 3500:
            details = details[-3500:]
        raise RuntimeError(
            f"The checksum-verified FriBiDi setup failed with exit code {process.returncode}. "
            "No unverified DLL was accepted. "
            + (details or "PowerShell did not return a diagnostic message.")
        )

    dll_path = root / "dlls" / "libfribidi-0.dll"
    license_path = root / "dlls" / "FRIBIDI-COPYING.txt"
    if not dll_path.is_file() or not (10_000 <= dll_path.stat().st_size <= 2 * 1024 * 1024):
        raise RuntimeError(
            "The FriBiDi setup reported success but did not create a valid dlls/libfribidi-0.dll."
        )
    if not license_path.is_file():
        raise RuntimeError(
            "The FriBiDi setup reported success but did not save the DLL's LGPL licence."
        )


_activate_bundled_raqm_pillow()
_register_windows_dll_paths()

from PIL import Image, ImageDraw, ImageFilter, ImageFont, features


WIDTH = 1080
HEIGHT = 1920
FPS = 30

SOURCE_LABEL = "SPORTS DESK"

SUBTITLE_SAFE_MARGIN = 64
SUBTITLE_MAX_WIDTH = WIDTH - (SUBTITLE_SAFE_MARGIN * 2)
SUBTITLE_MAX_SIZE = 70
SUBTITLE_MIN_SIZE = 54
SUBTITLE_STROKE_WIDTH = 5
SUBTITLE_WORD_SPACING = 10
SUBTITLE_LINE_GAP = 14
SUBTITLE_Y = 1390

DASH_TRANSLATION = str.maketrans({
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-",
    "﹘": "-", "﹣": "-", "－": "-",
})

ACCENT = (255, 205, 66)
BRAND_BLUE = (35, 105, 255)
WHITE = (249, 250, 252)
DARK = (5, 7, 10)


TOP5_EDITORIAL_MARGIN_X = 60
TOP5_EDITORIAL_SAFE_TOP = 150
TOP5_EDITORIAL_SAFE_BOTTOM = 1780
TOP5_EDITORIAL_HEADLINE_DEFAULT_SIZE = 118
TOP5_EDITORIAL_HEADLINE_MIN_SIZE = 60
TOP5_EDITORIAL_HEADLINE_MAX_LINES = 2
TOP5_EDITORIAL_HEADLINE_LINE_GAP = 8
TOP5_EDITORIAL_BODY_MAX_SIZE = 50
TOP5_EDITORIAL_BODY_MIN_SIZE = 34
TOP5_EDITORIAL_BODY_LINE_GAP = 10
TOP5_EDITORIAL_HEADLINE_BODY_GAP = 24
TOP5_EDITORIAL_STROKE_WIDTH = 2
TOP5_EDITORIAL_SHADOW_BLUR = 7
TOP5_EDITORIAL_SHADOW_ALPHA = 210
TOP5_EDITORIAL_SHADOW_OFFSET = (0, 5)
TOP5_SUBJECT_HEADLINE_MAX_SIZE = 220
TOP5_SUBJECT_HEADLINE_MIN_SIZE = 92
TOP5_SUBJECT_REMOVAL_MODEL = "ZhengPeng7/BiRefNet"
MANUAL_SUBJECT_MIN_FONT_SIZE = 72
MANUAL_SUBJECT_MAX_FONT_SIZE = 260
MANUAL_SUBJECT_DEFAULT_FONT_SIZE = 150
MANUAL_SUBJECT_FONT_OPTIONS = {
    "Barlow Condensed": {"file": "BarlowCondensed-Black.ttf"},
    "Anton": {"file": "Anton-Regular.ttf"},
    "Oswald": {"file": "Oswald-Bold.ttf"},
    "Barlow": {"file": "Barlow-Regular.ttf"},
    "Bebas Neue": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/bebasneue/BebasNeue-Regular.ttf"},
    "Teko": {"url": "https://raw.githubusercontent.com/itfoundry/teko/master/build/Teko-Bold.otf"},
    "Khand": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/khand/Khand-Bold.ttf"},
    "Kanit": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/kanit/Kanit-Black.ttf"},
    "Fjalla One": {"url": "https://raw.githubusercontent.com/google/fonts/main/ofl/fjallaone/FjallaOne-Regular.ttf"},
}
MANUAL_SUBJECT_STYLE_OPTIONS = (
    "Crisp Outline",
    "Soft Halo",
    "Long Fade",
    "Editorial Offset",
    "Heavy Drop",
    "Double Edge",
    "Split Shadow",
    "3D Extrusion",
    "Chromatic Echo",
)


def _normalise_indic_language(language: str | None) -> str:
    key = str(language or "").strip().casefold()
    return {"hi": "hindi", "te": "telugu"}.get(key, key)


def _indic_language_for_text(text: str) -> str | None:
    value = str(text or "")
    devanagari = any("\u0900" <= char <= "\u097F" for char in value)
    telugu = any("\u0C00" <= char <= "\u0C7F" for char in value)
    if devanagari and telugu:
        raise RuntimeError("A single text block cannot mix Hindi and Telugu scripts; split it by language.")
    if devanagari:
        return "hindi"
    if telugu:
        return "telugu"
    return None


def _raqm_runtime_probe(language: str) -> tuple[bool, str]:
    """Test real Indic font loading/shaping; a feature flag alone misses DLL-load failures."""
    language_key = _normalise_indic_language(language)
    if language_key not in {"hindi", "telugu"}:
        return True, ""

    try:
        if not features.check_feature("raqm"):
            return False, "This Pillow build does not report RAQM support."
    except (AttributeError, ValueError, OSError) as exc:
        return False, f"Pillow could not check RAQM support: {type(exc).__name__}: {exc}"

    filename, sample = (
        ("NotoSansDevanagari-Bold.ttf", "क्षेत्र की उपलब्धि")
        if language_key == "hindi"
        else ("NotoSansTelugu-Bold.ttf", "ప్రత్యేకమైన క్రీడాకారుడు")
    )
    font_path = Path(__file__).resolve().parent / "fonts" / filename
    if not font_path.is_file():
        return False, f"The bundled Indic font is missing: {filename}."

    try:
        font = ImageFont.truetype(
            str(font_path),
            48,
            layout_engine=ImageFont.Layout.RAQM,
        )
        bounds = font.getmask(sample).getbbox()
        if bounds is None:
            return False, f"RAQM returned an empty glyph mask for {language_key.title()} text."
    except Exception as exc:
        return False, (
            f"The real RAQM font-load/shaping test failed: "
            f"{type(exc).__name__}: {exc}"
        )
    return True, ""


def _activate_windows_fribidi(root: Path | None = None) -> str:
    """Load a bundled FriBiDi DLL explicitly and keep its Windows handle alive."""
    if os.name != "nt":
        return ""
    root = Path(root or Path(__file__).resolve().parent)
    _register_windows_dll_paths()
    configured = os.environ.get("FRIBIDI_DLL_PATH") or ""
    candidates = []
    if configured.strip():
        configured_path = Path(configured.strip().strip('"'))
        if configured_path.suffix.casefold() == ".dll":
            candidates.append(configured_path)
    candidates.extend((
        root / "dlls" / "libfribidi-0.dll",
        root / "dlls" / "fribidi-0.dll",
        root / "dlls" / "fribidi.dll",
    ))
    loader = getattr(ctypes, "WinDLL", None)
    if loader is None:
        return "This Python runtime does not expose the Windows DLL loader."
    seen = set()
    load_errors = []
    found_dll = False
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            resolved = path
        key = str(resolved).casefold()
        if key in seen or not resolved.is_file():
            continue
        seen.add(key)
        found_dll = True
        try:
            handle = loader(str(resolved))
            _FRIBIDI_DLL_HANDLES.append(handle)
            return ""
        except OSError as exc:
            load_errors.append(f"{resolved}: {exc}")
    if load_errors:
        return "Could not load any candidate FriBiDi DLL: " + " | ".join(load_errors)
    if found_dll:
        return "Candidate FriBiDi DLLs were found but none could be loaded."
    return "No FriBiDi DLL was found in the factory's configured DLL folders."


def _require_raqm(language: str) -> None:
    """Require working RAQM shaping, installing the verified Windows DLL when needed."""
    global _WINDOWS_FRIBIDI_INSTALL_ATTEMPTED, _WINDOWS_FRIBIDI_INSTALL_ERROR
    global _WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED
    global _WINDOWS_RAQM_PILLOW_INSTALL_ERROR, _WINDOWS_RAQM_PILLOW_READY_FOR_RESTART
    language_key = _normalise_indic_language(language)
    _register_windows_dll_paths()
    activation_error = _activate_windows_fribidi() if os.name == "nt" else ""

    available, probe_error = _raqm_runtime_probe(language_key)
    if available:
        return

    setup_error = activation_error
    if os.name == "nt":
        if not _WINDOWS_FRIBIDI_INSTALL_ATTEMPTED:
            _WINDOWS_FRIBIDI_INSTALL_ATTEMPTED = True
            try:
                _install_windows_fribidi_via_powershell()
                _register_windows_dll_paths()
                load_error = _activate_windows_fribidi()
                setup_error = load_error
            except Exception as exc:
                _WINDOWS_FRIBIDI_INSTALL_ERROR = str(exc)
                setup_error = _WINDOWS_FRIBIDI_INSTALL_ERROR
        else:
            setup_error = _WINDOWS_FRIBIDI_INSTALL_ERROR or activation_error

        # Re-open the bundled Noto font and force actual glyph shaping after setup.
        available, retry_error = _raqm_runtime_probe(language_key)
        if available:
            return
        if retry_error:
            probe_error = retry_error
        if not setup_error:
            setup_error = (
                "The DLL setup completed, but Pillow still failed the real font-load/shaping probe."
            )
        if probe_error:
            _WINDOWS_FRIBIDI_INSTALL_ERROR = (
                f"{setup_error} Final RAQM probe: {probe_error}"
            )

    probe_error_key = probe_error.casefold()
    needs_bundled_raqm_pillow = any(
        reason in probe_error_key
        for reason in (
            "does not report raqm support",
            "could not check raqm support",
            "font-load/shaping test failed",
            "empty glyph mask",
        )
    )
    if os.name == "nt" and not available and needs_bundled_raqm_pillow:
        if _WINDOWS_RAQM_PILLOW_READY_FOR_RESTART:
            raise RuntimeError(
                "The factory has prepared an isolated, RAQM-enabled Pillow wheel in "
                ".deps/raqm_pillow_11_3_0_cp311. Fully close every Final-Shorts / Streamlit process, then start it with Run_Final_Shorts.bat so "
                "the new Pillow loads before any image libraries; then retry the Hindi/Telugu text."
            )
        if not _WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED:
            _WINDOWS_RAQM_PILLOW_INSTALL_ATTEMPTED = True
            try:
                target = _install_raqm_enabled_pillow()
                _WINDOWS_RAQM_PILLOW_READY_FOR_RESTART = True
                _WINDOWS_RAQM_PILLOW_INSTALL_ERROR = (
                    f"Prepared isolated Pillow at {target}. A full factory restart is required."
                )
            except Exception as exc:
                _WINDOWS_RAQM_PILLOW_INSTALL_ERROR = str(exc)
        if _WINDOWS_RAQM_PILLOW_READY_FOR_RESTART:
            raise RuntimeError(
                "Your currently active Pillow build could not complete real RAQM text shaping. The factory has prepared a "
                "SHA-256-verified custom Windows Pillow wheel compiled with vendored RAQM and validated actual "
                "Hindi font shaping. Fully close every Final-Shorts / Streamlit process, then use "
                "Run_Final_Shorts.bat and retry your Hindi/Telugu Text Subject Cutout. No manual pip install "
                "or DLL copying is required."
            )
        if _WINDOWS_RAQM_PILLOW_INSTALL_ERROR:
            setup_error = (
                f"{setup_error} Isolated RAQM-enabled Pillow setup: "
                f"{_WINDOWS_RAQM_PILLOW_INSTALL_ERROR}"
            ).strip()

    extra = ""
    if setup_error:
        extra += f" Automatic FriBiDi setup detail: {setup_error}"
    if probe_error:
        extra += f" RAQM runtime check: {probe_error}"

    raise RuntimeError(
        f"{language_key.title()} text needs a working Pillow RAQM text-shaping engine. "
        "Rendering has been stopped rather than producing incorrectly joined letters. "
        "The factory tests both Pillow's compiled RAQM support and actual bundled Noto-font shaping. "
        "On Windows it installs the checksum-verified FriBiDi runtime and, when standard Pillow lacks RAQM, "
        "downloads the factory's custom RAQM-enabled wheel and verifies real Indic glyph shaping before accepting it. "
        "No global pip installation or manual DLL copying is required."
        + extra
    )


@lru_cache(maxsize=512)
def _font(candidates: tuple[Path, ...], size: int, language: str | None = None):
    language_key = _normalise_indic_language(language)
    if language_key in {"hindi", "telugu"}:
        _require_raqm(language_key)
        for path in candidates:
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
                except (OSError, ValueError):
                    continue
        raise RuntimeError(
            f"The bundled Noto Sans font for {language_key.title()} is missing or unreadable. "
            "The factory will not fall back to a font that may corrupt Indic text."
        )

    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)

    for path in (
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/ARLRDBD.TTF"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size)

    return ImageFont.load_default()


@lru_cache(maxsize=64)
def _font_candidates(role: str, language: str) -> tuple[Path, ...]:
    root = Path(__file__).resolve().parent / "fonts"
    language = _normalise_indic_language(language)

    if role == "headline":
        if language == "hindi":
            return (root / "NotoSansDevanagari-Bold.ttf",)
        if language == "telugu":
            return (root / "NotoSansTelugu-Bold.ttf",)
        return (root / "Oswald-Bold.ttf",)

    if language == "hindi":
        return (root / "NotoSansDevanagari-Bold.ttf",)
    if language == "telugu":
        return (root / "NotoSansTelugu-Bold.ttf",)
    return (root / "Oswald-Bold.ttf",)


def _headline_font_supports(font, char: str) -> bool:
    if not char or char in "\n\r\t":
        return True
    try:
        actual = font.getmask(char)
        missing = font.getmask("\U0010ffff")
        return actual.size != missing.size or bytes(actual) != bytes(missing)
    except (AttributeError, OSError, ValueError):
        return False


def _headline_runs(text: str, fonts: tuple[object, ...]) -> list[tuple[str, object]]:
    if not text:
        return []
    runs = []
    current_font = None
    current_text = []
    for char in text:
        font = next((candidate for candidate in fonts if _headline_font_supports(candidate, char)), fonts[-1])
        if current_font is not None and font is not current_font:
            runs.append(("".join(current_text), current_font))
            current_text = []
        if current_font is None or font is not current_font:
            current_font = font
        current_text.append(char)
    if current_text:
        runs.append(("".join(current_text), current_font))
    return runs


def _measure(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    stroke_width: int = 0,
) -> tuple[int, int]:
    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
        stroke_width=stroke_width,
    )
    return box[2] - box[0], box[3] - box[1]


@lru_cache(maxsize=1)
def _load_logo():
    path = Path(__file__).resolve().parent / "logo.png"
    if not path.exists():
        return None

    with Image.open(path) as source:
        logo = source.convert("RGBA")
    logo.thumbnail((150, 150), Image.Resampling.LANCZOS)
    return logo


def _paste_logo(base: Image.Image) -> None:
    logo = _load_logo()
    if logo is None:
        return

    base.paste(
        logo,
        (WIDTH - logo.width - 42, 36),
        logo,
    )


def _renderer_font_for_text(text: str, size: int, language: str = "english"):
    script_language = _indic_language_for_text(text)
    language_key = script_language or _normalise_indic_language(language)
    if language_key in {"hindi", "telugu"}:
        return _font(_font_candidates("subtitle", language_key), size, language=language_key)
    return _font((), size)


def _paste_source(base: Image.Image, source_label: str | None = None) -> None:
    draw = ImageDraw.Draw(base)
    label = str(source_label or SOURCE_LABEL).strip() or SOURCE_LABEL
    font = _renderer_font_for_text(label, 24)
    width, _ = _measure(draw, label, font)
    draw.text(
        (WIDTH - width - 42, HEIGHT - 86),
        label,
        font=font,
        fill=(210, 216, 224),
    )




@lru_cache(maxsize=128)
def _top5_body_font(size: int, language: str = "english"):
    root = Path(__file__).resolve().parent / "fonts"
    language_key = _normalise_indic_language(language)
    if language_key in {"hindi", "telugu"}:
        _require_raqm(language_key)
        font_name = "NotoSansDevanagari-Bold.ttf" if language_key == "hindi" else "NotoSansTelugu-Bold.ttf"
        path = root / font_name
        if not path.is_file():
            raise RuntimeError(f"The bundled Top-5 body font {font_name} is missing; Indic text will not use a substitute.")
        try:
            return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"The Top-5 body font {font_name} could not be loaded with RAQM.") from exc

    path = root / "Barlow-Regular.ttf"
    if path.is_file():
        return ImageFont.truetype(str(path), size)
    for candidate in (
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                continue
    return ImageFont.load_default()


def _top5_full_frame_image(value: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(value, Image.Image):
        image = value.convert("RGB")
    elif isinstance(value, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(value))) as source:
                image = source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("A Top-5 visual could not be decoded.") from exc
    else:
        raise ValueError("A Top-5 visual is missing.")
    if image.size == (WIDTH, HEIGHT):
        return image
    return _fit_visual_to_frame(image)


def _top5_editorial_measure(draw: ImageDraw.ImageDraw, text: str, fonts: tuple[object, ...]) -> tuple[int, int]:
    runs = _headline_runs(text, fonts)
    if not runs:
        return 0, 0
    boxes = [
        draw.textbbox((0, 0), run, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        for run, font in runs
    ]
    return sum(box[2] - box[0] for box in boxes), max(box[3] - box[1] for box in boxes)


def _top5_wrap_editorial_words(draw: ImageDraw.ImageDraw, text: str, fonts: tuple[object, ...], max_width: int) -> list[list[str]]:
    words = " ".join(str(text or "").split()).split()
    lines = []
    current = []
    for word in words:
        trial = " ".join(current + [word])
        if current and _top5_editorial_measure(draw, trial, fonts)[0] > max_width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


@lru_cache(maxsize=256)
def _top5_headline_font_stack(size: int, language: str) -> tuple[object, ...]:
    root = Path(__file__).resolve().parent / "fonts"
    language_key = _normalise_indic_language(language)
    if language_key in {"hindi", "telugu"}:
        _require_raqm(language_key)
        font_name = "NotoSansDevanagari-Bold.ttf" if language_key == "hindi" else "NotoSansTelugu-Bold.ttf"
        path = root / font_name
        if not path.is_file():
            raise RuntimeError(f"The bundled Top-5 font {font_name} is missing; Indic text will not use a substitute font.")
        return (ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM),)

    path = root / "Oswald-Bold.ttf"
    return (ImageFont.truetype(str(path), size),) if path.is_file() else (ImageFont.load_default(),)


def _top5_two_line_headline(draw: ImageDraw.ImageDraw, words: list[str], fonts: tuple[object, ...]):
    if len(words) < 2:
        width, height = _top5_editorial_measure(draw, " ".join(words), fonts)
        return [words], width, height
    best = None
    for split in range(1, len(words)):
        first, second = words[:split], words[split:]
        w1, h1 = _top5_editorial_measure(draw, " ".join(first), fonts)
        w2, h2 = _top5_editorial_measure(draw, " ".join(second), fonts)
        candidate = (abs(w1 - w2), [first, second], max(w1, w2), h1 + TOP5_EDITORIAL_HEADLINE_LINE_GAP + h2)
        if best is None or candidate[0] < best[0]:
            best = candidate
    return best[1], best[2], best[3]


def _top5_editorial_layout(
    headline: str,
    body: str,
    language: str,
    story_number: int,
    max_headline_lines: int = TOP5_EDITORIAL_HEADLINE_MAX_LINES,
    image: bytes | bytearray | Image.Image | None = None,
    subject_mask: Image.Image | None = None,
) -> dict:
    clean_headline = " ".join(str(headline or "").split()).upper()
    clean_body = "" if subject_mask is not None else " ".join(str(body or "").split())
    language = _indic_language_for_text(clean_headline) or _normalise_indic_language(language)
    body_language = _indic_language_for_text(clean_body) or language
    if not clean_headline:
        raise ValueError("Top-5 card requires a headline.")

    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left = TOP5_EDITORIAL_MARGIN_X
    right = WIDTH - TOP5_EDITORIAL_MARGIN_X
    top = TOP5_EDITORIAL_SAFE_TOP
    bottom = TOP5_EDITORIAL_SAFE_BOTTOM
    safe_width = right - left

    def horizontal(region, max_size, min_size):
        rx1, ry1, rx2, ry2 = region
        rw, rh = rx2 - rx1, ry2 - ry1
        words = clean_headline.split()
        for size in range(max_size, min_size - 1, -4):
            fonts = _top5_headline_font_stack(size, language)
            width, height = _top5_editorial_measure(draw, clean_headline, fonts)
            if width <= rw and height <= rh:
                return rx1 + (rw - width) // 2, ry1 + (rh - height) // 2, width, height, fonts, [words], size
            if max_headline_lines >= 2:
                two = _top5_two_line_headline(draw, words, fonts)
                if two[1] <= rw and two[2] <= rh:
                    return rx1 + (rw - two[1]) // 2, ry1 + (rh - two[2]) // 2, two[1], two[2], fonts, two[0], size
            if max_headline_lines > 2:
                lines = _top5_wrap_editorial_words(draw, clean_headline, fonts, rw)
                if 1 <= len(lines) <= max_headline_lines:
                    heights = [_top5_editorial_measure(draw, " ".join(line), fonts)[1] for line in lines]
                    width = max(_top5_editorial_measure(draw, " ".join(line), fonts)[0] for line in lines)
                    height = sum(heights) + TOP5_EDITORIAL_HEADLINE_LINE_GAP * (len(lines) - 1)
                    if width <= rw and height <= rh:
                        return rx1 + (rw - width) // 2, ry1 + (rh - height) // 2, width, height, fonts, lines, size
        return None

    if subject_mask is None:
        layout = horizontal((left, 520, right, bottom), TOP5_EDITORIAL_HEADLINE_DEFAULT_SIZE, TOP5_EDITORIAL_HEADLINE_MIN_SIZE)
        if layout is None:
            raise ValueError("Top-5 headline cannot fit the editorial card.")
        x, y, width, height, fonts, lines, size = layout
        body_font = None
        body_lines = []
        body_height = 0
        if clean_body:
            for body_size in range(TOP5_EDITORIAL_BODY_MAX_SIZE, TOP5_EDITORIAL_BODY_MIN_SIZE - 1, -2):
                font = _top5_body_font(body_size, body_language)
                lines_body = _top5_wrap_editorial_words(draw, clean_body, (font,), safe_width)
                box = draw.textbbox((0, 0), "Ag", font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
                line_height = box[3] - box[1]
                height_body = line_height * len(lines_body) + TOP5_EDITORIAL_BODY_LINE_GAP * max(0, len(lines_body) - 1)
                if y + height + TOP5_EDITORIAL_HEADLINE_BODY_GAP + height_body <= bottom:
                    body_font, body_lines, body_height = font, lines_body, height_body
                    break
        total_height = height + (TOP5_EDITORIAL_HEADLINE_BODY_GAP + body_height if body_lines else 0)
        return {
            "x": x, "y": max(top, min(bottom - total_height, y)), "width": width,
            "headline_fonts": fonts, "headline_lines": lines, "headline_height": height,
            "headline_size": size, "body_font": body_font, "body_lines": body_lines,
            "body_height": body_height, "body_size": body_font.size if body_font else None,
            "body_gap": TOP5_EDITORIAL_HEADLINE_BODY_GAP if body_lines else 0,
            "total_height": total_height, "zone_bottom": bottom, "subject_overlap": 0.0,
            "subject_bbox": None, "composition_mode": "editorial", "region_mode": "static",
            "story_number": story_number,
        }

    mask = subject_mask.convert("L").point(lambda value: 255 if value >= 96 else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise ValueError("Top-5 Subject Cutout returned no usable foreground subjects.")

    sx1, sy1, sx2, sy2 = bbox
    subject_height = max(1, sy2 - sy1)
    words = clean_headline.split()

    for size in range(TOP5_SUBJECT_HEADLINE_MAX_SIZE, TOP5_SUBJECT_HEADLINE_MIN_SIZE - 1, -2):
        fonts = _top5_headline_font_stack(size, language)
        width, height = _top5_editorial_measure(draw, clean_headline, fonts)
        lines = [words]
        if width > safe_width or height > (bottom - top):
            if max_headline_lines < 2:
                continue
            two = _top5_two_line_headline(draw, words, fonts)
            if two[1] > safe_width or two[2] > (bottom - top):
                continue
            lines, width, height = two[0], two[1], two[2]

        positions = [
            (left + (safe_width - width) / 2, sy1 - height * 0.62),
            (left + (safe_width - width) / 2, sy1 + (subject_height - height) / 2),
            (left + (safe_width - width) / 2, sy2 - height * 0.38),
        ]
        if sx1 > left + width * 0.18:
            positions.append((left, sy1 + (subject_height - height) / 2))
        if sx2 < right - width * 0.18:
            positions.append((right - width, sy1 + (subject_height - height) / 2))

        candidates = []
        for candidate_x, candidate_y in positions:
            x = int(round(max(left, min(right - width, candidate_x))))
            y = int(round(max(top, min(bottom - height, candidate_y))))
            overlap = mask.crop((x, y, x + width, y + height))
            overlap_ratio = sum(overlap.histogram()[1:]) / max(1, width * height)
            distance = abs(overlap_ratio - 0.22)
            candidates.append((distance, -overlap_ratio if overlap_ratio <= 0.42 else overlap_ratio, x, y, overlap_ratio))

        if candidates:
            viable = [candidate for candidate in candidates if candidate[4] <= 0.42]
            if viable:
                _, _, x, y, overlap_ratio = min(viable, key=lambda item: (item[0], item[1]))
                return {
                    "x": x, "y": y, "width": width, "headline_fonts": fonts,
                    "headline_lines": lines, "headline_height": height, "headline_size": size,
                    "body_font": None, "body_lines": [], "body_height": 0, "body_size": None,
                    "body_gap": 0, "total_height": height, "zone_bottom": bottom,
                    "subject_overlap": overlap_ratio, "subject_bbox": bbox,
                    "composition_mode": "subject-cutout", "region_mode": "hero-overlay",
                    "story_number": story_number,
                }

    raise ValueError("Top-5 Subject Cutout could not place the headline.")

@lru_cache(maxsize=1)
def _load_top5_birefnet():
    try:
        import torch
        from transformers import AutoModelForImageSegmentation
        from torchvision import transforms
    except ImportError as exc:
        raise RuntimeError("Top-5 Subject Cutout needs the existing torch, torchvision and transformers packages.") from exc

    model = AutoModelForImageSegmentation.from_pretrained(
        TOP5_SUBJECT_REMOVAL_MODEL,
        trust_remote_code=True,
    )
    model = model.to(torch.device("cpu")).float().eval()
    return model, transforms


@lru_cache(maxsize=64)
def _top5_subject_mask(image_bytes: bytes) -> Image.Image | None:
    if not image_bytes:
        return None
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("Top-5 Subject Cutout needs torch.") from exc

    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGB")

    model, transforms = _load_top5_birefnet()
    transform = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    tensor = transform(image).unsqueeze(0).to(dtype=torch.float32)

    with torch.inference_mode():
        prediction = model(tensor)
        if isinstance(prediction, (tuple, list)):
            prediction = prediction[-1]
        prediction = prediction.sigmoid().squeeze().cpu()

    mask = transforms.ToPILImage()(prediction)
    mask = mask.resize(image.size, Image.Resampling.BILINEAR)
    if mask.getbbox() is None:
        return None
    return mask.filter(ImageFilter.MedianFilter(3))


def _draw_top5_editorial_card(base: Image.Image, card: dict) -> Image.Image:
    language = str(card.get("language") or "english")
    headline = " ".join(str(card.get("headline") or "").split())
    subject_cutout = bool(card.get("subject_cutout"))
    body = "" if subject_cutout else " ".join(str(card.get("body") or "").split())
    if not headline:
        raise ValueError("Top-5 card requires a headline.")

    source_image = _top5_full_frame_image(base)
    subject_mask = None
    if subject_cutout:
        source_bytes = BytesIO()
        source_image.save(source_bytes, format="PNG", optimize=False)
        subject_mask = _top5_subject_mask(source_bytes.getvalue())
        if subject_mask is None:
            raise ValueError("Top-5 Subject Cutout could not produce a usable foreground mask.")

    layout = _top5_editorial_layout(
        headline,
        body,
        language,
        int(card.get("story_number") or 0),
        int(card.get("max_headline_lines") or TOP5_EDITORIAL_HEADLINE_MAX_LINES),
        image=source_image,
        subject_mask=subject_mask,
    )

    if subject_mask is not None:
        subject_mask = subject_mask.convert("L").point(lambda value: 255 if value >= 96 else 0)
        backdrop = Image.blend(
            source_image.convert("RGBA"),
            Image.new("RGBA", source_image.size, DARK + (255,)),
            0.20,
        )
        canvas = Image.composite(
            source_image.convert("RGBA"),
            backdrop,
            subject_mask,
        )

        subject_shadow = subject_mask.filter(ImageFilter.GaussianBlur(9))
        subject_shadow = subject_shadow.point(lambda value: min(150, value * 150 // 255))
        shadow_layer = Image.new("RGBA", canvas.size, DARK + (0,))
        shadow_layer.putalpha(subject_shadow)
        canvas.alpha_composite(shadow_layer, dest=(0, 7))
    else:
        canvas = source_image.convert("RGBA")

    draw = ImageDraw.Draw(canvas, "RGBA")
    commands = []
    cursor_y = layout["y"]

    for line_words in layout["headline_lines"]:
        line = " ".join(line_words)
        cursor_x = layout["x"]
        for run, font in _headline_runs(line, layout["headline_fonts"]):
            box = draw.textbbox((0, 0), run, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
            commands.append((run, font, cursor_x, cursor_y))
            cursor_x += box[2] - box[0]
        cursor_y += _top5_editorial_measure(draw, line, layout["headline_fonts"])[1] + TOP5_EDITORIAL_HEADLINE_LINE_GAP

    if layout["body_lines"] and layout["body_font"] is not None:
        cursor_y = layout["y"] + layout["headline_height"] + TOP5_EDITORIAL_HEADLINE_BODY_GAP
        for line_words in layout["body_lines"]:
            commands.append((" ".join(line_words), layout["body_font"], layout["x"], cursor_y))
            box = draw.textbbox((0, 0), "Ag", font=layout["body_font"], stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
            cursor_y += box[3] - box[1] + TOP5_EDITORIAL_BODY_LINE_GAP

    crop_box = (
        max(0, layout["x"]),
        max(0, layout["y"]),
        min(WIDTH, layout["x"] + max(1, layout["width"])),
        min(HEIGHT, layout["y"] + max(1, layout["total_height"])),
    )
    luma = source_image.convert("L").crop(crop_box).resize((1, 1)).getpixel((0, 0))
    light_text = luma < 145
    text_fill = (249, 250, 252, 255) if light_text else (5, 7, 10, 255)
    shadow_rgb = (5, 7, 10) if light_text else (249, 250, 252)
    stroke_fill = (5, 7, 10, 235) if light_text else (249, 250, 252, 235)

    text_mask = Image.new("L", canvas.size, 0)
    text_draw = ImageDraw.Draw(text_mask)
    for text, font, x, y in commands:
        box = text_draw.textbbox((0, 0), text, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        text_draw.text(
            (x - box[0], y - box[1]),
            text,
            font=font,
            fill=255,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=255,
        )

    shadow = text_mask.filter(ImageFilter.GaussianBlur(TOP5_EDITORIAL_SHADOW_BLUR))
    shadow = shadow.point(lambda value: value * TOP5_EDITORIAL_SHADOW_ALPHA // 255)
    shadow_layer = Image.new("RGBA", canvas.size, shadow_rgb + (0,))
    shadow_layer.putalpha(shadow)
    canvas.alpha_composite(shadow_layer, dest=TOP5_EDITORIAL_SHADOW_OFFSET)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for text, font, x, y in commands:
        box = draw.textbbox((0, 0), text, font=font, stroke_width=TOP5_EDITORIAL_STROKE_WIDTH)
        draw.text(
            (x - box[0], y - box[1]),
            text,
            font=font,
            fill=text_fill,
            stroke_width=TOP5_EDITORIAL_STROKE_WIDTH,
            stroke_fill=stroke_fill,
        )

    if subject_mask is not None:
        canvas = Image.composite(source_image.convert("RGBA"), canvas, subject_mask)

    return canvas


@lru_cache(maxsize=16)
def _manual_subject_font_bytes(font_name: str) -> bytes:
    source = MANUAL_SUBJECT_FONT_OPTIONS.get(font_name)
    if not source:
        raise ValueError("Manual Subject Cutout has an invalid font.")
    if source.get("file"):
        path = Path(__file__).resolve().parent / "fonts" / str(source["file"])
        if not path.exists():
            raise RuntimeError(f"Manual Subject Cutout requires the bundled {font_name} font.")
        return path.read_bytes()
    from urllib.request import urlopen
    try:
        with urlopen(str(source["url"]), timeout=20) as response:
            return response.read()
    except Exception as exc:
        raise RuntimeError(f"Manual Subject Cutout could not load the {font_name} font.") from exc



def _manual_subject_text_font_bytes(headline: str, font_name: str) -> bytes:
    script_language = _indic_language_for_text(headline)
    if not script_language:
        return _manual_subject_font_bytes(font_name)
    _require_raqm(script_language)
    filename = "NotoSansDevanagari-Bold.ttf" if script_language == "hindi" else "NotoSansTelugu-Bold.ttf"
    path = Path(__file__).resolve().parent / "fonts" / filename
    if not path.is_file():
        raise RuntimeError(f"Text Subject Cutout requires the bundled {filename} for {script_language.title()} copy.")
    return path.read_bytes()



def _manual_subject_cutout_layout_data_uncached(
    headline: str,
    polygon,
    font_size: int,
    font_name: str,
    style: str,
    polygon_flow: bool = True,
):
    clean_headline = " ".join(str(headline or "").split()).upper()
    if not clean_headline:
        raise ValueError("Manual Subject Cutout requires a headline.")

    if not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
        raise ValueError("Manual Subject Cutout requires a polygon text area.")

    try:
        points = [
            (
                max(0, min(WIDTH, int(point[0]))),
                max(0, min(HEIGHT, int(point[1]))),
            )
            for point in polygon
        ]
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError("Manual Subject Cutout has invalid polygon points.") from exc

    box_left = min(x for x, _ in points)
    box_top = min(y for _, y in points)
    box_right = max(x for x, _ in points)
    box_bottom = max(y for _, y in points)
    box_width = box_right - box_left
    box_height = box_bottom - box_top
    if box_width <= 0 or box_height <= 0:
        raise ValueError("Manual Subject Cutout text area must have positive dimensions.")

    try:
        requested_size = int(font_size or MANUAL_SUBJECT_DEFAULT_FONT_SIZE)
    except (TypeError, ValueError) as exc:
        raise ValueError("Manual Subject Cutout has invalid font size.") from exc
    requested_size = max(
        MANUAL_SUBJECT_MIN_FONT_SIZE,
        min(MANUAL_SUBJECT_MAX_FONT_SIZE, requested_size),
    )

    mode = str(font_name or "").strip()
    if mode not in MANUAL_SUBJECT_FONT_OPTIONS:
        raise ValueError("Manual Subject Cutout has an invalid font.")

    clean_style = str(style or "").strip()
    if clean_style not in MANUAL_SUBJECT_STYLE_OPTIONS:
        raise ValueError("Manual Subject Cutout has an invalid text style.")

    script_language = _indic_language_for_text(clean_headline)
    if script_language:
        _require_raqm(script_language)
    font_data = _manual_subject_text_font_bytes(clean_headline, mode)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    stroke_width = {
        "Crisp Outline": 4,
        "Soft Halo": 2,
        "Long Fade": 2,
        "Editorial Offset": 2,
        "Heavy Drop": 3,
        "Double Edge": 9,
        "Split Shadow": 3,
        "3D Extrusion": 3,
        "Chromatic Echo": 3,
    }[clean_style]

    def polygon_intervals(y_value: float) -> list[tuple[float, float]]:
        y_value = max(0.0, min(HEIGHT - 0.001, y_value))
        intersections = []
        for index, (x1, y1) in enumerate(points):
            x2, y2 = points[(index + 1) % len(points)]
            if y1 == y2:
                continue
            if (y1 <= y_value < y2) or (y2 <= y_value < y1):
                intersections.append(
                    x1 + (y_value - y1) * (x2 - x1) / (y2 - y1)
                )
        intersections.sort()
        return [
            (left, right)
            for left, right in zip(intersections[0::2], intersections[1::2])
            if right > left
        ]

    def line_position(
        line: str,
        font: ImageFont.FreeTypeFont,
        line_top: float,
        line_bottom: float,
    ):
        bbox = probe.textbbox(
            (0, 0),
            line,
            font=font,
            stroke_width=stroke_width,
        )
        line_width = bbox[2] - bbox[0]
        sample_y = [
            line_top + (line_bottom - line_top) * fraction
            for fraction in (0.05, 0.25, 0.5, 0.75, 0.95)
        ]
        regions = [polygon_intervals(y_value) for y_value in sample_y]
        if any(not region for region in regions):
            return None

        center_y = (line_top + line_bottom) / 2
        center_regions = polygon_intervals(center_y)
        if not center_regions:
            return None

        c_left, c_right = max(
            center_regions,
            key=lambda interval: interval[1] - interval[0],
        )

        left_edges = []
        right_edges = []
        for region in regions:
            overlapping = [
                iv for iv in region
                if not (iv[1] <= c_left or iv[0] >= c_right)
            ]
            if not overlapping:
                return None
            best = max(overlapping, key=lambda iv: iv[1] - iv[0])
            left_edges.append(best[0])
            right_edges.append(best[1])

        line_left = max(left_edges)
        line_right = min(right_edges)
        usable_width = line_right - line_left - 4
        if usable_width < line_width:
            return None

        left = int(round(line_left + 2))
        right = left + line_width
        if right > line_right - 2:
            return None
        return left, bbox, usable_width

    words = clean_headline.split()
    layouts = []
    if script_language:
        try:
            font = ImageFont.truetype(
                BytesIO(font_data),
                requested_size,
                layout_engine=ImageFont.Layout.RAQM,
            )
        except (OSError, ValueError) as exc:
            raise RuntimeError(
                f"Text Subject Cutout could not load the bundled Indic font with RAQM. "
                f"On Windows, confirm the FriBiDi runtime DLL is available and restart the factory."
            ) from exc
    else:
        # Preserve Pillow's established default layout engine for English.
        font = ImageFont.truetype(BytesIO(font_data), requested_size)
    line_box = probe.textbbox(
        (0, 0),
        "Ag",
        font=font,
        stroke_width=stroke_width,
    )
    line_height = max(1, line_box[3] - line_box[1])

    max_line_count = min(
        len(words),
        max(
            0,
            (box_height - 4 + TOP5_EDITORIAL_HEADLINE_LINE_GAP)
            // (line_height + TOP5_EDITORIAL_HEADLINE_LINE_GAP),
        ),
    )
    split_masks = (
        sum(1 << (position - 1) for position in split_positions)
        for line_count in range(1, max_line_count + 1)
        for split_positions in combinations(range(1, len(words)), line_count - 1)
    )

    for mask in split_masks:
        breaks = [
            index + 1
            for index in range(len(words) - 1)
            if mask & (1 << index)
        ]
        breaks.append(len(words))
        lines = []
        start = 0
        for end in breaks:
            lines.append(" ".join(words[start:end]))
            start = end

        total_height = (
            line_height * len(lines)
            + TOP5_EDITORIAL_HEADLINE_LINE_GAP * max(0, len(lines) - 1)
        )
        if total_height > box_height - 4:
            continue

        max_start_y = box_bottom - total_height - 2
        cand_starts = [box_top + 2]
        if max_start_y > box_top + 2:
            step = max(2, int(line_height // 8))
            cand_starts.extend(
                range(box_top + 2 + step, int(max_start_y) + 1, step)
            )

        valid = False
        placements = []
        fill_ratios = []
        start_y = box_top + 2
        for cand_y in cand_starts:
            cand_valid = True
            trial_placements = []
            trial_fill_ratios = []
            word_index = 0
            for line_index, end in enumerate(breaks):
                line = " ".join(words[word_index:end])
                line_top = cand_y + line_index * (
                    line_height + TOP5_EDITORIAL_HEADLINE_LINE_GAP
                )
                line_bottom = line_top + line_height
                position = line_position(line, font, line_top, line_bottom)
                if position is None:
                    cand_valid = False
                    break
                cursor_x, bbox, usable_width = position
                trial_placements.append((line, line_top, cursor_x, bbox))
                trial_fill_ratios.append(
                    (bbox[2] - bbox[0]) / max(1.0, usable_width)
                )
                word_index = end

            if cand_valid:
                valid = True
                placements = trial_placements
                fill_ratios = trial_fill_ratios
                start_y = cand_y
                break

        if valid:
            h_fill = sum(fill_ratios) / len(fill_ratios)
            v_fill = total_height / max(1.0, box_height - 4)
            fill_score = (h_fill * 0.5) + (v_fill * 0.5)
            layouts.append({
                "line_breaks": tuple(breaks),
                "lines": tuple(lines),
                "placements": tuple(placements),
                "fill_ratio": h_fill,
                "fill_score": fill_score,
            })

    layouts.sort(
        key=lambda item: (
            item["fill_score"],
            item["fill_ratio"],
            item["line_breaks"],
        ),
        reverse=True,
    )
    return {
        "headline": clean_headline,
        "points": points,
        "box_height": box_height,
        "font_size": requested_size,
        "font_name": mode,
        "style": clean_style,
        "polygon_flow": bool(polygon_flow),
        "font_data": font_data,
        "font": font,
        "stroke_width": stroke_width,
        "layouts": layouts,
    }


@lru_cache(maxsize=32)
def _manual_subject_cutout_layout_data_cached(
    headline: str,
    polygon: tuple[tuple[int, int], ...],
    font_size: int,
    font_name: str,
    style: str,
    polygon_flow: bool,
    font_signature: str,
):
    # Geometry is independent of the source photo. Keep a small cache for ordinary
    # Short headlines so Preview Options and Render Now can reuse the same layout.
    return _manual_subject_cutout_layout_data_uncached(
        headline,
        polygon,
        font_size,
        font_name,
        style,
        polygon_flow,
    )


def _manual_subject_cutout_layout_data(
    headline: str,
    polygon,
    font_size: int,
    font_name: str,
    style: str,
    polygon_flow: bool = True,
):
    clean_headline = " ".join(str(headline or "").split()).upper()
    if not clean_headline or not isinstance(polygon, (list, tuple)) or len(polygon) < 3:
        return _manual_subject_cutout_layout_data_uncached(
            headline, polygon, font_size, font_name, style, polygon_flow
        )

    try:
        polygon_key = tuple((int(point[0]), int(point[1])) for point in polygon)
        size_key = int(font_size or MANUAL_SUBJECT_DEFAULT_FONT_SIZE)
    except (TypeError, ValueError, IndexError):
        return _manual_subject_cutout_layout_data_uncached(
            headline, polygon, font_size, font_name, style, polygon_flow
        )

    # The line-break search has exponential complexity in word count. Keep long
    # headlines out of the cache so a single large layout cannot retain excessive RAM.
    if len(clean_headline.split()) > 10:
        return _manual_subject_cutout_layout_data_uncached(
            headline, polygon, font_size, font_name, style, polygon_flow
        )

    font_key = str(font_name or "").strip()
    style_key = str(style or "").strip()
    if font_key not in MANUAL_SUBJECT_FONT_OPTIONS or style_key not in MANUAL_SUBJECT_STYLE_OPTIONS:
        return _manual_subject_cutout_layout_data_uncached(
            headline, polygon, font_size, font_name, style, polygon_flow
        )

    font_signature = hashlib.sha1(_manual_subject_text_font_bytes(clean_headline, font_key)).hexdigest()
    return _manual_subject_cutout_layout_data_cached(
        clean_headline,
        polygon_key,
        size_key,
        font_key,
        style_key,
        bool(polygon_flow),
        font_signature,
    )


def _draw_manual_subject_cutout_frame(
    base: Image.Image,
    data: dict,
    placements,
    *,
    mode: str,
    subject_mask: Image.Image | None = None,
) -> Image.Image:
    canvas = _top5_full_frame_image(base).convert("RGBA")

    if mode == "behind-subject":
        if subject_mask is None:
            source = BytesIO()
            canvas.convert("RGB").save(source, format="PNG", optimize=False)
            subject_mask = _top5_subject_mask(source.getvalue())
            if subject_mask is None:
                raise ValueError("Manual Subject Cutout could not produce a usable subject mask.")
            subject_mask = subject_mask.convert("L").point(
                lambda value: 255 if value >= 96 else value
            )
        backdrop = Image.blend(
            canvas,
            Image.new("RGBA", canvas.size, DARK + (255,)),
            0.18,
        )
        canvas = Image.composite(canvas, backdrop, subject_mask)

    text_mask = Image.new("L", canvas.size, 0)
    text_draw = ImageDraw.Draw(text_mask)
    for line, line_top, cursor_x, bbox in placements:
        text_draw.text(
            (cursor_x - bbox[0], line_top - bbox[1]),
            line,
            font=data["font"],
            fill=255,
            stroke_width=data["stroke_width"],
            stroke_fill=255,
        )

    def shifted_layer(
        offset_x: int,
        offset_y: int,
        alpha: int,
        blur: int = 0,
        fill=DARK,
    ) -> None:
        layer_mask = text_mask.filter(ImageFilter.GaussianBlur(blur)) if blur else text_mask
        layer_mask = layer_mask.point(lambda value: value * alpha // 255)
        layer = Image.new("RGBA", canvas.size, fill + (0,))
        layer.putalpha(layer_mask)
        canvas.alpha_composite(layer, dest=(offset_x, offset_y))

    style = data["style"]
    if style == "Soft Halo":
        shifted_layer(0, 0, 80, 24)
        shifted_layer(0, 4, 175, 16)
    elif style == "Long Fade":
        shifted_layer(0, 4, 115, 7)
        shifted_layer(0, 8, 90, 7)
        shifted_layer(0, 12, 65, 7)
        shifted_layer(0, 16, 40, 7)
    elif style == "Editorial Offset":
        shifted_layer(5, 6, 155, 2, ACCENT)
        shifted_layer(0, 5, 110, 5)
    elif style == "Heavy Drop":
        shifted_layer(4, 8, 235)
        shifted_layer(8, 14, 170)
        shifted_layer(12, 19, 90, 1)
    elif style == "Double Edge":
        shifted_layer(0, 4, 210, 3)
    elif style == "Split Shadow":
        shifted_layer(-7, 5, 145, 2, ACCENT)
        shifted_layer(6, 8, 220, 5)
    elif style == "3D Extrusion":
        shifted_layer(3, 4, 245)
        shifted_layer(6, 8, 225)
        shifted_layer(9, 12, 195)
        shifted_layer(12, 16, 150)
        shifted_layer(15, 20, 105, 1)
    elif style == "Chromatic Echo":
        shifted_layer(-7, 5, 175, 1, ACCENT)
        shifted_layer(7, -4, 130, 2)
        shifted_layer(0, 6, 145, 5)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for line, line_top, cursor_x, bbox in placements:
        position = (cursor_x - bbox[0], line_top - bbox[1])
        if style == "Double Edge":
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=9,
                stroke_fill=DARK + (255,),
            )
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=2,
                stroke_fill=DARK + (245,),
            )
        else:
            draw.text(
                position,
                line,
                font=data["font"],
                fill=WHITE + (255,),
                stroke_width=data["stroke_width"],
                stroke_fill=DARK + (245,),
            )

    if subject_mask is not None:
        canvas = Image.composite(
            _top5_full_frame_image(base).convert("RGBA"),
            canvas,
            subject_mask,
        )

    return canvas


def _draw_manual_subject_cutout(base: Image.Image, config: dict) -> Image.Image:
    mode = str(config.get("mode") or "negative-space").strip().casefold()
    if mode not in {"negative-space", "behind-subject"}:
        raise ValueError("Manual Subject Cutout has an invalid composition mode.")

    font_size = int(config.get("font_size") or MANUAL_SUBJECT_DEFAULT_FONT_SIZE)
    headline = config.get("headline") or ""
    data = None
    step_size = font_size
    while step_size >= MANUAL_SUBJECT_MIN_FONT_SIZE:
        try:
            cand_data = _manual_subject_cutout_layout_data(
                headline,
                config.get("text_polygon"),
                step_size,
                str(config.get("font") or "Barlow Condensed").strip(),
                str(config.get("style") or "Crisp Outline").strip(),
                bool(config.get("polygon_flow", True)),
            )
            if cand_data.get("layouts"):
                data = cand_data
                break
        except RuntimeError:
            raise
        except RuntimeError:
            raise
        except Exception:
            pass
        step_size -= 10

    if not data or not data.get("layouts"):
        data = _manual_subject_cutout_layout_data(
            headline,
            config.get("text_polygon"),
            font_size,
            str(config.get("font") or "Barlow Condensed").strip(),
            str(config.get("style") or "Crisp Outline").strip(),
            bool(config.get("polygon_flow", True)),
        )
    layouts = data["layouts"]
    if not layouts:
        raise ValueError(
            f"Text size {data['font_size']}px does not fit the selected polygon. Make the polygon larger or choose a smaller size."
        )

    selected_breaks = config.get("line_breaks")
    if selected_breaks is not None:
        try:
            selected_breaks = tuple(int(value) for value in selected_breaks)
        except (TypeError, ValueError):
            raise ValueError("Manual Subject Cutout has invalid line breaks.")
        layout = next(
            (item for item in layouts if item["line_breaks"] == selected_breaks),
            None,
        )
        if layout is None:
            raise ValueError("The selected line-break layout does not fit the current polygon or text size.")
    else:
        layout = layouts[0]

    subject_mask = None
    if mode == "behind-subject":
        source = BytesIO()
        _top5_full_frame_image(base).convert("RGB").save(source, format="PNG", optimize=False)
        try:
            subject_mask = _top5_subject_mask(source.getvalue())
        except Exception:
            subject_mask = None
        if subject_mask is not None:
            subject_mask = subject_mask.convert("L").point(
                lambda value: 255 if value >= 96 else value
            )

    return _draw_manual_subject_cutout_frame(
        base,
        data,
        layout["placements"],
        mode=mode,
        subject_mask=subject_mask,
    )


def build_manual_subject_cutout_preview(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    *,
    mode: str,
    font_size: int,
    font: str = "Barlow Condensed",
    style: str = "Crisp Outline",
    text_polygon: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
    line_breaks: tuple[int, ...] | list[int] | None = None,
    polygon_flow: bool = True,
) -> bytes:
    frame = _draw_manual_subject_cutout(
        source_image,
        {
            "headline": headline,
            "mode": mode,
            "text_polygon": text_polygon,
            "font_size": int(font_size),
            "font": font,
            "style": style,
            "line_breaks": line_breaks,
            "polygon_flow": polygon_flow,
        },
    )
    buffer = BytesIO()
    frame.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def build_manual_subject_cutout_layout_previews(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    *,
    mode: str,
    font_size: int,
    font: str = "Barlow Condensed",
    style: str = "Crisp Outline",
    text_polygon: list[tuple[int, int]] | tuple[tuple[int, int], ...] = (),
    polygon_flow: bool = True,
) -> list[dict]:
    selected_mode = str(mode or "negative-space").strip().casefold()
    if selected_mode not in {"negative-space", "behind-subject"}:
        raise ValueError("Manual Subject Cutout has an invalid composition mode.")

    data = None
    step_size = int(font_size or MANUAL_SUBJECT_DEFAULT_FONT_SIZE)
    while step_size >= MANUAL_SUBJECT_MIN_FONT_SIZE:
        try:
            cand_data = _manual_subject_cutout_layout_data(
                headline,
                text_polygon,
                step_size,
                font,
                style,
                polygon_flow,
            )
            if cand_data.get("layouts"):
                data = cand_data
                break
        except Exception:
            pass
        step_size -= 10

    if not data or not data.get("layouts"):
        data = _manual_subject_cutout_layout_data(
            headline,
            text_polygon,
            font_size,
            font,
            style,
            polygon_flow,
        )
    if not data["layouts"]:
        raise ValueError(
            f"Text size {data['font_size']}px does not fit the selected polygon. Make the polygon larger or choose a smaller size."
        )

    subject_mask = None
    if selected_mode == "behind-subject":
        base = _top5_full_frame_image(
            source_image if isinstance(source_image, Image.Image) else Image.open(BytesIO(bytes(source_image)))
        ).convert("RGBA")
        source = BytesIO()
        base.convert("RGB").save(source, format="PNG", optimize=False)
        try:
            subject_mask = _top5_subject_mask(source.getvalue())
        except Exception:
            subject_mask = None
        if subject_mask is not None:
            subject_mask = subject_mask.convert("L").point(
                lambda value: 255 if value >= 96 else value
            )

    base_image = (
        source_image.convert("RGB")
        if isinstance(source_image, Image.Image)
        else Image.open(BytesIO(bytes(source_image))).convert("RGB")
    )

    previews = []
    for index, layout in enumerate(data["layouts"], 1):
        frame = _draw_manual_subject_cutout_frame(
            base_image,
            data,
            layout["placements"],
            mode=selected_mode,
            subject_mask=subject_mask,
        ).resize((360, 640), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        frame.convert("RGB").save(buffer, format="JPEG", quality=84, optimize=True)
        previews.append({
            "index": index,
            "line_breaks": layout["line_breaks"],
            "lines": layout["lines"],
            "preview": buffer.getvalue(),
        })
    return previews


def _paste_top5_source(base: Image.Image, source_label: str | None) -> None:
    label = str(source_label or "Commons").strip() or "Commons"
    draw = ImageDraw.Draw(base)
    font = _renderer_font_for_text(label, 20)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text(
        (WIDTH - TOP5_EDITORIAL_MARGIN_X - (box[2] - box[0]), HEIGHT - 48),
        label,
        font=font,
        fill=(86, 91, 100),
    )


def build_top5_card_preview(
    source_image: bytes | bytearray | Image.Image,
    headline: str,
    body: str = "",
    story_number: int = 0,
    total_stories: int = 5,
    source_label: str | None = None,
    subject_cutout: bool = False,
    logo_enabled: bool = False,
) -> bytes:
    frame = _draw_top5_editorial_card(
        source_image,
        {
            "headline": headline,
            "body": body,
            "story_number": story_number,
            "total_stories": total_stories,
            "subject_cutout": bool(subject_cutout),
        },
    )
    if logo_enabled:
        _paste_logo(frame)
    _paste_top5_source(frame, source_label)
    buffer = BytesIO()
    frame.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@lru_cache(maxsize=1024)
def _motion_profile(seed: str) -> tuple[int, float, float, int, int]:
    """Choose a stable, varied editorial camera path from story/visual evidence."""
    digest = hashlib.sha1(str(seed or "visual").encode("utf-8")).digest()
    return (
        digest[0] % 10,
        1.025 + (digest[1] % 9) * 0.005,
        1.075 + (digest[2] % 11) * 0.005,
        -1 if digest[3] & 1 else 1,
        -1 if digest[4] & 1 else 1,
    )


def _animate_visual(
    image: Image.Image,
    t: float,
    duration: float,
    seed: str,
) -> Image.Image:
    """Apply a deterministic story-specific Ken Burns path without changing the master frame."""
    if duration <= 0.0:
        return image.copy()

    mode, start_scale, end_scale, x_direction, y_direction = _motion_profile(seed)
    progress = min(1.0, max(0.0, float(t) / duration))
    eased = 0.5 - 0.5 * math.cos(math.pi * progress)
    sweep = (eased - 0.5) * 2.0

    # Ten restrained paths: directional push/pull, horizontal/vertical sweeps,
    # and diagonals. They remain deterministic for repeatable render previews.
    reverse_zoom_modes = {1, 5, 8}
    if mode in reverse_zoom_modes:
        scale = end_scale - (end_scale - start_scale) * eased
    elif mode == 4:
        scale = start_scale + (end_scale - start_scale) * eased * 0.65
    elif mode == 7:
        scale = start_scale + (end_scale - start_scale) * (eased * 0.8)
    else:
        scale = start_scale + (end_scale - start_scale) * eased

    if mode == 0:
        x_progress, y_progress = eased * x_direction, 0.0
    elif mode == 1:
        x_progress, y_progress = 0.0, eased * y_direction
    elif mode == 2:
        x_progress, y_progress = eased * x_direction, eased * y_direction
    elif mode == 3:
        x_progress, y_progress = sweep * x_direction, 0.0
    elif mode == 4:
        x_progress, y_progress = 0.45 * eased * x_direction, sweep * y_direction
    elif mode == 5:
        x_progress, y_progress = -eased * x_direction, 0.0
    elif mode == 6:
        x_progress, y_progress = eased * x_direction, -eased * y_direction
    elif mode == 7:
        x_progress, y_progress = 0.0, sweep * y_direction
    elif mode == 8:
        x_progress, y_progress = 0.65 * eased * x_direction, 0.35 * eased * y_direction
    else:
        x_progress, y_progress = sweep * x_direction, 0.35 * eased * y_direction

    scaled_width = max(WIDTH, int(round(WIDTH * scale)))
    scaled_height = max(HEIGHT, int(round(HEIGHT * scale)))
    scaled = image.resize((scaled_width, scaled_height), Image.Resampling.BICUBIC)
    max_x, max_y = scaled_width - WIDTH, scaled_height - HEIGHT
    x = int(round(max_x / 2.0 + max_x / 2.0 * x_progress))
    y = int(round(max_y / 2.0 + max_y / 2.0 * y_progress))
    x = max(0, min(max_x, x))
    y = max(0, min(max_y, y))
    return scaled.crop((x, y, x + WIDTH, y + HEIGHT))



def _cue_at_time(subtitle_data: dict, t: float):
    for cue in subtitle_data.get("cues") or []:
        try:
            if float(cue["start"]) <= t < float(cue["end"]):
                return cue
        except (KeyError, TypeError, ValueError):
            continue
    return None


def validate_subtitle_handoff(subtitle_data: dict) -> bool:
    if not isinstance(subtitle_data, dict):
        return False
    if subtitle_data.get("schema") != "final-shorts.subtitles.v1":
        return False
    if not str(subtitle_data.get("language") or "").strip():
        return False

    previous_end = -1.0
    for cue in subtitle_data.get("cues") or []:
        try:
            start = float(cue["start"])
            end = float(cue["end"])
        except (KeyError, TypeError, ValueError):
            return False

        if start < 0 or end <= start or start < previous_end:
            return False

        words = cue.get("words")
        if not isinstance(words, list) or not words:
            return False

        word_end = start
        for word in words:
            try:
                word_start = float(word["start"])
                current_end = float(word["end"])
            except (KeyError, TypeError, ValueError):
                return False

            if (
                not str(word.get("text") or "").strip()
                or word_start < start
                or current_end <= word_start
                or current_end > end
                or word_start < word_end
            ):
                return False
            word_end = current_end

        previous_end = end

    return bool(subtitle_data.get("cues"))


def _subtitle_lines(
    words: list[dict],
    draw: ImageDraw.ImageDraw,
    font,
) -> list[list[dict]]:
    if not words:
        return []

    measurements = [
        _measure(
            draw,
            str(word.get("text") or ""),
            font,
            SUBTITLE_STROKE_WIDTH,
        )[0]
        for word in words
    ]

    def line_width(start: int, end: int) -> int:
        return (
            sum(measurements[start:end])
            + SUBTITLE_WORD_SPACING * max(0, end - start - 1)
        )

    if line_width(0, len(words)) <= SUBTITLE_MAX_WIDTH:
        return [words]

    candidates = []
    for split in range(1, len(words)):
        top = line_width(0, split)
        bottom = line_width(split, len(words))
        if (
            top <= SUBTITLE_MAX_WIDTH
            and bottom <= SUBTITLE_MAX_WIDTH
        ):
            candidates.append((max(top, bottom), abs(top - bottom), split))

    if not candidates:
        raise ValueError("Subtitle cue is too wide to fit in two lines.")

    _, _, split = min(candidates)
    return [words[:split], words[split:]]


@lru_cache(maxsize=256)
def _fit_subtitle_layout_cached(
    word_texts: tuple[str, ...],
    language: str,
):
    words = [{"text": text} for text in word_texts]
    language = _normalise_indic_language(language or "english")
    script_language = _indic_language_for_text(" ".join(word_texts))
    render_language = script_language or language
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for size in range(SUBTITLE_MAX_SIZE, SUBTITLE_MIN_SIZE - 1, -1):
        font = _font(_font_candidates("subtitle", render_language), size, language=render_language)
        try:
            lines = _subtitle_lines(words, probe, font)
        except ValueError:
            continue
        return font, tuple(len(line) for line in lines)

    raise ValueError("Subtitle cue is too wide to fit in two lines.")

@lru_cache(maxsize=512)
def _subtitle_render_geometry_cached(
    word_texts: tuple[str, ...],
    language: str,
):
    words = [{"text": text} for text in word_texts]
    font, line_lengths = _fit_subtitle_layout_cached(word_texts, language)
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    measurements = tuple(
        probe.textbbox(
            (0, 0),
            str(word.get("text") or ""),
            font=font,
            stroke_width=SUBTITLE_STROKE_WIDTH,
        )
        for word in words
    )
    line_heights = []
    offset = 0
    for length in line_lengths:
        indices = range(offset, offset + length)
        line_heights.append(
            max(
                measurements[index][3] - measurements[index][1]
                for index in indices
            )
        )
        offset += length
    total_height = sum(line_heights) + SUBTITLE_LINE_GAP * max(
        0, len(line_heights) - 1
    )
    return font, line_lengths, measurements, tuple(line_heights), total_height


def _draw_subtitles(
    base: Image.Image,
    subtitle_data: dict,
    t: float,
    y_position: int | None = None,
) -> None:
    cue = _cue_at_time(subtitle_data, t)
    if cue is None:
        return

    words = cue["words"]
    language = subtitle_data.get("language") or "english"
    draw = ImageDraw.Draw(base)
    font, line_lengths, measurements, line_heights, total_height = _subtitle_render_geometry_cached(
        tuple(str(word.get("text") or "") for word in words),
        language,
    )
    lines = []
    offset = 0
    for length in line_lengths:
        lines.append(words[offset:offset + length])
        offset += length

    y = (int(y_position) if y_position is not None else SUBTITLE_Y) - total_height // 2
    ascent, _ = font.getmetrics()

    word_index = 0
    for row, line in enumerate(lines):
        widths = [
            measurements[word_index + offset][2] - measurements[word_index + offset][0]
            for offset in range(len(line))
        ]
        line_width = sum(widths) + SUBTITLE_WORD_SPACING * max(0, len(line) - 1)
        cursor = (WIDTH - line_width) // 2
        baseline_y = y + ascent

        for offset, word in enumerate(line):
            index = word_index + offset
            text = str(word["text"]).translate(DASH_TRANSLATION)
            box = measurements[index]
            width = box[2] - box[0]
            start = float(word["start"])
            end = float(word["end"])
            active = start <= t < end

            text_fill = ACCENT if active else WHITE

            draw.text(
                (cursor, baseline_y),
                text,
                font=font,
                fill=text_fill,
                stroke_width=SUBTITLE_STROKE_WIDTH,
                stroke_fill=DARK,
                anchor="ls",
            )
            cursor += width + SUBTITLE_WORD_SPACING

        y += line_heights[row] + SUBTITLE_LINE_GAP
        word_index += len(line)


def render_frame(
    base_image: Image.Image,
    t: float,
    subtitle_data: dict | None = None,
    source_label: str | None = None,
    subtitle_y: int | None = None,
    top5_card: dict | None = None,
    validate_handoff: bool = True,
    logo_enabled: bool = False,
    source_enabled: bool = True,
) -> Image.Image:
    if subtitle_data is None:
        subtitle_data = {"language": "english", "cues": []}
    elif validate_handoff and not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Invalid subtitle handoff.")

    if base_image.size == (WIDTH, HEIGHT) and base_image.mode == "RGBA":
        frame = base_image.copy()
    else:
        frame = base_image.convert("RGBA")
        if frame.size != (WIDTH, HEIGHT):
            frame = frame.resize(
                (WIDTH, HEIGHT),
                Image.Resampling.LANCZOS,
            )

    if top5_card is not None:
        _draw_top5_editorial_card(frame, top5_card)
    else:
        if subtitle_y is None:
            _draw_subtitles(frame, subtitle_data, t)
        else:
            _draw_subtitles(frame, subtitle_data, t, subtitle_y)

    if logo_enabled:
        _paste_logo(frame)
    if source_enabled:
        if source_label is None:
            _paste_source(frame)
        else:
            _paste_source(frame, source_label)
    return frame.convert("RGB")


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None



def write_preview_video(frames, path: Path) -> Path:
    if not _ffmpeg_available():
        raise RuntimeError("ffmpeg is required to create renderer videos.")

    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "rgb24",
            "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
            "-an",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "18",
            "-profile:v", "high",
            "-bf", "2",
            "-g", str(max(1, FPS // 2)),
            "-keyint_min", str(max(1, FPS // 2)),
            "-flags", "+cgop",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709",
            "-color_trc", "bt709",
            "-colorspace", "bt709",
            "-movflags", "+faststart",
            "-fps_mode", "cfr",
            str(path),
        ],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin is not None

    try:
        wrote_frame = False
        for frame in frames:
            wrote_frame = True
            if frame.size != (WIDTH, HEIGHT):
                frame = frame.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            raw = frame.tobytes() if frame.mode == "RGB" else frame.convert("RGB").tobytes()
            process.stdin.write(raw)
        if not wrote_frame:
            process.stdin.close()
            process.kill()
            raise ValueError("No frames were provided.")
        process.stdin.close()
    except BrokenPipeError as exc:
        process.kill()
        raise RuntimeError("ffmpeg stopped while creating the video.") from exc

    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise RuntimeError(stderr.strip() or "ffmpeg failed to create the video.")
    return path

def _fit_visual_to_frame(value: bytes | bytearray | Image.Image) -> Image.Image:
    if isinstance(value, Image.Image):
        image = value.convert("RGB")
    elif isinstance(value, (bytes, bytearray)):
        try:
            with Image.open(BytesIO(bytes(value))) as source:
                image = source.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ValueError("A visual asset could not be decoded.") from exc
    else:
        raise ValueError("Each visual must contain image bytes.")

    target_ratio = WIDTH / HEIGHT
    current_ratio = image.width / image.height
    if current_ratio > target_ratio:
        crop_width = max(1, int(image.height * target_ratio))
        left = (image.width - crop_width) // 2
        image = image.crop((left, 0, left + crop_width, image.height))
    elif current_ratio < target_ratio:
        crop_height = max(1, int(image.width / target_ratio))
        top = (image.height - crop_height) // 2
        image = image.crop((0, top, image.width, top + crop_height))

    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)



def _mux_audio(
    silent_video: Path,
    audio_scenes: list[dict],
    output_path: Path,
) -> Path:
    inputs = ["-i", str(silent_video)]
    continuous_master = (
        audio_scenes[0].get("continuous_master_path")
        if audio_scenes
        else None
    )
    is_continuous_take = bool(
        continuous_master
        and all(
            scene.get("continuous_master_path") == continuous_master
            for scene in audio_scenes
        )
        and not any(scene.get("human_recorded") for scene in audio_scenes)
    )

    if is_continuous_take:
        master_path = Path(str(continuous_master))
        if not master_path.is_file() or master_path.stat().st_size <= 0:
            raise ValueError("The continuous Chatterbox master audio file is missing.")
        inputs.extend(["-i", str(master_path)])
        filter_complex = "[1:a]loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    else:
        filter_inputs = []
        for index, scene in enumerate(audio_scenes, 1):
            audio_path = Path(str(scene.get("path") or ""))
            if not audio_path.is_file() or audio_path.stat().st_size <= 0:
                raise ValueError(f"Audio file for scene {scene.get('scene') or index} is missing.")
            inputs.extend(["-i", str(audio_path)])
            filter_inputs.append(f"[{index}:a]")
        filter_complex = (
            "".join(filter_inputs)
            + f"concat=n={len(audio_scenes)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
        )

    process = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *inputs,
            "-filter_complex", filter_complex,
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(output_path),
        ],
        capture_output=True, text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(process.stderr.strip() or "ffmpeg failed to attach the audio.")
    return output_path

def render_production_video(
    approved_script: dict,
    approved_audio: dict,
    subtitle_data: dict | None,
    visuals: list[dict],
    output_path: str | Path,
    source_label: str | None = None,
    logo_enabled: bool = False,
    source_enabled: bool = True,
) -> Path:
    """Render an approved Cricket or Top-5 production handoff."""
    if (
        not isinstance(approved_script, dict)
        or approved_script.get("approved_for_audio") is not True
    ):
        raise ValueError("Renderer requires the approved Scriptwriter handoff.")

    if (
        not isinstance(approved_audio, dict)
        or approved_audio.get("approved_for_visuals") is not True
    ):
        raise ValueError("Renderer requires the approved Audio handoff.")

    is_top5 = approved_script.get("schema") == "final-shorts.top5-script.v1"
    if not is_top5 and not validate_subtitle_handoff(subtitle_data):
        raise ValueError("Renderer requires a valid subtitle handoff.")

    script_scenes = (
        approved_script.get("slides")
        if is_top5
        else approved_script.get("script")
    )
    audio_scenes = approved_audio.get("scenes")
    if (
        not isinstance(script_scenes, list)
        or not isinstance(audio_scenes, list)
        or len(script_scenes) != len(audio_scenes)
        or len(visuals) != len(script_scenes)
        or not script_scenes
    ):
        raise ValueError("Script, audio and visual scene counts must match.")

    durations = []
    for number, scene in enumerate(audio_scenes, 1):
        try:
            duration = float(scene.get("duration") or 0.0)
        except (AttributeError, TypeError, ValueError):
            duration = 0.0
        if not math.isfinite(duration) or duration <= 0.0:
            raise ValueError(f"Audio scene {number} has no valid measured duration.")
        durations.append(duration)

    scene_total_duration = sum(durations)
    declared_total = approved_audio.get("total_duration")
    if declared_total is None:
        declared_total_duration = scene_total_duration
    else:
        try:
            declared_total_duration = float(declared_total)
        except (TypeError, ValueError):
            raise ValueError("Audio handoff has an invalid total duration.")
        if not math.isfinite(declared_total_duration) or declared_total_duration <= 0.0:
            raise ValueError("Audio handoff has an invalid total duration.")

    # Use the more conservative value so a stale/rounded master-duration field
    # cannot let an overlength render through when per-scene sums differ slightly.
    total_duration = max(scene_total_duration, declared_total_duration)
    if total_duration >= 30.0:
        raise ValueError(
            f"Renderer refuses a {total_duration:.2f}-second Short: the factory limit is strictly under 30 seconds. "
            "Regenerate Audio with the timing correction or shorten the narration."
        )

    if not is_top5:
        language = _normalise_indic_language(
            approved_script.get("language_used") or approved_audio.get("language")
        )
        if language in {"hindi", "telugu"} and durations[0] > 5.2:
            raise ValueError(
                f"{language.title()} Slide 1 audio is {durations[0]:.2f}s; it must be no more than 5.2 seconds. "
                "Regenerate Audio so its measured timing is corrected before rendering."
            )

    prepared_visuals = []
    for index, visual in enumerate(visuals, 1):
        if not isinstance(visual, dict):
            raise ValueError(f"Visual {index} is malformed.")
        top5_card = visual.get("top5_card")
        if top5_card is not None and not isinstance(top5_card, dict):
            raise ValueError(f"Visual {index} has malformed Top-5 card data.")
        manual_subject_cutout = visual.get("manual_subject_cutout")
        if manual_subject_cutout is not None and not isinstance(manual_subject_cutout, dict):
            raise ValueError(f"Visual {index} has malformed Manual Subject Cutout data.")
        card_studio = visual.get("card_studio")
        if card_studio is not None and not isinstance(card_studio, dict):
            raise ValueError(f"Visual {index} has malformed Card Studio data.")

        image = _fit_visual_to_frame(visual.get("bytes")).convert("RGBA")
        static_frame = None
        if isinstance(manual_subject_cutout, dict):
            preview_bytes = visual.get("preview_bytes")
            if isinstance(preview_bytes, (bytes, bytearray)):
                with Image.open(BytesIO(bytes(preview_bytes))) as preview_image:
                    static_frame = preview_image.convert("RGB").copy()
            else:
                static_frame = _draw_manual_subject_cutout(image, manual_subject_cutout).convert("RGB")
        elif isinstance(top5_card, dict):
            static_frame = _draw_top5_editorial_card(image, top5_card)
            if logo_enabled:
                _paste_logo(static_frame)
            if source_enabled:
                _paste_source(
                    static_frame,
                    str(visual.get("source") or source_label or "Commons").strip() or "Commons",
                )
            static_frame = static_frame.convert("RGB")
        elif isinstance(card_studio, dict):
            preview_bytes = visual.get("preview_bytes")
            if not isinstance(preview_bytes, (bytes, bytearray)):
                raise ValueError(f"Visual {index} Card Studio data is missing its rendered preview.")
            try:
                with Image.open(BytesIO(bytes(preview_bytes))) as preview_image:
                    static_frame = preview_image.convert("RGB").copy()
            except (OSError, ValueError) as exc:
                raise ValueError(f"Visual {index} Card Studio preview is not a valid image.") from exc
            if static_frame.size != (WIDTH, HEIGHT):
                static_frame = static_frame.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
            if logo_enabled:
                _paste_logo(static_frame)
            if source_enabled:
                _paste_source(
                    static_frame,
                    str(visual.get("source") or source_label or "Commons").strip() or "Commons",
                )

        motion_seed = ""
        if static_frame is None and not isinstance(top5_card, dict) and not manual_subject_cutout and not card_studio:
            scene_metadata = script_scenes[index - 1] if index - 1 < len(script_scenes) else {}
            seed_parts = [
                str(approved_script.get("story_angle") or ""),
                *(
                    str(visual.get(key) or "")
                    for key in (
                        "primary_entity",
                        "visual_intent",
                        "specific_search_prompt",
                        "sport_or_topic_category",
                        "source",
                    )
                ),
            ]
            # Standard Shorts use the spoken beat and story identity in addition
            # to image metadata. This makes each camera path follow the actual
            # editorial cut, rather than choosing motion from the image search
            # prompt alone. Top-5 keeps its established motion-seed behavior.
            if not is_top5 and isinstance(scene_metadata, dict):
                seed_parts.extend((
                    str(approved_script.get("source_title") or approved_script.get("headline") or ""),
                    str(scene_metadata.get("voiceover") or scene_metadata.get("headline") or ""),
                    f"scene:{index}",
                ))
            motion_seed = "|".join(seed_parts).strip("|")
            if not motion_seed:
                # Image bytes are stable for this scene; hashing them per frame is
                # pure repeated work, so derive the fallback seed only once here.
                motion_seed = hashlib.sha1(image.tobytes()).hexdigest()

        prepared_visuals.append({
            "image": image,
            "static_frame": static_frame,
            "is_top5_card": isinstance(top5_card, dict),
            "top5_card": top5_card,
            "manual_subject_cutout": manual_subject_cutout,
            "card_studio": card_studio,
            "motion_seed": motion_seed,
        })

    durations = []
    for index, scene in enumerate(audio_scenes, 1):
        try:
            duration = float(scene["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Audio scene {index} has no usable duration.") from exc
        if duration <= 0:
            raise ValueError(f"Audio scene {index} has an invalid duration.")
        durations.append(duration)

    total_duration = sum(durations)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    # A fixed intermediate filename collides when Streamlit reruns or two renders
    # overlap. Give every render its own file so one run cannot lock another run's
    # intermediate video during cleanup.
    with tempfile.NamedTemporaryFile(
        prefix=f"{output.stem}.",
        suffix=".silent.mp4",
        dir=output.parent,
        delete=False,
    ) as silent_handle:
        silent_video = Path(silent_handle.name)


    def frames():
        frame_count = max(1, int(math.ceil(total_duration * FPS)))
        elapsed = 0.0
        scene_index = 0
        for frame_index in range(frame_count):
            t = frame_index / FPS
            while scene_index < len(durations) - 1 and t >= elapsed + durations[scene_index]:
                elapsed += durations[scene_index]
                scene_index += 1

            visual = prepared_visuals[scene_index]
            scene_time = max(0.0, t - elapsed)
            scene_duration = durations[scene_index]
            if visual.get("static_frame") is not None:
                yield visual["static_frame"]
                continue

            base_image = visual["image"]
            if visual.get("motion_seed"):
                base_image = _animate_visual(
                    base_image, scene_time, scene_duration, visual["motion_seed"]
                )

            yield render_frame(
                base_image,
                t,
                subtitle_data,
                source_label=source_label,
                top5_card=None,
                validate_handoff=False,
                logo_enabled=logo_enabled,
                source_enabled=source_enabled,
            )

    try:
        write_preview_video(frames(), silent_video)
        return _mux_audio(silent_video, audio_scenes, output)
    finally:
        # Windows antivirus/indexing or a media reader can briefly hold an MP4
        # handle. Cleanup is best-effort: never turn an already completed final
        # render into a reported failure merely because a temporary file is locked.
        for attempt in range(4):
            try:
                silent_video.unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt < 3:
                    time.sleep(0.15 * (attempt + 1))
                else:
                    warnings.warn(
                        f"Render succeeded, but the temporary silent video could not be deleted: {silent_video}",
                        RuntimeWarning,
                    )
            except OSError as exc:
                warnings.warn(
                    f"Render succeeded, but temporary video cleanup failed for {silent_video}: {exc}",
                    RuntimeWarning,
                )
                break

