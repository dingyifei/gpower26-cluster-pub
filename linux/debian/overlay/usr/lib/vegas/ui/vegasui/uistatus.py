"""Status values as Home and Network show them (spec 1.1 / 1.2): thin adapters over vegasui.readers and
vegasui.charge, the strip's own readers, so the strip, Home and the glance read the same files the same way.

The readers keep the #5 traps (named sysfs files only, never primary_chg/type, USB link = carrier, capacity -1 = no
gauge, never the load average) and prefix every path with $VEGAS_SYSROOT for tests. Only values that come from a
command the tests must fake go through the injectable runner: the sharing tools' status lines (designer point 4: the
Network page shows what vegas-hotspot / vegas-usbshare report, not a /run file) and the failed-unit count.
"""
import re

from . import charge, readers as R
from .host import exists, read

# One format and one colour rule for every view (B3/B4), re-exported for Home/Network.
fmt_amps = R.fmt_amps
fmt_deg = R.fmt_deg
bat_level_role = R.bat_level_role
bat_temp_role = R.bat_temp_role
soc_temp_role = R.soc_temp_role
cap_role = R.cap_role

CG = "/run/vegas-chargeguard"


def battery():
    """cap (soc % or None), temp, amps, online: True (charger in), False (on battery) or None (primary_chg/online
    unreadable; shown "charger ?" in amber, like the report and the glance)."""
    b = R.battery()
    return {"cap": b["soc"], "temp": b["temp"], "amps": b["current"],
            "online": None if b["online"] is None else b["online"] == 1}


def guard():
    """stop/resume (override applied), tresume, want, control, override - readers.guard()."""
    return R.guard()


def charge_word():
    """(word, role) per spec 1.2 - the same rule list the strip and the glance use."""
    w, role, _glyph = charge.word(R.battery(), R.guard())
    return w, role


def charge_mode():
    """As `vegas-charge status`: 'band', 'full' (override file present, applied or pending) or 'ignored'."""
    if not exists(f"{CG}/override"):
        return "band"
    return "ignored" if (read(f"{CG}/override-state", "") or "").startswith("WARNING") else "full"


soc_temp = R.soc_temp
hostname = R.hostname
root_role = R.root_role
rescue_pending = R.rescue_pending
away_on = R.away
away_open = R.away_open     # B1: Away on but SSH open on Wi-Fi (red warning)


def cpu_cap():
    """(percent, 'first / last MHz'); 100 = no cap."""
    c = R.cpu_cap()
    return (100, "? MHz") if c is None else (c[0], f"{c[1]} / {c[2]} MHz")


def wifi():
    """{'up','ip','ssid','dbm','freq'} for wlan0 (never names ccmni*). up = link up and an IPv4 address."""
    w = R.wifi()
    link = R.wifi_link() if w["up"] else {}
    return {"up": w["up"] and w["addr"] is not None, "ip": w["addr"],
            "ssid": link.get("ssid"), "dbm": link.get("dbm"), "freq": link.get("freq")}


def usb():
    u = R.usb()
    return {"link": u["link"], "ip": u["addr"] or "172.16.42.1"}


def ssh_local_addrs():
    """Local addresses of established SSH sessions; len() = session count."""
    return [local for local, _remote in R.ssh_sessions()]


def uptime():
    return R.fmt_uptime(R.uptime_s())


def disk_free():
    return R.fmt_gb(R.disk_free()) + " free"


def failed_units(runner):
    r = runner.run(["systemctl", "--failed", "--plain", "--no-legend"], timeout=5)
    return len([l for l in r.out.splitlines() if l.strip()]) if r.rc in (0, 1) else None


def hotspot(runner):
    """{'kind': None|'wifi'|'usb', 'ssid', 'devices', 'usb'} from the tools' own status lines (both need root).
    Both kinds can be on at once (the tools allow it); kind names the Wi-Fi one first. 'uplink': False when a tool
    that is on says ", no uplink" (ruling R9: wlan0 lost its address; sharing stays on until its timer)."""
    h = {"kind": None, "ssid": None, "devices": 0, "usb": None, "uplink": True}
    out = runner.run(["vegas-hotspot", "status"], timeout=6).out.strip()
    m = re.match(r"on: (.*), (\d+) device", out)
    if m:
        h.update(kind="wifi", ssid=m.group(1), devices=int(m.group(2)))
        h["uplink"] = not out.endswith(", no uplink")
    out = runner.run(["vegas-usbshare", "status"], timeout=6).out.strip()
    if out.startswith("on"):
        h["usb"] = out
        h["kind"] = h["kind"] or "usb"
        h["uplink"] = h["uplink"] and not out.endswith(", no uplink")
    return h


# ------------------------------------------------------------------------------------------------ Home detail lines
# Home's second (dim) line of a status row, as segments [(text, role)], joined with SEP. role None = the line's own
# dim colour; any other role is a warning or limit and is drawn in its colour inside the dim line (B4: a warning is
# never dim). The same rules colour the glance and the report. Render with tui.ROLE (role -> colour); plain() gives
# the uncoloured text (width, tests).
SEP = " · "


def plain(segs, sep=SEP):
    return sep.join(t for t, _ in segs)


def battery_detail(b, band, word=None):
    """b = battery(), band = guard(), word = the charging word. -> e.g.
    [("charger in", None), ("+1.1 A", None), ("band 70-80 %", None), ("41 °C", "warn")]."""
    online = None if b.get("online") is None else int(bool(b["online"]))
    return [R.charger(online),
            (R.fmt_amps(b.get("amps")), None),
            ("band %d-%d %%" % (band["resume"], band["stop"]), None),
            (R.fmt_deg(b.get("temp")), R.bat_temp_role(b.get("temp"), word))]


def cpu_detail(pct, mhz):
    """cpu_cap() -> [("cap 80 %", "limit"), ("2000 / 1800 MHz", None)], or "no cap" (plain) at 100 %."""
    return [("no cap", None) if pct is None or pct >= 100 else ("cap %d %%" % pct, "limit"), (mhz, None)]


def root_detail(rescue, disk):
    """[("rescue pending", "warn")?, ("disk in /data", None), (disk_free(), None)]."""
    return ([("rescue pending", "warn")] if rescue else []) + [("disk in /data", None), (disk, None)]
