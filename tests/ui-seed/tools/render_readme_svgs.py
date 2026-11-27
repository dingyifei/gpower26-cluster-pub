"""Render the README screenshots of the vegas touch UI as SVG, from made-up data only (no phone, no network).

    .venv/bin/python tests/ui-seed/tools/render_readme_svgs.py [OUTDIR]      (default: docs/ui/img)

Needs Textual (rich comes with it); runs on a Mac or in the trixie VM. Everything shown comes from a fake sysfs tree
(VEGAS_SYSROOT) and a fake command runner built below; the clock is fixed so the output does not change between runs.
- glance.svg / glance-landscape.svg: vegas-glance's own frame() at 20 x 20 (upright) and 44 x 9 (landscape),
  its ANSI colours turned into rich Text and exported with rich's SVG writer on the glance's dark background.
- pin-pad-wait.svg / pin-pad-landscape.svg: vegas-glance's pin_frame() with vegasui.pin.wait_msg(30, wrong=True).
- home.svg / network.svg: the Textual apps (vegasui.home.Home, vegasui.net.Net) under App.run_test() at the size the
  UI tests use (60 x 56), saved with App.save_screenshot().
"""
import asyncio
import importlib.machinery
import importlib.util
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OV = os.path.join(REPO, "linux", "debian", "overlay")
UI = os.path.join(OV, "usr", "lib", "vegas", "ui")
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "docs", "ui", "img"))

NOW = time.mktime((2026, 11, 26, 9, 41, 0, 0, 0, -1))      # a fixed Thursday morning


def mac(n):
    """A locally administered address 02:00:00:00:00:<n> (built, so no MAC-shaped literal sits in the source)."""
    return ":".join(["02", "00", "00", "00", "00", "%02x" % n])


SSIDS = [  # (bssid, MHz, dBm, flags, ssid): made-up names, locally administered addresses
    (mac(1), 5180, -48, "[WPA2-PSK-CCMP][ESS]", "example-5g"),
    (mac(2), 2437, -60, "[ESS]", "cafe-guest"),
    (mac(3), 2462, -67, "[WPA2-PSK-CCMP][ESS]", "lab-net"),
    (mac(4), 5745, -74, "[SAE-CCMP][ESS]", "demo-wpa3"),
    (mac(5), 2412, -81, "[WPA2-PSK-CCMP][ESS]", "test-ap"),
]


