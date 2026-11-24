"""vegas-home: the Home page, tmux window 0 (spec 3; design page "Home (status)", D6/D13/D15/D17, Q15/Q23).

Top = what you read (status rows), bottom = what you press (finger-sized buttons): brightness, text size, rotation,
tmux windows, Away / Charge to full / Programs / Power. Network set-up and the hotspot live in vegas-net (window 1),
never here (draft 6). Same page over SSH. Status refreshes every 10 s in a thread and repaints only changed rows.
Brightness goes through vegas-keys (/run/vegas-ui/ctl), never sysfs. Rotation acts on button release (Textual's
Pressed fires on release), never while a finger is down; vegas-rotate itself records the rotation and restarts lisgd
(ruling B8). Nothing here stops, reloads or signals sway (D10).
Rulings of 23 Nov: warnings keep their colour inside the dim second lines (B4, segments from uistatus.*_detail);
the Wi-Fi row reads the address first and "<ssid> · -52 dBm ›" below (B11); no 10 s refresh with the screen off
(B6, VegasApp.tick); a program already running is switched to, not started twice (B9). Layout: 60 columns upright
fits 60x56 (keyboard hidden) without scrolling; wider than 100 columns (landscape, 132x22 with the keyboard hidden)
three columns: status | brightness, text size, screen | windows, travel/programs/power (2x2).
Rulings of 24 Nov: upright, the spare rows sit between the status rows and BRIGHTNESS (#gap, sized by VegasApp.fit), so
the buttons are at the bottom and the message line is the last line, at 51, 60, 68 and 72 columns (R2); Away and
Charge are state buttons, "Charge" / "80 %" on two lines when one does not fit (R4, tui.StateButton).
"""
import json

from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Static

from . import uictl, uistatus as st
from . import readers as R
from .host import P, exists, write_atomic
from .tui import AskScreen, Button, Scroll, ChoiceScreen, StateButton, StatusRow, VegasApp, notice, styled

TEXT_SIZES = {"51": "8.25", "60": "7.25", "68": "6.25", "72": "5.75"}   # columns -> foot point size (60 measured)
ROTATIONS = [("normal", "upright"), ("90", "keys up"), ("270", "keys down")]
PROGRAMS = [("firefox-esr", "Firefox"), ("netsurf-gtk3", "NetSurf"), ("zathura", "PDF viewer (zathura)")]
PROGRAM_WS = "2"            # graphical programs open on workspace 2 (sway config, D18)
CG_OVERRIDE = "/run/vegas-chargeguard/override"

HOME_CSS = """
#cols { height: auto; }
#left, #right, #right2, #list, #wins { height: auto; }
.wide #cols { layout: horizontal; }
.wide #left { width: 48; }
.wide #right, .wide #right2 { width: 1fr; }
.wide .msg { margin: 0 1 0 1; }
#head { height: 1; margin: 1 1 0 1; }
#gap { height: 0; }
.wide #gap { display: none; }
#bdown, #bup { width: 13; }
.wide #bdown, .wide #bup { width: 9; }
#bar { width: 1fr; height: 4; content-align: center middle; }
#travel { layout: grid; grid-size: 4; grid-gutter: 0 1; grid-rows: 4; height: 4; margin: 0 1 0 1; }
#travel Button { width: 100%; margin: 0; }
.wide #travel { grid-size: 2; grid-gutter: 1 1; height: 9; }
"""


class Bar(Static):
    """The brightness bar. It repaints itself when its own width changes: Home's resize handler can run before the
    bar has its new width (a text size change drew a 26-cell bar into 22 cells, wrapped onto a second line)."""

    def on_resize(self, ev) -> None:
        app = self.app
        app._paint_bar(app.data["level"] if app.data else uictl.brightness())


