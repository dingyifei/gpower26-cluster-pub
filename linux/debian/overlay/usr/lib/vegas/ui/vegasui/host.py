"""Paths and commands for the Vegas UI, both replaceable for tests.

P("/sys/...") prefixes every sysfs/proc/etc/run path with $VEGAS_SYSROOT (default empty), so the readers run in the
trixie VM against a fake tree (as chargeguard does with VEGAS_BAT). Runner runs external commands; the apps take a
runner argument so tests pass a fake one that answers from canned outputs. No command here ever touches sway's life
(D10): the UI only runs swaymsg for exec/workspace/kill-of-a-client, never exit/reload.
"""
import os
import shutil
import subprocess
from dataclasses import dataclass


def P(path: str) -> str:
    return os.environ.get("VEGAS_SYSROOT", "") + path


def read(path: str, default=None):
    """First line of a file (stripped), or default if missing/unreadable."""
    try:
        with open(P(path), encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


def read_int(path: str, default=None):
    v = read(path)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def exists(path: str) -> bool:
    return os.path.exists(P(path))


def write_atomic(path: str, text: str, mode: int = 0o600) -> None:
    """Write via temp file + rename (never a half-written file for a reader)."""
    real = P(path)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    tmp = real + ".new"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, real)


@dataclass
class Result:
    rc: int
    out: str = ""
    err: str = ""

    @property
    def ok(self) -> bool:
        return self.rc == 0

    @property
    def last(self) -> str:
        """Last non-empty output line (wpa_cli answers OK/FAIL/<id> there)."""
        lines = [l for l in self.out.splitlines() if l.strip()]
        return lines[-1].strip() if lines else ""


class Runner:
    """Runs commands for real. Tests replace it (see FakeRunner in the tests)."""

    def run(self, argv, timeout: float = 10, input: str | None = None) -> Result:
        try:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, input=input,
                               stdin=None if input is not None else subprocess.DEVNULL)
            return Result(p.returncode, p.stdout, p.stderr)
        except FileNotFoundError:
            return Result(127, "", f"{argv[0]}: not installed")
        except subprocess.TimeoutExpired:
            return Result(124, "", f"{argv[0]}: timed out after {timeout:.0f} s")

    def which(self, name: str) -> bool:
        return shutil.which(name) is not None

    def sleep(self, seconds: float) -> None:
        import time
        time.sleep(seconds)
