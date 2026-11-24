"""Designer rulings of 24 Nov (captures on the glass): R1 one background colour, R2 buttons at the bottom (spare rows
between the read-only block and the first button group, message line last, Network's list scrolls in the spare rows),
R3 Network scans when its window comes to the front, R4 state buttons break between name and state, R5 empty-list
texts. Cell grids: foot JetBrains Mono at the four text sizes on the 1080x2388 panel (scale 3, 1020 x 2232 px for
foot, one row for the tmux bar): 51x49, 60x56, 68x64, 72x71 (72x67 too, the designer's estimate), landscape 132x23."""
import os
import re

import pytest
from conftest import put
from rich.cells import cell_len
from textual.widgets import Static

import test_net
from test_net import HDR, make, settle
from vegasui import tui, uictl
from vegasui.host import Result
from vegasui.home import Home
from vegasui.net import SCAN_STALE, Net, NetRow
from vegasui.tui import StateButton, state_label

OVERLAY = "/path/to/repo/linux/debian/overlay"
UPRIGHT = [(51, 49), (60, 56), (68, 64), (72, 67), (72, 71)]
LANDSCAPE = (132, 23)
ALL = UPRIGHT + [LANDSCAPE]


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def lines(btn):
    return btn.label.plain.split("\n")


def check_state_button(btn, name, state):
    """R4: one line when it fits the inside width, else name / whole state; never wider than the inside."""
    inside = btn.size.width - 2
    one = f"{name} {state}"
    if cell_len(one) <= inside:
        assert lines(btn) == [one], (btn.id, btn.size, btn.label.plain)
    else:
        assert lines(btn) == [name, state], (btn.id, btn.size, btn.label.plain)
    assert all(cell_len(x) <= inside for x in lines(btn)), (btn.id, inside, btn.label.plain)
    assert btn.label.no_wrap, "the break is ours, never Textual's wrap"


def scans(fw):
    return [a for a in fw.log if a[:1] == ["scan"]]


# ------------------------------------------------------------------------------------------------------------ R4
def test_r4_state_label():
    assert state_label("Charge", "80 %", 11) == "Charge 80 %"
    assert state_label("Charge", "80 %", 10) == "Charge\n80 %"
    assert state_label("Away", "off", 9) == "Away off"
    assert state_label("Hotspot", "on · wifi + usb", 22) == "Hotspot\non · wifi + usb"
    assert state_label("Charge", "full", 0) == "Charge full"          # not laid out yet: one line


@pytest.mark.parametrize("size", ALL, ids=lambda s: f"{s[0]}x{s[1]}")
async def test_r4_home_state_buttons(sysroot, runner, size):
    app = Home(runner=runner)
    async with app.run_test(size=size) as pilot:
        await settle(app, pilot)
        for charge, cstate in (("band", "80 %"), ("full", "full"), ("ignored", "ignored")):
            for away, astate in ((False, "off"), (True, "on")):
                app.apply(dict(app.data, charge=charge, away=away, away_open=False))
                await pilot.pause()
                check_state_button(app.query_one("#charge", StateButton), "Charge", cstate)
                check_state_button(app.query_one("#away", StateButton), "Away", astate)


async def test_r4_home_51_breaks_charge_60_does_not(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=(51, 49)) as pilot:
        await settle(app, pilot)
        assert app.query_one("#charge", StateButton).label.plain == "Charge\n80 %"     # the glass: "Charge 80" / "%"
        assert app.query_one("#away", StateButton).label.plain == "Away off"
        # a text size change (foot restarts with another grid) and a rotation recompute the break
        await pilot.resize_terminal(60, 56)
        await settle(app, pilot)
        assert app.query_one("#charge", StateButton).label.plain == "Charge 80 %"
        await pilot.resize_terminal(51, 49)
        await settle(app, pilot)
        assert app.query_one("#charge", StateButton).label.plain == "Charge\n80 %"
        await pilot.resize_terminal(*LANDSCAPE)
        await settle(app, pilot)
        assert app.query_one("#charge", StateButton).label.plain == "Charge 80 %"


@pytest.mark.parametrize("size", ALL, ids=lambda s: f"{s[0]}x{s[1]}")
async def test_r4_net_hotspot_button(sysroot, size):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=size) as pilot:
        await settle(app, pilot)
        for hot, state in (({"kind": None, "usb": None}, "off"), ({"kind": "wifi", "usb": None}, "on · wifi"),
                           ({"kind": "usb", "usb": "on"}, "on · usb"),
                           ({"kind": "wifi", "usb": "on"}, "on · wifi + usb")):
            app._apply_status((app.status, hot, []))
            await pilot.pause()
            check_state_button(app.query_one("#hotspot", StateButton), "Hotspot", state)


