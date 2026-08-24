"""Build a clean, self-contained release tree from this repo.

What ships is the pipeline, its tests, its documentation, and the one MMX
template it reads. What does not ship is anything that would let a reader
reconstruct a superseded state of the project, plus the bulky derived
artifacts a clone can regenerate:

  * `_archive/`, `docs/_archive/`  superseded templates, crosswalks
  * `docs/_project/`               dated plans, audits, handoffs
  * `test_data/stress_test/`       ~600 MB of synthetic CSVs; the generator
                                   ships instead (`tests/generate_stress_data.py`)
  * `frontend/dist`, `node_modules`, caches, `output/`, `tmp/`

Usage:
    python scripts/build_release.py [dest]

Refuses to write into a non-empty directory unless --force is given, and
never writes inside the source tree.
"""
from __future__ import annotations

import argparse
import re
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Top-level entries to copy. Anything not listed does not ship.
INCLUDE = [
    "qeeg", "api", "scripts", "tests", "docs", "Ref Files",
    "README.md", "HANDOFF.md", "pyproject.toml", "requirements.txt",
    "install.py", "start.py",
]

# The release gets its own .gitignore. The development one encodes dev-repo
# policy that is actively wrong here: it blanket-ignores `test_data/`, which
# would drop the two alignment fixtures the suite reads, and `HANDOFF.md`,
# which is this tree's entry document.
RELEASE_GITIGNORE = """__pycache__/
*.pyc
*.egg-info/
.venv/
build/
dist/

# Runtime and cache
output/
tmp/
.qeeg_cache/
.pytest_cache/

# Patient-derived data must never be committed. The synthetic stress cohort is
# generated locally by tests/generate_stress_data.py; the two alignment
# fixtures beside it are small, synthetic and intentionally tracked.
.uploads/
.exports/
test_data/stress_test/

# Frontend build output — shadows the API routes if present during dev
frontend/dist/
frontend/node_modules/

# Editors
.vscode/
.idea/
*.swp
"""

# Directory names pruned wherever they appear.
PRUNE_DIRS = {
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "node_modules", "dist", ".git", ".claude", ".qeeg_cache",
    "_archive", "_project", "stress_test", ".vite",
}

PRUNE_SUFFIXES = {".pyc", ".pyo", ".log", ".tmp"}

# Individual files that do not ship. The frozen 2026-05-15 format reference is
# a dated V7-era artifact -- real provenance for the dev repo, but shipping it
# would put a superseded template's prose in the release.
PRUNE_FILES = {"PersystTrendCSV_Format_Reference_ORIGINAL_2026-05-15.md"}

# Frontend ships as source plus its build config -- not as a built bundle.
FRONTEND_INCLUDE = [
    "src", "public", "index.html", "package.json", "package-lock.json",
    "tsconfig.json", "tsconfig.node.json", "vite.config.ts",
    "vitest.config.ts", "tailwind.config.js", "postcss.config.js",
    "eslint.config.js", ".gitignore",
]

MMX = Path("Ref Files") / "PedQuEST_Pennsieve_V10_research.mmx"


def _ignore(_dir: str, names: list[str]) -> set[str]:
    drop = {n for n in names if n in PRUNE_DIRS or n in PRUNE_FILES}
    drop |= {n for n in names if Path(n).suffix in PRUNE_SUFFIXES}
    return drop


