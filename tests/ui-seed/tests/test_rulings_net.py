"""Designer rulings of 23 Nov on Network: B2 join guard (the old network comes back within 60 s even if vegas-net
dies mid-join, no reboot), B6 no refresh while dark, B7 hotspot passphrase through `vegas-hotspot newpass`,
B10 OWE labelled and refused like 802.1X."""
import json
import os
import subprocess
import sys

import pytest
from conftest import put
from textual.widgets import Input, Static

import test_net
from test_net import make, settle
from vegasui import net as netmod, wpa
from vegasui.host import Result
from vegasui.net import Net, NetRow

SIZE = (60, 56)
DEAD = 2 ** 22 + 7        # above pid_max: never a live process


class Died(BaseException):
    """vegas-net killed in the middle of a join (BaseException: nothing in the join catches it)."""


def rec(sysroot):
    p = sysroot / "run/vegas-ui/net-join"
    return json.loads(p.read_text()) if p.exists() else None


def die_after_select(r):
    """Wrap the fake wpa_cli so the process 'dies' right after select_network of a new network."""
    inner = r.table[("wpa_cli",)]

    def f(argv):
        out = inner(argv)
        if argv[5:6] == ["select_network"] and argv[6] != "0":
            raise Died()
        return out
    r.table[("wpa_cli",)] = f


# ---------------------------------------------------------------------------------------------------------- B10
def test_b10_owe_is_not_open():
    assert wpa.security("[WPA2-OWE-CCMP][ESS]") == "OWE"
    assert wpa.security("[RSN-OWE-CCMP][ESS]") == "OWE"
    assert wpa.security("[ESS][OWE-TRANS]") == "open"        # the open half of a transition pair is open
    assert wpa.security("[WPA2-PSK-CCMP][ESS]") == "WPA2"
    assert wpa.security("[WPA2-EAP-CCMP][ESS]") == "802.1X"
    assert wpa.security("[WEP][ESS]") == "WEP"
    r, fw = make()
    assert wpa.Wpa(r).join_new(b"x", "OWE") == (False, "OWE networks are not supported yet.")


async def test_b10_owe_row_and_tap(sysroot, monkeypatch):
    monkeypatch.setattr(test_net, "SCAN", test_net.SCAN + "aa:00:00:00:00:0b\t2412\t-30\t[WPA2-OWE-CCMP][ESS]\towe-cafe\n")
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        row = [x for x in app.query(NetRow) if x.net["ssid"] == b"owe-cafe"][0]
        assert "● OWE" in str(row.render()) and "○" not in str(row.render())
        row.action_choose()
        await pilot.pause()
        text = " ".join(str(s.render()) for s in app.screen.query(Static))
        assert "owe-cafe: OWE" in text and "not supported yet" in text
        assert not app.screen.query(Input)                   # no passphrase asked, nothing joined
        assert not any(c[5:6] == ["add_network"] for c in r.calls if c[0] == "wpa_cli")


# ---------------------------------------------------------------------------------------------------------- B7
async def test_b7_newpass_goes_through_the_tool(sysroot):
    r, fw = make(extra={("vegas-hotspot", "newpass"): "new passphrase set\n"})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.click("#moreopts")
        await pilot.pause()
        await pilot.click("#c-newpass")
        await settle(app, pilot)
        assert r.called("vegas-hotspot", "newpass")
        assert not (sysroot / "etc/vegas/hotspot.conf").exists()      # vegas-net never writes it
        assert "New passphrase set" in str(app.query_one("#msg", Static).render())


async def test_b7_tool_output_never_on_the_message_line(sysroot):
    r, fw = make(extra={("vegas-hotspot", "newpass"): Result(1, "PSK=leakyleaky99\n", "PSK=leakyleaky99\n")})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.new_hotspot_pass()
        await settle(app, pilot)
        msg = str(app.query_one("#msg", Static).render())
        assert "leaky" not in msg and "failed (exit 1)" in msg
    r, fw = make()                                     # an old vegas-hotspot without the verb / not installed
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        r.table[("vegas-hotspot", "newpass")] = Result(127, "", "vegas-hotspot: not installed")
        app.new_hotspot_pass()
        await settle(app, pilot)
        assert "not installed" in str(app.query_one("#msg", Static).render())


async def test_b7_refused_while_the_hotspot_is_on(sysroot):
    r, fw = make(extra={("vegas-hotspot", "status"): "on: vegas-7k2, 1 device(s)\n"})
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        app.new_hotspot_pass()
        await pilot.pause()
        assert "Turn the hotspot off first" in " ".join(str(s.render()) for s in app.screen.query(Static))
        assert not r.called("vegas-hotspot", "newpass")


# ---------------------------------------------------------------------------------------------------------- B2
def guarded(r):
    return wpa.Wpa(r, wpa.JoinGuard(r))


