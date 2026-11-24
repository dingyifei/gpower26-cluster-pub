"""Readers for the Vegas status values (UI spec 1.1; design page "Status data", corrected with #5 facts).
The one reader module (designer ruling B3): the strip and the report (vegas-status), the glance (vegas-glance) and
Home/Network (through the thin adapters in vegasui.uistatus) all read through these functions, and format the shared
values with the fmt_* / *_role helpers at the end, so no two views can disagree on a value or its colour.

Every absolute path goes through p(), which prefixes $VEGAS_SYSROOT (default empty) so the readers run in the VM
against a fake tree. Functions marked "forks" run a program; everything else is a few file reads or syscalls and is
cheap enough for the strip. Traps kept here: never read primary_chg/type (stale); read named power_supply files only
(listing every property logs kernel errors); USB link = usb0 carrier only (the address stays without a cable);
capacity -1 = no gauge; never the load average (vendor kthreads hold it near 14).
"""
import fcntl
import os
import re
import socket
import struct
import subprocess
import time

ROOT = os.environ.get("VEGAS_SYSROOT", "")
BAT = "/sys/class/power_supply/battery"
CHG = "/sys/class/power_supply/primary_chg/online"
GUARD = "/run/vegas-chargeguard"
GUARD_CONF = "/etc/vegas/chargeguard.conf"
UI = "/run/vegas-ui"
SBIN = os.environ.get("VEGAS_SBIN", "/usr/local/sbin")


def p(path):
    return ROOT + path      # ROOT is read at each call: tests may monkeypatch readers.ROOT


def rd(path, default=None):
    try:
        with open(p(path)) as f:
            return f.read().strip()
    except (OSError, UnicodeDecodeError):
        return default


def rint(path):
    try:
        return int(rd(path))
    except (TypeError, ValueError):
        return None


def exists(path):
    return os.path.exists(p(path))


def run(argv, timeout=3):
    """forks: stdout of a program, or None if it is missing, fails or hangs."""
    try:
        r = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=timeout, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def tool(name):
    return os.path.join(SBIN, name)


# ---------------------------------------------------------------- battery and the charge guard
def battery():
    """soc (0..100 or None = no gauge), status, temp (degC float or None), current (A, + = into the battery),
    online (1/0/None)."""
    soc = rint(BAT + "/capacity")
    t10 = rint(BAT + "/temp")
    ua = rint(BAT + "/current_now")
    return {
        "soc": soc if soc is not None and 0 <= soc <= 100 else None,
        "status": rd(BAT + "/status", ""),
        "temp": t10 / 10 if t10 is not None else None,
        "current": ua / 1e6 if ua is not None else None,
        "online": rint(CHG),
    }


