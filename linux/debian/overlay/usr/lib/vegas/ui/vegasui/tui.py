"""Shared Textual pieces of vegas-home and vegas-net: CSS, status row, dialogs, the base app (spec 0.1, 3.1, 3.2, 4.8).

60 columns upright (foot JetBrains Mono 7.25). Buttons four text rows tall (~10 mm). Colour carries state only.
Key highlight (spec 3.2/4.8, [BUILDER CHOICE] clearing rules): vegas-keys turns Vol-up/Vol-down into Up/Down and the
Power press into Enter only while /run/vegas-ui/<app> says highlight=1. Up/Down move focus and set highlight=1 (the
focused button turns amber via the 'keys' class); any mouse/touch event, 15 s without a key, or the screen going
off clears it, so a finger tap never leaves something for the Power key to press.
Slow work (commands) runs in threads via VegasApp.bg(); the UI never blocks on a tool.
Screen dark (ruling B6): the 10 s refresh (VegasApp.tick) is skipped while /run/vegas-ui/state says off (one file
read, no fork); when vegas-keys writes another state the page refreshes once at once (inotify on /run/vegas-ui;
without inotify, a 2 s file read while dark).
Keyboard (ruling 8): Home and Network are drawn with the keyboard hidden; it comes up only while a text field is open
(AskScreen) and goes away when it closes, through uictl.kbd_field (its pid file lets the tmux window hook bring it
back when this window returns to the front, and restore the person's choice on a shell window).
"""
import ctypes
import os
import struct

from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button as _Button, Input, Static

from . import uictl
from .host import P, Runner
from .theme import AMBER, BG, BUTTON, DIM, GREEN, INK, RED, ROW, STRIP, TEXT

ROLE = {"ok": GREEN, "warn": AMBER, "limit": RED, "dim": DIM, None: TEXT}

CSS = f"""
Screen {{ background: {BG}; color: {TEXT}; }}
Scroll {{ scrollbar-size-vertical: 1; scrollbar-background: {BG}; scrollbar-color: {BUTTON}; }}
.title {{ height: 1; margin: 1 1 0 1; text-style: bold; }}
.section {{ height: 1; margin: 1 1 0 1; color: {DIM}; text-style: bold; }}
StatusRow {{ height: 2; background: {ROW}; margin: 0 1 0 1; padding: 0 1; }}
.btnrow {{ height: 4; margin: 0 1 0 1; }}
.btnrow Button {{ width: 1fr; margin: 0 1 0 0; }}
.btnrow Button.last {{ margin: 0; }}
Button {{
  height: 4; min-width: 5; border: none; background: {BUTTON}; color: {TEXT}; text-style: bold;
  content-align: center middle;
}}
Button:hover {{ background: {BUTTON}; color: {TEXT}; }}
Button:focus {{ text-style: bold; background-tint: 0%; }}
Button.-active {{ background: {BUTTON}; border: none; tint: 0%; }}
Button.on, Button.on:hover {{ background: {AMBER}; color: {INK}; }}
Button.alarm, Button.alarm:hover {{ background: {RED}; color: {INK}; }}
Button.quiet, Button.quiet:hover {{ background: {ROW}; }}
Button.dimmed, Button.dimmed:hover {{ background: {ROW}; color: {DIM}; }}
.keys Button:focus, .keys .row:focus {{ background: {AMBER}; color: {INK}; }}
.msg {{ height: auto; margin: 1 1 0 1; }}
ChoiceScreen, AskScreen {{ background: {BG}; align: center bottom; }}
.dialog {{ width: 100%; height: auto; max-height: 100%; background: {STRIP}; padding: 1 1 0 1; }}
.dialog Button {{ width: 100%; margin: 0 0 1 0; }}
.dialog Input {{ margin: 0 0 1 0; border: tall {BUTTON}; background: {ROW}; height: 3; }}
.dialog Input:focus {{ border: tall {AMBER}; }}
.dialog .text {{ height: auto; margin: 0 0 1 0; }}
"""


