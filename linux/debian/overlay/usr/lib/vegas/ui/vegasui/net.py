"""vegas-net: the Network page, tmux window 1 (spec 4; design page "Network" / "Joining a network"; D14, D15, D16).

Wi-Fi: scan, join (passphrase hashed on the phone, SSID as hex), connect/forget/reorder saved networks, hidden
network - all through wpa_supplicant's control socket (vegasui.wpa). Share: a front-end to the existing tools
vegas-usbshare (USB to laptop) and vegas-hotspot (Wi-Fi hotspot, its own 60 min limit), showing what they report;
both kinds may be on at once (page v28); a tool is never retried in a loop (chip reset loops). Mobile data: a dim "no modem" row only - the modem is never started or
queried (D16). Never lists ccmni*. Joining changes the route of an SSH session over Wi-Fi; usb0 is never touched.
Rulings of 23 Nov: every join/connect is guarded (B2, wpa.JoinGuard: a failed join selects the old network
explicitly; a systemd timer brings it back within 60 s even if this process dies; every start runs enable_network
all and finishes a join a dead vegas-net left); `vegas-net --restore <token>` is that timer's entry point (no
Textual). OWE networks are labelled OWE and refused like 802.1X (B10). A new hotspot passphrase is made by
`vegas-hotspot newpass` (B7: the tool owns /etc/vegas/hotspot.conf; no passphrase on the message line). No 10 s
refresh while the screen is off (B6).
Rulings of 24 Nov: Network asks wpa_supplicant for one scan when its window (tmux window 1 of "main") comes to the
front and the last scan request is older than SCAN_STALE (R3). It knows it is in front from /run/vegas-ui/kbd-window,
which uictl's tmux hook (session-window-changed) writes and the inotify watch on /run/vegas-ui reports (at start,
when the file is not there yet, it asks tmux once). Never with the screen off or another window in front, never
retried after a failure (the next try needs another visit to the front at least SCAN_STALE later), never while
wpa_supplicant does not answer, never automatically while the Wi-Fi hotspot is on; Rescan always asks, and only a
tapped Rescan puts a refused request on the message line. Empty list: "No other networks in range" while
connected, "No networks in range" otherwise (R5). Upright, the in-range list takes the spare rows and scrolls in them,
so the button groups stay at the bottom when a scan fills it (R2); the Hotspot button is a state button (R4).
Rulings of 25 Nov: "scanned N min ago" is the age of the list on screen, whoever asked for the scan (R12):
wpa_supplicant's own scans and wpa_cli's count. The ages come from wpa_supplicant's BSS table (Wpa.bss_ages: one
age per BSS), read with the status every 10 s refresh and after each of our scans; when the table holds a newer list
than the one last brought in (an outside scan), it is brought in with its own ages. R3's two-minute test uses the
same age as the head (a list wpa_supplicant has just refreshed is not scanned again), plus the request time (a
refused request is not repeated within SCAN_STALE). A wpa_supplicant that does not answer BSS: the age of our own
last scan, as before.
Follow-on rulings (after the R8-R16 build):
F3 (R12 order): between sorts, rows only update in place or get appended (Net._take_list): a network still in range
keeps its row with new values, one that went away keeps its row drawn "out of range" (no bars), new networks go after
the rows (beyond SHOWN they wait in "more"), a saved mark changes in place. Rows are sorted by signal (and the
out-of-range ones dropped) only (a) on Network's own scan (Rescan, the R3 automatic scan, the scan after a
join/forget; results that land up to OWN_LATE s after our request, when the 3 s wait missed them, count as that scan)
and (b) each time the Network window comes to the front (Net.resort): tmux window 1 of "main" selected, learnt
exactly as R3 learns it (uictl's session-window-changed hook writes /run/vegas-ui/kbd-window, the inotify watch on
/run/vegas-ui calls front_changed; the 10 s refresh re-reads the file as a fallback). "Page shown" is that same
event (G5 below adds the screen coming back); a dialog of Network's own closing does not re-sort (a finger may be
lifting off the glass then). The sort happens at the front event itself; a newer list the gather started then brings
in is sorted as well. A row drawn "out of range" is not joined when tapped (G6 below: a join to a network the last
scan did not see would fail and drop the Wi-Fi in use, and SSH with it). A list read
by a gather is re-tested on the UI thread before it is taken (_still_newer): an older list never replaces a newer.
F4 (R12 age): "scanned N min ago" and R3's 2-minute test use the MEDIAN age of the rows on screen (Net.list_age):
the rows drawn in the in-range list = the first SHOWN (6), or all of them while "more" is open; a list shorter than
that counts whole (rows scrolled out of view upright still count). A row's age = time since a scan last saw its
network's freshest BSS (out-of-range rows keep aging from their last sighting); an even count takes the mean of the
two middle ages. Empty list: the age of the table as a whole. The associated BSS may always read fresh (to check on
#5): it alone never pulls a newer list in, but its row's age is its own.
Second follow-on rulings (G5, G6):
G5 "Network comes to the front" has ONE definition, used by both R3's two-minute scan test and F3's re-sort
(Net.came_to_front, the only place either starts from): (a) Network's window (tmux window 1 of "main") is selected
on the phone (kbd-window, as above: _front_check), OR (b) the screen comes back - vegas-keys' /run/vegas-ui/state
goes to "on" from off, glance or pin (H1: not dim; a wake, or the glance or the PIN pad closing; a menu in between is
transparent, tui.VegasApp._screen_seen) - while Network is the phone's current tmux window (screen_back). Both
triggers come from the one inotify watch on /run/vegas-ui (kbd-window and state are written there by rename). One
event per visit: a window selected while the screen is not on (off, glance, pin; e.g. a strip tap under the
glance, or tmux from SSH) only marks Network current, and the event comes when the screen does ([BUILDER CHOICE]);
screen_back reads kbd-window first, so a selection and a wake in the same batch count once. Not in front: no event.
H1 (G5 correction): "on" from DIM is not the screen coming back - neither a re-sort nor R3's test (dim is left by any
input, usually a touch on the list; a re-sort then could put another row under the finger). on from off, glance or pin
still counts. Network's window selected while dimmed counts, at the selection itself (designer's default, [BUILDER
CHOICE] on the timing): dim is a lit screen (VegasApp.screen_on), the input that selected the window was not on a row,
and the return to "on" adds nothing. Menu over dim (dim, menu, on) is a return from dim: no event (the menu stays
transparent, tui.VegasApp._screen_seen); off, menu, on is still a wake.
G6 A row of a network that dropped out of range (F3's "gone" row) is drawn dim - bars, name, security and saved mark
all in the dim colour - with "out of range" in place of its signal figures (dBm · band). A tap (or Enter) on it says
"Out of range" on the message line and does nothing else: no join, no dialog. The next sort drops it (F3).
R9: the sharing tools refuse with no uplink ("Not connected: nothing to share. Join a network first.", shown on the
message line; the button stays "Hotspot off"); sharing that lost its uplink says "no uplink" in amber on the current-
network lines and on the hotspot page (from the tools' status lines: uistatus.hotspot()['uplink']).
"""
import re
import shlex
import statistics
import sys
import time
import urllib.parse

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Static

