"""Root pytest configuration to bootstrap Indic runtime and FriBiDi before any tests import PIL."""
import sys
from pathlib import Path

# Ensure repo root is in sys.path
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

import indic_bootstrap