def copy_tree(src: Path, dst: Path) -> None:
    if src.is_dir():
        shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def build(dest: Path, force: bool) -> int:
    dest = dest.resolve()
    if ROOT in dest.parents or dest == ROOT:
        sys.exit(f"refusing to build inside the source tree: {dest}")
    if dest.exists() and any(dest.iterdir()) and not force:
        sys.exit(f"{dest} exists and is not empty; pass --force to overwrite")

    dest.mkdir(parents=True, exist_ok=True)

    for name in INCLUDE:
        src = ROOT / name
        if not src.exists():
            print(f"  skip (absent): {name}")
            continue
        copy_tree(src, dest / name)
        print(f"  copied: {name}")

    for name in FRONTEND_INCLUDE:
        src = ROOT / "frontend" / name
        if src.exists():
            copy_tree(src, dest / "frontend" / name)
    print("  copied: frontend (source only)")

    # test_data keeps the small alignment fixtures; the 600 MB stress CSVs do
    # not ship (PRUNE_DIRS drops stress_test), so leave a pointer to the
    # generator rather than an unexplained gap.
    for name in ("clinical_data.csv", "eeg_date_correction.csv"):
        src = ROOT / "test_data" / name
        if src.exists():
            copy_tree(src, dest / "test_data" / name)
    (dest / "test_data" / "README.md").write_text(
        "# test_data\n\n"
        "`clinical_data.csv` and `eeg_date_correction.csv` are the small alignment\n"
        "fixtures the suite reads directly.\n\n"
        "The stress-test cohort (5 synthetic patients x 48 h, ~600 MB) is **not**\n"
        "shipped. Generate it locally:\n\n"
        "```bash\n"
        "python tests/generate_stress_data.py\n"
        "```\n\n"
        "It writes to `test_data/stress_test/`. Everything in it is synthetic --\n"
        "no patient data is distributed with this release.\n",
        encoding="utf-8")
    print("  copied: test_data (fixtures + generator pointer)")

    (dest / ".gitignore").write_text(RELEASE_GITIGNORE, encoding="utf-8")
    print("  wrote: .gitignore (release policy, not the dev one)")

    # Refuse to ship patient identifiers. This is the gate rather than a repo
    # sweep because the sweep works off `git ls-files`, and HANDOFF.md -- which
    # names recordings freely -- is gitignored in the development repo, so a
    # tracked-file scan cannot see it. The published tree is what matters, so
    # the published tree is what gets checked.
    id_patterns = [
        re.compile(r"\b4290[-_]\d+"),            # study subject IDs
        re.compile(r"POCCA_429\d"),           # study-prefixed form
        re.compile(r"cardiac_arrest"),           # the data share
        # A path into the data share specifically. `Users` is deliberately
        # absent: it matches every generic Windows dev path.
        re.compile(r"[A-Za-z]:[\\\\/][^\\\\/]*[\\\\/]?cardiac_arrest", re.I),
    ]
    text_suffixes = {".py", ".md", ".json", ".csv", ".html", ".ts", ".tsx",
                     ".txt", ".yml", ".yaml", ".toml", ".cfg"}
    offenders: list[str] = []
    for f in dest.rglob("*"):
        if not f.is_file() or f.suffix.lower() not in text_suffixes:
            continue
        if f.name in ("test_column_map_artifacts.py", "build_release.py"):
            continue          # these carry the patterns by definition
        try:
            body = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pat in id_patterns:
            m = pat.search(body)
            if m:
                offenders.append(f"{f.relative_to(dest).as_posix()}: {m.group(0)!r}")
                break
    if offenders:
        print()
        print("REFUSING TO SHIP - patient identifiers in the release tree:")
        for o in offenders[:15]:
            print(f"  {o}")
        if len(offenders) > 15:
            print(f"  ... and {len(offenders) - 15} more")
        sys.exit(1)
    print("  checked: no patient identifiers in the tree")

    # Fingerprint the shipped template so a swap is detectable.
    mmx = dest / MMX
    if not mmx.exists():
        sys.exit(f"shipped template missing from the release: {MMX}")
    digest = hashlib.sha256(mmx.read_bytes()).hexdigest()
    (dest / "MMX_SHA256").write_text(f"{digest}  {MMX.as_posix()}\n", encoding="utf-8")

    others = [p.name for p in (dest / "Ref Files").glob("*.mmx") if p.name != MMX.name]
    if others:
        sys.exit(f"release ships more than one template: {others}")

    n_files = sum(1 for p in dest.rglob("*") if p.is_file())
    size_mb = sum(p.stat().st_size for p in dest.rglob("*") if p.is_file()) / 1e6
    print(f"\n{dest}")
    print(f"  {n_files} files, {size_mb:.0f} MB")
    print(f"  template sha256 {digest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dest", nargs="?",
                    default=str(ROOT.parent / "qeeg-pipeline-release-v4.0.0"))
    ap.add_argument("--force", action="store_true",
                    help="overwrite a non-empty destination")
    args = ap.parse_args()
    return build(Path(args.dest), args.force)


if __name__ == "__main__":
    raise SystemExit(main())