# ------------------------------------------------------------------------------------------------------------ R2
def no_page_scroll(app):
    page = app.query_one("#page")
    assert page.max_scroll_y == 0, f"page scrolls at {app.size}: {page.virtual_size}"


def msg_last(app):
    msg = app.query_one("#msg")
    assert msg.region.bottom == app.size.height, (msg.region, app.size)


@pytest.mark.parametrize("size", UPRIGHT, ids=lambda s: f"{s[0]}x{s[1]}")
async def test_r2_home_buttons_at_the_bottom(sysroot, runner, size):
    app = Home(runner=runner)
    async with app.run_test(size=size) as pilot:
        await settle(app, pilot)
        app.say("Back to the 70-80 % band")
        await settle(app, pilot)
        no_page_scroll(app)
        msg_last(app)
        ssh = app.query_one("#r-ssh").region
        first = app.query_one("#right").region                  # BRIGHTNESS: the first button group
        gap = app.query_one("#gap").region.height
        assert gap > 0, f"no spare rows at {size}"
        assert first.y >= ssh.bottom + gap and first.y - ssh.bottom > 1, (ssh, first, gap)
        # the buttons end where the message line starts: nothing spare below them
        travel = app.query_one("#travel").region
        assert app.query_one("#msg").region.y == travel.bottom + 1
        # spare rows are given back to a longer message, the message stays last
        app.say("Charging to full until reboot (temperature limits still apply) - a long line to wrap")
        await settle(app, pilot)
        no_page_scroll(app)
        msg_last(app)