from . import uictl, uistatus as st
from .host import Runner
from .theme import AMBER, DIM, GREEN, TEXT
from .tui import AskScreen, Button, Scroll, ChoiceScreen, StateButton, VegasApp, notice, styled
from .wpa import JoinGuard, Wpa, band, bars, heal, printable, show

SHOWN = 6
SCAN_STALE = 120          # s: R3/R12, an automatic scan only when the list and the last request are older than this
FRESH_SLACK = 2           # s: R12, BSS ages are whole seconds: a list counts as newer only beyond this
OWN_LATE = 15             # s: F3, a list that lands this soon after our own scan request (results late) is sorted
NET_WINDOW = 1            # tmux window of "main" that runs vegas-net (vegas-session)
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"   # [BUILDER CHOICE] spec 4.5
UNSUPPORTED = ("802.1X", "WEP", "OWE")     # tapping one says "not supported yet" (ruling B10: OWE is not open)
HEALED = {"restored": "An interrupted join was undone: back on the old network.",
          "kept": "An interrupted join had worked: the new network is kept and saved."}

NET_CSS = """
#cols { height: auto; }
#left, #right, #list, #wins, #inrange { height: auto; }
.wide #cols { layout: horizontal; }
.wide #left, .wide #right { width: 1fr; }
#head { height: 1; margin: 1 1 0 1; }
#cur { height: 2; margin: 1 1 0 1; }
NetRow { height: 3; margin: 0 1 0 1; padding: 0 1; background: #17202A; content-align: left middle; }
NetRow.alt { background: #141B24; }
#more { margin: 0 1 0 1; }
#empty { height: auto; margin: 0 1 0 2; color: #7F8B99; }
HotspotScreen { background: #0B0F14; align: center top; }
"""


def bars_text(dbm) -> Text:
    n = bars(dbm)
    t = Text()
    for i, ch in enumerate("▂▄▆█"):
        t.append(ch, style=GREEN if i < n else DIM)
    return t


class NetRow(Static):
    """One network in range: three text rows tall; tap or Enter chooses it. A network out of range (net["gone"],
    F3) is drawn all dim with "out of range" in place of its signal figures (G6)."""

    can_focus = True
    BINDINGS = [Binding("enter", "choose", show=False)]

    class Chosen(Message):
        def __init__(self, net):
            super().__init__()
            self.net = net

    def __init__(self, net, saved: bool, classes: str = ""):
        super().__init__(classes=f"row {classes}".strip())
        self.net, self.saved = net, saved

    def render(self) -> Text:
        n, w = self.net, max(self.size.width, 30)
        gone = bool(n.get("gone"))
        t = bars_text(None if gone else n["dbm"])
        t.append(" " + show(n["ssid"])[:w - 6], style=DIM if gone else f"bold {TEXT}")
        left = "     out of range" if gone else f"     {n['dbm']} dBm · {band(n['freq'])}"   # F3/G6
        mark = ("○ " if n["sec"] == "open" else "● ") + n["sec"]
        right = mark + (" saved" if self.saved else "")
        t.append("\n" + left, style=DIM)
        t.append(" " * max(1, w - len(left) - len(right)))
        t.append(mark, style=DIM if gone else TEXT)
        if self.saved:
            t.append(" saved", style=DIM if gone else GREEN)
        return t

    def on_click(self) -> None:
        self.action_choose()

    def action_choose(self) -> None:
        self.post_message(self.Chosen(self.net))


