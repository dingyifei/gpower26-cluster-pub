"""Away PIN: hash, check, lockout (D17, Q29 own touch pad). Used by vegas-keys (pad), vegas-home and vegas-away.

PIN = 4..6 digits, stored as pbkdf2_sha256$<iter>$<salt>$<hash hex> in /etc/vegas/away-pin (root 0600); the salt is
32 hex characters used as UTF-8 text (as vegas-keys' check_pin reads it).
Lockout: after 5 wrong tries, 30 s, doubling with each further wrong try, capped at 1 h [BUILDER CHOICE on the cap];
the counter lives in /var/lib/vegas/away-fails ("fails=<n> until=<epoch>") so a reboot does not reset it.
CLI (vegas-away uses it): python3 -m vegasui.pin set|check|status   (PIN on stdin, one line; set takes it twice)
Exit codes of check: 0 right, 1 wrong, 3 locked (prints the seconds left), 4 no PIN set.
"""
import hashlib
import hmac
import os
import re
import sys
import time


def P(path):   # $VEGAS_SYSROOT prefix for tests (kept local: this module must not depend on the rest of vegasui)
    return os.environ.get("VEGAS_SYSROOT", "") + path


PIN_FILE = "/etc/vegas/away-pin"
FAILS_FILE = "/var/lib/vegas/away-fails"
ITER = 100_000          # ~0.2 s on the phone's big cores [BUILDER CHOICE]
FREE_TRIES, LOCK0, LOCK_MAX = 5, 30, 3600


def valid(pin: str) -> bool:
    return bool(re.fullmatch(r"[0-9]{4,6}", pin or ""))


def _hash(pin: str, salt: str, it: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), it).hex()


def _write(path: str, text: str) -> None:
    real = P(path)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    fd = os.open(real + ".new", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(real + ".new", real)


def is_set() -> bool:
    return os.path.exists(P(PIN_FILE))


def set_pin(pin: str) -> None:
    if not valid(pin):
        raise ValueError("PIN must be 4 to 6 digits")
    salt = os.urandom(16).hex()
    _write(PIN_FILE, f"pbkdf2_sha256${ITER}${salt}${_hash(pin, salt, ITER)}\n")
    _write(FAILS_FILE, "fails=0 until=0\n")


def _fails():
    try:
        d = dict(kv.split("=", 1) for kv in open(P(FAILS_FILE)).read().split())
        return int(d.get("fails", 0)), float(d.get("until", 0))
    except (OSError, ValueError):
        return 0, 0.0


def locked_for() -> int:
    """Seconds of lockout left (0 = may try). A clock jump can never lock longer than LOCK_MAX."""
    _n, until = _fails()
    return max(0, min(LOCK_MAX, int(until - time.time() + 0.999)))


def check(pin: str):
    """('ok'|'wrong'|'locked'|'unset', seconds_locked). Counts wrong tries; a right one resets the counter."""
    if not is_set():
        return "unset", 0
    left = locked_for()
    if left:
        return "locked", left
    try:
        _algo, it, salt, want = open(P(PIN_FILE)).read().strip().split("$")
        good = valid(pin) and hmac.compare_digest(_hash(pin, salt, int(it)), want)
    except (OSError, ValueError):
        good = False
    if good:
        _write(FAILS_FILE, "fails=0 until=0\n")
        return "ok", 0
    n = _fails()[0] + 1
    lock = 0 if n < FREE_TRIES else min(LOCK_MAX, LOCK0 * 2 ** (n - FREE_TRIES))
    _write(FAILS_FILE, f"fails={n} until={int(time.time() + lock)}\n")
    return ("locked", lock) if lock else ("wrong", 0)


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    if cmd == "set":
        a, b = sys.stdin.readline().strip(), sys.stdin.readline().strip()
        if a != b:
            print("the two PINs differ", file=sys.stderr)
            return 1
        try:
            set_pin(a)
        except ValueError as e:
            print(e, file=sys.stderr)
            return 1
        return 0
    if cmd == "check":
        res, secs = check(sys.stdin.readline().strip())
        if res == "locked":
            print(f"locked for {secs} s")
        return {"ok": 0, "wrong": 1, "locked": 3, "unset": 4}[res]
    if cmd == "status":
        print(("set" if is_set() else "unset") + (f", locked for {locked_for()} s" if locked_for() else ""))
        return 0
    print("usage: python3 -m vegasui.pin set|check|status  (PIN on stdin)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