def gather(runner):
    """Everything Home shows, read in a worker thread (files via vegasui.readers, commands via the runner)."""
    word, role = st.charge_word()
    pct, mhz = st.cpu_cap()
    rot = uictl.ui_read("rotation")
    if rot not in ("normal", "90", "270"):       # vegas-rotate not yet writing /run/vegas-ui/rotation: ask sway
        rot = "normal"
        r = runner.run(["swaymsg", "-t", "get_outputs", "-r"], timeout=3)
        try:
            for o in json.loads(r.out or "[]"):
                if o.get("name") == "DSI-1":
                    rot = {"90": "90", "270": "270"}.get(str(o.get("transform")), "normal")
        except ValueError:
            pass
    return {
        "host": st.hostname(), "up": st.uptime(), "failed": st.failed_units(runner),
        "bat": st.battery(), "band": st.guard(), "word": word, "role": role, "soc": st.soc_temp(), "cap": pct,
        "mhz": mhz, "wifi": st.wifi(), "usb": st.usb(), "root": st.root_role(), "rescue": st.rescue_pending(),
        "disk": st.disk_free(), "ssh": st.ssh_local_addrs(), "away": st.away_on(), "away_open": st.away_open(),
        "charge": st.charge_mode(), "windows": uictl.windows(runner), "rot": rot,
        "font": uictl.ui_read("fontsize", "7.25"), "level": uictl.brightness(),
    }


