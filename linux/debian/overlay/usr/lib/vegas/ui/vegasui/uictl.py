"""/run/vegas-ui helpers, keyboard show/hide and tmux calls (spec 0.5, 2.8, 3.2, 5.1).

The UI never writes the backlight: it asks vegas-keys through the FIFO /run/vegas-ui/ctl (one writer, D4). Until
vegas-keys exists the FIFO has no reader and the request is dropped (ENXIO), which the caller reports.
Keyboard (designer ruling 8, 23 Nov): the keyboard is hidden while Home (tmux window 0) or Network (1) is in front.
It comes up there only while a text field has focus (passphrase, PIN, hidden network name) and goes away after.
Leaving for a shell window (2 and up) restores what the person last chose. Files in /run/vegas-ui (wvkbd has no
state query):
  kbd                 shown|hidden, what the keyboard shows now (the strip's badge, vegas-kbd's start state)
  kbd-user            shown|hidden, the person's own choice: set only by the strip's kbd tap, the bottom-edge swipe
                      and the keyboard's Hide key (verbs show/hide/toggle); restored on a shell window
  kbd-field-<app>     pid of the Home/Network process while one of its text fields has focus (a dead pid counts as
                      no field, so a crashed page never keeps the keyboard up)
  kbd-window          the window of "main" last seen in front (written by `window`, `auto` and the field verbs)
Verbs (kbd(), and `vegas-kbd <verb>` / `python3 -m vegasui.uictl kbd <verb>` for shell callers):
  show | hide | toggle    the person's choice: sets kbd and kbd-user
  field-on APP | field-off APP   a text field of APP (home|net) got / lost focus, then "auto" (from the CLI the field
                          belongs to the calling process)
  window N                tmux's session-window-changed hook (/etc/vegas/tmux-vegas.conf): apply the rule for window N
  auto                    the tmux hook: apply the rule when the window in front of "main" changed since kbd-window
                          (asks tmux). The hook is global, so it also fires when the Mac's grouped session switches
                          its own windows; main's window is the same then and nothing changes under the phone
                          user's finger (a keyboard swiped up on Home stays up).
The signal goes to whichever keyboard vegas-kbd runs (v2 wvkbd-vegas or stock wvkbd-mobintl): SIGUSR2 shows,
SIGUSR1 hides. Never touches sway (D10).
"""
import errno
import fcntl
import os
import signal
import sys

from .host import P, Runner, read, write_atomic

RUN = "/run/vegas-ui"
STEPS = [20, 40, 70, 110, 170, 250, 360, 520, 700, 889, 1200, 1600, 2047]   # [BUILDER CHOICE] spec 2.8
KBD_PATTERN = "wvkbd-(vegas|mobintl)"   # pkill -x takes an extended regex


def ui_write(name: str, text: str) -> None:
    try:
        os.makedirs(P(RUN), mode=0o700, exist_ok=True)
        write_atomic(f"{RUN}/{name}", text if text.endswith("\n") else text + "\n")
    except OSError:
        pass


def ui_read(name: str, default=None):
    return read(f"{RUN}/{name}", default)


def send(cmd: str) -> bool:
    """One line to vegas-keys. False when nobody reads the FIFO (vegas-keys not running)."""
    try:
        fd = os.open(P(f"{RUN}/ctl"), os.O_WRONLY | os.O_NONBLOCK | os.O_APPEND)
    except OSError as e:
        if e.errno in (errno.ENXIO, errno.ENOENT):
            return False
        raise
    try:
        os.write(fd, (cmd + "\n").encode())
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def brightness():
    """Current 'on' level: vegas-keys' record, else the backlight's own value (read only), else 889."""
    for path in (f"{RUN}/brightness", "/sys/class/backlight/ktd3136-bl/brightness"):
        v = read(path)
        if v and v.isdigit():
            return int(v)
    return 889


def brightness_cells(level: int, cells: int = 26) -> int:
    """Bar length by step index (the steps are roughly logarithmic, so this reads as 'how bright')."""
    idx = max(i for i, s in enumerate([0] + STEPS) if s <= max(level, 0))
    return round(cells * idx / len(STEPS))


KBD_APPS = {0: "home", 1: "net"}          # tmux windows of "main" that keep the keyboard down (vegas-session)
KBD_USER_VERBS = ("show", "hide", "toggle")


def _kbd_signal(runner, show: bool) -> None:
    runner.run(["pkill", "-USR2" if show else "-USR1", "-x", KBD_PATTERN], timeout=3)
    was = ui_read("kbd")
    ui_write("kbd", "shown" if show else "hidden")
    if was != ("shown" if show else "hidden"):
        poke_strip()


def poke_strip() -> None:
    """Wake the strip feed (vegas-status --bar) so its kbd badge follows now, not at its next 10 s read. Only the pid
    the feed wrote itself, and only while that pid is still a `vegas-status --bar` (a reused pid is never signalled;
    an older feed without a SIGUSR1 handler never wrote the file). No fork."""
    pid = ui_read("strip.pid")
    if not (pid and pid.isdigit()):
        return
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            argv = f.read().split(b"\0")
        if not any(a.endswith(b"vegas-status") for a in argv) or b"--bar" not in argv:
            return
        os.kill(int(pid), signal.SIGUSR1)
    except (OSError, ValueError):
        pass


def kbd_shown() -> bool:
    return ui_read("kbd", "shown") != "hidden"


def kbd_user_shown() -> bool:
    """The person's choice; missing (no choice yet this boot) = shown, as the keyboard starts."""
    return ui_read("kbd-user", "shown") != "hidden"


