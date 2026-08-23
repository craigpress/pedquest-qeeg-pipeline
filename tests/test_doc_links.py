"""Anti-drift: every relative Markdown link in the canonical docs must resolve.

This guards the class of bug where a doc points at a renamed or removed file
(e.g. a README still linking a reference doc that was renamed). Scope is
the *canonical* docs only — README + docs/*.md excluding _archive/ (frozen history)
and _project/ (dated, non-canonical work files per INDEX.md sec 3). External
(http/mailto), in-page anchors, in-code-fence examples, and links that resolve
outside the repo (external provenance, e.g. the OneDrive CSV reference) are ignored.
"""
import re
from pathlib import Path
from urllib.parse import unquote

import pytest

_REPO = Path(__file__).resolve().parent.parent
_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


_NONCANONICAL = {"_archive", "_project"}


def _canonical_md_files() -> list[Path]:
    files = [_REPO / "README.md"]
    for p in sorted((_REPO / "docs").rglob("*.md")):
        if _NONCANONICAL & set(p.parts):
            continue
        files.append(p)
    return [f for f in files if f.exists()]


def _relative_links(md: Path) -> list[str]:
    """Return relative link targets (anchors/externals stripped/skipped)."""
    out = []
    in_fence = False
    for line in md.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in _LINK.finditer(line):
            url = m.group(1).strip()
            # strip an optional "title" suffix: (path "title")
            url = url.split()[0] if url else url
            if not url or url.startswith(("http://", "https://", "mailto:", "#")):
                continue
            url = url.split("#", 1)[0]  # drop in-page anchor
            if url:
                out.append(url)
    return out


def test_canonical_docs_have_no_broken_relative_links():
    broken = []
    repo = _REPO.resolve()
    for md in _canonical_md_files():
        for url in _relative_links(md):
            # Percent-encoding is valid in a Markdown target -- a path with a
            # space is written `Ref%20Files/...` and resolves in any renderer.
            target = (md.parent / unquote(url)).resolve()
            # External provenance lives outside the repo (e.g. OneDrive) — unverifiable.
            if repo not in target.parents and target != repo:
                continue
            if not target.exists():
                broken.append(f"{md.relative_to(_REPO)} -> {url}")
    assert not broken, "Broken relative Markdown links:\n  " + "\n  ".join(broken)
