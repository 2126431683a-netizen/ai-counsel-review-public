"""Optional per-user data location for the Windows distribution."""

import os
from pathlib import Path

DATA_ROOT = Path(os.getenv("AI_COUNSEL_DATA_DIR") or Path(__file__).parent.parent / "data")
