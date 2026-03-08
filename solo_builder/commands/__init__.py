"""Solo Builder commands package."""
import sys as _sys
import os as _os
_SOLO = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _SOLO not in _sys.path:
    _sys.path.insert(0, _SOLO)