def freshest(t, ages, skip=None):
    """clock() when a scan last saw the freshest BSS of `ages` (Wpa.bss_ages at clock t), leaving out bssid `skip`;
    None = no such BSS."""
    vals = [a for b, a in ages.items() if b != skip]
    return t - min(vals) if vals else None


def kinds(h) -> list:
    """Sharing kinds that are on, from uistatus.hotspot(): ['wifi'], ['usb'] or ['wifi', 'usb']."""
    return [k for k, on in (("wifi", h.get("kind") == "wifi"), ("usb", bool(h.get("usb")))) if on]


class HotspotScreen(ModalScreen):
    """Shown while sharing is on: per kind what the tool reports (Wi-Fi: name, passphrase, devices, QR code);
    a Turn-off button per kind that is on, and the other kind to add. Dismisses with the chosen id or None."""

    def __init__(self, info: str, qr: str, on: list):
        super().__init__()
        self.info, self.qr, self.on = info, qr, on

    def compose(self) -> ComposeResult:
        with Scroll(classes="dialog"):
            yield Static(Text(self.info) if isinstance(self.info, str) else self.info,   # SSIDs: plain text, no markup
                         classes="text")
            if self.qr:
                yield Static(Text(self.qr, no_wrap=True), classes="text")
            if "wifi" in self.on:
                yield Button("Turn off Wi-Fi hotspot", id="off-wifi")
            if "usb" in self.on:
                yield Button("Turn off USB sharing", id="off-usb")
            if "wifi" not in self.on:
                yield Button("Also a Wi-Fi hotspot", id="add-wifi", classes="quiet")
            if "usb" not in self.on:
                yield Button("Also share over USB", id="add-usb", classes="quiet")
            yield Button("Close", id="close", classes="quiet")

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        ev.stop()
        self.dismiss(None if ev.button.id == "close" else ev.button.id)


URL_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~:/?#[]@!&()*+=%")


def safe_url(url: str):
    """A captive-portal URL (from networkctl, i.e. from the network) made safe to hand to a shell or to sway:
    http/https with a host only, every character outside URL_OK percent-encoded (so no quote, space, ; , $ ` { }
    survives: sway splits commands on ; and , and tmux expands #{...}). None if it is not a plain web address."""
    try:
        u = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname or any(ord(ch) < 33 or ord(ch) == 127 for ch in url.strip()):
        return None
    return "".join(ch if ch in URL_OK else urllib.parse.quote(ch, safe="") for ch in url.strip())


def wifi_qr_escape(s: str) -> str:
    return re.sub(r'([\\;,:"])', r"\\\1", s)