class Scroll(VerticalScroll):
    """A scrolling page that never takes focus itself (the key highlight should land on buttons and rows only)."""

    can_focus = False


class Button(_Button):
    """Textual's Button without the 0.2 s 'active' flash (no animation, and a second tap within 0.2 s counts).
    A str label is taken as plain text, never markup: labels carry SSIDs and tmux window names ("[/x]" raised
    MarkupError, "[@click=app.quit]" became a live action)."""

    def __init__(self, label=None, *a, **kw):
        super().__init__(Text(label) if isinstance(label, str) else label, *a, **kw)
        self.active_effect_duration = 0


def styled(text: str, role=None, bold=False) -> Text:
    return Text(text, style=f"{'bold ' if bold else ''}{ROLE.get(role, TEXT)}")


class StatusRow(Static):
    """Two text lines: bold label + value (coloured by role) right-aligned; second line dim, right-aligned.
    The second line is a str, or segments [(text, role)] joined with " · " (uistatus.*_detail): role None is the
    line's dim colour, any other role keeps its colour inside the dim line (ruling B4: a warning is never dim).
    .detail is always the plain text."""

    SEP = " · "

    def __init__(self, label: str, **kw):
        super().__init__(**kw)
        self.label, self.value, self.role, self.detail, self.segs = label, "…", None, "", ()

    def set(self, value: str, role=None, detail="") -> None:
        segs = ((detail, None),) if isinstance(detail, str) else tuple((t, r) for t, r in detail if t)
        if (value, role, segs) != (self.value, self.role, self.segs):   # repaint only on change
            self.value, self.role, self.segs = value, role, segs
            self.detail = self.SEP.join(t for t, _ in segs)
            self.refresh()

    def render(self) -> Text:
        w = max(self.size.width, 20)
        t = Text()
        t.append(self.label, style=f"bold {TEXT}")
        t.append(" " * max(1, w - len(self.label) - len(self.value)))
        t.append(self.value, style=ROLE.get(self.role, TEXT))
        t.append("\n" + " " * max(0, w - len(self.detail)))
        for i, (text, role) in enumerate(self.segs):
            if i:
                t.append(self.SEP, style=DIM)
            t.append(text, style=DIM if role in (None, "dim") else ROLE.get(role, DIM))
        return t