def _conf_numbers(path):
    out = {}
    for line in (rd(path, "") or "").splitlines():
        m = re.match(r"\s*([A-Z]+)=([0-9]+)\b", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def guard():
    """The guard's view: band STOP/RESUME (override applied), TRESUME, want (None = guard has not run yet),
    control ('cmd'/'qpnp'/'none'/None), override (True while charge-to-full is in force)."""
    c = {"STOP": 80, "RESUME": 70, "TSTOP": 42, "TRESUME": 40}
    c.update(_conf_numbers(GUARD_CONF))
    ostate = rd(GUARD + "/override-state", "") or ""
    override = False
    m = re.match(r"override: STOP=(\d+) RESUME=(\d+)", ostate)
    if m and exists(GUARD + "/override"):   # the guard validated it; the file gone = switched back, not yet applied
        c["STOP"], c["RESUME"], override = int(m.group(1)), int(m.group(2)), True
    ctl = rd(GUARD + "/control")
    return {
        "stop": c["STOP"], "resume": c["RESUME"], "tstop": c["TSTOP"], "tresume": c["TRESUME"],
        "want": rd(GUARD + "/want"),
        "control": ctl.split(":", 1)[1].strip() if ctl and ":" in ctl else None,
        "override": override,
        "override_ignored": ostate.startswith("WARNING"),
    }


# ---------------------------------------------------------------- processor
_zone = None


def soc_zone():
    """The soc_max thermal zone (what vegas-thermal reads), else thermal_zone0 (fallback only). Every view reads the
    SoC temperature here (B3): the strip, Home, the report and the glance."""
    global _zone
    if _zone is None:
        _zone = "/sys/class/thermal/thermal_zone0"
        try:
            for z in sorted(os.listdir(p("/sys/class/thermal"))):
                if z.startswith("thermal_zone") and rd("/sys/class/thermal/%s/type" % z) == "soc_max":
                    _zone = "/sys/class/thermal/" + z
                    break
        except OSError:
            pass
    return _zone


def soc_temp():
    v = rint(soc_zone() + "/temp")
    return round(v / 1000) if v is not None else None


def cpu_cap():
    """(cap % = min over policies of scaling_max/cpuinfo_max, MHz of the first policy, MHz of the last) or None."""
    base = "/sys/devices/system/cpu/cpufreq"
    try:
        pols = sorted((d for d in os.listdir(p(base)) if d.startswith("policy")), key=lambda d: int(d[6:]))
    except (OSError, ValueError):
        return None
    caps, mhz = [], []
    for d in pols:
        s, m = rint("%s/%s/scaling_max_freq" % (base, d)), rint("%s/%s/cpuinfo_max_freq" % (base, d))
        if s and m:
            caps.append(min(100, round(100 * s / m)))
            mhz.append(s // 1000)
    if not caps:
        return None
    return min(caps), mhz[0], mhz[-1]


# ---------------------------------------------------------------- network
def operstate(ifname):
    return rd("/sys/class/net/%s/operstate" % ifname)


def carrier(ifname):
    return rint("/sys/class/net/%s/carrier" % ifname) == 1


def ipv4(ifname):
    """IPv4 address of an interface by ioctl (no fork), or None."""
    if ROOT:   # test tree: a plain file
        return rd("/run/vegas-test/ipv4/" + ifname)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            r = fcntl.ioctl(s.fileno(), 0x8915, struct.pack("256s", ifname.encode()[:15]))  # SIOCGIFADDR
            return socket.inet_ntoa(r[20:24])
    except OSError:
        return None


def wifi_link():
    """forks (iw): {'ssid','dbm','freq'} of wlan0's association, or {} when not associated."""
    out = rd("/run/vegas-test/iw-link") if ROOT else run(["iw", "dev", "wlan0", "link"])
    if not out or not out.startswith("Connected"):
        return {}
    info = {}
    for line in out.splitlines():
        k, _, v = line.strip().partition(": ")
        if k == "SSID":
            info["ssid"] = v
        try:
            if k == "signal":
                info["dbm"] = int(float(v.split()[0]))
            elif k == "freq":
                info["freq"] = int(float(v.split()[0]))
        except (ValueError, IndexError):   # an iw format change must not crash the report
            pass
    return info


def wifi():
    """{'up': bool, 'addr': str|None}: cheap (operstate + ioctl)."""
    up = operstate("wlan0") == "up"
    return {"up": up, "addr": ipv4("wlan0") if up else None}


def usb():
    return {"link": carrier("usb0"), "addr": ipv4("usb0")}


def usbshare_on():
    """Cheap check: the /run networkd file vegas-usbshare writes (its 'status' also checks the NAT rule)."""
    return exists("/run/systemd/network/05-usb0-share.network")


def hotspot(cheap_only=False):
    """None when no hotspot; else {'kind': 'wifi'|'usb', 'ssid', 'devices', 'text'}.
    Wi-Fi: /run/vegas-hotspot exists only while the AP unit runs; then (forks) `vegas-hotspot status`
    -> 'on: <ssid>, N device(s)'. USB: the vegas-usbshare /run file."""
    if exists("/run/vegas-hotspot"):
        if cheap_only:
            return {"kind": "wifi", "ssid": None, "devices": None, "text": "on"}
        out = run([tool("vegas-hotspot"), "status"]) or ""
        m = re.match(r"on: (.*), (\d+) device", out)
        if m:
            return {"kind": "wifi", "ssid": m.group(1), "devices": int(m.group(2)), "text": out}
        if out == "off":
            return None
        return {"kind": "wifi", "ssid": None, "devices": None, "text": out or "on"}
    if usbshare_on():
        return {"kind": "usb", "ssid": None, "devices": None, "text": "on"}
    return None


def _hexaddr(h):
    """/proc/net/tcp{,6} address 'XXXXXXXX:PPPP' -> 'a.b.c.d' (IPv4 or v4-mapped IPv6) or an IPv6 string."""
    a = h.split(":")[0]
    raw = b"".join(bytes.fromhex(a[i:i + 8])[::-1] for i in range(0, len(a), 8))   # host-order 32-bit words
    if len(raw) == 16 and raw[:12] == b"\0" * 10 + b"\xff\xff":
        raw = raw[12:]
    return socket.inet_ntop(socket.AF_INET if len(raw) == 4 else socket.AF_INET6, raw)


def ssh_sessions():
    """[(local address, remote address)] of established TCP connections to local port 22 (no fork)."""
    out = []
    for f in ("/proc/net/tcp", "/proc/net/tcp6"):
        for line in (rd(f, "") or "").splitlines()[1:]:
            parts = line.split()
            if len(parts) > 3 and parts[3] == "01" and parts[1].endswith(":0016"):
                try:
                    out.append((_hexaddr(parts[1]), _hexaddr(parts[2])))
                except ValueError:
                    out.append(("?", "?"))
    return out


# ---------------------------------------------------------------- system
def hostname():
    return rd("/etc/hostname") or socket.gethostname()


def root_role():
    """'main' on the main root, 'rescue' otherwise (no /etc/vegas/root-role)."""
    return "main" if rd("/etc/vegas/root-role") == "main" else "rescue"


def rescue_pending():
    return exists("/rescue")


def away():
    return exists("/etc/vegas/away")


def away_ssh():
    """'closed' | 'open' | None (unknown): /run/vegas-ui/away-ssh, written by vegas-away on/off/apply/status (no
    fork). Ruling B1: with Away on and this "open" (the boot unit could not close SSH on Wi-Fi for IPv4 or IPv6),
    every view shows a red warning instead of claiming protection; a missing file shows nothing extra."""
    v = rd(UI + "/away-ssh")
    return v if v in ("closed", "open") else None


def away_open():
    """Away is on but SSH is open on Wi-Fi (B1): the red warning on the strip, glance, report and Home."""
    return away() and away_ssh() == "open"


def kbd_shown():
    return rd(UI + "/kbd", "shown") != "hidden"


def uptime_s():
    try:
        return float(rd("/proc/uptime").split()[0])
    except (AttributeError, ValueError, IndexError):
        return None


def debian_version():
    v = rd("/etc/debian_version", "")
    return v.split(".")[0] if v else "?"


def failed_units():
    """forks (systemctl)."""
    out = run(["systemctl", "--failed", "--plain", "--no-legend"])
    return None if out is None else len([l for l in out.splitlines() if l.strip()])


def disk_free():
    try:
        s = os.statvfs(p("/") if ROOT else "/")
        return s.f_bavail * s.f_frsize
    except OSError:
        return None


# ---------------------------------------------------------------- formatting
def fmt_uptime(s, short=False):
    if s is None:
        return "?"
    d, r = divmod(int(s), 86400)
    h, m = divmod(r // 60, 60)
    if short:
        return "%dd" % d if d else "%dh" % h if h else "%dm" % m
    return ("%dd " % d if d else "") + "%02d:%02d" % (h, m)


def fmt_gb(b):
    return "?" if b is None else "%d GB" % (b // 10**9)


def band(g):
    return "%d-%d %%" % (g["resume"], g["stop"])


def clock(t=None):
    return time.strftime("%H:%M", time.localtime(t))


def date(t=None):
    """'Mon 23 Nov' (the glance's top line)."""
    tm = time.localtime(t)
    return "%s %d %s" % (time.strftime("%a", tm), tm.tm_mday, time.strftime("%b", tm))


def fmt_amps(a):
    """Battery current, one format on strip, Home, report and glance (B3): signed when not zero ("+1.1 A",
    "-0.3 A"), "0.0 A" at zero (anything that rounds to 0.0, so never "+0.0" or "-0.0"), "? A" when unknown."""
    if a is None:
        return "? A"
    s = "%+.1f A" % a
    return "0.0 A" if s[1:] == "0.0 A" else s


def fmt_deg(t, space=True):
    """A temperature in whole degC: "31 °C" (report, Home) or "31°C" (space=False: the 20-column glance). Unknown:
    "? °C" with space (like "? A"), a bare "?" in the glance."""
    if t is None:
        return "? °C" if space else "?"
    return ("%.0f °C" if space else "%.0f°C") % t


# ---------------------------------------------------------------- colour rules (one place; B3/B4)
# Roles are the keys of theme.ROLE and tui.ROLE: "ok" green, "warn" amber, "limit" red, "dim", None = the view's
# plain colour. A warning is never dim (B4): a view that prints a value in a dim line still colours it by its role.
def bat_level_role(soc):
    """Battery level: red at <= 5 % or no gauge, amber at <= 15 %."""
    return "limit" if soc is None or soc <= 5 else "warn" if soc <= 15 else None


def bat_temp_role(t, word=None):
    """Battery temperature: amber at 40 degC (or while the charging word is "paused: warm"), red at 42 (the guard
    stops charging)."""
    if t is not None and t >= 42:
        return "limit"
    return "warn" if (t is not None and t >= 40) or word == "paused: warm" else None


def soc_temp_role(t):
    """SoC temperature: amber at 70 degC, red at 80."""
    return None if t is None else "limit" if t >= 80 else "warn" if t >= 70 else None


def cap_role(pct):
    """CPU cap: red while below 100 % (a limit is active)."""
    return "limit" if pct is not None and pct < 100 else None


def charger(online):
    """(text, role) for primary_chg/online: 1 "charger in", 0 "on battery" (amber), missing "charger ?" (amber)."""
    return {1: ("charger in", None), 0: ("on battery", "warn")}.get(online, ("charger ?", "warn"))