def put(root, path, text):
    full = os.path.join(root, path.lstrip("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


def fake_tree(root):
    """78 % holding in the 70-80 band, 31 C, SoC 41 C, Wi-Fi + USB up, one SSH session, main root up 3 days."""
    b = "/sys/class/power_supply/battery/"
    for k, v in {"capacity": "78", "status": "Not charging", "current_now": "0", "temp": "312"}.items():
        put(root, b + k, v + "\n")
    put(root, "/sys/class/power_supply/primary_chg/online", "1\n")
    put(root, "/sys/class/thermal/thermal_zone0/temp", "41200\n")
    for pol, mx in (("policy0", 2000000), ("policy6", 2400000)):
        put(root, f"/sys/devices/system/cpu/cpufreq/{pol}/scaling_max_freq", f"{mx}\n")
        put(root, f"/sys/devices/system/cpu/cpufreq/{pol}/cpuinfo_max_freq", f"{mx}\n")
    put(root, "/sys/class/net/wlan0/operstate", "up\n")
    put(root, "/sys/class/net/usb0/carrier", "1\n")
    put(root, "/etc/vegas/chargeguard.conf",
        "STOP=80\nRESUME=70\nTSTOP=42\nTRESUME=40\nTOFF=55\nSOCOFF=5\nCONTROL=auto\n")
    put(root, "/run/vegas-chargeguard/want", "off\n")
    put(root, "/run/vegas-chargeguard/control", "control: cmd\n")
    put(root, "/run/vegas-chargeguard/override-state", "override: none\n")
    put(root, "/etc/vegas/root-role", "main\n")
    put(root, "/etc/hostname", "vegas-demo\n")
    put(root, "/proc/uptime", "274320.5 1000.0\n")                        # 3 d 4 h
    put(root, "/run/vegas-test/ipv4/wlan0", "192.168.1.57\n")
    put(root, "/run/vegas-test/ipv4/usb0", "172.16.42.1\n")
    put(root, "/run/vegas-test/iw-link", "Connected to " + mac(1) + " (on wlan0)\n\tSSID: example-5g\n"
                                         "\tfreq: 5180.0\n\tsignal: -48 dBm\n")
    # one established session 172.16.42.1:22 <- 172.16.42.2:51234 (little-endian hex, state 01)
    put(root, "/proc/net/tcp", "  sl  local_address rem_address   st\n"
        "   0: 012A10AC:0016 022A10AC:C822 01 00000000:00000000 00:00000000 00000000 0 0 1\n")
    os.makedirs(os.path.join(root, "run/vegas-ui"), exist_ok=True)


ROOT = tempfile.mkdtemp(prefix="vegas-readme-")
fake_tree(ROOT)
os.environ["VEGAS_SYSROOT"] = ROOT          # readers read it once, at import: set before any vegasui import
os.environ["VEGAS_UI_LIB"] = UI
sys.path.insert(0, UI)
sys.dont_write_bytecode = True

from rich.console import Console            # noqa: E402
from rich.terminal_theme import TerminalTheme   # noqa: E402
from rich.text import Text                  # noqa: E402

from vegasui import readers as R            # noqa: E402
from vegasui.host import Result             # noqa: E402
from vegasui.pin import wait_msg            # noqa: E402

_clock, _date = R.clock, R.date
R.clock = lambda t=None: _clock(NOW if t is None else t)
R.date = lambda t=None: _date(NOW if t is None else t)
R.disk_free = lambda: 28_000_000_000        # statvfs of the fake tree would report the host's own disk

_loader = importlib.machinery.SourceFileLoader("vegas_glance_readme", os.path.join(OV, "usr/lib/vegas/vegas-glance"))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
G = importlib.util.module_from_spec(_spec)
_loader.exec_module(G)


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


GLANCE_THEME = TerminalTheme(_rgb(G.BG), _rgb(G.FG), [_rgb(G.BG), _rgb(G.REDC), _rgb(G.GREENC), _rgb(G.AMBERC),
                                                      _rgb(G.DIMC), _rgb(G.DIMC), _rgb(G.DIMC), _rgb(G.FG)])


def foot_svg(rows, cols, name, title):
    """Frame rows (ANSI truecolor, as vegas-glance writes them to foot) -> an SVG of a cols-wide terminal."""
    con = Console(record=True, width=cols, file=io.StringIO(), force_terminal=True, color_system="truecolor",
                  legacy_windows=False, highlight=False)
    for row in rows:
        t = Text.from_ansi(row)
        t.pad_right(max(0, cols - t.cell_len))
        con.print(t, no_wrap=True, crop=True, overflow="crop")
    path = os.path.join(OUT, name)
    con.save_svg(path, title=title, theme=GLANCE_THEME)
    return path


def glance_data():
    d = G.gather(with_tools=False)
    d["ssh"] = 1
    return d


class FakeRunner:
    """Answers the commands Home and Network run from a table (longest argv prefix wins); anything else rc 127."""

    def __init__(self, table):
        self.table = table

    def run(self, argv, timeout=10, input=None):
        argv = list(argv)
        best = max((k for k in self.table if tuple(argv[:len(k)]) == k), key=len, default=None)
        if best is None:
            return Result(127, "", f"{argv[0]}: not faked")
        v = self.table[best]
        v = v(argv) if callable(v) else v
        return v if isinstance(v, Result) else Result(0, v, "")

    def which(self, name):
        return False

    def sleep(self, s):
        pass


def fake_wpa(argv):
    """wpa_cli -p ... -i wlan0 <cmd>: associated to example-5g, five networks in range."""
    a = argv[5:]
    c = a[0] if a else ""
    if c == "status":
        return ("bssid=" + mac(1) + "\nfreq=5180\nssid=example-5g\nid=0\nkey_mgmt=WPA2-PSK\n"
                "wpa_state=COMPLETED\nip_address=192.168.1.57\n")
    if c == "signal_poll":
        return "RSSI=-48\nLINKSPEED=433\n"
    if c == "scan_results":
        return "bssid / frequency / signal level / flags / ssid\n" + "".join(
            "%s\t%d\t%d\t%s\t%s\n" % s for s in SSIDS)
    if c == "list_networks":
        return "network id / ssid / bssid / flags\n0\texample-5g\tany\t[CURRENT]\n1\tlab-net\tany\t\n"
    if c in ("scan", "set", "save_config"):
        return "OK\n"
    return "FAIL\n"


TABLE = {
    ("ip", "-4", "-br", "addr", "show", "wlan0"): "wlan0  UP  192.168.1.57/24 \n",
    ("ip", "-4", "-br", "addr", "show", "usb0"): "usb0  UP  172.16.42.1/24 \n",
    ("iw", "dev", "wlan0", "link"): "Connected to " + mac(1) + " (on wlan0)\n\tSSID: example-5g\n"
                                    "\tfreq: 5180.0\n\tsignal: -48 dBm\n",
    ("ss",): "0 0 172.16.42.1:22 172.16.42.2:51234\n",
    ("systemctl", "--failed"): "",
    ("df",): "  Avail\n28000000000\n",
    ("tmux", "list-windows"): "0 home\n1 net\n2 sh\n3 logs\n",
    ("tmux", "display-message"): "1\n",
    ("vegas-hotspot", "status"): "off\n",
    ("vegas-usbshare", "status"): "off\n",
    ("swaymsg", "-t", "get_outputs"): '[{"name":"DSI-1","transform":"normal"}]',
    ("systemd-run",): "",
    ("systemctl", "stop"): "",
    ("pgrep",): Result(1, "", ""),
    ("wpa_cli",): fake_wpa,
}


async def textual_svg(app, size, name, title):
    async with app.run_test(size=size) as pilot:
        for _ in range(4):
            await app.workers.wait_for_complete()
            await pilot.pause()
        app.title = title
        app.save_screenshot(name, OUT)
    return os.path.join(OUT, name)


async def textual_shots():
    from vegasui.home import Home
    from vegasui.net import Net
    from vegasui import wpa
    wpa._spawn_detached = lambda argv: None     # never a real join-guard sleeper
    return [await textual_svg(Home(runner=FakeRunner(TABLE)), (60, 56), "home.svg", "vegas Home"),
            await textual_svg(Net(runner=FakeRunner(TABLE), clock=lambda: 1000.0), (60, 56), "network.svg",
                              "vegas Network")]


def main():
    os.makedirs(OUT, exist_ok=True)
    d = glance_data()
    done = [foot_svg(G.frame(d, 20, 20, "glance"), 20, "glance.svg", "glance"),
            foot_svg(G.frame(d, 44, 9, "glance"), 44, "glance-landscape.svg", "glance, landscape")]
    put(ROOT, "/run/vegas-ui/pin", "n=0 max=6 hl=- ask=- msg=%s\n" % wait_msg(30, wrong=True))
    done += [foot_svg(G.frame(d, 20, 20, "pin"), 20, "pin-pad-wait.svg", "PIN pad"),
             foot_svg(G.frame(d, 44, 9, "pin"), 44, "pin-pad-landscape.svg", "PIN pad, landscape")]
    done += asyncio.run(textual_shots())
    for p in done:
        print("%7d  %s" % (os.path.getsize(p), os.path.relpath(p, REPO)))


if __name__ == "__main__":
    main()
