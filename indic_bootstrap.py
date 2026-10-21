"""Bootstrap Windows runtime libraries for FriBiDi and RAQM text shaping before PIL is imported."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

_DLL_HANDLES: list[object] = []
_BOOTSTRAP_ATTEMPTED = False


def bootstrap_indic_runtime(repo_root: Path | None = None) -> bool:
    """Ensure Windows FriBiDi and RAQM libraries are available before Pillow initializes _imagingft."""
    global _BOOTSTRAP_ATTEMPTED
    if _BOOTSTRAP_ATTEMPTED:
        return True
    _BOOTSTRAP_ATTEMPTED = True

    root = Path(repo_root or Path(__file__).resolve().parent)
    search_dirs: list[Path] = [
        root / "dlls",
        Path(sys.prefix) / "Lib" / "site-packages" / "pillow.libs",
        root / ".deps" / "raqm_pillow_11_3_0_cp311" / "pillow.libs",
        root / ".deps" / "raqm_pillow_11_3_0_cp311",
        root / ".deps" / "raqm_pillow",
    ]

    # Add candidate directories to PATH and Windows DLL loader
    valid_dirs = [str(d) for d in search_dirs if d.is_dir()]
    if valid_dirs:
        os.environ["PATH"] = os.pathsep.join(valid_dirs + [os.environ.get("PATH", "")])

    if os.name == "nt" and hasattr(os, "add_dll_directory"):
        for d in search_dirs:
            if d.is_dir():
                try:
                    handle = os.add_dll_directory(str(d))
                    _DLL_HANDLES.append(handle)
                except (OSError, ValueError):
                    pass

    # Pre-load FriBiDi DLL so that _imagingft's internal LoadLibrary("fribidi") succeeds
    if os.name == "nt" and hasattr(ctypes, "WinDLL"):
        fribidi_names = ("libfribidi-0.dll", "fribidi.dll", "fribidi-0.dll")
        loaded = False
        for d in search_dirs:
            if not d.is_dir():
                continue
            for name in fribidi_names:
                dll_path = d / name
                if dll_path.is_file():
                    try:
                        handle = ctypes.WinDLL(str(dll_path))
                        _DLL_HANDLES.append(handle)
                        loaded = True
                        break
                    except OSError:
                        pass
            if loaded:
                break

    return True


bootstrap_indic_runtime()
