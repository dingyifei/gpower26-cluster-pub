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
Screen back (ruling G5, 25 Nov): the page is told (VegasApp.screen_back) when the screen comes back, i.e. vegas-keys'
state goes to "on" from off, glance or pin (a wake, or the glance or the PIN pad closing; H1: not dim). "menu" does
not count as a state of its own here: a menu opened over a dark screen and closed to "on" is a wake, one opened and
closed with the screen on is not ([BUILDER CHOICE]: the menu is transparent; the state before it decides). Seen from
the same inotify event as the refresh above; without inotify, at the 2 s poll while dark and at the 10 s tick. Network
uses it for "Network comes to the front" (net.py, G5), with VegasApp.screen_on (the last state seen is on) to hold
back a window selected while the screen is away until the screen comes back (one event per visit).
H1 (25 Nov, G5 correction): "on" after DIM is not the screen coming back. Dim is left by any input, usually a touch
on the list, and a re-sort then could put another row under the finger. Dim is a lit screen for G5: screen_on is True
while dimmed, so a window selected while dimmed is an event at the selection (a window switch is not a tap on a row)
and the return to "on" after it adds nothing. Menu stays transparent: dim, menu, on is a return from dim (no event);
off, menu, on is still a wake. Only off, glance and pin are away (SCREEN_BACK_FROM).
Layout (ruling R2, 24 Nov): upright, the rows a page does not need go between its read-only block and its first
button group (VegasApp.fit grows the page's FLEX widget: Home's #gap, Network's in-range list), so the buttons sit at
the bottom within thumb reach and the message line is the last line. Landscape (.wide) keeps its own layout.
State buttons (ruling R4): StateButton draws "name state" on one line when that fits the button's inside width, else
the name on line 1 and the whole state on line 2; recomputed from the button's own width on every resize.
Keyboard (ruling 8): Home and Network are drawn with the keyboard hidden; it comes up only while a text field is open
(AskScreen) and goes away when it closes, through uictl.kbd_field (its pid file lets the tmux window hook bring it
back when this window returns to the front, and restore the person's choice on a shell window).
"""
import ctypes
import os
import struct

from rich.cells import cell_len
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

SCREEN_BACK_FROM = ("off", "glance", "pin")    # G5: "on" after one of these = the screen came back (H1: not dim)
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
    """A scrolling page that never takes focus itself (the key highlight should land on buttons and rows only).
    The page itself (id "page") asks the app to recount its spare rows (VegasApp.fit, R2) whenever its size or its
    content height changes: a single count after a rotation could still see the old layout."""

    can_focus = False

    def _refit(self) -> None:
        if self.id == "page" and self.is_attached:
            self.app.call_after_refresh(self.app.fit)

    def watch_virtual_size(self, old, new) -> None:
        self._refit()

    def on_resize(self, ev) -> None:
        self._refit()


class Button(_Button):
    """Textual's Button without the 0.2 s 'active' flash (no animation, and a second tap within 0.2 s counts).
    A str label is taken as plain text, never markup: labels carry SSIDs and tmux window names ("[/x]" raised
    MarkupError, "[@click=app.quit]" became a live action)."""

    def __init__(self, label=None, *a, **kw):
        super().__init__(Text(label) if isinstance(label, str) else label, *a, **kw)
        self.active_effect_duration = 0


def state_label(name: str, state: str, inside: int) -> str:
    """Ruling R4: "name state" when it fits `inside` cells, else "name\nstate" (a state is never split; unknown width
    (inside <= 0, not laid out yet): one line)."""
    one = f"{name} {state}"
    return one if inside <= 0 or cell_len(one) <= inside else f"{name}\n{state}"


class StateButton(Button):
    """A button that shows a name and a state (Away off, Charge 80 %, Hotspot on · wifi): ruling R4. The line break is
    computed from the button's inside width (its width less Button's one-cell padding each side), never left to
    Textual's wrap, and recomputed when the width changes (text size, rotation)."""

    PAD = 2

    def __init__(self, name: str, state: str, **kw):
        self.what, self.state = name, state
        super().__init__(Text(f"{name} {state}", no_wrap=True, overflow="crop"), **kw)

    def set_state(self, state: str) -> None:
        self.state = state
        self.relabel()

    def relabel(self) -> None:
        text = state_label(self.what, self.state, self.size.width - self.PAD)
        if self.label.plain != text or not self.label.no_wrap:
            self.label = Text(text, no_wrap=True, overflow="crop")

    def on_resize(self, ev) -> None:
        self.relabel()


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
        self._screen = None         # G5: the last screen state seen other than "menu" (None = not read yet)

    # --- what the page refreshes; Home and Network override ----------------------------------------------------
    def refresh_status(self) -> None:
        pass

    def rotation_changed(self) -> None:
        """/run/vegas-ui/rotation was written (Home's SCREEN row follows it)."""
        pass

    def screen_back(self) -> bool:
        """G5: the screen came back (state "on" after off, glance or pin; H1: not dim). True = the page refreshed itself
        (the B6 refresh after a dark spell is then not run a second time)."""
        return False

    def screen_on(self) -> bool:
        """G5: the screen is on as last seen by the watch (a menu over it does not count; not seen yet: the file).
        H1: dim counts as on (lit, only dimmer)."""
        state = self._screen if self._screen is not None else uictl.screen_state()
        return state not in SCREEN_BACK_FROM

    def _screen_seen(self, state) -> bool:
        """G5: note a screen state read from /run/vegas-ui/state; True when it is the screen coming back. "menu" is
        transparent (the state before it decides: dim, menu, on is a return from dim, no event, H1)."""
        if state == "menu":
            return False
        prev, self._screen = self._screen, state
        return state == "on" and prev in SCREEN_BACK_FROM

    def tick(self) -> None:
        """The 10 s refresh. While the screen is off: one file read, no thread, no fork; remember to refresh."""
        state = uictl.screen_state()
        back = self._screen_seen(state)
        if state == "off":
            self.set_hl(False)
            if not self.stale:
                self.stale = True
                if self._ino is None and self._wake_poll is not None:
                    self._wake_poll.resume()
            return
        self.stale = False
        if back and self.screen_back():
            return
        self.refresh_status()

    def _state_event(self) -> None:
        """/run/vegas-ui/state was written (inotify) or read by the 2 s poll while dark: G5 screen back, then B6."""
        if self._screen_seen(uictl.screen_state()) and self.screen_back():
            self._woke()
        self._wake_check()

    def _woke(self) -> None:
        self.stale = False
        if self._wake_poll is not None:
            self._wake_poll.pause()

    def _wake_check(self) -> None:
        """The screen came back (a state other than off): refresh once now, not at the next 10 s tick."""
        if self.stale and uictl.screen_state() != "off":
            self._woke()
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
            self._wake_poll = self.set_interval(2, self._state_event, pause=True)

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
                self._state_event()
            if b"rotation" in names:     # vegas-rotate wrote it (from a key, the menu, a shell): no fork, no gather
                self.rotation_changed()
            if b"kbd-window" in names:   # uictl's tmux hook: another window of "main" is in front
                self.front_changed()
            if b"pin-ask" in names:      # R10: vegas-keys answered a PIN pad request (Home)
                self.pin_ask_changed()
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
        self.call_after_refresh(self.fit)      # a longer message takes rows from the spare space (R2)

    # --- spare rows (ruling R2) -------------------------------------------------------------------------------------
    FLEX = None          # selector of the widget that takes the spare rows upright (inside the page Scroll #page)
    FLEX_MIN = 0         # its smallest height; below that the page scrolls

    def fit(self) -> None:
        """Upright: size FLEX so the page content ends on the last row of the page (message line last, buttons at the
        bottom); never below FLEX_MIN (then the page scrolls as before). Landscape: flex_wide(). Textual's fr units
        cannot do this inside a scrolling page (an fr child of an auto-height column resolves against the whole
        viewport), so the rows are counted here."""
        if not self.FLEX:
            return
        try:
            page, flex = self.q("#page"), self.q(self.FLEX)
        except Exception:
            return
        if self.has_class("wide"):
            self.flex_wide(flex)
            return
        view = page.scrollable_content_region.height
        if view <= 0:
            return
        bottom = max((c.virtual_region.bottom + c.styles.margin.bottom for c in page.children if c.display),
                     default=0)
        cur = flex.outer_size.height
        h = max(self.FLEX_MIN, cur + view - bottom)
        if h != cur or str(flex.styles.height) != str(h):
            flex.styles.height = h

    def flex_wide(self, flex) -> None:
        """Landscape layouts are unchanged by R2: the FLEX widget goes back to its own height."""
        flex.styles.height = "auto"

    def front_changed(self) -> None:
        """/run/vegas-ui/kbd-window was written (the tmux hook: the window in front of "main" changed)."""
        pass

    def pin_ask_changed(self) -> None:
        """/run/vegas-ui/pin-ask was written (vegas-keys' answer to a PIN pad request, ruling R10)."""
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
        self.call_after_refresh(self.fit)

    def on_mount(self) -> None:
        uictl.set_highlight(self.UI_NAME, False)    # also makes /run/vegas-ui for the watch
        self._screen_seen(uictl.screen_state())      # G5: the state at start is no transition
        self.set_class(self.size.width > 100, "wide")
        self._watch_state()
        self.call_after_refresh(self.fit)

    def on_unmount(self) -> None:
        self._unwatch_state()
