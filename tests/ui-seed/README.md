# tests/ui-seed: the raw VM test suites of the touch UI

These are the off-phone test suites the v1 touch UI was built with, imported as they were. They ran in a Debian
trixie VM against `linux/debian/overlay`. They are a seed, not a finished test tree: issue `ui-testing-01` moves them
to `tests/ui/`, makes the paths repo-relative and adds one runner.

What to know before you run anything:

- Absolute paths were replaced on import: `/path/to/repo` is this checkout, `/path/to/scratch` was the build
  session's working folder, `/path/to/home` a home directory. Nothing runs until those are fixed (that is the issue).
- Stale `.pyc` files gave wrong results during the build. Run with `PYTHONDONTWRITEBYTECODE=1` and no `__pycache__`.
- No test here may be pointed at a phone. The sway and uinput tests start their own throwaway headless session.

| Folder | What it tests |
|---|---|
| `tests/` | Textual pilot tests for the Home and Network screens, with a fake sysroot (`conftest.py`) |
| `status-tests/` | `vegas-status` (the strip feed and the text report, `test_hole.py` for the camera-hole band, which compares against `vegas-status.pre-r6`, the strip feed as it was before that band); `vm/` holds the headless-sway harness |
| `keys-test/` | `vegas-keys` through uinput; `bin/` holds stub programs it calls |
| `session-tests/` | Away mode, hotspot, power menu, keyboard and Firefox preference checks |
| `strip-test/` | strip layout rendering |
| `glyph-measure/` | one-off tools that measured the strip's glyph widths in headless sway (`blocks.json` is their generated input); `r6b.sh` is `status-tests/vm/r6.sh` with two more knobs (`VSENV`, `WAIT`) |
| `glue-live/`, `test-glue.sh` | the session glue (terminal loop, tmux) |
| `integ-smoke.sh` | the full headless sway smoke test |
