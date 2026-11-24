"""Follow-up to the 23 Nov rulings on Home (review of the integrated build): B1 Away never claims protection that is
not in force (/run/vegas-ui/away-ssh = open -> red), the vegas-away line shown as returned (warn when it says OPEN),
the SCREEN row follows a rotation made elsewhere at the resize (not at the next 10 s refresh), and an unknown
battery temperature reads "? °C" like "? A"."""
from conftest import put
from textual.widgets import Button

from vegasui.home import Home
from vegasui.theme import AMBER, DIM, RED
from vegasui.tui import StatusRow
from test_rulings_home import SIZE, colours, settle


async def test_b1_away_with_ssh_open_is_red(sysroot, runner):
    put(sysroot, "/etc/vegas/away", "")
    put(sysroot, "/run/vegas-ui/away-ssh", "open\n")
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        away = app.query_one("#away", Button)
        assert str(away.label) == "Away on" and away.has_class("on") and away.has_class("alarm")
        ssh = app.query_one("#r-ssh", StatusRow)
        assert ssh.detail == "ssh root@192.0.2.57 · OPEN on Wi-Fi"
        assert colours(ssh)["OPEN on Wi-Fi"] == RED and colours(ssh)["ssh root@192.0.2.57"] == DIM
        assert str(away.styles.background.hex).upper() == RED.upper()
        # the boot unit closes it later (or `vegas-away status` finds it closed): back to the plain amber Away
        put(sysroot, "/run/vegas-ui/away-ssh", "closed\n")
        app.refresh_status()
        await settle(app, pilot)
        assert not away.has_class("alarm") and away.has_class("on")
        assert ssh.detail == "ssh root@192.0.2.57"
        assert str(away.styles.background.hex).upper() == AMBER.upper()


async def test_b1_unknown_or_away_off_shows_nothing_extra(sysroot, runner):
    put(sysroot, "/run/vegas-ui/away-ssh", "open\n")          # `off` writes open: Away off, so no warning
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert not app.query_one("#away", Button).has_class("alarm")
        assert "OPEN" not in app.query_one("#r-ssh", StatusRow).detail
        put(sysroot, "/etc/vegas/away", "")
        (sysroot / "run/vegas-ui/away-ssh").unlink()           # missing file: unknown, nothing extra
        app.refresh_status()
        await settle(app, pilot)
        assert app.query_one("#away", Button).has_class("on")
        assert not app.query_one("#away", Button).has_class("alarm")


async def test_b1_vegas_away_line_as_returned(sysroot, runner):
    """`vegas-away on` with the IPv6 fallback says so; its line is shown as returned. A refusal shows stderr's last
    line (why Away stays off) in amber."""
    from vegasui import pin
    from vegasui.host import Result
    runner.installed.add("vegas-away")
    pin.set_pin("1234")
    runner.table[("vegas-away", "on")] = lambda a: (put(sysroot, "/etc/vegas/away", ""),
                                                   "away on: SSH closed except USB/VPN; IPv6 off on Wi-Fi\n")[1]
    said = []
    app = Home(runner=runner)
    app.say = lambda text, role=None: said.append((text, role))
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#away")
        await settle(app, pilot)
        assert said[-1] == ("away on: SSH closed except USB/VPN; IPv6 off on Wi-Fi", None)
    (sysroot / "etc/vegas/away").unlink()
    runner.table[("vegas-away", "on")] = Result(1, "", "vegas-away: ip6tables-legacy rules failed\n"
                                                       "vegas-away: SSH over IPv6 could not be closed; Away stays off\n")
    said = []
    app = Home(runner=runner)
    app.say = lambda text, role=None: said.append((text, role))
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#away")
        await settle(app, pilot)
        assert said[-1] == ("vegas-away: SSH over IPv6 could not be closed; Away stays off", "warn")
        assert not app.query_one("#away", Button).has_class("on")


async def test_screen_row_follows_rotation_made_elsewhere(sysroot, runner):
    """integ-smoke 08: after `vegas-rotate 90` from elsewhere, SCREEN still said upright for up to 10 s."""
    put(sysroot, "/run/vegas-ui/rotation", "normal\n")
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert app.query_one("#rot-normal", Button).has_class("on")
        n = len(runner.called("systemctl", "--failed"))
        put(sysroot, "/run/vegas-ui/rotation", "90\n")           # vegas-rotate wrote it; then the terminal resized
        await pilot.resize_terminal(132, 22)
        await pilot.pause()
        await pilot.pause()
        assert app.query_one("#rot-90", Button).has_class("on")
        assert not app.query_one("#rot-normal", Button).has_class("on")
        assert len(runner.called("systemctl", "--failed")) == n   # a file read only, no new gather


async def test_unknown_battery_temperature_has_its_unit(sysroot, runner):
    (sysroot / "sys/class/power_supply/battery/temp").unlink()
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert app.query_one("#r-bat", StatusRow).detail.endswith(" · ? °C")


async def test_b1_status_line_with_open_is_warn(sysroot, runner):
    """A line that says OPEN (e.g. a `vegas-away on` whose check found SSH open) is never shown plain."""
    from vegasui import pin
    runner.installed.add("vegas-away")
    pin.set_pin("1234")
    runner.table[("vegas-away", "on")] = "on (SSH OPEN on Wi-Fi over IPv6; PIN set)\n"
    said = []
    app = Home(runner=runner)
    app.say = lambda text, role=None: said.append((text, role))
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#away")
        await settle(app, pilot)
        assert said[-1] == ("on (SSH OPEN on Wi-Fi over IPv6; PIN set)", "warn")


async def test_screen_row_follows_rotation_file_written_after_the_resize(sysroot, runner):
    """vegas-rotate writes the file just AFTER the transform (the resize can come first): the inotify watch on
    /run/vegas-ui (CLOSE_WRITE) moves the SCREEN row when the file is written, with no gather."""
    import asyncio
    put(sysroot, "/run/vegas-ui/rotation", "normal\n")
    app = Home(runner=runner)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        n = len(runner.called("systemctl", "--failed"))
        await pilot.resize_terminal(132, 22)
        await pilot.pause()
        assert app.query_one("#rot-normal", Button).has_class("on")      # file not written yet
        with open(sysroot / "run/vegas-ui/rotation", "w") as f:          # like `echo 90 > rotation`
            f.write("90\n")
        for _ in range(20):
            await asyncio.sleep(0.05)
            await pilot.pause()
            if app.query_one("#rot-90", Button).has_class("on"):
                break
        assert app.query_one("#rot-90", Button).has_class("on")
        assert not app.query_one("#rot-normal", Button).has_class("on")
        assert len(runner.called("systemctl", "--failed")) == n