class Home(VegasApp):
    CSS = VegasApp.CSS + HOME_CSS
    UI_NAME = "home"
    TITLE = "vegas-home"
    FLEX = "#gap"            # R2: the spare rows upright, between the status rows and the first button group

    def compose(self) -> ComposeResult:
        with Scroll(id="page"):
            yield Static("", id="head")
            with Vertical(id="cols"):
                with Vertical(id="left"):
                    yield StatusRow("Battery", id="r-bat")
                    yield StatusRow("Processor", id="r-cpu")
                    yield StatusRow("Wi-Fi", id="r-wifi")
                    yield StatusRow("USB", id="r-usb")
                    yield StatusRow("Root", id="r-root")
                    yield StatusRow("SSH", id="r-ssh")
                yield Static("", id="gap")
                with Vertical(id="right"):
                    yield Static("BRIGHTNESS", classes="section")
                    with Horizontal(classes="btnrow"):
                        yield Button("−", id="bdown")
                        yield Bar("", id="bar")
                        yield Button("+", id="bup", classes="last")
                    yield Static("TEXT SIZE, COLUMNS", classes="section")
                    with Horizontal(classes="btnrow"):
                        for i, cols in enumerate(TEXT_SIZES):
                            yield Button(cols, id=f"ts-{cols}", classes="last" if i == 3 else "")
                    yield Static("SCREEN", classes="section")
                    with Horizontal(classes="btnrow"):
                        for i, (t, label) in enumerate(ROTATIONS):
                            yield Button(label, id=f"rot-{t}", classes="last" if i == 2 else "")
                with Vertical(id="right2"):
                    yield Static("WINDOWS", classes="section")
                    yield Horizontal(classes="btnrow", id="wins")
                    yield Static("TRAVEL, PROGRAMS, POWER", classes="section")
                    with Grid(id="travel"):
                        yield StateButton("Away", "off", id="away")
                        yield StateButton("Charge", "80 %", id="charge")
                        yield Button("Programs", id="programs", classes="quiet")
                        yield Button("Power", id="power", classes="quiet")
            yield Static("", id="msg", classes="msg")

    data = None          # the last gather() result

    def on_mount(self) -> None:
        self._windows = None
        self.refresh_status()
        self.set_interval(10, self.tick)

    def refresh_status(self) -> None:
        self.bg(gather, self.apply, self.runner)

    def on_resize(self, ev) -> None:     # (Textual also runs VegasApp.on_resize: the wide class)
        if self.data is not None:         # the head line and the bar follow the new width (rotation)
            self.call_after_refresh(self.apply, self._with_rotation(self.data))
            self.set_timer(1.5, self.rotation_changed)   # vegas-rotate writes the file just after the transform

    def _with_rotation(self, d):
        """A rotation made elsewhere (vegas-rotate from a key, the menu, a shell): the SCREEN row follows the file
        at once (one read, no fork), not at the next 10 s refresh."""
        rot = uictl.ui_read("rotation")
        return dict(d, rot=rot) if rot in ("normal", "90", "270") and rot != d.get("rot") else d

    def rotation_changed(self) -> None:
        if self.data is None:
            return
        d = self._with_rotation(self.data)
        if d is not self.data:
            self.data = d
            for t, _ in ROTATIONS:
                self.q(f"#rot-{t}", Button).set_class(d["rot"] == t, "on")

    # --- painting -------------------------------------------------------------------------------------------------
    def apply(self, d) -> None:
        self.data = d
        w = max(self.size.width - 2, 20)
        failed = "?" if d["failed"] is None else d["failed"]
        right = f"up {d['up']} · {failed} failed units"
        head = styled(d["host"], bold=True)
        head.append(" " * max(1, w - len(d["host"]) - len(right)))
        head.append(right, style="#F0B429" if d["failed"] else "#7F8B99")
        self.q("#head", Static).update(head)

        b, band = d["bat"], d["band"]
        cap = "?" if b["cap"] is None else f"{b['cap']} %"
        cap_role = R.bat_level_role(b["cap"])
        self.q("#r-bat", StatusRow).set(f"{cap} {d['word']}", d["role"] if cap_role is None else cap_role,
                                        st.battery_detail(b, band, d["word"]))
        soc = d["soc"]
        self.q("#r-cpu", StatusRow).set("?" if soc is None else f"{soc} °C", R.soc_temp_role(soc),
                                        st.cpu_detail(d["cap"], d["mhz"]))
        wf = d["wifi"]
        if wf["up"]:     # B11: the address on the first line (it must stay on Home), "<ssid> · -52 dBm ›" below
            self.q("#r-wifi", StatusRow).set(wf["ip"], "ok", [
                (wf["ssid"] or "connected", None), (f"{'?' if wf['dbm'] is None else wf['dbm']} dBm ›", None)])
        else:
            self.q("#r-wifi", StatusRow).set("not connected", "dim", "tap: Network ›")
        u = d["usb"]
        self.q("#r-usb", StatusRow).set(u["ip"], None if u["link"] else "dim",
                                                "Mac connected" if u["link"] else "no link")
        self.q("#r-root", StatusRow).set(
            d["root"], "warn" if d["root"] != "main" or d["rescue"] else None, st.root_detail(d["rescue"], d["disk"]))
        n = len(d["ssh"])
        how = [(f"ssh root@{wf['ip'] or '172.16.42.1'}", None)]
        if d.get("away_open"):     # B1: Away is on but SSH could not be closed on Wi-Fi: red, never hidden
            how.append(("OPEN on Wi-Fi", "limit"))
        self.q("#r-ssh", StatusRow).set(f"{n} session{'s' if n != 1 else ''}", None, how)

        self._paint_bar(d["level"])
        for cols, pt in TEXT_SIZES.items():
            self.q(f"#ts-{cols}", Button).set_class(d["font"] == pt, "on")
        for t, _ in ROTATIONS:
            self.q(f"#rot-{t}", Button).set_class(d["rot"] == t, "on")
        away = self.q("#away", StateButton)
        away.set_state("on" if d["away"] else "off")
        away.set_class(d["away"], "on")
        away.set_class(bool(d["away"] and d.get("away_open")), "alarm")   # B1: red while SSH is open on Wi-Fi
        ch = self.q("#charge", StateButton)
        ch.set_state(charge_state(d["charge"]))
        ch.set_class(d["charge"] != "band", "on")
        if d["windows"] != self._windows:
            self._windows = d["windows"]
            self.call_later(self._paint_windows)   # async: the old buttons must be gone before the same ids return

    def _paint_bar(self, level) -> None:
        try:
            w = self.q("#bar", Static).size.width
        except Exception:      # the 0.4 s timer after a brightness tap can fire while the app is closing
            return
        cells = 26 if w <= 0 else max(6, min(26, w - 2))   # 26 upright; narrower in the landscape columns
        n = uictl.brightness_cells(level, cells)
        bar = styled("▇" * n, "warn")
        bar.append("░" * (cells - n), style="#7F8B99")
        self.q("#bar", Static).update(bar)

    async def _paint_windows(self) -> None:
        box = self.q("#wins", Horizontal)
        await box.remove_children()        # not awaited = DuplicateIds on the next repaint (win-1 etc.)
        btns = [Button("1 net", id="win-1")]
        btns += [Button(f"{i} {name}"[:9], id=f"win-{i}") for i, name in self._windows[:3]]
        btns.append(Button("+ new", id="win-new", classes="quiet last"))
        await box.mount(*btns)

    # --- actions --------------------------------------------------------------------------------------------------
    def on_click(self, ev) -> None:
        w = ev.widget
        while w is not None and not isinstance(w, StatusRow):
            w = w.parent
        if w is not None and w.id == "r-wifi":
            uictl.select_window(self.runner, 1)

    def on_button_pressed(self, ev: Button.Pressed) -> None:
        bid = ev.button.id or ""
        r = self.runner
        if bid in ("bdown", "bup"):
            if not uictl.send("brightness " + ("down" if bid == "bdown" else "up")):
                self.say("Brightness needs vegas-keys, which is not running.", "warn")
            self.set_timer(0.4, lambda: self._paint_bar(uictl.brightness()))
        elif bid.startswith("ts-"):
            pt = TEXT_SIZES[bid[3:]]
            uictl.ui_write("fontsize", pt)
            for cols in TEXT_SIZES:
                self.q(f"#ts-{cols}", Button).set_class(cols == bid[3:], "on")
            if not uictl.term_restart(r):
                self.say("Text size is saved; it applies when the terminal (vegas-term) restarts.", "warn")
        elif bid.startswith("rot-"):
            t = bid[4:]
            res = r.run(["vegas-rotate", t], timeout=10)   # it records the rotation and restarts lisgd (B8)
            if res.ok:
                for tt, _ in ROTATIONS:
                    self.q(f"#rot-{tt}", Button).set_class(tt == t, "on")
            else:
                self.say(f"Rotate: {res.err.strip() or res.out.strip()}", "warn")
        elif bid == "win-new":
            uictl.tmux(r, "new-window", "-t", "main")
        elif bid.startswith("win-"):
            uictl.select_window(r, bid[4:])
        elif bid == "power":
            if not uictl.send("menu"):
                self.say("The power menu needs vegas-keys, which is not running.", "warn")
        elif bid == "programs":
            rows = [(cmd, label + (" · running" if running(r, cmd) else "")) for cmd, label in PROGRAMS
                    if r.which(cmd)]
            if not rows:
                notice(self, "No graphical programs installed")
            else:
                self.push_screen(ChoiceScreen("Programs", rows + [("cancel", "Cancel", "quiet")]),
                                 self._start_program)
        elif bid == "charge":
            self._charge_toggle()
        elif bid == "away":
            self._away_toggle()

    def _start_program(self, cmd) -> None:
        """B9: a program already running is switched to (workspace 2), never started a second time."""
        if not cmd:
            return
        if running(self.runner, cmd):
            res = self.runner.run(["swaymsg", "workspace", PROGRAM_WS], timeout=5)
            self.say(f"{cmd} is running: workspace {PROGRAM_WS}" if res.ok else f"{cmd}: {res.err.strip()}",
                     None if res.ok else "warn")
            return
        res = self.runner.run(["swaymsg", "exec", f"choom -n 0 -- {cmd}"], timeout=5)
        self.say(f"Starting {cmd} on workspace 2" if res.ok else f"{cmd}: {res.err.strip()}",
                 None if res.ok else "warn")

    # --- charge to full (spec 5.7) ----------------------------------------------------------------------------------
    def _charge_toggle(self) -> None:
        full = st.charge_mode() == "band"
        self.q("#charge", StateButton).set_class(full, "on")
        self.q("#charge", StateButton).set_state("full" if full else "80 %")
        self.bg(charge_set, self._charge_done, self.runner, full)

    def _charge_done(self, msg) -> None:
        self.say(msg)
        self.refresh_status()

    # --- Away (spec 5.6, D17, Q29/Q31) ------------------------------------------------------------------------------
    def _away_toggle(self) -> None:
        if not self.runner.which("vegas-away"):
            notice(self, "Away needs vegas-away", "The Away switch (SSH closed on Wi-Fi, PIN pad on wake) is not "
                   "installed on this root yet.")
            return
        from . import pin
        if st.away_on():
            self.push_screen(AskScreen("Away is on. PIN to turn it off", "Turn Away off", password=True,
                                       digits=True), self._away_off)
        elif not pin.is_set():
            self.push_screen(AskScreen("New Away PIN (4 to 6 digits)", "Next", password=True, digits=True,
                                       check=lambda v: None if pin.valid(v) else "4 to 6 digits"), self._pin_new)
        else:
            self._away_on()

    def _pin_new(self, first) -> None:
        if first:
            self.push_screen(AskScreen("The same PIN again", "Set PIN and turn Away on", password=True, digits=True,
                                       check=lambda v: None if v == first else "Not the same PIN"),
                             lambda v: self._pin_set(v))

    def _pin_set(self, v) -> None:
        if v:
            from . import pin
            pin.set_pin(v)
            self._away_on()

    def _away_on(self) -> None:
        res = self.runner.run(["vegas-away", "on"], timeout=10)
        uictl.send("away changed")
        # the tool's own line as returned: stdout's first, or (refused) stderr's last, which says why Away stays off
        msg = res.out.strip().splitlines()[0] if res.out.strip() else \
            (res.err.strip().splitlines() or ["Away on"])[-1]
        self.say(msg, None if res.ok and "OPEN" not in msg else "warn")
        self.refresh_status()

    def _away_off(self, v) -> None:
        if not v:
            return
        from . import pin
        res, secs = pin.check(v)
        if res != "ok":
            self.say({"locked": f"Locked: try again in {secs} s", "unset": "No PIN set"}.get(res, "Wrong PIN"),
                     "warn")
            return
        out = self.runner.run(["vegas-away", "off"], timeout=10)
        uictl.send("away changed")
        self.say(out.out.strip() or out.err.strip() or "Away off", None if out.ok else "warn")
        self.refresh_status()


