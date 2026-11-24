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
"""
import re
import shlex
import sys
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
from .theme import DIM, GREEN, TEXT
from .tui import AskScreen, Button, Scroll, ChoiceScreen, VegasApp, notice, styled
from .wpa import JoinGuard, Wpa, band, bars, heal, printable, show

SHOWN = 6
CHECK_URL = "http://connectivitycheck.gstatic.com/generate_204"   # [BUILDER CHOICE] spec 4.5
UNSUPPORTED = ("802.1X", "WEP", "OWE")     # tapping one says "not supported yet" (ruling B10: OWE is not open)
HEALED = {"restored": "An interrupted join was undone: back on the old network.",
          "kept": "An interrupted join had worked: the new network is kept and saved."}

NET_CSS = """
#cols { height: auto; }
#left, #right, #list, #wins { height: auto; }
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
    """One network in range: three text rows tall; tap or Enter chooses it."""

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
        t = bars_text(n["dbm"])
        t.append(" " + show(n["ssid"])[:w - 6], style=f"bold {TEXT}")
        left = f"     {n['dbm']} dBm · {band(n['freq'])}"
        mark = ("○ " if n["sec"] == "open" else "● ") + n["sec"]
        right = mark + (" saved" if self.saved else "")
        t.append("\n" + left, style=DIM)
        t.append(" " * max(1, w - len(left) - len(right)))
        t.append(mark, style=TEXT)
        if self.saved:
            t.append(" saved", style=GREEN)
        return t

    def on_click(self) -> None:
        self.action_choose()

    def action_choose(self) -> None:
        self.post_message(self.Chosen(self.net))


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
            yield Static(Text(self.info), classes="text")   # SSIDs: plain text, no markup
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

    def __init__(self, runner=None, **kw):
        super().__init__(runner=runner, **kw)
        self.wpa = Wpa(self.runner, JoinGuard(self.runner))
        self.nets, self.saved, self.expanded = [], {}, False
        self.status, self.hot, self.ssh = {}, {"kind": None}, []
        self.scan_age = None      # minutes since the last scan result; None = never
        self.busy = False

    def compose(self) -> ComposeResult:
        with Scroll():
            yield Static("", id="head")
            yield Static("", id="cur")
            with Vertical(id="cols"):
                with Vertical(id="left"):
                    yield Static("IN RANGE", classes="section")
                    yield Vertical(id="list")
                    yield Button("", id="more", classes="quiet")
                with Vertical(id="right"):
                    yield Static("SHARE THIS CONNECTION", classes="section")
                    with Horizontal(classes="btnrow"):
                        yield Button("Hotspot off", id="hotspot")
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
        self.rescan()
        self.set_interval(10, self.tick)
        self.set_interval(60, self._age)

    # --- reading ----------------------------------------------------------------------------------------------------
    def _gather(self):
        s = self.wpa.status()
        s["rssi"] = self.wpa.rssi() if s.get("wpa_state") == "COMPLETED" else None
        return s, st.hotspot(self.runner), st.ssh_local_addrs()

    def refresh_status(self) -> None:
        self.bg(self._gather, self._apply_status)

    def _healed(self, res) -> None:
        """Start-up: every start runs enable_network all, and finishes a join a dead vegas-net left (ruling B2)."""
        if res in HEALED:
            self.say(HEALED[res], "warn" if res == "restored" else "ok")
            self.refresh_status()

    def _apply_status(self, res) -> None:
        self.status, self.hot, self.ssh = res
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
        cur.update(t)
        on = kinds(self.hot)
        hb = self.q("#hotspot", Button)
        hb.label = f"Hotspot on · {' + '.join(on)}" if on else "Hotspot off"
        hb.set_class(bool(on), "on")
        self._paint_head()

    def on_resize(self, ev) -> None:     # (Textual also runs VegasApp.on_resize: the wide class)
        self.call_after_refresh(self._paint_head)   # the right-aligned scan age follows a rotation

    def _age(self) -> None:
        if self.scan_age is not None:
            self.scan_age += 1
        self._paint_head()

    def _paint_head(self) -> None:
        w = max(self.size.width - 2, 20)
        right = ("scanning" if self.busy else "not scanned" if self.scan_age is None
                 else "scanned just now" if self.scan_age == 0 else f"scanned {self.scan_age} min ago")
        t = styled("Network", bold=True)
        t.append(" " * max(1, w - 7 - len(right)) + right, style=DIM)
        self.q("#head", Static).update(t)

    def rescan(self) -> None:
        if self.busy:
            return
        self.busy = True
        self._paint_head()

        def job():
            self.wpa.scan()
            self.runner.sleep(3)
            return self.wpa.scan_results(), self.wpa.networks()
        self.bg(job, self._apply_scan)

    def _apply_scan(self, res) -> None:
        self.busy = False
        self.nets, nets_saved = res
        self.saved = {n["ssid"]: n for n in nets_saved}
        self.scan_age = 0
        self._paint_head()
        self.call_later(self._paint_list)   # async: the old rows must be gone before #empty can come back

    async def _paint_list(self) -> None:
        box = self.q("#list", Vertical)
        await box.remove_children()        # not awaited = DuplicateIds (#empty) on the next empty scan
        shown = self.nets if self.expanded else self.nets[:SHOWN]
        rows = [NetRow(n, n["ssid"] in self.saved, classes="alt" if i % 2 else "") for i, n in enumerate(shown)]
        if not rows:
            rows = [Static("No networks in range (Rescan)", id="empty")]
        await box.mount(*rows)
        more = self.q("#more", Button)
        extra = len(self.nets) - SHOWN
        more.display = extra > 0
        more.label = "▲ fewer" if self.expanded else f"▼ {extra} more"

    def say_from_thread(self, text: str) -> None:
        self.call_from_thread(self.say, text)

    # --- choosing a network ---------------------------------------------------------------------------------------
    def on_net_row_chosen(self, ev: NetRow.Chosen) -> None:
        n = ev.net
        if n["ssid"] in self.saved:
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
        elif bid == "rescan":
            self.rescan()
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
        lines += [f"feeding from  {feed}",
                  f"battery       {'?' if bat['cap'] is None else bat['cap']} %",
                  f"processor     {'?' if soc is None else soc} °C"]
        return "\n".join(lines), qr

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
