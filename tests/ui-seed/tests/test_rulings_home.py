"""Designer rulings of 23 Nov on Home (and the shared tui pieces): B4 warnings never dim, B6 no refresh while the
screen is off, B9 a running program is switched to, ruling 8 keyboard only while a text field is open, and the
layout fitting 60x56 upright and 132x22 landscape with the keyboard hidden."""
import os

from conftest import put
from textual.widgets import Button, Input

from vegasui import tui
from vegasui.home import Home
from vegasui.theme import AMBER, DIM, RED
from vegasui.tui import StatusRow

SIZE = (60, 56)


async def settle(app, pilot):
    for _ in range(2):
        await app.workers.wait_for_complete()
        await pilot.pause()


def colours(row: StatusRow) -> dict:
    """{text of a second-line segment: colour} from the rendered row."""
    t = row.render()
    second = t.plain.index("\n")
    out = {}
    for sp in t.spans:
        if sp.start > second:
            out[t.plain[sp.start:sp.end]] = str(sp.style)
    return out


async def test_b4_warnings_keep_their_colour_in_the_dim_line(sysroot, runner):
    put(sysroot, "/rescue", "")                                                     # rescue pending
    put(sysroot, "/sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq", "1800000\n")   # cap 75 %
    put(sysroot, "/sys/class/power_supply/battery/temp", "412\n")                   # 41.2 degC: amber
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        root, cpu, bat = (app.query_one(f"#{i}", StatusRow) for i in ("r-root", "r-cpu", "r-bat"))
        assert root.detail.startswith("rescue pending · disk in /data")
        assert colours(root)["rescue pending"] == AMBER and colours(root)["disk in /data"] == DIM
        assert colours(cpu)["cap 75 %"] == RED and colours(cpu)["2000 / 1800 MHz"] == DIM
        assert colours(bat)["41 °C"] == AMBER and colours(bat)["band 70-80 %"] == DIM
        put(sysroot, "/sys/class/power_supply/battery/temp", "425\n")               # 42.5 degC: red
        put(sysroot, "/sys/devices/system/cpu/cpufreq/policy6/scaling_max_freq", "2400000\n")
        app.refresh_status()
        await settle(app, pilot)
        assert colours(bat)["42 °C"] == RED
        assert cpu.detail.startswith("no cap") and colours(cpu)["no cap"] == DIM


