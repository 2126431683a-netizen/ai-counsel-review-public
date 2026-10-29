"""Windows desktop backend entry point, also runnable from the source checkout."""

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3340)
    parser.add_argument("--data-dir")
    args = parser.parse_args()
    data = Path(args.data_dir or Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "AICounselReview")
    data.mkdir(parents=True, exist_ok=True)
    os.environ["AI_COUNSEL_DATA_DIR"] = str(data.resolve())
    os.environ["AI_COUNSEL_REVIEW_ONLY"] = "1"
    os.environ["PORT_BACKEND"] = str(args.port)
    os.environ["LLM_COUNCIL_BIND_HOST"] = "127.0.0.1"
    os.environ["PYTHONUTF8"] = "1"
    os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,::1")
    os.environ.setdefault("CUSTOM_REQUEST_TIMEOUT", "300")
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(root))
    os.environ["FRONTEND_DIST_DIR"] = str(root / "frontend" / "dist")
    os.chdir(data)
    log = open(data / "server.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    from desktop.seed import seed_profile
    seed_profile(data)
    import uvicorn
    from backend.main import app
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
