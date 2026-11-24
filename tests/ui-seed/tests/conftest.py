"""Fixtures for the vegas-home / vegas-net tests: a fake sysfs tree (VEGAS_SYSROOT) and a fake command runner.

Run in the trixie VM:  orb -m vegas-deb python3 -m pytest -q <this dir>
"""
import os
import sys

import pytest

OVERLAY = "/path/to/repo/linux/debian/overlay"
sys.path.insert(0, OVERLAY + "/usr/lib/vegas/ui")

from vegasui.host import Result  # noqa: E402


class FakeRunner:
    """Answers commands from a table: key = tuple prefix of argv, value = str | Result | callable(argv)->Result.
    Longest matching prefix wins. Every call is recorded in .calls. Unknown commands -> rc 127."""

    def __init__(self, table=None, installed=()):
        self.table = dict(table or {})
        self.installed = set(installed)
        self.calls = []

    def run(self, argv, timeout=10, input=None):
        argv = list(argv)
        self.calls.append(argv)
        best = None
        for k in self.table:
            if tuple(argv[:len(k)]) == k and (best is None or len(k) > len(best)):
                best = k
        if best is None:
            return Result(127, "", f"{argv[0]}: not faked")
        v = self.table[best]
        if callable(v):
            v = v(argv)
        return v if isinstance(v, Result) else Result(0, v, "")

    def which(self, name):
        return name in self.installed

    def sleep(self, s):
        pass

    def called(self, *prefix):
        return [c for c in self.calls if tuple(c[:len(prefix)]) == prefix]


def put(root, path, text):
    full = os.path.join(str(root), path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


@pytest.fixture(autouse=True)
def no_real_join_guard(monkeypatch):
    """A test must never start a real guard: no detached `sleep 60; exec vegas-net --restore` (one run before
    systemd-run was faked left nine of them in the VM, running the installed vegas-net). A test that wants the
    fallback passes its own spawn to JoinGuard."""
    from vegasui import wpa

    def refuse(argv):
        raise OSError("tests: no real join-guard sleeper")
    monkeypatch.setattr(wpa, "_spawn_detached", refuse)


@pytest.fixture
def sysroot(tmp_path, monkeypatch):
    from vegasui import readers
    monkeypatch.setenv("VEGAS_SYSROOT", str(tmp_path))
    monkeypatch.setattr(readers, "ROOT", str(tmp_path))      # readers reads the env var once, at import
    return make_tree(tmp_path)


def make_tree(tmp_path):
    """A #5-like fake tree: 78 % holding in the 70-80 band, 31 C, SoC 41 C, Wi-Fi + USB up, main root."""
    b = "/sys/class/power_supply/battery/"
    for k, v in {"capacity": "78", "status": "Not charging", "current_now": "0", "temp": "312"}.items():
        put(tmp_path, b + k, v + "\n")
    put(tmp_path, "/sys/class/power_supply/primary_chg/online", "1\n")
    put(tmp_path, "/sys/class/thermal/thermal_zone0/temp", "41200\n")
    for pol, mx in (("policy0", 2000000), ("policy6", 2400000)):
        put(tmp_path, f"/sys/devices/system/cpu/cpufreq/{pol}/scaling_max_freq", f"{mx}\n")
        put(tmp_path, f"/sys/devices/system/cpu/cpufreq/{pol}/cpuinfo_max_freq", f"{mx}\n")
    put(tmp_path, "/sys/class/net/wlan0/operstate", "up\n")
    put(tmp_path, "/sys/class/net/usb0/carrier", "1\n")
    put(tmp_path, "/etc/vegas/chargeguard.conf",
        "STOP=80        # %\nRESUME=70\nTSTOP=42\nTRESUME=40\nTOFF=55\nSOCOFF=5\nCONTROL=auto\n")
    put(tmp_path, "/run/vegas-chargeguard/want", "off\n")
    put(tmp_path, "/run/vegas-chargeguard/control", "control: cmd\n")
    put(tmp_path, "/run/vegas-chargeguard/override-state", "override: none\n")
    put(tmp_path, "/etc/vegas/root-role", "main\n")
    put(tmp_path, "/etc/hostname", "vegas5\n")
    put(tmp_path, "/proc/uptime", "274320.5 1000.0\n")
    # readers' test hooks: addresses and the iw link as plain files; SSH sessions from /proc/net/tcp
    put(tmp_path, "/run/vegas-test/ipv4/wlan0", "192.0.2.57\n")
    put(tmp_path, "/run/vegas-test/ipv4/usb0", "172.16.42.1\n")
    put(tmp_path, "/run/vegas-test/iw-link", "Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: harbour-guest\n"
                                             "\tfreq: 5180.0\n\tsignal: -52 dBm\n")
    # one established session 172.16.42.1:22 <- 172.16.42.2:51234 (little-endian hex, state 01)
    put(tmp_path, "/proc/net/tcp", "  sl  local_address rem_address   st\n"
        "   0: 012A10AC:0016 022A10AC:C822 01 00000000:00000000 00:00000000 00000000 0 0 1\n")
    os.makedirs(tmp_path / "run/vegas-ui", exist_ok=True)
    return tmp_path


BASE = {
    ("ip", "-4", "-br", "addr", "show", "wlan0"): "wlan0  UP  192.0.2.57/24 \n",
    ("ip", "-4", "-br", "addr", "show", "usb0"): "usb0  UP  172.16.42.1/24 \n",
    ("iw", "dev", "wlan0", "link"): "Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: harbour-guest\n"
                                    "\tfreq: 5180.0\n\tsignal: -52 dBm\n",
    ("ss",): "0 0 172.16.42.1:22 172.16.42.2:51234\n",
    ("systemctl", "--failed"): "",
    ("df",): "  Avail\n28000000000\n",
    ("tmux", "list-windows"): "0 home\n1 net\n2 sh\n3 logs\n",
    ("vegas-hotspot", "status"): "off\n",
    ("vegas-usbshare", "status"): "off\n",
    ("swaymsg", "-t", "get_outputs"): '[{"name":"DSI-1","transform":"normal"}]',
    # join guard (wpa.JoinGuard): a transient timer; never a real one (or the detached fallback) from a test
    ("systemd-run",): "",
    ("systemctl", "stop"): "",
    ("pgrep",): Result(1, "", ""),          # no program running
}


@pytest.fixture
def runner():
    return FakeRunner(BASE)