async def test_r2_home_landscape_unchanged(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await pilot.resize_terminal(*LANDSCAPE)
        await settle(app, pilot)
        assert app.has_class("wide") and not app.query_one("#gap").display
        left, right = app.query_one("#left").region, app.query_one("#right").region
        assert left.y == right.y and left.x < right.x
        await pilot.resize_terminal(60, 56)
        await settle(app, pilot)
        no_page_scroll(app)
        msg_last(app)


def many(n):
    return HDR + "".join(f"bb:00:00:00:00:{i:02x}\t2412\t-{40 + i}\t[WPA2-PSK-CCMP][ESS]\tnet-{i:02d}\n"
                         for i in range(n))


@pytest.mark.parametrize("size", UPRIGHT, ids=lambda s: f"{s[0]}x{s[1]}")
async def test_r2_net_buttons_keep_their_place(sysroot, monkeypatch, size):
    monkeypatch.setattr(test_net, "SCAN", many(30))
    r, fw = make()
    del r.table[("tmux", "display-message")]                 # not in front: no scan at start, the list is empty
    app = Net(runner=r)
    async with app.run_test(size=size) as pilot:
        await settle(app, pilot)
        assert not scans(fw) and not app.query(NetRow)
        no_page_scroll(app)
        msg_last(app)
        cur, inrange = app.query_one("#cur").region, app.query_one("#inrange").region
        assert inrange.y > cur.bottom and inrange.height >= app.FLEX_MIN
        ys = {b: app.query_one(f"#{b}").region.y for b in ("hotspot", "rescan", "signin", "moreopts")}
        await pilot.click("#rescan")
        await settle(app, pilot)
        assert len(app.query(NetRow)) == 6
        assert {b: app.query_one(f"#{b}").region.y for b in ys} == ys
        await pilot.click("#more")                               # all 30: the list scrolls inside its rows
        await settle(app, pilot)
        assert len(app.query(NetRow)) == 30
        assert app.query_one("#inrange").max_scroll_y > 0
        assert {b: app.query_one(f"#{b}").region.y for b in ys} == ys
        no_page_scroll(app)
        msg_last(app)
        # the last button group ends where the message line starts
        assert app.query_one("#msg").region.y == app.query_one("#rescan").region.bottom + 1


async def test_r2_net_landscape_unchanged(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=LANDSCAPE) as pilot:
        await settle(app, pilot)
        assert app.has_class("wide")
        left, right = app.query_one("#left").region, app.query_one("#right").region
        assert left.y == right.y and left.x < right.x
        inr = app.query_one("#inrange")
        assert str(inr.styles.height) == "auto" and inr.max_scroll_y == 0   # the page scrolls, as before


# ------------------------------------------------------------------------------------------------------------ R3
async def front(app, pilot, window):
    """What the tmux hook does: uictl writes /run/vegas-ui/kbd-window; the inotify watch tells the page."""
    uictl.ui_write("kbd-window", str(window))
    for _ in range(20):
        await pilot.pause(0.02)
        if app.front == (str(window) == "1"):
            break
    await settle(app, pilot)


def not_in_front(extra=None):
    r, fw = make(extra=extra)
    del r.table[("tmux", "display-message")]
    return r, fw


async def test_r3_no_scan_in_the_background(sysroot):
    r, fw = not_in_front()
    clock = Clock()
    app = Net(runner=r, clock=clock)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        assert not scans(fw) and not app.front
        assert str(app.query_one("#empty", Static).render()) == "Not scanned yet"
        await front(app, pilot, 0)
        clock.t += 3600
        app.tick()
        await settle(app, pilot)
        assert not scans(fw), "never a scan while another window is in front"


async def test_r3_scan_on_front_when_stale(sysroot):
    r, fw = not_in_front()
    clock = Clock()
    app = Net(runner=r, clock=clock)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await front(app, pilot, 1)                    # never scanned: stale
        assert len(scans(fw)) == 1 and len(app.query(NetRow)) == 6
        app.front_changed()                           # the same window again (a field verb rewrote the file)
        await settle(app, pilot)
        assert len(scans(fw)) == 1
        await front(app, pilot, 0)
        clock.t += 60
        await front(app, pilot, 1)                    # back after 1 min: fresh, no scan
        assert len(scans(fw)) == 1
        await front(app, pilot, 2)
        clock.t += SCAN_STALE - 59                    # 2 min + 1 s after the scan
        await front(app, pilot, 1)
        assert len(scans(fw)) == 2
        clock.t += 3600                               # staying in front: no timer scans again
        app.tick()
        await settle(app, pilot)
        assert len(scans(fw)) == 2


async def test_r3_in_front_at_start_asks_tmux_once(sysroot):
    r, fw = make()                                    # tmux says window 1; no kbd-window file yet
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        assert app.front and len(scans(fw)) == 1
        assert len(r.called("tmux", "display-message")) == 1


async def test_r3_failure_is_not_repeated(sysroot):
    r, fw = not_in_front()
    inner = r.table[("wpa_cli",)]
    r.table[("wpa_cli",)] = lambda a: "FAIL\n" if a[5:6] == ["scan"] else inner(a)
    clock = Clock()
    app = Net(runner=r, clock=clock)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await front(app, pilot, 1)
        assert len(scans(fw)) == 0 and len(r.called("wpa_cli")) > 0
        asked = [c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]]
        assert len(asked) == 1
        assert str(app.query_one("#msg", Static).render()) == "", "an automatic scan leaves the message line alone"
        assert not app.busy and app.scan_age is None
        for _ in range(3):                            # no retry: not on ticks, not on a quick return to the front
            clock.t += 30
            app.tick()
            await front(app, pilot, 0)
            await front(app, pilot, 1)
        asked = [c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]]
        assert len(asked) == 1
        clock.t += SCAN_STALE                         # a later visit, 2 min after the failed request: one more try
        await front(app, pilot, 0)
        await front(app, pilot, 1)
        asked = [c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]]
        assert len(asked) == 2


async def test_r3_tapped_rescan_reports_a_refusal(sysroot):
    r, fw = not_in_front()
    inner = r.table[("wpa_cli",)]
    r.table[("wpa_cli",)] = lambda a: "FAIL\n" if a[5:6] == ["scan"] else inner(a)
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await pilot.click("#rescan")
        await settle(app, pilot)
        assert "Rescan to try again" in str(app.query_one("#msg", Static).render())
        assert not app.busy and app.scan_age is None


async def test_r3_no_automatic_scan_when_wpa_supplicant_does_not_answer(sysroot):
    r, fw = not_in_front()
    r.table[("wpa_cli",)] = lambda a: Result(255, "Failed to connect to non-global ctrl_ifname: wlan0  "
                                                  "error: No such file or directory\n", "")
    clock = Clock()
    app = Net(runner=r, clock=clock)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        assert app.status == {}
        assert "Wi-Fi is off" in str(app.query_one("#cur", Static).render())
        for _ in range(3):
            await front(app, pilot, 1)
            await front(app, pilot, 0)
            clock.t += SCAN_STALE + 1
        await front(app, pilot, 1)
        asked = [c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]]
        assert not asked and not app.busy
        assert str(app.query_one("#msg", Static).render()) == ""


