#!/usr/bin/env python3
"""Farm: maintain racked phones over adb. Unrooted by default; root only on demand.

    .venv/bin/python scripts/farm.py                    # TUI (dashboard)
    .venv/bin/python scripts/farm.py status [--json]    # one-shot table (for scripts / Claude)
    .venv/bin/python scripts/farm.py run <action> [serial ...|all]
    .venv/bin/python scripts/farm.py connect <ip[:port]> ...   # adb over the network (e.g. USB NCM)

Targets are adb serials, so a phone on USB (ZL83...) and one over the network (10.x.x.x:5555) look the same.
Actions run existing scripts (scripts/phone.sh, scripts/reroot.sh), in parallel across phones:
  wake park record charge-protect      no root
  root                                 temp root (reroot.sh); then protected + ram (one-time config, idempotent)
  protected ram                        need a root session
  reboot                               plain reboot (temp root is gone afterwards)
All racked phones are end state D. Serials listed in farm-exclude.txt (experiment units, e.g. the Linux route-B
phone) are skipped by `status`, `run ... all` and the TUI; name a serial explicitly to reach it anyway.

TUI keys: space select · a select all · w wake · p park · c charge-protect · r root session · b reboot
          e record · g refresh · q quit
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHONE = ROOT / "scripts" / "phone.sh"
REROOT = ROOT / "scripts" / "reroot.sh"

PROBE = r"""
echo "sn=$(getprop ro.serialno)"
echo "bat=$(cat /sys/class/power_supply/battery/capacity)"
echo "chg=$(cat /sys/class/power_supply/battery/status)"
echo "btemp=$(cat /sys/class/power_supply/battery/temp)"
echo "cap=$(dumpsys battery | grep -oE 'mUpperLimit:-?[0-9]+' | cut -d: -f2)"
echo "cpu=$(dumpsys thermalservice | grep -m1 -oE 'mValue=[0-9.]+, mType=0' | grep -oE '[0-9.]+' | head -1)"
echo "up=$(cut -d. -f1 /proc/uptime)"
echo "mem=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)"
echo "uid=$(id -u)"
echo "carrier=$(getprop ro.carrier)"
echo "vbs=$(getprop ro.boot.verifiedbootstate)"
echo "ota=$(dumpsys package com.motorola.ccc.ota | grep -m1 -E '^ +User 0:' | grep -oE 'enabled=[0-9]+' | cut -d= -f2)"
echo "wifi=$(settings get global wifi_on)"
echo "data=$(settings get global mobile_data)"
echo "wake=$(dumpsys power | grep -m1 -oE 'mWakefulness=[A-Za-z]+' | cut -d= -f2)"
echo "ip=$(ip -4 -o addr show 2>/dev/null | awk '$2!="lo"{print $2":"$4}' | tr '\n' ' ')"
"""
COLS = ["serial", "bat", "chg", "cap", "btemp", "cpu", "mem", "up", "root", "end", "ota", "net", "wake", "ip"]
EXCLUDE_FILE = ROOT / "farm-exclude.txt"


def excluded() -> set[str]:
    """Serials taken out of farm maintenance (experiment units). One serial per line, '#' comments."""
    try:
        return {ln.split("#", 1)[0].strip() for ln in EXCLUDE_FILE.read_text().splitlines()} - {""}
    except FileNotFoundError:
        return set()


def adb_devices() -> dict[str, str]:
    """adb devices, minus excluded serials (name them explicitly to reach them anyway)."""
    out = {}
    skip = excluded()
    try:
        for ln in subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=10).stdout.splitlines()[1:]:
            p = ln.split()
            if len(p) >= 2 and p[0] not in skip:
                out[p[0]] = p[1]
    except Exception:
        pass
    return out


def probe(serial: str) -> dict:
    row: dict = {"serial": serial}
    try:
        r = subprocess.run(["adb", "-s", serial, "shell", PROBE], capture_output=True, text=True, timeout=25,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        row["err"] = "timeout"
        return row
    for ln in r.stdout.replace("\r", "").splitlines():
        k, _, v = ln.partition("=")
        if k:
            row[k.strip()] = v.strip()
    if not row.get("sn"):
        row["err"] = (r.stderr or r.stdout).strip()[:60] or "no data"
    return row


def fmt(row: dict) -> dict:
    """Probe row -> display strings."""
    if row.get("err"):
        return {"serial": row["serial"], "bat": "?", "chg": row["err"]}
    up = int(row.get("up") or 0)
    vbs, car = row.get("vbs", ""), row.get("carrier", "")
    end = "A" if vbs == "orange" else ("D" if vbs == "green" and car == "retus" else f"{vbs}/{car}")
    try:
        bt = f"{int(row.get('btemp') or 0) / 10:.0f}°"
    except ValueError:
        bt = "?"
    cpu = row.get("cpu") or ""
    return {
        "serial": row["serial"] + ("" if row.get("sn") in (None, "", row["serial"]) else f" ({row['sn']})"),
        "bat": f"{row.get('bat', '?')}%",
        "chg": {"Not charging": "hold", "Charging": "chg", "Discharging": "dis", "Full": "full"}.get(row.get("chg", ""), row.get("chg", "")),
        "cap": "80" if row.get("cap") == "80" else (row.get("cap") or "-"),
        "btemp": bt,
        "cpu": f"{float(cpu):.0f}°" if cpu else "",
        "mem": f"{int(row.get('mem') or 0) / 1024:.1f}G",
        "up": f"{up // 86400}d{up % 86400 // 3600:02d}h" if up >= 86400 else f"{up // 3600}h{up % 3600 // 60:02d}m",
        "root": "root" if row.get("uid") == "0" else "-",
        "end": end,
        "ota": {"3": "off", "2": "off", "0": "ON", "1": "ON"}.get(row.get("ota", ""), row.get("ota") or "absent"),
        "net": ("W" if row.get("wifi") == "1" else "") + ("D" if row.get("data") == "1" else "") or "off",
        "wake": row.get("wake", ""),
        "ip": row.get("ip", ""),
    }


def status(serials: list[str] | None = None) -> list[dict]:
    devs = adb_devices()
    targets = serials or [s for s, st in devs.items() if st == "device"]
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(probe, targets))
    for s, st in devs.items():
        if st != "device" and (not serials or s in serials):
            rows.append({"serial": s, "err": st})
    return rows


def action_cmds(action: str, serial: str) -> list[list[str]]:
    if action in ("wake", "park", "record", "charge-protect", "protected", "ram"):
        return [[str(PHONE), action, serial]]
    if action == "root":
        return [[str(REROOT), serial], [str(PHONE), "protected", serial], [str(PHONE), "ram", serial]]
    if action == "reboot":
        return [["adb", "-s", serial, "reboot"]]
    raise SystemExit(f"unknown action {action}")


def run_action(action: str, serial: str) -> tuple[str, int, str]:
    out, rc = [], 0
    for cmd in action_cmds(action, serial):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, stdin=subprocess.DEVNULL)
        out.append(r.stdout + r.stderr)
        rc = r.returncode
        if rc:
            break
    return serial, rc, "".join(out)


def cli() -> None:
    ap = argparse.ArgumentParser(description="farm maintenance over adb")
    sub = ap.add_subparsers(dest="cmd")
    st = sub.add_parser("status"); st.add_argument("serials", nargs="*"); st.add_argument("--json", action="store_true")
    ru = sub.add_parser("run"); ru.add_argument("action"); ru.add_argument("serials", nargs="*")
    co = sub.add_parser("connect"); co.add_argument("addrs", nargs="+")
    sub.add_parser("tui")
    a = ap.parse_args()
    if a.cmd in (None, "tui"):
        return tui()
    if a.cmd == "connect":
        for ad in a.addrs:
            ad = ad if ":" in ad else ad + ":5555"
            print(subprocess.run(["adb", "connect", ad], capture_output=True, text=True).stdout.strip())
        return
    if a.cmd == "status":
        rows = status(a.serials or None)
        if a.json:
            print(json.dumps(rows, indent=1)); return
        disp = [fmt(r) for r in rows]
        w = {c: max(len(c), *(len(str(d.get(c, ""))) for d in disp)) if disp else len(c) for c in COLS}
        print("  ".join(c.ljust(w[c]) for c in COLS))
        for d in disp:
            print("  ".join(str(d.get(c, "")).ljust(w[c]) for c in COLS))
        return
    if a.cmd == "run":
        devs = adb_devices()
        targets = [s for s, stt in devs.items() if stt == "device"] if a.serials in ([], ["all"]) else a.serials
        with ThreadPoolExecutor(max_workers=8) as ex:
            for s, rc, out in ex.map(lambda s: run_action(a.action, s), targets):
                print(f"===== {s}: {a.action} -> {'OK' if rc == 0 else f'FAILED ({rc})'}")
                print("\n".join(ln for ln in out.splitlines() if re.search(r"PASS|FAIL|WARN|ROOT|error|!!", ln)))


def tui() -> None:
    from textual import work
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import DataTable, Footer, Header, RichLog

    class Farm(App):
        TITLE = "gpower2026 farm"
        CSS = "#tbl { height: 1fr; } #log { height: 14; border-top: solid $accent; }"
        BINDINGS = [Binding("space", "toggle", "Select"), Binding("a", "all", "All"),
                    Binding("w", "act('wake')", "Wake"), Binding("p", "act('park')", "Park"),
                    Binding("c", "act('charge-protect')", "80% cap"), Binding("r", "act('root')", "Root session"),
                    Binding("b", "act('reboot')", "Reboot"), Binding("e", "act('record')", "Record"),
                    Binding("g", "refresh", "Refresh"), Binding("q", "quit", "Quit")]

        def __init__(self) -> None:
            super().__init__()
            self.sel: set[str] = set()
            self.rows: list[dict] = []

        def compose(self) -> ComposeResult:
            yield Header()
            yield DataTable(id="tbl", cursor_type="row", zebra_stripes=True)
            yield RichLog(id="log", wrap=True, max_lines=3000)
            yield Footer()

        def on_mount(self) -> None:
            self.t = self.query_one("#tbl", DataTable)
            self.lg = self.query_one("#log", RichLog)
            self.t.add_columns("✓", *COLS)
            self.set_interval(20, self.action_refresh)
            self.action_refresh()

        @work(thread=True, exclusive=True, group="probe")
        def action_refresh(self) -> None:
            rows = status()
            self.call_from_thread(self._show, rows)

        def _show(self, rows: list[dict]) -> None:
            self.rows = rows
            cur = self.t.cursor_row
            self.t.clear()
            for r in rows:
                d = fmt(r)
                self.t.add_row("●" if r["serial"] in self.sel else " ", *[str(d.get(c, "")) for c in COLS], key=r["serial"])
            if rows:
                self.t.move_cursor(row=min(cur, len(rows) - 1))

        def _cur(self) -> str | None:
            if not self.rows:
                return None
            return self.rows[min(self.t.cursor_row, len(self.rows) - 1)]["serial"]

        def action_toggle(self) -> None:
            s = self._cur()
            if s:
                self.sel ^= {s}
                self._show(self.rows)

        def action_all(self) -> None:
            ids = {r["serial"] for r in self.rows}
            self.sel = set() if self.sel == ids else ids
            self._show(self.rows)

        def action_act(self, action: str) -> None:
            targets = sorted(self.sel) or ([self._cur()] if self._cur() else [])
            if targets:
                self.lg.write(f"$ {action} -> {', '.join(targets)}")
                self._run(action, targets)

        @work(thread=True, group="act")
        def _run(self, action: str, targets: list[str]) -> None:
            with ThreadPoolExecutor(max_workers=8) as ex:
                for s, rc, out in ex.map(lambda s: run_action(action, s), targets):
                    lines = [ln for ln in out.splitlines() if re.search(r"PASS|FAIL|WARN|ROOT|error|!!", ln)]
                    self.call_from_thread(self.lg.write, f"{s} {action}: {'OK' if rc == 0 else f'FAILED ({rc})'}")
                    for ln in lines[-8:]:
                        self.call_from_thread(self.lg.write, "   " + ln.strip())
            self.call_from_thread(self.action_refresh)

    Farm().run()


if __name__ == "__main__":
    cli()