def kbd_field_alive(app: str) -> bool:
    pid = ui_read(f"kbd-field-{app}")
    if not (pid and pid.isdigit() and int(pid) > 1):
        return False
    try:
        os.kill(int(pid), 0)          # signal 0: only asks whether the process exists
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def current_window(runner):
    """Index of the window in front in session main, or None when tmux does not answer."""
    r = tmux(runner, "display-message", "-p", "-t", "main", "#{window_index}")
    v = r.out.strip() if r.ok else ""
    return int(v) if v.isdigit() else None


def _kbd_rule(runner, window, default=None) -> None:
    """Home/Network in front: up only while that page has a text field; a shell window: the person's choice.
    window None (tmux unknown): `default` (True/False) or leave it as it is."""
    if window is None:
        if default is not None:
            _kbd_signal(runner, default)
        return
    if window in KBD_APPS:
        if ui_read("kbd-user") is None:       # first Home/Network visit this boot: remember what to restore
            ui_write("kbd-user", "shown" if kbd_shown() else "hidden")
        _kbd_signal(runner, kbd_field_alive(KBD_APPS[window]))
    else:
        _kbd_signal(runner, kbd_user_shown())


class _KbdLock:
    """One keyboard change at a time (the strip, the hook and the pages can act together)."""

    def __enter__(self):
        self.fd = None
        try:
            os.makedirs(P(RUN), mode=0o700, exist_ok=True)
            self.fd = os.open(P(f"{RUN}/kbd.lock"), os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(self.fd, fcntl.LOCK_EX)
        except OSError:
            pass
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            os.close(self.fd)


def kbd(runner=None, verb: str = "auto", arg=None, pid=None) -> None:
    """Keyboard verbs (see the module doc). runner=None runs commands for real (the strip, the CLI)."""
    runner = runner or Runner()
    with _KbdLock():
        if verb in KBD_USER_VERBS:
            show = (not kbd_shown()) if verb == "toggle" else verb == "show"
            ui_write("kbd-user", "shown" if show else "hidden")
            _kbd_signal(runner, show)
        elif verb in ("field-on", "field-off"):
            if arg not in KBD_APPS.values():
                raise ValueError(f"kbd {verb}: app must be one of {sorted(KBD_APPS.values())}")
            on = verb == "field-on"
            if on:
                ui_write(f"kbd-field-{arg}", str(pid or os.getpid()))
            else:
                try:
                    os.unlink(P(f"{RUN}/kbd-field-{arg}"))
                except OSError:
                    pass
            w = current_window(runner)
            if w is not None:
                ui_write("kbd-window", str(w))
            _kbd_rule(runner, w, default=on)
        elif verb == "window":
            w = int(arg)
            ui_write("kbd-window", str(w))
            _kbd_rule(runner, w)
        elif verb == "auto":
            w = current_window(runner)
            if w is None or ui_read("kbd-window") == str(w):
                return            # tmux not answering, or main's window did not change (another session's switch)
            ui_write("kbd-window", str(w))
            _kbd_rule(runner, w)
        else:
            raise ValueError(f"kbd: unknown verb {verb!r}")


def kbd_field(runner, app: str, on: bool) -> None:
    """A text field of Home ("home") or Network ("net") got (on) or lost focus: up while it has focus, then down again
    unless a shell window is in front. Call it from the field's mount/focus and its close/blur."""
    kbd(runner, "field-on" if on else "field-off", app)


def _app_from_argv():
    return {"vegas-home": "home", "vegas-net": "net"}.get(os.path.basename(sys.argv[0] if sys.argv else ""))


def keyboard(runner, show: bool, app=None) -> None:
    """Older call (text-field dialogs): field semantics for Home/Network (app given or taken from argv[0]),
    otherwise the person's own show/hide."""
    app = app or _app_from_argv()
    if app in KBD_APPS.values():
        kbd_field(runner, app, show)
    else:
        kbd(runner, "show" if show else "hide")


def set_highlight(app_name: str, on: bool) -> None:
    ui_write(app_name, f"highlight={1 if on else 0}")


def screen_state():
    return ui_read("state", "on")


# tmux: phone-side commands always name the session "main" (spec 5.1)
def tmux(runner, *args):
    return runner.run(["tmux", *args], timeout=3)


def select_window(runner, n) -> None:
    tmux(runner, "select-window", "-t", f"main:{n}")


def windows(runner):
    """[(index, name)] of session main, without 0 and 1 (Home and Network)."""
    r = tmux(runner, "list-windows", "-t", "main", "-F", "#{window_index} #{window_name}")
    out = []
    for line in r.out.splitlines():
        idx, _, name = line.partition(" ")
        if idx.isdigit() and int(idx) > 1:
            out.append((int(idx), name))
    return out


def term_restart(runner) -> bool:
    """Kill the main foot (vegas-term reopens it). Never touches sway; never a stale pid (could be anything)."""
    pid = ui_read("term.pid")
    if not (pid and pid.isdigit()) or read(f"/proc/{pid}/comm") != "foot":
        return False
    return runner.run(["kill", pid], timeout=3).ok


def _main(argv) -> int:
    """`python3 -m vegasui.uictl kbd <verb> [arg]` (vegas-kbd's verbs, the tmux hook, lisgd, sway bindings). Silent:
    the tmux hook's run-shell would show any output in a pane."""
    if len(argv) >= 2 and argv[0] == "kbd":
        try:
            # field verbs from a shell: the field belongs to the caller (vegas-kbd execs this from its shell)
            kbd(None, argv[1], argv[2] if len(argv) > 2 else None,
                pid=os.getppid() if argv[1].startswith("field") else None)
            return 0
        except (ValueError, TypeError) as e:
            print(f"vegasui.uictl: {e}", file=sys.stderr)
            return 2
    print("usage: python3 -m vegasui.uictl kbd show|hide|toggle|auto|window N|field-on APP|field-off APP",
          file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