class Net(VegasApp):
    CSS = VegasApp.CSS + NET_CSS
    UI_NAME = "net"
    TITLE = "vegas-net"

    FLEX = "#inrange"        # R2: the list takes the spare rows upright and scrolls in them
    FLEX_MIN = 6             # two network rows; below that the page scrolls

    def __init__(self, runner=None, clock=None, **kw):
        super().__init__(runner=runner, **kw)
        self.wpa = Wpa(self.runner, JoinGuard(self.runner))
        self.nets, self.saved, self.expanded = [], {}, False
        self.status, self.hot, self.ssh = {}, {"kind": None}, []
        self.clock = clock or time.monotonic
        self.scanned_at = None    # clock() when a scan (R12: anybody's) last saw the table as a whole; None = never
        self.table_seen = None    # the same without the associated BSS: a newer outside list is one beyond this
        self.own_due = None       # F3: asked_at of our scan whose results were not in yet (the next list is sorted)
        self.asked_at = None      # clock() of the last scan request (automatic or Rescan, worked or not)
        self.busy = False
        self.front = False        # window 1 is the one in front of "main"
        self.status_seen = False  # the first status (hotspot state) is in: automatic scans may start

    def shown(self) -> list:
        """The rows on screen: the first SHOWN, or all of them while "more" is open (a shorter list: all of it)."""
        return self.nets if self.expanded else self.nets[:SHOWN]

    def list_age(self):
        """F4: seconds; the MEDIAN age of the rows on screen (shown()), a row's age being the time since a scan
        (anybody's, R12) last saw its network (its freshest BSS); an even count takes the mean of the two middle
        ages. Rows without an age (a BSS the 4 KiB BSS reply cut off) are left out. No row with an age (empty list):
        the age of the table as a whole (scanned_at). None = never scanned."""
        now = self.clock()
        ages = [now - n["seen"] for n in self.shown() if n.get("seen") is not None]
        if ages:
            return max(0, statistics.median(ages))
        return None if self.scanned_at is None else max(0, now - self.scanned_at)

    @property
    def scan_age(self):
        """Whole minutes of list_age() (F4: median of the rows on screen); None = never scanned."""
        a = self.list_age()
        return None if a is None else int(a // 60)

    def compose(self) -> ComposeResult:
        with Scroll(id="page"):
            yield Static("", id="head")
            yield Static("", id="cur")
            with Vertical(id="cols"):
                with Vertical(id="left"):
                    yield Static("IN RANGE", classes="section")
                    with Scroll(id="inrange"):
                        yield Vertical(id="list")
                        yield Button("", id="more", classes="quiet")
                with Vertical(id="right"):
                    yield Static("SHARE THIS CONNECTION", classes="section")
                    with Horizontal(classes="btnrow"):
                        yield StateButton("Hotspot", "off", id="hotspot")
                        yield Button("Mobile data · no modem", id="mobile", classes="dimmed last")
                    yield Static("NETWORK", classes="section")
                    with Horizontal(classes="btnrow"):
                        yield Button("Rescan", id="rescan")
                        yield Button("Sign-in check", id="signin")
                        yield Button("More", id="moreopts", classes="quiet last")
            yield Static("", id="msg", classes="msg")

    def on_mount(self) -> None:
        self.q("#more").display = False
        self.bg(lambda: heal(self.wpa, self.wpa.guard, at_start=True), self._healed)
        self.refresh_status()
        self.call_later(self._paint_list)
        if uictl.ui_read("kbd-window") is None:       # no window change seen this boot yet: ask tmux once
            self.bg(uictl.current_window, lambda w: self._front_check("" if w is None else str(w)), self.runner)
        self.set_interval(10, self.tick)
        self.set_interval(60, self._age)

    # --- reading ----------------------------------------------------------------------------------------------------
    def _gather(self):
        s = self.wpa.status()          # {} = wpa_supplicant did not answer ("Wi-Fi is off"; no automatic scan)
        if s.get("wpa_state") == "COMPLETED":
            s["rssi"] = self.wpa.rssi()
        return s, st.hotspot(self.runner), st.ssh_local_addrs(), self._newer_list(s)

    def _newer_list(self, s):
        """R12 (worker thread): (t, ages, nets, saved, assoc) when wpa_supplicant holds a newer list than the one
        last brought in (a scan it or wpa_cli asked for), else None. Newer = some BSS other than the associated one
        was seen after table_seen (F4 note: the associated BSS may always read fresh; it alone never pulls the list
        in). Not while our own scan runs (it reads the list itself), not without BSS ages (an old wpa_supplicant)."""
        if not s or self.busy:
            return None
        t, ages = self.clock(), self.wpa.bss_ages()
        if not ages:
            return None
        assoc = s.get("bssid", "").lower() or None
        newest = freshest(t, ages, assoc if self.table_seen is not None else None)
        if newest is None or (self.table_seen is not None and newest <= self.table_seen + FRESH_SLACK):
            return None
        return t, ages, self.wpa.scan_results(), self.wpa.networks(), assoc

    def _still_newer(self, newer) -> bool:
        """UI thread: a list _newer_list read in the worker is still newer than the one on screen (the same test, made
        again: our scan may have brought a newer list in meanwhile), and our scan is not running (it reads its own)."""
        if self.busy:
            return False
        t, ages, _nets, _saved, assoc = newer
        if not ages:
            return True
        newest = freshest(t, ages, assoc if self.table_seen is not None else None)
        return newest is not None and (self.table_seen is None or newest > self.table_seen + FRESH_SLACK)

    def refresh_status(self) -> None:
        self._front_check()          # one file read: the fallback when the inotify watch is not there
        self.bg(self._gather, self._apply_status)

    # --- scan when the window comes to the front (R3) -------------------------------------------------------------
    def front_changed(self) -> None:
        self._front_check()

    def _front_check(self, window=None) -> bool:
        """G5 trigger (a): window = the index in front as a str; None = read /run/vegas-ui/kbd-window (missing: no
        change). Network's window selected while the screen is on (or dimmed, H1) runs came_to_front; selected while
        the screen is off, or under the glance or PIN pad, the event waits for the screen to come back (screen_back:
        one front event per visit, never two). True = came_to_front started a status gather."""
        if window is None:
            window = uictl.ui_read("kbd-window")
            if window is None:
                return False
        front = window == str(NET_WINDOW)
        came = front and not self.front
        self.front = front
        return bool(came and self.screen_on() and self.came_to_front())

    def screen_back(self) -> bool:
        """G5 trigger (b): the screen came back (tui: state "on" after off/glance/pin; H1: not dim) while Network is the
        current window of "main". kbd-window is read first: a window change the watch has not reported yet counts
        once, as (a). True = a status gather was started (it refreshes the page)."""
        was = self.front
        started = self._front_check()       # the screen is on now: a window just selected fires here, as (a)
        if was and self.front:              # Network was already the current window (or was selected while dark)
            started = self.came_to_front()
        return started

    def came_to_front(self) -> bool:
        """G5: Network comes to the front (its window selected, or the screen back with it in front): the one place
        F3's re-sort and R3's automatic scan start from. True = a status gather was started (it refreshes the page)."""
        self.resort()              # F3: sorted at the front event itself (no finger on a row yet), not after a gather
        if not self.status_seen:   # start-up: the first status runs auto_scan itself
            return False
        # then a newer list the gather brings in is sorted too (it is part of coming up), and R3 looks at the age
        self.bg(self._gather, lambda res: (self._apply_status(res, front=True), self.auto_scan()))
        return True

    def resort(self) -> None:
        """F3: Network came to the front: sort the rows by signal again and drop the networks out of range. Between
        sorts rows are only updated in place or appended (_take_list)."""
        nets = sorted((n for n in self.nets if not n.get("gone")), key=lambda n: -n["dbm"])
        if [id(n) for n in nets] == [id(n) for n in self.nets]:
            return
        self.nets = nets
        self._paint_head()
        self.call_later(self._paint_list)

    def auto_scan(self) -> None:
        """R3: one scan, only in front, screen on, Wi-Fi answering, hotspot off, the list on screen older than
        SCAN_STALE (R12: whoever scanned it, so a list wpa_supplicant has just refreshed is not scanned again) and our
        last request too (a refused request is not repeated)."""
        if not self.front or self.busy or not self.status.get("wpa_state") or "wifi" in kinds(self.hot):
            return
        if uictl.screen_state() == "off":
            return
        if self.asked_at is not None and self.clock() - self.asked_at < SCAN_STALE:
            return
        age = self.list_age()             # F4: the median age of the rows on screen, as the head shows it
        if age is not None and age < SCAN_STALE:
            return
        self.rescan()

    def _healed(self, res) -> None:
        """Start-up: every start runs enable_network all, and finishes a join a dead vegas-net left (ruling B2)."""
        if res in HEALED:
            self.say(HEALED[res], "warn" if res == "restored" else "ok")
            self.refresh_status()

    def _apply_status(self, res, front=False) -> None:
        """front: the gather started when Network came to the front (F3: a newer list it brings in is sorted)."""
        self.status, self.hot, self.ssh, *more = res      # more: [the newer list (R12) or None]; absent = none
        newer = more[0] if more else None
        if newer is not None and not self._still_newer(newer):
            newer = None           # R12: read before a list brought in since (our scan): an older list never wins
        due = self.own_due is not None and self.clock() - self.own_due <= OWN_LATE
        if newer is not None:      # R12: an outside scan's list, before auto_scan looks at the age
            self.own_due = None
            self._take_list(newer, sort=due or front)   # F3: in place / appended, sorted as our late scan or on front
        elif not due:
            self.own_due = None
        first = not self.status_seen
        self.status_seen = True
        if first:
            self.call_later(self.auto_scan)     # in front at start: the first scan once the hotspot state is known
        s = self.status
        cur = self.q("#cur", Static)
        if s.get("wpa_state") == "COMPLETED":
            t = styled(show(s.get("ssid_bytes", b"?")) + "  ", bold=True)
            t.append("connected", style=GREEN)
            km = s.get("key_mgmt", "")
            sec = "WPA3" if "SAE" in km else "OWE" if "OWE" in km else "open" if km == "NONE" else "WPA2"
            parts = [s.get("ip_address", "no address yet"), f"{s['rssi']} dBm" if s.get("rssi") is not None else None,
                     band(s.get("freq")), sec]
            t.append("\n" + " · ".join(p for p in parts if p), style=DIM)
        elif not s:
            t = styled("Wi-Fi is off", "warn")
            t.append("\nwpa_supplicant is not answering", style=DIM)
        else:
            t = styled("Not connected", "warn")
            t.append("\n" + s.get("wpa_state", "").lower().replace("_", " "), style=DIM)
        on = kinds(self.hot)
        if on and not self.hot.get("uplink", True):     # R9: sharing that lost its uplink stays on until its timer
            t.append(" · ", style=DIM)
            t.append("no uplink", style=AMBER)
        cur.update(t)
        hb = self.q("#hotspot", StateButton)
        hb.set_state(f"on · {' + '.join(on)}" if on else "off")
        hb.set_class(bool(on), "on")
        for e in self.q("#list").query("#empty"):    # connected or not changes the empty-list text (R5)
            e.update(self._empty_text())
        self._paint_head()

    def on_resize(self, ev) -> None:     # (Textual also runs VegasApp.on_resize: the wide class)
        self.call_after_refresh(self._paint_head)   # the right-aligned scan age follows a rotation

    def _age(self) -> None:
        self._paint_head()

    def _paint_head(self) -> None:
        w = max(self.size.width - 2, 20)
        right = ("scanning" if self.busy else "not scanned" if self.scan_age is None
                 else "scanned just now" if self.scan_age == 0 else f"scanned {self.scan_age} min ago")
        t = styled("Network", bold=True)
        t.append(" " * max(1, w - 7 - len(right)) + right, style=DIM)
        self.q("#head", Static).update(t)

    def rescan(self, tapped=False) -> None:
        """One scan request (Rescan, after a join/forget, or auto_scan); never retried. Only a Rescan the person tapped
        reports a refused request on the message line; an automatic or post-join one leaves the line alone (a join's
        "connected" stays) and the head keeps the age of the last scan that worked."""
        if self.busy:
            return
        self.busy = True
        self.asked_at = self.clock()
        self._paint_head()

        def job():
            try:
                if not self.wpa.scan():
                    return None
                self.runner.sleep(3)
                t, ages = self.clock(), self.wpa.bss_ages()     # R12/F4: the rows' own ages (results late: older)
                assoc = self.status.get("bssid", "").lower() or None
                return t, ages, self.wpa.scan_results(), self.wpa.networks(), assoc
            except Exception:
                return None
        self.bg(job, lambda res: self._apply_scan(res, tapped))

    def _apply_scan(self, res, tapped=False) -> None:
        self.busy = False
        if res is None:
            self._paint_head()
            if tapped:
                self.say("Scan: wpa_supplicant did not take the request. Rescan to try again.", "warn")
            return
        self._take_list(res, sort=True)       # F3: Network's own scan sorts by signal
        if res[1] and self.asked_at is not None and (self.table_seen is None
                                                      or self.table_seen < self.asked_at - FRESH_SLACK):
            self.own_due = self.asked_at      # the table is older than our request: its results are still due

    def _take_list(self, res, sort) -> None:
        """A list from wpa_supplicant's BSS table (R12: from our scan or anybody's). res = (t, ages, nets, saved,
        assoc): t = clock() when the ages were read, ages = Wpa.bss_ages() (None: an old wpa_supplicant, the list
        counts as seen at t). Each network gets 'seen' = t - the age of its freshest BSS (F4).
        sort (F3: Network's own scan; coming to the front is resort()): the rows are drawn anew in signal order,
        networks out of range dropped. Otherwise (a list Network did not ask for: wpa_supplicant scans every few
        seconds while not connected) rows only update in place or get appended: a network still in range keeps its
        row with the new values, a network that went away keeps its row, drawn "out of range" (its age keeps
        growing), and new networks go after the rows, so a row is never moved or taken away under a finger.
        A row's saved mark is updated in place."""
        t, ages, nets, nets_saved, assoc = res
        for n in nets:
            if ages is None:
                n["seen"] = t
            else:
                a = [ages[b] for b in n.get("bssids", ()) if b in ages]
                n["seen"] = t - min(a) if a else None
        saved = {n["ssid"]: n for n in nets_saved}
        if not sort and self.nets:
            new = {n["ssid"]: n for n in nets}
            nets = [new.pop(o["ssid"], None) or dict(o, gone=True) for o in self.nets] + \
                [n for n in nets if n["ssid"] in new]
        self.nets, self.saved = nets, saved
        if ages:
            self.scanned_at = freshest(t, ages)
            ts = freshest(t, ages, assoc)
            self.table_seen = self.scanned_at if ts is None else ts
        else:
            self.scanned_at, self.table_seen = t, (t if ages is None else None)
        self._paint_head()
        rows, shown = list(self.query(NetRow)), self.shown()
        if not rows or [r.net["ssid"] for r in rows] != [n["ssid"] for n in shown[:len(rows)]]:
            self.call_later(self._paint_list)   # async: the old rows must be gone before #empty can come back
            return
        for row, n in zip(rows, shown):
            row.net, row.saved = n, n["ssid"] in saved
            row.refresh()
        add = [NetRow(n, n["ssid"] in saved, classes="alt" if i % 2 else "")
               for i, n in enumerate(shown[len(rows):], len(rows))]
        if add:
            self.q("#list", Vertical).mount(*add)      # after the rows on screen: none of them moves
        self._paint_more()

    def _empty_text(self) -> str:
        if self.scanned_at is None:
            return "Not scanned yet"
        if self.status.get("wpa_state") == "COMPLETED":
            return "No other networks in range"
        return "No networks in range"

    async def _paint_list(self) -> None:
        box = self.q("#list", Vertical)
        await box.remove_children()        # not awaited = DuplicateIds (#empty) on the next empty scan
        shown = self.shown()
        rows = [NetRow(n, n["ssid"] in self.saved, classes="alt" if i % 2 else "") for i, n in enumerate(shown)]
        if not rows:
            rows = [Static(self._empty_text(), id="empty")]
        await box.mount(*rows)
        self._paint_more()

    def _paint_more(self) -> None:
        more = self.q("#more", Button)
        extra = len(self.nets) - SHOWN
        more.display = extra > 0
        more.label = "▲ fewer" if self.expanded else f"▼ {extra} more"

    def say_from_thread(self, text: str) -> None:
        self.call_from_thread(self.say, text)

    # --- choosing a network ---------------------------------------------------------------------------------------
    def on_net_row_chosen(self, ev: NetRow.Chosen) -> None:
        n = ev.net
        if n.get("gone"):      # G6: the last scan did not see it; a join would fail (and drop the Wi-Fi in use)
            self.say("Out of range")
        elif n["ssid"] in self.saved:
            self.saved_dialog(self.saved[n["ssid"]])
        elif n["sec"] in UNSUPPORTED:
            notice(self, f"{show(n['ssid'])}: {n['sec']}", "This kind of network is not supported yet.")
        elif n["sec"] == "open":
            self.join(n["ssid"], "open", "")
        else:
            self.ask_pass(n["ssid"], n["sec"])

    def _ssh_over_wifi(self) -> bool:
        ip = self.status.get("ip_address")
        return bool(ip) and ip in self.ssh

    def ask_pass(self, ssid: bytes, sec: str, hidden=False, error="") -> None:
        text = []
        if error:
            text.append(error)
        if sec == "WPA3":
            text.append("WPA3: may not work yet on this phone.")
        if self._ssh_over_wifi():
            text.append("This cuts your SSH over Wi-Fi. If it fails, the phone goes back to the old network "
                        "within 60 s. USB is not affected.")
        check = (lambda v: None if 8 <= len(v) <= 63 else "8 to 63 characters") if sec == "WPA2" else \
                (lambda v: None if v else "Type the passphrase")
        label = "Join, go back if it fails" if self._ssh_over_wifi() else "Join"
        self.push_screen(AskScreen(f"Passphrase for {show(ssid)}", label, password=True, text="\n".join(text),
                                   check=check),
                         lambda v: v is not None and self.join(ssid, sec, v, hidden))

    def join(self, ssid: bytes, sec: str, passphrase: str, hidden=False) -> None:
        self.say(f"{show(ssid)}: joining")

        def job():
            return self.wpa.join_new(ssid, sec, passphrase, hidden,
                                     progress=lambda s: self.say_from_thread(f"{show(ssid)}: {s}"))

        def done(res):
            ok, msg = res
            self.say(f"{show(ssid)}: {msg}", "ok" if ok else "warn")
            if not ok and msg == "Wrong passphrase?":
                self.ask_pass(ssid, sec, hidden, error="Wrong passphrase?")
            if ok:
                self.refresh_status()
                self.rescan()
                if sec == "open":
                    self.signin_check()
        self.bg(job, done)

    def saved_dialog(self, n) -> None:
        name = show(n["ssid"])
        rows = [("connect", "Connect"), ("forget", "Forget"), ("up", "Move up"), ("down", "Move down"),
                ("cancel", "Cancel", "quiet")]

        def chosen(c):
            if not c:
                return
            if c == "connect":
                self.say(f"{name}: joining")
                self.bg(lambda: self.wpa.connect(n["id"], progress=lambda s: self.say_from_thread(f"{name}: {s}")),
                        lambda r: (self.say(f"{name}: {r[1]}", "ok" if r[0] else "warn"), self.refresh_status()))
            elif c == "forget":
                self.bg(lambda: self.wpa.forget(n["id"]),
                        lambda r: (self.say(f"{name}: {r[1]}", None if r[0] else "warn"), self.rescan()))
            else:
                self.bg(lambda: self.wpa.move(n["id"], c == "up"),
                        lambda r: self.say(f"{name}: {r[1]}", None if r[0] else "warn"))
        self.push_screen(ChoiceScreen(name + (" (saved)"), rows), chosen)

    # --- buttons --------------------------------------------------------------------------------------------------
    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id
        if bid == "more":
            self.expanded = not self.expanded
            self.call_later(self._paint_list)
            self._paint_head()             # F4: other rows on screen, another median age
        elif bid == "rescan":
            self.rescan(tapped=True)
        elif bid == "mobile":
            notice(self, "Mobile data · no modem", "Reboot to Android for calls and mobile data.")
        elif bid == "signin":
            self.signin_check()
        elif bid == "moreopts":
            self.more()
        elif bid == "hotspot":
            self.hotspot()

    # --- sign-in check (spec 4.5) ------------------------------------------------------------------------------------
    def signin_check(self) -> None:
        self.say("Sign-in check: asking the internet")

        def job():
            code = self.runner.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5",
                                    CHECK_URL], timeout=10).out.strip()
            m = re.search(r"Captive Portal: (\S+)", self.runner.run(["networkctl", "status", "wlan0"], timeout=5).out)
            return code, m.group(1) if m else None

        def done(res):
            code, portal = res
            if code == "204":
                self.say("Online: no sign-in page in the way.", "ok")
                return
            url = portal or CHECK_URL
            shown = printable(url)       # from DHCP via networkctl: no raw control bytes into the terminal
            self.say("A sign-in page is in the way." if code not in ("", "000") else "No internet answer.", "warn")
            rows = []
            if self.runner.which("w3m"):
                rows.append(("w3m", "Open in w3m"))
            if self.runner.which("firefox-esr"):
                rows.append(("firefox", "Open in Firefox"))
            if not rows:
                notice(self, "Sign-in page", f"{shown}\nNo browser installed (w3m or firefox-esr).")
                return
            self.push_screen(ChoiceScreen("Sign-in page", rows + [("cancel", "Cancel", "quiet")], shown),
                             lambda c: self._open_signin(c, url))
        self.bg(job, done)

    def _open_signin(self, c, url) -> None:
        url = safe_url(url)
        if url is None:
            self.say("The sign-in address is not a plain http(s) URL; not opened.", "warn")
        elif c == "w3m":    # argv form after --: tmux execs w3m directly, no shell sees the URL
            uictl.tmux(self.runner, "new-window", "-t", "main", "-n", "signin", "--", "w3m", url)
        elif c == "firefox":   # sway runs exec through sh -c: the URL is quoted, and safe_url left no quote in it
            self.runner.run(["swaymsg", "exec", f"choom -n 0 -- firefox-esr {shlex.quote(url)}"], timeout=5)

    # --- More (spec 4.7) ----------------------------------------------------------------------------------------------
    def more(self) -> None:
        rows = [("saved", "Saved networks"), ("hidden", "Hidden network"),
                ("newpass", "New hotspot passphrase", "dimmed" if "wifi" in kinds(self.hot) else ""),
                ("country", "Country · later", "dimmed"), ("tz", "Time zone · later", "dimmed"),
                ("vpn", "VPN · later", "dimmed"), ("mac", "Borrow a device address · later", "dimmed"),
                ("cancel", "Cancel", "quiet")]
        self.push_screen(ChoiceScreen("More", rows), self._more_chosen)

    def _more_chosen(self, c) -> None:
        if c == "saved":
            def list_saved(nets):
                if not nets:
                    notice(self, "No saved networks")
                    return
                byid = {str(n["id"]): n for n in nets}
                self.push_screen(ChoiceScreen("Saved networks", [(str(n["id"]), show(n["ssid"])) for n in nets]
                                              + [("cancel", "Cancel", "quiet")]),
                                 lambda i: i and self.saved_dialog(byid[i]))
            self.bg(self.wpa.networks, list_saved)
        elif c == "hidden":
            self.push_screen(AskScreen("Hidden network name (SSID)", "Next",
                                       check=lambda v: None if 0 < len(v.encode()) <= 32 else "1 to 32 bytes"),
                             self._hidden_pass)
        elif c == "newpass":
            self.new_hotspot_pass()

    def _hidden_pass(self, name) -> None:
        if name is None:
            return
        ssid = name.encode()
        self.push_screen(AskScreen(f"Passphrase for {name} (empty = open network)", "Join", password=True,
                                   check=lambda v: None if v == "" or 8 <= len(v) <= 63 else "Empty or 8 to 63"),
                         lambda v: v is not None and self.join(ssid, "WPA2" if v else "open", v, hidden=True))

    def new_hotspot_pass(self) -> None:
        """`vegas-hotspot newpass` makes and stores the passphrase (the file has one owner, ruling B7). Its output is
        never shown: the message line says only whether it worked; the passphrase is on the hotspot page."""
        if "wifi" in kinds(self.hot):
            notice(self, "Turn the hotspot off first", "A new passphrase applies the next time it is turned on.")
            return
        self.say("New hotspot passphrase: working")

        def done(r):
            if r.ok:
                self.say("New passphrase set. It applies the next time the hotspot is turned on.", "ok")
            elif r.rc == 127:
                self.say("New hotspot passphrase needs vegas-hotspot, which is not installed.", "warn")
            else:
                self.say(f"New hotspot passphrase: vegas-hotspot failed (exit {r.rc}).", "warn")
        self.bg(lambda: self.runner.run(["vegas-hotspot", "newpass"], timeout=15), done)

    # --- hotspot (spec 4.4, D15) -------------------------------------------------------------------------------------
    def hotspot(self) -> None:
        if kinds(self.hot):
            self.bg(self._hotspot_info, lambda r: self.push_screen(HotspotScreen(*r, kinds(self.hot)),
                                                                   self._hotspot_page_done))
            return
        rows = [("usb", "USB to laptop"), ("wifi", "Wi-Fi hotspot"),
                ("modem", "Mobile data · no modem", "dimmed"), ("cancel", "Cancel", "quiet")]
        self.push_screen(ChoiceScreen("Share this connection", rows), self._hotspot_kind)

    def _hotspot_kind(self, c) -> None:
        if c and "usb" in c:
            self.push_screen(ChoiceScreen(
                "USB to laptop", [("go", "Share over USB"), ("cancel", "Cancel", "quiet")],
                "This changes how the laptop reaches the internet. The cable is also the farm's management link "
                "(SSH stays up). The laptop must renew its DHCP lease to use it. Lasts until reboot."),
                lambda g: g and self._tool(["vegas-usbshare", "on"]))
        elif c and "wifi" in c:
            self._tool(["vegas-hotspot", "on", "60"])

    def _tool(self, argv) -> None:
        """Run a sharing tool once (never retried: chip reset loops) and show what it said."""
        self.say(f"{argv[0]} {argv[1]}: working")

        def done(r):
            text = (r.out.strip() + "\n" + r.err.strip()).strip() or f"exit {r.rc}"
            self.say(text, None if r.ok else "warn")
            self.refresh_status()
        self.bg(lambda: self.runner.run(argv, timeout=45), done)

    def _hotspot_info(self):
        on = kinds(self.hot)
        bat, soc = st.battery(), st.soc_temp()
        feed = show(self.status.get("ssid_bytes", b"?"))
        lines, qr = [], ""
        if "wifi" in on:
            out = self.runner.run(["vegas-hotspot", "show"], timeout=5).out
            ssid = (re.search(r"^SSID (.+)$", out, re.M) or [None, "?"])[1]
            psk = (re.search(r"^passphrase (.+)$", out, re.M) or [None, "?"])[1]
            lines += [f"Wi-Fi hotspot  {ssid}", f"passphrase    {psk}", f"devices       {self.hot.get('devices', 0)}",
                      "turns itself off after 60 min"]
            r = self.runner.run(["qrencode", "-t", "UTF8", "-m", "1",
                                 f"WIFI:T:WPA;S:{wifi_qr_escape(ssid)};P:{wifi_qr_escape(psk)};;"], timeout=5)
            qr = r.out.rstrip("\n") if r.ok else ""
        if "usb" in on:
            lines += ["USB to laptop", "  " + self.hot["usb"]]
        info = Text("\n".join(lines + ["feeding from  "]))
        if self.hot.get("uplink", True):
            info.append(feed)
        else:                                   # R9: on until its timer, nothing to feed from
            info.append("no uplink", style=AMBER)
        info.append(f"\nbattery       {'?' if bat['cap'] is None else bat['cap']} %"
                    f"\nprocessor     {'?' if soc is None else soc} °C")
        return info, qr

    def _hotspot_page_done(self, c) -> None:
        if c == "off-wifi":
            self._tool(["vegas-hotspot", "off"])
        elif c == "off-usb":
            self._tool(["vegas-usbshare", "off"])
        elif c:
            self._hotspot_kind(c)


def restore(token) -> int:
    """`vegas-net --restore <token>`: the join guard's timer (wpa.JoinGuard) fired. No Textual, no terminal."""
    r = Runner()
    res = heal(Wpa(r), JoinGuard(r), token=token)
    print(f"vegas-net --restore: {res}")
    return 0


def main() -> None:
    if sys.argv[1:2] == ["--restore"]:
        sys.exit(restore(sys.argv[2] if len(sys.argv) > 2 else None))
    Net().run(mouse=True)


if __name__ == "__main__":
    main()
