"""
qEEG Pipeline — setup and verification script.

Run this once after cloning the repo. It checks prerequisites, installs
Python and Node dependencies, builds the frontend, and verifies the server
starts correctly.

Usage:
    python install.py

No external packages required — uses Python stdlib only.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

OK   = "[OK]  "
FAIL = "[FAIL]"
INFO = "[    ] "
SKIP = "[SKIP]"

PYTHON_MIN = (3, 11)
NODE_MIN   = (18, 0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], cwd: Path | None = None, capture: bool = True) -> tuple[int, str]:
    result = subprocess.run(
        cmd, cwd=str(cwd or PROJECT_ROOT),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
    )
    return result.returncode, result.stdout.strip()


def _version_tuple(text: str) -> tuple[int, ...]:
    """Extract first version-like token from a string, e.g. 'v18.3.0' → (18, 3, 0)."""
    import re
    m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return (0,)
    return tuple(int(x) for x in m.groups() if x is not None)


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) != 0


def _wait_for_server(url: str, timeout: int = 30) -> bool:
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


# ---------------------------------------------------------------------------
# Check steps
# ---------------------------------------------------------------------------

def check_python() -> bool:
    v = sys.version_info[:2]
    if v >= PYTHON_MIN:
        print(f"{OK} Python {sys.version.split()[0]} (>= {'.'.join(map(str, PYTHON_MIN))} required)")
        return True
    print(f"{FAIL} Python {sys.version.split()[0]} is too old — need {'.'.join(map(str, PYTHON_MIN))}+")
    print(f"       Download from https://www.python.org/downloads/")
    return False


def check_node() -> bool:
    node = shutil.which("node")
    if not node:
        print(f"{FAIL} Node.js not found — install from https://nodejs.org/ (v{NODE_MIN[0]}+)")
        return False
    code, out = _run(["node", "--version"])
    v = _version_tuple(out)
    if v >= NODE_MIN:
        print(f"{OK} Node.js {out.lstrip('v')} (>= {NODE_MIN[0]} required)")
        return True
    print(f"{FAIL} Node.js {out} is too old — need v{NODE_MIN[0]}+")
    print(f"       Download from https://nodejs.org/")
    return False


def check_npm() -> bool:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print(f"{FAIL} npm not found — it should be bundled with Node.js")
        return False
    code, out = _run(["npm", "--version"] if sys.platform != "win32" else ["npm.cmd", "--version"])
    print(f"{OK} npm {out}")
    return True


def install_python_deps() -> bool:
    print(f"\n{INFO}Installing Python dependencies (pip install -e .) ...")
    code, out = _run([sys.executable, "-m", "pip", "install", "-e", "."])
    if code == 0:
        print(f"{OK} Python dependencies installed")
        return True
    print(f"{FAIL} pip install failed:\n{out}")
    return False


def install_node_deps() -> bool:
    if not (FRONTEND_DIR / "node_modules").exists():
        print(f"\n{INFO}Installing Node dependencies (npm install) ...")
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        code, out = _run([npm, "install"], cwd=FRONTEND_DIR)
        if code != 0:
            print(f"{FAIL} npm install failed:\n{out}")
            return False
        print(f"{OK} Node dependencies installed")
    else:
        print(f"{SKIP} node_modules already present — skipping npm install")
    return True


def build_frontend() -> bool:
    print(f"\n{INFO}Building frontend (npm run build) ...")
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    code, out = _run([npm, "run", "build"], cwd=FRONTEND_DIR)
    if code != 0:
        print(f"{FAIL} vite build failed:\n{out}")
        return False
    # Verify expected output exists
    if not (FRONTEND_DIST / "index.html").exists():
        print(f"{FAIL} Build finished but frontend/dist/index.html not found")
        return False
    size_kb = sum(f.stat().st_size for f in FRONTEND_DIST.rglob("*") if f.is_file()) // 1024
    print(f"{OK} Frontend built ({size_kb} KB in frontend/dist/)")
    return True


def verify_server() -> bool:
    port = 18432  # unlikely to be in use; avoid clashing with dev port
    print(f"\n{INFO}Starting server on port {port} for verification ...")

    if not _port_free(port):
        print(f"{SKIP} Port {port} in use — skipping server verification")
        return True  # non-fatal; deps and build already confirmed

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    health_url = f"http://127.0.0.1:{port}/api/health"
    index_url  = f"http://127.0.0.1:{port}/"

    try:
        if not _wait_for_server(health_url, timeout=20):
            print(f"{FAIL} Server did not respond at {health_url} within 20s")
            return False

        print(f"{OK} /api/health responded 200")

        # Check static mount serves the React app
        try:
            with urllib.request.urlopen(index_url, timeout=5) as resp:
                body = resp.read(256).decode("utf-8", errors="replace")
                if "<!doctype html>" in body.lower() or "<html" in body.lower():
                    print(f"{OK} / served index.html (React app)")
                else:
                    print(f"{FAIL} / responded but body doesn't look like HTML")
                    return False
        except Exception as e:
            print(f"{FAIL} Could not fetch /: {e}")
            return False

        return True

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print(" qEEG Pipeline — Installation and Verification")
    print("=" * 60)
    print()

    # --- Prerequisites ---
    print("Checking prerequisites...")
    prereqs_ok = all([
        check_python(),
        check_node(),
        check_npm(),
    ])

    if not prereqs_ok:
        print()
        print("Fix the issues above, then re-run:  python install.py")
        sys.exit(1)

    # --- Install ---
    steps_ok = all([
        install_python_deps(),
        install_node_deps(),
        build_frontend(),
    ])

    if not steps_ok:
        print()
        print("Installation failed. See errors above.")
        sys.exit(1)

    # --- Verify ---
    server_ok = verify_server()

    # --- Summary ---
    print()
    print("=" * 60)
    if server_ok:
        print(" Installation complete and verified.")
        print()
        print(" To start the app:")
        print("   python start.py")
        print()
        print(" The browser will open automatically.")
        print("=" * 60)
    else:
        print(" Dependencies installed but server verification failed.")
        print(" Try running:  python start.py")
        print(" and check for errors in the terminal.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
