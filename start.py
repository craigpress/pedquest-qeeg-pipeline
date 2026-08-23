"""
qEEG Pipeline launcher.

Usage:
    python start.py            # production mode (serves built frontend)
    python start.py --dev      # dev mode (Vite dev server + API with hot-reload)
    python start.py --port 9000

Production mode requires a built frontend (frontend/dist/).
If dist/ is missing, it will be built automatically (requires Node + npm).

IMPORTANT for developers: delete frontend/dist/ before running in dev mode.
The FastAPI static mount is a catch-all — if dist/ exists it will shadow the
Vite proxy and you will NOT see live-reload updates.
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _npm() -> str:
    return "npm.cmd" if sys.platform == "win32" else "npm"


def _port_free(port: int) -> bool:
    """Return True if *port* is not in use on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _lan_ip() -> str:
    """Best-effort local LAN IP (not loopback)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "?.?.?.?"


def _wait_for_server(url: str, timeout: int = 30) -> bool:
    """Poll *url* until it returns HTTP 200 or *timeout* seconds elapse."""
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def _check_deps() -> None:
    """Verify required packages are importable and print versions."""
    missing = []
    for pkg in ("fastapi", "uvicorn", "pandas", "numpy", "pyarrow", "pydantic"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[qEEG] ERROR: missing packages: {', '.join(missing)}")
        print("       Run:  pip install -e .")
        sys.exit(1)

    import pandas as pd
    import numpy as np
    import fastapi
    print(f"[qEEG] Python {sys.version.split()[0]} | "
          f"pandas {pd.__version__} | numpy {np.__version__} | fastapi {fastapi.__version__}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    mode = "dev" if "--dev" in sys.argv else "prod"

    # Parse --port N
    port = int(os.environ.get("PORT", "8000"))
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    # Dependency health check
    _check_deps()

    # Port availability check
    if not _port_free(port):
        print(f"[qEEG] ERROR: port {port} is already in use.")
        print(f"       Use a different port:  python start.py --port {port + 1}")
        sys.exit(1)

    procs: list[subprocess.Popen] = []

    def _shutdown(signum=None, frame=None) -> None:
        print("\n[qEEG] Shutting down...")
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _shutdown)

    # ------------------------------------------------------------------
    # Production mode
    # ------------------------------------------------------------------
    if mode == "prod":
        if not FRONTEND_DIST.exists():
            print("[qEEG] frontend/dist/ not found — building frontend...")
            result = subprocess.run(
                [_npm(), "run", "build"],
                cwd=str(FRONTEND_DIR),
            )
            if result.returncode != 0:
                print("[qEEG] ERROR: vite build failed. Check Node/npm are installed.")
                sys.exit(1)
            print("[qEEG] Frontend build complete.")

        lan = _lan_ip()
        print(f"[qEEG] Starting production server on port {port}...")
        api_proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "api.main:app",
                "--host", "127.0.0.1",  # P0-5: localhost-only default (no auth + patient data). Front with an authenticated reverse proxy for LAN/remote access.
                "--port", str(port),
            ],
            cwd=str(PROJECT_ROOT),
        )
        procs.append(api_proc)

        health_url = f"http://127.0.0.1:{port}/api/health"
        app_url = f"http://localhost:{port}"
        print(f"[qEEG] Waiting for server at {health_url}...")
        if _wait_for_server(health_url, timeout=30):
            print(f"[qEEG] Ready — opening {app_url}")
            webbrowser.open(app_url)
        else:
            print(f"[qEEG] Server did not respond in 30s. Open manually: {app_url}")

        print(f"\n  Local:  http://localhost:{port}")
        print(f"  LAN:    http://{lan}:{port}")
        print(f"\n  Press Ctrl+C to stop.\n")

    # ------------------------------------------------------------------
    # Dev mode
    # ------------------------------------------------------------------
    else:
        if FRONTEND_DIST.exists():
            print("[qEEG] WARNING: frontend/dist/ exists in dev mode.")
            print("       The FastAPI static mount will shadow Vite proxy.")
            print("       Delete frontend/dist/ before developing:")
            print("         rm -rf frontend/dist/")
            print()

        vite_port = 3000

        lan = _lan_ip()
        print(f"[qEEG] Starting FastAPI on port {port} (hot-reload)...")
        api_proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "api.main:app",
                "--host", "127.0.0.1",  # P0-5: localhost-only default (no auth + patient data). Front with an authenticated reverse proxy for LAN/remote access.
                "--port", str(port),
                "--reload",
            ],
            cwd=str(PROJECT_ROOT),
        )
        procs.append(api_proc)

        print(f"[qEEG] Starting Vite dev server on port {vite_port}...")
        vite_env = {**os.environ, "API_PORT": str(port)}
        vite_proc = subprocess.Popen(
            [_npm(), "run", "dev"],
            cwd=str(FRONTEND_DIR),
            env=vite_env,
        )
        procs.append(vite_proc)

        health_url = f"http://127.0.0.1:{vite_port}"
        app_url = f"http://localhost:{vite_port}"
        print(f"[qEEG] Waiting for Vite at {health_url}...")
        if _wait_for_server(health_url, timeout=30):
            print(f"[qEEG] Ready — opening {app_url}")
            webbrowser.open(app_url)
        else:
            print(f"[qEEG] Vite did not respond in 30s. Open manually: {app_url}")

        print(f"\n  Local:    http://localhost:{vite_port}")
        print(f"  LAN:      http://{lan}:{vite_port}")
        print(f"  API:      http://localhost:{port}/api/health")
        print(f"  API docs: http://localhost:{port}/docs")
        print("\n  Press Ctrl+C to stop.\n")

    # Keep main thread alive
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        _shutdown()


if __name__ == "__main__":
    main()
