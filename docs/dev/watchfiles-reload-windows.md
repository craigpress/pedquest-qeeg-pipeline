---
tags:
  - domain/eeg-monitoring
  - project/qeeg-pipeline
  - domain/research-methods
  - type/reference
---

# Windows dev-server reload is unreliable

Status: open upstream, no clean fix. Workarounds documented below.

## Symptom

`python start.py --dev` launches uvicorn with `--reload`. Editing any file
under `api/` or `qeeg/` causes watchfiles to log

```
WARNING:  WatchFiles detected changes in 'api\main.py'. Reloading...
```

but the worker process PID does **not** change and the API keeps serving the
old code. The only recovery seen in the wild is to Stop-Process the worker by
hand (which start.py then respawns on its own).

Confirmed on this machine 2026-04-23:

- Python 3.13, Windows 11
- uvicorn 0.44.0
- watchfiles 1.1.1
- Local NTFS (C: drive, DriveType=3 — not a network share)

## Reproduction

1. `python start.py --dev`
2. Note the worker PID:
   ```powershell
   Get-CimInstance Win32_Process |
     Where-Object { $_.CommandLine -match 'multiprocessing-fork' } |
     Select-Object ProcessId,ParentProcessId,CreationDate
   ```
3. Touch `api/main.py` (add/remove a comment).
4. Wait 10–60 s. Re-run the PID query. PID is unchanged.

## Root cause (upstream)

The uvicorn supervisor restarts the worker by sending `signal.CTRL_C_EVENT`
via `os.kill(pid, ...)`. On Windows that event is only delivered when the
controlling console is "updated." If uvicorn's stdout is not attached to a
foreground console (headless launch, stdout redirected to a pipe/file, some
IDE integrated terminals), the event is queued but never delivered — so the
worker is told to stop, watchfiles logs "Reloading…", but the worker keeps
running.

Upstream PR [#2604](https://github.com/Kludex/uvicorn/pull/2604) (merged
2025-04-14, shipped in 0.44.0) added

```python
os.kill(self.process.pid, signal.CTRL_C_EVENT)
sys.stdout.write(" ")
sys.stdout.flush()
```

as a workaround: writing to stdout pokes the console enough to deliver the
event. This helps interactive terminals (Windows Terminal, VS Code integrated
terminal) but the PR author explicitly notes it still fails "running
headlessly" in CI — i.e., when stdout is not a real console. That matches our
case when `start.py` is launched in the background, or when an agent (Claude
Code, Codex) spawns it via `subprocess.Popen` without inheriting a console.

See also upstream discussion threads:

- <https://github.com/Kludex/uvicorn/issues/2000>
  (root cause: "Windows not passing on the Ctrl+C event until the console is
  updated in some way … stuck at 'Reloading…' until you go and click the
  terminal window")
- <https://github.com/Kludex/uvicorn/discussions/1977>
- <https://github.com/Kludex/uvicorn/discussions/1973>

## Alternatives tested on this machine (all failed)

| Attempt | Result |
|---|---|
| `--reload-dir api --reload-dir qeeg` (restrict watch scope) | Still stuck at "detected changes" |
| `--reload-delay 1` | Still stuck |
| `WATCHFILES_FORCE_POLLING=true` env var | Still stuck |
| Force StatReload (block `watchfiles` import) | StatReload logs "detected changes" — still stuck |

The watch layer (watchfiles vs StatReload) does not matter; the bug is in
uvicorn's restart mechanism, not its file watcher.

`--reload-impl` is not a recognised flag on current uvicorn and cannot be used.

## Recommended workarounds

For interactive development, in order of preference:

1. **Launch `start.py` from a foreground terminal** (Windows Terminal, a
   Git Bash / PowerShell window you can see). PR 2604's stdout-flush workaround
   only fires when there is a real console behind uvicorn's stdout.
2. **If reload stalls, click the terminal window** to bring it to the
   foreground — that single UI event flushes the queued `CTRL_C_EVENT` and the
   reload completes.
3. **Force-restart manually** when reload hangs:
   ```powershell
   # Find the worker (child of the uvicorn reloader)
   Get-CimInstance Win32_Process |
     Where-Object { $_.CommandLine -match 'multiprocessing-fork' } |
     Select-Object ProcessId,ParentProcessId
   # Stop just the worker; the reloader will respawn it
   Stop-Process -Id <worker-pid> -Force
   ```
   The `dev-server` skill can do this cleanly — prefer it over manual kills.
4. **Do not launch `start.py --dev` from an agent background job** if you
   expect reloads. Agents redirect stdout and the workaround becomes inert.
   Start it yourself in a visible terminal.

## Why `start.py` is not being changed

Options considered:

- `subprocess.CREATE_NEW_CONSOLE` on Windows — pops up a second window; bad UX
  for a developer running `start.py` from their own terminal.
- Custom reloader (poll + `process.terminate()`) — reimplements uvicorn
  internals and risks diverging on every uvicorn upgrade.
- Switching reload implementation — both watchfiles and StatReload exhibit the
  same symptom, so this is not a real option.

None of those is a clear win for our use case, and all three would add code
to maintain for a bug that is fundamentally upstream. The simplest reliable
knob is "run `start.py` in a visible terminal." This doc exists so the next
person who hits the bug does not rediscover all of the above.