async def test_b3_current_format(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        for ua, txt in (("1100000", "+1.1 A"), ("-300000", "-0.3 A"), ("40000", "0.0 A"), ("-40000", "0.0 A")):
            put(sysroot, "/sys/class/power_supply/battery/current_now", ua + "\n")
            app.refresh_status()
            await settle(app, pilot)
            assert app.query_one("#r-bat", StatusRow).detail.split(" · ")[1] == txt


def _gathers(runner):
    return len(runner.called("systemctl", "--failed"))


async def test_b6_no_refresh_while_dark_then_one_at_once(sysroot, runner):
    """vegas-keys writes /run/vegas-ui/state by rename; with it 'off' the 10 s tick forks nothing; the write of
    'on' brings one refresh at once (inotify), not at the next tick."""
    state = sysroot / "run/vegas-ui/state"

    def write_state(s):
        tmp = str(state) + ".tmp"
        with open(tmp, "w") as f:
            f.write(s + "\n")
        os.replace(tmp, state)
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert app._ino is not None                       # Linux: the inotify watch is up
        n = _gathers(runner)
        calls = len(runner.calls)
        write_state("off")
        await pilot.pause()
        app.tick()
        app.tick()
        await settle(app, pilot)
        assert len(runner.calls) == calls and app.stale  # nothing forked while dark
        write_state("on")
        for _ in range(20):
            await pilot.pause(0.05)
            await app.workers.wait_for_complete()
            if _gathers(runner) > n:
                break
        assert _gathers(runner) == n + 1 and not app.stale
        app.tick()                                        # screen on: the tick refreshes again
        await settle(app, pilot)
        assert _gathers(runner) == n + 2


async def test_b6_poll_fallback_without_inotify(sysroot, runner, monkeypatch):
    def no_inotify(*a, **k):
        raise OSError("no inotify")
    monkeypatch.setattr(tui.ctypes, "CDLL", no_inotify)
    put(sysroot, "/run/vegas-ui/state", "off\n")
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert app._ino is None and app._wake_poll is not None
        n = _gathers(runner)
        app.tick()
        app._wake_check()                                 # still off: nothing
        await settle(app, pilot)
        assert _gathers(runner) == n and app.stale
        put(sysroot, "/run/vegas-ui/state", "glance\n")
        app._wake_check()
        await settle(app, pilot)
        assert _gathers(runner) == n + 1 and not app.stale


async def test_b6_dark_clears_key_highlight(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.press("down")
        assert app.has_class("keys")
        put(sysroot, "/run/vegas-ui/state", "off\n")
        app.tick()
        assert not app.has_class("keys")
        assert (sysroot / "run/vegas-ui/home").read_text().strip() == "highlight=0"


async def test_b9_running_program_switches_to_workspace_2(sysroot, runner):
    runner.installed.update({"firefox-esr", "zathura"})
    runner.table[("swaymsg", "exec")] = ""
    runner.table[("swaymsg", "workspace")] = ""
    runner.table[("pgrep", "-x", "firefox-esr")] = "4321\n"     # Firefox runs, zathura does not
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#programs")
        await pilot.pause()
        assert str(app.screen.query_one("#c-firefox-esr", Button).label) == "Firefox · running"
        assert str(app.screen.query_one("#c-zathura", Button).label) == "PDF viewer (zathura)"
        await pilot.click("#c-firefox-esr")
        await pilot.pause()
        assert runner.called("swaymsg", "workspace", "2")
        assert not runner.called("swaymsg", "exec")
        await pilot.click("#programs")
        await pilot.pause()
        await pilot.click("#c-zathura")
        await pilot.pause()
        assert runner.called("swaymsg", "exec", "choom -n 0 -- zathura")
        assert not any("exit" in c or "reload" in c for c in runner.called("swaymsg"))   # D10


async def test_ruling8_keyboard_only_while_a_field_is_open(sysroot, runner):
    """The PIN fields: the keyboard comes up with the field (pid file for the tmux hook) and goes away after."""
    runner.installed.add("vegas-away")
    runner.table[("vegas-away", "on")] = lambda a: (put(sysroot, "/etc/vegas/away", ""), "away on")[1]
    field = sysroot / "run/vegas-ui/kbd-field-home"
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert not runner.called("pkill", "-USR2")        # nothing shows the keyboard on Home by itself
        await pilot.click("#away")
        await pilot.pause()
        assert isinstance(app.screen.query_one("#field"), Input)
        assert field.read_text().strip() == str(os.getpid())
        assert (sysroot / "run/vegas-ui/kbd").read_text().strip() == "shown"
        await pilot.press(*"1234", "enter")               # first PIN -> the second field opens: still shown
        await pilot.pause()
        assert field.exists() and (sysroot / "run/vegas-ui/kbd").read_text().strip() == "shown"
        await pilot.press(*"1234", "enter")
        await settle(app, pilot)
        assert not field.exists()
        assert (sysroot / "run/vegas-ui/kbd").read_text().strip() == "hidden"
        await pilot.click("#away")                        # Away is on: the PIN to turn it off, then Cancel
        await pilot.pause()
        assert field.exists()
        await pilot.press("escape")
        await pilot.pause()
        assert not field.exists() and (sysroot / "run/vegas-ui/kbd").read_text().strip() == "hidden"


def _fits(app, width, height):
    scroll = app.query_one(tui.Scroll)
    assert scroll.max_scroll_y == 0, f"Home scrolls at {width}x{height}: {scroll.virtual_size}"
    for w in app.query("Button, StatusRow"):
        assert w.region.right <= width and w.region.bottom <= height, (w, w.region)


async def test_fits_upright_keyboard_hidden(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        app.say("Charging to full until reboot (temperature limits still apply)")
        await pilot.pause()
        _fits(app, 60, 56)


async def test_fits_landscape_keyboard_hidden(sysroot, runner):
    runner.table[("tmux", "list-windows")] = "0 home\n1 net\n2 sh\n3 logs\n4 build\n"
    app = Home(runner=runner)
    async with app.run_test(size=(132, 22)) as pilot:
        await settle(app, pilot)
        app.say("Back to the 70-80 % band")
        await pilot.pause()
        assert app.has_class("wide")
        left, right, right2 = (app.query_one(f"#{i}") for i in ("left", "right", "right2"))
        assert left.region.y == right.region.y == right2.region.y
        assert left.region.x < right.region.x < right2.region.x
        _fits(app, 132, 22)
        # the 2x2 travel block: every label shown whole
        for bid in ("away", "charge", "programs", "power"):
            b = app.query_one(f"#{bid}", Button)
            assert b.region.width >= len(str(b.label)) + 2, (bid, b.region)
        assert len(app.query_one("#bar").render().plain.strip()) <= app.query_one("#bar").region.width
        # the head line spans the full width after the resize
        assert app.query_one("#head").render().plain.rstrip().endswith("failed units")
        assert len(app.query_one("#head").render().plain.rstrip()) > 100


async def test_rotate_resize_repaints(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=(60, 56)) as pilot:
        await settle(app, pilot)
        await pilot.resize_terminal(132, 22)
        await settle(app, pilot)
        assert app.has_class("wide") and len(app.query_one("#head").render().plain.rstrip()) > 100
        await pilot.resize_terminal(60, 56)
        await settle(app, pilot)
        assert not app.has_class("wide")
        _fits(app, 60, 56)


def test_statusrow_plain_detail_and_segments():
    r = StatusRow("X")
    r.set("v", None, [("a", None), ("b", "warn"), ("", None)])
    assert r.detail == "a · b" and r.segs == (("a", None), ("b", "warn"))
    r.set("v", None, "plain")
    assert r.detail == "plain"


def test_no_rotation_writes_left_in_home():
    import inspect
    from vegasui import home
    src = inspect.getsource(home)
    assert "pkill" not in src and 'ui_write("rotation' not in src
