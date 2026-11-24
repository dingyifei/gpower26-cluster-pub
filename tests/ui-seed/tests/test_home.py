"""vegas-home headless tests (Textual pilot, 60x56 cells = the phone's upright terminal)."""
import os

from conftest import put
from textual.widgets import Button, Static

from vegasui import uistatus as st
from vegasui.home import Home
from vegasui.tui import StatusRow

SIZE = (60, 56)


async def settle(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


def row(app, rid):
    r = app.query_one(f"#{rid}", StatusRow)
    return r.value, r.role, r.detail


async def test_status_rows(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert row(app, "r-bat") == ("78 % holding", "ok", "charger in · 0.0 A · band 70-80 % · 31 °C")
        assert row(app, "r-cpu") == ("41 °C", None, "no cap · 2000 / 2400 MHz")
        assert row(app, "r-wifi")[:2] == ("192.0.2.57", "ok")              # B11: the address first
        assert row(app, "r-wifi")[2] == "harbour-guest · -52 dBm ›"
        assert row(app, "r-usb") == ("172.16.42.1", None, "Mac connected")
        assert row(app, "r-root")[0] == "main" and " GB free" in row(app, "r-root")[2]
        assert row(app, "r-ssh")[0] == "1 session"
        head = str(app.query_one("#head", Static).render())
        assert "vegas5" in head and "up 3d 04:12 · 0 failed units" in head
        assert app.query_one("#ts-60", Button).has_class("on")
        assert app.query_one("#rot-normal", Button).has_class("on")
        assert [b.id for b in app.query("#wins Button")] == ["win-1", "win-2", "win-3", "win-new"]
        # nothing overflows 60 columns: every widget fits the screen width
        for w in app.query("Button, StatusRow"):
            assert w.region.right <= 60, w


def test_charge_word_order(sysroot):
    assert st.charge_word() == ("holding", "ok")
    put(sysroot, "/sys/class/power_supply/primary_chg/online", "0")
    assert st.charge_word() == ("on battery", "warn")
    put(sysroot, "/sys/class/power_supply/primary_chg/online", "1")
    put(sysroot, "/sys/class/power_supply/battery/temp", "410")
    assert st.charge_word() == ("paused: warm", "warn")
    put(sysroot, "/sys/class/power_supply/battery/capacity", "-1")
    assert st.charge_word() == ("no gauge", "limit")
    put(sysroot, "/sys/class/power_supply/battery/capacity", "100")
    put(sysroot, "/sys/class/power_supply/battery/temp", "300")
    put(sysroot, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99\n")
    put(sysroot, "/run/vegas-chargeguard/override-state", "override: STOP=100 RESUME=99 (from x)")
    bd = st.guard()
    assert (bd["stop"], bd["resume"], bd["override"]) == (100, 99, True)
    assert st.charge_word() == ("full", "ok")
    put(sysroot, "/run/vegas-chargeguard/control", "control: none")
    assert st.charge_word() == ("no charge control", "limit")


async def test_charge_to_full_without_tool(sysroot, runner):
    runner.table[("systemctl", "start")] = ""
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#charge")
        await settle(app, pilot)
        ov = sysroot / "run/vegas-chargeguard/override"
        assert ov.read_text() == "STOP=100\nRESUME=99\n"
        assert runner.called("systemctl", "start", "vegas-chargeguard.service")
        assert app.query_one("#charge", Button).has_class("on")
        assert str(app.query_one("#charge", Button).label) == "Charge full"
        await pilot.click("#charge")
        await settle(app, pilot)
        assert not ov.exists()
        assert str(app.query_one("#charge", Button).label) == "Charge 80 %"


async def test_charge_uses_vegas_charge_when_installed(sysroot, runner):
    runner.installed.add("vegas-charge")
    runner.table[("vegas-charge",)] = "charge to full until reboot\n"
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#charge")
        await settle(app, pilot)
        assert runner.called("vegas-charge", "full")
        assert not (sysroot / "run/vegas-chargeguard/override").exists()


async def test_buttons(sysroot, runner):
    runner.table[("vegas-rotate",)] = ""
    runner.table[("tmux", "select-window")] = ""
    runner.table[("kill",)] = ""
    put(sysroot, "/run/vegas-ui/term.pid", "4242\n")
    put(sysroot, "/proc/4242/comm", "foot\n")
    fifo = sysroot / "run/vegas-ui/ctl"
    fifo.write_text("")            # a plain file stands in for the FIFO
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#rot-90")
        assert runner.called("vegas-rotate", "90")
        # B8: vegas-rotate records the rotation and restarts lisgd; Home no longer repeats it
        assert not (sysroot / "run/vegas-ui/rotation").exists()
        assert not runner.called("pkill", "-x", "lisgd")
        assert app.query_one("#rot-90", Button).has_class("on")
        await pilot.click("#ts-68")
        assert (sysroot / "run/vegas-ui/fontsize").read_text().strip() == "6.25"
        assert runner.called("kill", "4242")
        await pilot.click("#bup")
        await pilot.click("#power")
        assert fifo.read_text() == "brightness up\nmenu\n"
        await pilot.click("#win-3")
        assert runner.called("tmux", "select-window", "-t", "main:3")
        await pilot.click("#r-wifi")
        assert runner.called("tmux", "select-window", "-t", "main:1")


async def test_programs_empty_and_list(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#programs")
        await pilot.pause()
        assert "No graphical programs installed" in str(app.screen.query_one("Static").render())
        await pilot.click("#c-cancel")
        runner.installed.add("zathura")
        runner.table[("swaymsg", "exec")] = ""
        await pilot.click("#programs")
        await pilot.pause()
        await pilot.click("#c-zathura")
        assert runner.called("swaymsg", "exec", "choom -n 0 -- zathura")


async def test_key_highlight(sysroot, runner):
    app = Home(runner=runner)
    hl = sysroot / "run/vegas-ui/home"
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert hl.read_text().strip() == "highlight=0" and app.focused is None
        await pilot.press("down")
        assert hl.read_text().strip() == "highlight=1" and app.has_class("keys")
        first = app.focused
        await pilot.press("down", "up")
        assert app.focused is first
        await pilot.click("#rot-normal")          # a finger tap clears the highlight
        assert hl.read_text().strip() == "highlight=0" and not app.has_class("keys")


async def test_key_enter_presses(sysroot, runner):
    runner.table[("vegas-rotate",)] = ""
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.query_one("#rot-270", Button).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert runner.called("vegas-rotate", "270")


async def test_away_not_installed(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#away")
        await pilot.pause()
        assert "vegas-away" in str(app.screen.query_one("Static").render())


async def test_wide_layout(sysroot, runner):
    app = Home(runner=runner)
    async with app.run_test(size=(130, 30)) as pilot:
        await settle(app, pilot)
        assert app.has_class("wide")
        left, right = app.query_one("#left"), app.query_one("#right")
        assert left.region.y == right.region.y and right.region.x > left.region.x


async def test_away_set_pin_then_off(sysroot, runner):
    runner.installed.add("vegas-away")
    runner.table[("vegas-away", "on")] = lambda a: (put(sysroot, "/etc/vegas/away", ""), "away on")[1]
    runner.table[("vegas-away", "off")] = lambda a: (os.remove(sysroot / "etc/vegas/away"), "away off")[1]
    from textual.widgets import Input
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#away")
        await pilot.pause()
        await pilot.press(*"12a34")                 # letters are refused by the digit field
        assert app.screen.query_one("#field", Input).value == "1234"
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*"1234", "enter")
        await settle(app, pilot)
        assert runner.called("vegas-away", "on") and (sysroot / "etc/vegas/away-pin").exists()
        assert app.query_one("#away", Button).has_class("on")
        await pilot.click("#away")
        await pilot.pause()
        await pilot.press(*"9999", "enter")
        await settle(app, pilot)
        assert not runner.called("vegas-away", "off") and "Wrong PIN" in str(app.query_one("#msg", Static).render())
        await pilot.click("#away")
        await pilot.pause()
        await pilot.press(*"1234", "enter")
        await settle(app, pilot)
        assert runner.called("vegas-away", "off")
        assert str(app.query_one("#away", Button).label) == "Away off"


async def test_windows_repaint_and_refresh_under_dialog(sysroot, runner):
    """Review fixes: a changed window list repaints without DuplicateIds; a refresh while a dialog is open updates
    the page (App.query_one would search the dialog); a window name is plain text, never markup."""
    from vegasui.tui import ChoiceScreen
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        runner.table[("tmux", "list-windows")] = "0 home\n1 net\n2 sh\n3 logs\n4 [/x]\n"
        app.refresh_status()
        await settle(app, pilot)
        assert [b.id for b in app.query("#wins Button")] == ["win-1", "win-2", "win-3", "win-4", "win-new"]
        assert str(app.query_one("#win-4", Button).label) == "4 [/x]"
        app.push_screen(ChoiceScreen("x", [("cancel", "OK")]))
        await pilot.pause()
        runner.table[("tmux", "list-windows")] = "0 home\n1 net\n2 sh\n"
        put(sysroot, "/sys/class/power_supply/battery/capacity", "50\n")
        app.refresh_status()
        await settle(app, pilot)
        await pilot.press("escape")
        await settle(app, pilot)
        assert row(app, "r-bat")[0].startswith("50 %")
        assert [b.id for b in app.query("#wins Button")] == ["win-1", "win-2", "win-new"]
