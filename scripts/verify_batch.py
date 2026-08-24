"""Run verify_full_panel.py over every full-panel export under a directory.

Each export runs in its own subprocess, so a file that exhausts memory or trips
a parser bug records a failure and the batch continues. Writes a JSON summary
plus the full stdout of every run.

Usage:
    python scripts/verify_batch.py [dir] [--out DIR] [--min-cols N] [--skip-verified]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import export_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCAN = None   # resolved from QEEG_EXPORT_DIR; see scripts/_paths.py


def panel_width(csv_path: Path) -> int:
    with csv_path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i > 120:
                return 0
            if line.startswith("ClockDateTime,"):
                return len(line.split(","))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scan", nargs="?", default=None)
    ap.add_argument("--out", default=str(ROOT / "output" / "verify_batch"))
    ap.add_argument("--min-cols", type=int, default=400)
    ap.add_argument("--glob", default="2026*.csv")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    root = Path(args.scan) if args.scan else export_dir()

    targets = []
    for f in sorted(root.rglob(args.glob)):
        w = panel_width(f)
        if w >= args.min_cols:
            targets.append((f, w))

    print(f"{len(targets)} full-panel export(s) to verify "
          f"({sum(f.stat().st_size for f, _ in targets) / 1e9:.1f} GB)\n", flush=True)

    results = []
    for n, (f, width) in enumerate(targets, 1):
        tag = f"{f.parent.name}__{f.stem}"
        mb = f.stat().st_size / 1e6
        print(f"[{n}/{len(targets)}] {f.parent.name}/{f.name}  "
              f"{width} cols  {mb:.0f} MB", flush=True)
        t0 = time.time()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_full_panel.py"), str(f)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        dt = time.time() - t0
        log = out / f"{tag}.txt"
        log.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")

        text = proc.stdout or ""
        passed = text.count("[PASS]")
        failed = text.count("[FAIL]")
        skipped = text.count("[SKIP]")
        if proc.returncode == 0 and failed == 0 and passed:
            status = "PASS"
        elif proc.returncode != 0 and not passed:
            status = "ERROR"
        else:
            status = "FAIL"

        # First line of a traceback, if the run died.
        err = ""
        if status == "ERROR":
            lines = [l for l in (proc.stderr or "").strip().splitlines() if l.strip()]
            err = lines[-1][:160] if lines else f"exit {proc.returncode}"

        results.append({
            "patient": f.parent.name, "file": f.name, "cols": width,
            "size_mb": round(mb), "status": status, "passed": passed,
            "failed": failed, "skipped": skipped, "seconds": round(dt, 1),
            "error": err, "log": str(log),
        })
        print(f"        -> {status}  ({passed} pass, {failed} fail, "
              f"{skipped} skip, {dt:.0f}s)" + (f"  {err}" if err else ""), flush=True)

    (out / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    print(f"{'patient':22s} {'file':22s} {'cols':>5s} {'MB':>6s} {'status':7s} {'P/F/S':>10s}")
    print("-" * 78)
    for r in results:
        print(f"{r['patient']:22s} {r['file']:22s} {r['cols']:5d} {r['size_mb']:6d} "
              f"{r['status']:7s} {r['passed']:3d}/{r['failed']}/{r['skipped']:<4d}")
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    print("-" * 78)
    print(f"{n_pass}/{len(results)} passed")
    for r in results:
        if r["status"] != "PASS":
            print(f"  {r['status']}: {r['patient']}/{r['file']}"
                  + (f" — {r['error']}" if r["error"] else ""))
    print(f"\nlogs + summary.json in {out}")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