def charge_state(mode) -> str:
    """The Charge button's state (R4: short enough for the 51-column button's inside width of 9 cells): the 70-80 %
    band shows its stop level, "full" while charging to full, "ignored" when the guard ignored the override."""
    return {"full": "full", "ignored": "ignored"}.get(mode, "80 %")


def running(runner, cmd: str) -> bool:
    """Is the program running (any user)? pgrep -x on its process name (comm keeps 15 characters)."""
    return runner.run(["pgrep", "-x", cmd[:15]], timeout=3).ok


def charge_set(runner, full: bool) -> str:
    """vegas-charge full|band if installed; else the same thing by hand: the override file + one guard run."""
    if runner.which("vegas-charge"):
        res = runner.run(["vegas-charge", "full" if full else "band"], timeout=20)
        # vegas-charge prints its status word (seen on #5: a bare "band" on the message line); say it in words
        words = {"band": "Back to the 70-80 % band",
                 "full": "Charging to full until reboot (temperature limits still apply)",
                 "full (pending)": "Charge to full set; the guard applies it within 60 s",
                 "ignored": "Charge to full ignored by the guard (see vegas-charge status)"}
        out = res.out.strip()
        if res.ok and out in words:
            return words[out]
        return (out or res.err.strip()) or ("Charging to full" if full else "Back to the 70-80 % band")
    import os
    try:
        if full:
            write_atomic(CG_OVERRIDE, "STOP=100\nRESUME=99\n", 0o644)
        elif exists(CG_OVERRIDE):
            os.remove(P(CG_OVERRIDE))
    except OSError as e:
        return f"Charge: {e}"
    runner.run(["systemctl", "start", "vegas-chargeguard.service"], timeout=20)   # apply now, not within 60 s
    return ("Charging to full until reboot (temperature limits still apply)" if full
            else "Back to the 70-80 % band")


def main() -> None:
    Home().run(mouse=True)


if __name__ == "__main__":
    main()
