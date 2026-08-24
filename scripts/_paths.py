"""Where the real exports live — resolved at runtime, never hardcoded.

These dev scripts read Persyst exports from a research share whose directory
names are patient identifiers. Baking that path into the repo puts an
identifier in source control, so the location comes from the environment:

    set QEEG_EXPORT_DIR=C:\\path\\to\\exports      (Windows)
    export QEEG_EXPORT_DIR=/path/to/exports        (POSIX)

Nothing in the pipeline itself needs this — only the audit, diagnostic and
map-generation scripts that run against real recordings.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "QEEG_EXPORT_DIR"


def export_dir(required: bool = True) -> Path | None:
    """Return the configured export root.

    With ``required`` (the default) an unset variable is a clean exit with an
    instruction rather than a traceback or, worse, a silent skip.
    """
    raw = os.environ.get(ENV_VAR, "").strip().strip('"')
    if not raw:
        if not required:
            return None
        raise SystemExit(
            f"{ENV_VAR} is not set.\n"
            f"  This script reads real Persyst exports. Point it at the directory\n"
            f"  holding them, e.g.\n"
            f"      set {ENV_VAR}=C:\\path\\to\\exports\n"
            f"  The path is deliberately not stored in the repository: export\n"
            f"  directory names are patient identifiers."
        )
    return Path(raw)


def recording_dir(name: str, required: bool = True) -> Path | None:
    """Return ``<export root>/<name>`` for one recording directory."""
    root = export_dir(required=required)
    return None if root is None else root / name