def test_b2_guard_armed_before_select_and_disarmed_on_success(sysroot):
    r, fw = make()
    seen = {}

    def spy(argv):
        if argv[5:6] == ["select_network"]:
            seen["rec_at_select"] = rec(sysroot)
        return fw(argv)
    r.table[("wpa_cli",)] = spy
    ok, msg = guarded(r).join_new(b"n8", "WPA2", "correct horse")
    assert ok
    g = seen["rec_at_select"]
    assert (g["old"], g["new"], g["added"], g["pid"]) == (0, 1, True, os.getpid())
    assert "correct horse" not in json.dumps(g) and "n8" not in json.dumps(g)      # ids and a token only
    (call,) = r.called("systemd-run")
    assert f"--on-active={wpa.GUARD_SECS}" in call and call[-3:] == ["/usr/local/bin/vegas-net", "--restore", g["token"]]
    assert f"--unit=vegas-net-guard-{g['token']}" in call and "--collect" in call
    assert rec(sysroot) is None                                                   # disarmed
    assert r.called("systemctl", "stop", f"vegas-net-guard-{g['token']}.timer")
    assert oct((sysroot / "run/vegas-ui").stat().st_mode & 0o777) in ("0o700", "0o755")


def test_b2_failed_join_selects_the_old_network_explicitly(sysroot):
    r, fw = make(join="never")
    ok, msg = guarded(r).join_new(b"cafe-lumen", "open")
    assert not ok and "back on the old network" in msg
    log = [c for c in fw.log if c[0] in ("select_network", "enable_network", "remove_network")]
    assert log == [["select_network", "1"], ["remove_network", "1"], ["select_network", "0"],
                   ["enable_network", "all"]]
    assert fw.cur == 0 and set(fw.nets) == {0} and fw.saves == 0 and rec(sysroot) is None


def test_b2_connect_saved_failure_goes_back(sysroot):
    r, fw = make(join="never")
    fw.nets[1] = {"ssid": "other", "flags": "", "prio": 0, "psk": None}
    ok, msg = guarded(r).connect(1)
    assert not ok and fw.cur == 0 and 1 in fw.nets          # a saved network is never removed
    assert ["select_network", "0"] in fw.log and fw.log[-1] == ["enable_network", "all"]


def test_b2_vegas_net_dies_mid_join_then_the_guard_fires(sysroot):
    """The property: with vegas-net dead after select_network, the timer's `vegas-net --restore <token>` puts the
    old network back (no reboot)."""
    r, fw = make(join="never")
    die_after_select(r)
    with pytest.raises(Died):
        guarded(r).join_new(b"cafe-lumen", "open")
    g = rec(sysroot)
    assert g and fw.cur is None and "[DISABLED]" in fw.nets[0]["flags"]          # stranded, as before the fix
    r.table[("wpa_cli",)] = fw
    assert wpa.heal(wpa.Wpa(r), wpa.JoinGuard(r), token="0000") == "stale"        # another join's timer: no-op
    assert fw.cur is None
    assert wpa.heal(wpa.Wpa(r), wpa.JoinGuard(r), token=g["token"]) == "restored"
    assert fw.cur == 0 and set(fw.nets) == {0} and "[DISABLED]" not in fw.nets[0]["flags"]
    assert rec(sysroot) is None


def test_b2_guard_keeps_a_join_that_worked(sysroot):
    r, fw = make(join="ok")
    die_after_select(r)
    with pytest.raises(Died):
        guarded(r).join_new(b"n8", "WPA2", "correct horse")
    r.table[("wpa_cli",)] = fw
    assert wpa.heal(wpa.Wpa(r), wpa.JoinGuard(r), token=rec(sysroot)["token"]) == "kept"
    assert fw.cur == 1 and fw.saves == 1 and rec(sysroot) is None


async def test_b2_respawned_vegas_net_heals_at_start(sysroot):
    r, fw = make(join="never")
    die_after_select(r)
    with pytest.raises(Died):
        guarded(r).join_new(b"cafe-lumen", "open")
    g = rec(sysroot)
    g["pid"] = DEAD
    put(sysroot, "/run/vegas-ui/net-join", json.dumps(g))
    r.table[("wpa_cli",)] = fw
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert fw.cur == 0 and set(fw.nets) == {0} and rec(sysroot) is None
        assert "interrupted join was undone" in str(app.query_one("#msg", Static).render())


async def test_b2_every_start_runs_enable_network_all(sysroot):
    r, fw = make()
    fw.nets[0]["flags"] = "[CURRENT]"
    fw.nets[1] = {"ssid": "other", "flags": "[DISABLED]", "prio": 0, "psk": None}
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert ["enable_network", "all"] in fw.log and fw.nets[1]["flags"] == ""