async def test_r3_failed_scan_after_a_join_keeps_the_join_message(sysroot):
    r, fw = not_in_front()
    inner = r.table[("wpa_cli",)]
    state = {"refuse": False}
    r.table[("wpa_cli",)] = lambda a: "FAIL\n" if a[5:6] == ["scan"] and state["refuse"] else inner(a)
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await pilot.click("#rescan")
        await settle(app, pilot)
        asked = len([c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]])
        row = [x for x in app.query(NetRow) if x.net["ssid"] == 'Café "Nord"'.encode()][0]
        state["refuse"] = True
        row.action_choose()
        await pilot.pause()
        app.screen.query_one("#field").value = "correct horse"
        await pilot.press("enter")
        await settle(app, pilot)
        await settle(app, pilot)
        assert len([c for c in r.calls if c[0] == "wpa_cli" and c[5:6] == ["scan"]]) == asked + 1   # it did ask
        msg = str(app.query_one("#msg", Static).render())
        assert "connected" in msg and "Rescan to try again" not in msg, msg


async def test_r3_not_automatic_with_the_hotspot_on_rescan_forces(sysroot):
    r, fw = not_in_front({("vegas-hotspot", "status"): "on: vegas-7k2, 1 device(s)\n"})
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await front(app, pilot, 1)
        assert app.front and not scans(fw)
        await pilot.click("#rescan")
        await settle(app, pilot)
        assert len(scans(fw)) == 1


async def test_r3_usb_sharing_does_not_stop_it(sysroot):
    r, fw = not_in_front({("vegas-usbshare", "status"): "on: 172.16.42.1\n"})
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await front(app, pilot, 1)
        assert len(scans(fw)) == 1


async def test_r3_not_with_the_screen_off(sysroot):
    r, fw = not_in_front()
    put(sysroot, "/run/vegas-ui/state", "off\n")
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        app._apply_status((app.status or {"wpa_state": "COMPLETED"}, {"kind": None}, []))
        await front(app, pilot, 1)
        assert not scans(fw)


async def test_r3_rescan_forces_even_when_fresh(sysroot):
    r, fw = make()
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        assert len(scans(fw)) == 1
        await pilot.click("#rescan")
        await settle(app, pilot)
        assert len(scans(fw)) == 2


# ------------------------------------------------------------------------------------------------------------ R5
async def test_r5_empty_texts(sysroot, monkeypatch):
    monkeypatch.setattr(test_net, "SCAN", HDR)
    r, fw = make()
    app = Net(runner=r, clock=Clock())
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        assert str(app.query_one("#empty", Static).render()) == "No other networks in range"
        fw.cur = None                                   # not connected any more
        app.refresh_status()
        await settle(app, pilot)
        assert str(app.query_one("#empty", Static).render()) == "No networks in range"
        await pilot.click("#rescan")
        await settle(app, pilot)
        assert str(app.query_one("#empty", Static).render()) == "No networks in range"


# ------------------------------------------------------------------------------------------------------------ R1
def test_r1_one_background():
    term = open(OVERLAY + "/usr/lib/vegas/vegas-term").read()
    assert "-o colors.background=0b0f14" in term and "-o colors.foreground=d5dbe3" in term
    sway = open(OVERLAY + "/etc/vegas/sway/config").read()
    assert re.search(r"^output DSI-1 .* bg #0b0f14 solid_color$", sway, re.M)
    from vegasui import theme
    assert theme.BG.lower() == "#0b0f14" and theme.TEXT.lower() == "#d5dbe3"
    hits = []
    for d, _, files in os.walk(OVERLAY):
        for f in files:
            p = os.path.join(d, f)
            try:
                text = open(p, encoding="utf-8").read().lower()
            except (UnicodeDecodeError, OSError):
                continue
            if "242424" in text or "1d3b53" in text:
                hits.append(p)
    assert not hits, hits


# ------------------------------------------------------------------------------------- text size change (VM shot)
async def test_bar_follows_a_text_size_change_with_the_screen_dark(sysroot, runner):
    """The 51-column VM shot: after foot restarted with another grid the brightness bar was still 26 cells, wrapped
    onto a second line (Home's resize repaint ran before the bar had its new width; dark: no 10 s refresh)."""
    app = Home(runner=runner)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        put(sysroot, "/run/vegas-ui/state", "off\n")
        for size in ((51, 49), (72, 71), (60, 56), LANDSCAPE, (51, 49)):
            await pilot.resize_terminal(*size)
            await settle(app, pilot)
            bar = app.query_one("#bar")
            text = bar.render().plain
            assert "\n" not in text and len(text) <= bar.size.width, (size, bar.size, text)