class ChoiceScreen(ModalScreen):
    """Full-width list of big buttons; dismisses with the chosen id (None = Cancel). Rows: (id, label, cls)."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, title: str, rows, text: str = ""):
        super().__init__()
        self.title_text, self.rows, self.text = title, rows, text

    def compose(self) -> ComposeResult:
        with Scroll(classes="dialog"):
            yield Static(styled(self.title_text, bold=True), classes="text")
            if self.text:                  # plain text: it can hold a portal URL or an SSID (no markup)
                yield Static(Text(self.text), classes="text")
            for rid, label, *cls in self.rows:
                yield Button(label, id=f"c-{rid}", classes=" ".join(cls))

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        ev.stop()
        rid = ev.button.id[2:]
        if "dimmed" in ev.button.classes:
            return
        self.dismiss(None if rid == "cancel" else rid)

    def action_cancel(self) -> None:
        self.dismiss(None)


def notice(app, title: str, text: str = "") -> None:
    app.push_screen(ChoiceScreen(title, [("cancel", "OK")], text))


class AskScreen(ModalScreen):
    """One text field (password-hidden if asked) + Show toggle + OK/Cancel; shows the touch keyboard while open.
    Dismisses with the text, or None. check(text) -> error message or None keeps the page open with the message."""

    BINDINGS = [Binding("escape", "cancel", show=False)]

    def __init__(self, title, ok_label="OK", password=False, text="", check=None, digits=False, value=""):
        super().__init__()
        self.title_text, self.ok_label, self.password, self.text = title, ok_label, password, text
        self.check, self.digits, self.value = check, digits, value

    def compose(self) -> ComposeResult:
        with Scroll(classes="dialog"):
            yield Static(styled(self.title_text, bold=True), classes="text")
            if self.text:
                yield Static(Text(self.text), classes="text")
            yield Input(value=self.value, password=self.password, id="field",
                        restrict=r"[0-9]*" if self.digits else None, max_length=6 if self.digits else 0)
            yield Static("", id="err", classes="text")
            if self.password:
                yield Button("Show", id="show", classes="quiet")
            yield Button(self.ok_label, id="ok")
            yield Button("Cancel", id="cancel", classes="quiet")

    def on_mount(self) -> None:
        self.query_one("#field", Input).cursor_blink = False   # no blinking anywhere (spec 0.1)
        self.query_one("#field", Input).focus()
        self.app.field_open(True)

    def _close(self, value) -> None:
        self.app.field_open(False)     # before dismiss: a follow-up AskScreen (PIN twice) shows it again on mount
        self.dismiss(value)

    def _submit(self) -> None:
        v = self.query_one("#field", Input).value
        err = self.check(v) if self.check else None
        if err:
            self.query_one("#err", Static).update(styled(err, "warn"))
            self.query_one("#field", Input).focus()
            return
        self._close(v)

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        ev.stop()
        self._submit()

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        ev.stop()
        f = self.query_one("#field", Input)
        if ev.button.id == "show":
            f.password = not f.password
            ev.button.label = "Hide" if not f.password else "Show"
            f.focus()                      # the toggle returns focus to the field (page "Joining a network")
        elif ev.button.id == "ok":
            self._submit()
        else:
            self._close(None)

    def action_cancel(self) -> None:
        self._close(None)


class VegasApp(App):
    """Base: runner injection, threaded jobs, key highlight bookkeeping, wide (landscape) class."""

    CSS = CSS
    AUTO_FOCUS = None          # no highlight until a key asks for one
    ENABLE_COMMAND_PALETTE = False
    UI_NAME = "home"           # /run/vegas-ui/<UI_NAME> carries highlight=0|1
    BINDINGS = [Binding("up", "key_move(-1)", show=False, priority=True),
                Binding("down", "key_move(1)", show=False, priority=True)]

    def __init__(self, runner=None, **kw):
        super().__init__(**kw)
        self.runner = runner or Runner()
        self._hl = False
        self._hl_timer = None
        self.stale = False          # a refresh was skipped while the screen was off
        self._ino = None            # inotify fd on /run/vegas-ui, or None
        self._wake_poll = None      # fallback timer while dark when inotify is not there

    # --- what the page refreshes; Home and Network override ----------------------------------------------------
    def refresh_status(self) -> None:
        pass

    def rotation_changed(self) -> None:
        """/run/vegas-ui/rotation was written (Home's SCREEN row follows it)."""
        pass

    def tick(self) -> None:
        """The 10 s refresh. While the screen is off: one file read, no thread, no fork; remember to refresh."""
        if uictl.screen_state() == "off":
            self.set_hl(False)
            if not self.stale:
                self.stale = True
                if self._ino is None and self._wake_poll is not None:
                    self._wake_poll.resume()
            return
        self.stale = False
        self.refresh_status()

    def _wake_check(self) -> None:
        """The screen came back (a state other than off): refresh once now, not at the next 10 s tick."""
        if self.stale and uictl.screen_state() != "off":
            self.stale = False
            if self._wake_poll is not None:
                self._wake_poll.pause()
            self.refresh_status()

    def _watch_state(self) -> None:
        """inotify on /run/vegas-ui (vegas-keys writes state by rename: IN_MOVED_TO). Linux only; else poll."""
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            fd = libc.inotify_init1(os.O_NONBLOCK | os.O_CLOEXEC)
            if fd < 0:
                raise OSError(ctypes.get_errno(), "inotify_init1")
            if libc.inotify_add_watch(fd, P(uictl.RUN).encode(), 0x00000008 | 0x00000080) < 0:  # CLOSE_WRITE|MOVED_TO
                os.close(fd)
                raise OSError(ctypes.get_errno(), "inotify_add_watch")
            import asyncio
            asyncio.get_running_loop().add_reader(fd, self._ino_event)
            self._ino = fd
        except (AttributeError, OSError, RuntimeError, NotImplementedError):
            self._ino = None
            self._wake_poll = self.set_interval(2, self._wake_check, pause=True)

    def _ino_event(self) -> None:
        try:
            buf = os.read(self._ino, 4096)
        except (OSError, TypeError):
            return
        names, i = [], 0
        while i + 16 <= len(buf):
            _wd, _mask, _cookie, n = struct.unpack_from("iIII", buf, i)
            names.append(buf[i + 16:i + 16 + n].rstrip(b"\0"))
            i += 16 + n
        try:
            if b"state" in names:
                self._wake_check()
            if b"rotation" in names:     # vegas-rotate wrote it (from a key, the menu, a shell): no fork, no gather
                self.rotation_changed()
        except Exception:   # never let a late event (app closing) raise inside the event loop
            pass

    def _unwatch_state(self) -> None:
        if self._ino is not None:
            try:
                import asyncio
                asyncio.get_running_loop().remove_reader(self._ino)
            except (RuntimeError, ValueError):
                pass
            os.close(self._ino)
            self._ino = None

    # --- touch keyboard: only while a text field is open (ruling 8) ----------------------------------------------
    def field_open(self, on: bool) -> None:
        """An AskScreen opened (True) or closed (False)."""
        uictl.kbd_field(self.runner, self.UI_NAME, on)

    # --- threads -------------------------------------------------------------------------------------------------
    def bg(self, fn, then=None, *args):
        """Run fn(*args) in a thread; then(result) on the UI thread."""
        def job():
            try:
                res = fn(*args)
            except Exception as e:          # a tool or parse error must never take the page down
                self.call_from_thread(self.say, f"error: {type(e).__name__}: {e}", "limit")
                return
            if then is not None:
                self.call_from_thread(then, res)
        self.run_worker(job, thread=True, exit_on_error=False)

    def q(self, selector, expect_type=None):
        """query_one on the page itself. App.query_one searches the ACTIVE screen, which is a dialog while one is open:
        a 10 s refresh or the 60 s scan-age timer then raised NoMatches (a timer error ends the app)."""
        stack = self.screen_stack
        base = stack[0] if stack else self.screen
        return base.query_one(selector, expect_type) if expect_type else base.query_one(selector)

    def say(self, text: str, role=None) -> None:
        """The page's message line (#msg)."""
        try:
            self.q("#msg", Static).update(styled(text, role))
        except Exception:
            pass

    # --- key highlight ---------------------------------------------------------------------------------------------
    def set_hl(self, on: bool) -> None:
        if on == self._hl:
            return
        self._hl = on
        self.set_class(on, "keys")
        uictl.set_highlight(self.UI_NAME, on)
        if not on and self.focused is not None and not isinstance(self.focused, Input):
            self.set_focus(None)

    def action_key_move(self, step: int) -> None:
        if isinstance(self.focused, Input):
            return
        self.screen.focus_next() if step > 0 else self.screen.focus_previous()
        if self.focused is not None:
            self.focused.scroll_visible(animate=False)
        self.set_hl(True)
        if self._hl_timer:
            self._hl_timer.stop()
        self._hl_timer = self.set_timer(15, lambda: self.set_hl(False))

    async def on_event(self, event: events.Event) -> None:
        if isinstance(event, events.MouseDown):
            self.set_hl(False)
        await super().on_event(event)

    # --- layout ---------------------------------------------------------------------------------------------------
    def on_resize(self, ev: events.Resize) -> None:
        self.set_class(ev.size.width > 100, "wide")   # landscape 127-132 columns: two columns (Textual has no breakpoints)

    def on_mount(self) -> None:
        uictl.set_highlight(self.UI_NAME, False)    # also makes /run/vegas-ui for the watch
        self.set_class(self.size.width > 100, "wide")
        self._watch_state()

    def on_unmount(self) -> None:
        self._unwatch_state()