async def test_b2_start_leaves_a_live_join_alone(sysroot):
    """A second vegas-net (say over SSH) starting while the first is joining must not undo that join."""
    r, fw = make()
    put(sysroot, "/run/vegas-ui/net-join", json.dumps({"pid": os.getppid(), "old": 0, "new": 5, "added": True,
                                                       "token": "abc", "unit": None, "pgid": None}))
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        assert rec(sysroot)["token"] == "abc"
        assert not any(c[0] in ("enable_network", "select_network", "remove_network") for c in fw.log)
    assert guarded(r).join_new(b"n8", "WPA2", "correct horse")[1].startswith("Another vegas-net is joining")


def test_b2_detached_sleeper_when_systemd_run_fails(sysroot):
    """No systemd-run: a sleeper in its own session; success kills it (only if its cmdline carries the token)."""
    r, fw = make(extra={("systemd-run",): Result(1, "", "Failed to start transient timer unit")})
    procs = []

    def spawn(argv):
        assert argv[:2] == ["sh", "-c"] and argv[2].startswith(f"sleep {wpa.GUARD_SECS}; exec /usr/local/bin/vegas-net --restore ")
        p = subprocess.Popen(["sleep", "30"], start_new_session=True)
        put(sysroot, f"/proc/{p.pid}/cmdline", "\0".join(argv))        # the fake /proc holds the real argv
        procs.append(p)
        return p
    w = wpa.Wpa(r, wpa.JoinGuard(r, spawn=spawn))
    seen = {}
    inner = r.table[("wpa_cli",)]
    r.table[("wpa_cli",)] = lambda a: (seen.setdefault("rec", rec(sysroot)) if a[5:6] == ["select_network"]
                                       else None, inner(a))[1]
    assert w.join_new(b"n8", "WPA2", "correct horse")[0]
    assert seen["rec"]["pgid"] == procs[0].pid and seen["rec"]["unit"] is None
    assert procs[0].wait(timeout=5) is not None and rec(sysroot) is None


def test_b2_restore_entry_point(sysroot, monkeypatch):
    r, fw = make(join="never")
    die_after_select(r)
    with pytest.raises(Died):
        guarded(r).join_new(b"cafe-lumen", "open")
    r.table[("wpa_cli",)] = fw
    monkeypatch.setattr(netmod, "Runner", lambda: r)
    monkeypatch.setattr(sys, "argv", ["vegas-net", "--restore", rec(sysroot)["token"]])
    with pytest.raises(SystemExit) as e:
        netmod.main()
    assert e.value.code == 0 and fw.cur == 0 and rec(sysroot) is None


# ---------------------------------------------------------------------------------------------------------- B6
async def test_b6_net_skips_refresh_while_dark(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        n = len(r.calls)
        put(sysroot, "/run/vegas-ui/state", "off\n")
        app.tick()
        await settle(app, pilot)
        assert len(r.calls) == n
        put(sysroot, "/run/vegas-ui/state", "on\n")
        app.tick()
        await settle(app, pilot)
        assert r.called("vegas-hotspot", "status") and len(r.calls) > n


async def test_net_head_follows_rotation(sysroot):
    r, fw = make()
    app = Net(runner=r)
    async with app.run_test(size=SIZE) as pilot:
        await settle(app, pilot)
        await pilot.resize_terminal(132, 22)
        await settle(app, pilot)
        head = app.query_one("#head", Static).render().plain
        assert head.startswith("Network ") and head.rstrip().endswith("scanned just now") and len(head) > 100


def test_b2_old_network_back_within_60_s():
    """Review 23 Nov: the property is "the old network is BACK within 60 s", not "going back starts at 60 s".
    The guard (vegas-net died) fires at GUARD_SECS, `vegas-net --restore` starts (RESTORE_START) and waits up to
    BACK_SECS for the old network; vegas-net's own deadline comes before the guard so the guard never cuts a live
    join short."""
    assert wpa.GUARD_SECS + wpa.RESTORE_START + wpa.BACK_SECS <= 60
    assert wpa.WAIT_SECS + wpa.BACK_SECS <= 60
    assert wpa.WAIT_SECS < wpa.GUARD_SECS



def test_b2_back_to_waits_at_most_back_secs():
    """back_to polls the old network at most BACK_SECS times (one runner.sleep(1) each), then enables all."""
    sleeps = []

    class R:
        def run(self, argv, timeout=10, input=None):
            if argv[-1] == "list_networks":
                return Result(0, "network id / ssid / bssid / flags\n0\told\tany\t[DISABLED]\n")
            if argv[-1] == "status":
                return Result(0, "wpa_state=SCANNING\n")      # the old network never comes back
            return Result(0, "OK\n")

        def sleep(self, s):
            sleeps.append(s)
    assert wpa.Wpa(R()).back_to(0) is False
    assert len(sleeps) == wpa.BACK_SECS
