"""wpa_supplicant control for vegas-net through wpa_cli (spec 4.1-4.3, D14: no NetworkManager, no new service).

Same pattern as linux/tools/wifi-conf.sh: SSIDs always go to wpa_supplicant as hex, WPA2 passphrases are hashed on
the phone (PBKDF2-SHA1, 4096, 32 bytes) and only the hash is stored, save_config only after a join worked.
wpa_cli prints SSIDs escaped (\\xNN, \\", \\\\); unescape() turns them back into bytes for display and matching.
Only wlan0 is ever named (never ccmni*: the modem stays off, D16).

Join guard (deviations 5.7, ruling B2): select_network disables every other network, so a vegas-net that dies in the
middle of a join (killed tmux window, SSH gone, crash) used to leave the phone off its old network until a reboot.
Now every join/connect is bracketed by JoinGuard: before select_network it writes /run/vegas-ui/net-join (old id,
new id, a token; no secrets) and arms a transient systemd timer (`systemd-run --on-active=60`, outside tmux and
outside this process; a detached `sleep` is the fallback) that runs `vegas-net --restore <token>`. Success or
vegas-net's own go-back (after WAIT_SECS = 30 s) removes the record and stops the timer.
Timing (the property is "the old network is BACK within 60 s", not "going back starts at 60 s"): vegas-net waits
WAIT_SECS = 30 s for the new network, then selects the old one and waits up to BACK_SECS = 18 s for it (back by ~48 s).
If vegas-net died, the guard fires at GUARD_SECS = 38 s (after vegas-net's own deadline, so it never cuts a live
join short) and the old network is back by 38 + ~2 s start + 18 s = ~58 s at worst. A guard that fires while a live
vegas-net is itself going back is harmless: both select the old network. If the timer fires with the
record still there, heal() puts the old network back. A respawned vegas-net heals at start too (heal(at_start=True)),
and runs enable_network all every start.

Scan ages (R12, F4): Wpa.bss_ages() reads one age per BSS (BSS RANGE=ALL MASK=0x203) and scan_results() lists every
BSS of an SSID under 'bssids', so vegas-net can give each row the age of its network's freshest BSS and show the
median over the rows on screen (net.py, F4).
"""
import hashlib
import json
import os
import re
import secrets
import signal
import subprocess
import time

from .host import P, read, write_atomic

WPA_CLI = ["wpa_cli", "-p", "/run/wpa_supplicant", "-i", "wlan0"]
WAIT_SECS = 30        # vegas-net's own wait for an address before it goes back
GUARD_SECS = 38       # the guard fires after vegas-net's own deadline (+8 s for slow wpa_cli answers)
BACK_SECS = 18        # how long going back waits for the old network before enabling all the others
RESTORE_START = 2     # `vegas-net --restore` start-up (Python, no Textual), seconds
# ruling B2: GUARD_SECS + RESTORE_START + BACK_SECS <= 60 and WAIT_SECS < GUARD_SECS (test_rulings_net checks it)
GUARD_REC = "/run/vegas-ui/net-join"
VEGAS_NET = "/usr/local/bin/vegas-net"


def unescape(s: str) -> bytes:
    """Reverse of wpa_supplicant's printf_encode (used for SSIDs in scan_results/list_networks/status)."""
    out, i = bytearray(), 0
    esc = {"n": 10, "r": 13, "t": 9, "e": 27, '"': 34, "\\": 92}
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]
            if n == "x" and re.fullmatch(r"[0-9a-fA-F]{2}", s[i + 2:i + 4]):
                out.append(int(s[i + 2:i + 4], 16))
                i += 4
                continue
            if n in esc:
                out.append(esc[n])
                i += 2
                continue
        out += c.encode()
        i += 1
    return bytes(out)


def printable(s: str) -> str:
    """Text from the network (SSIDs, a captive-portal URL) made safe to draw in the root terminal: every character
    that is not printable (C0 incl. ESC, DEL, C1 incl. U+009B CSI, bidi/format controls, line separators) becomes a
    visible \\xNN / \\uNNNN escape. Rich/Textual do NOT strip ESC: a beaconed SSID could otherwise send raw CSI/OSC/DCS
    sequences to tmux (reviewed 2026-11-23, reproduced in the VM). Matching and wpa_cli keep the raw bytes."""
    return "".join(c if c.isprintable() else ("\\x%02x" % ord(c) if ord(c) < 0x100 else "\\u%04x" % ord(c))
                   for c in s)


def show(ssid: bytes) -> str:
    """Display form of an SSID (every SSID shown by vegas-net goes through here)."""
    return printable(ssid.decode("utf-8", errors="replace"))


def _key_mgmt(flags: str) -> set:
    """Key management names of the WPA/RSN elements of a scan_results flags field: '[WPA2-PSK+SAE-CCMP][ESS]' ->
    {'PSK', 'SAE'}. The OWE transition marks ([OWE-TRANS], [OWE-TRANS-OPEN]) are not WPA/RSN elements."""
    out = set()
    for el in re.findall(r"\[([^\]]*)\]", flags):
        proto, _, rest = el.partition("-")
        if proto in ("WPA", "WPA2", "RSN", "OSEN") and rest:
            out.update(rest.split("-")[0].split("+"))
    return out


def security(flags: str) -> str:
    """'WPA3' (SAE only), 'WPA2' (any PSK), '802.1X' (EAP: not joinable in v1), 'OWE' (enhanced open: not joinable
    in v1, ruling B10), 'WEP' or 'open'. An open BSS in OWE transition mode ([OWE-TRANS]) stays 'open': it is one."""
    km = _key_mgmt(flags)
    if "EAP" in flags:
        return "802.1X"
    if "PSK" in flags:
        return "WPA2"
    if "SAE" in flags:
        return "WPA3"
    if "OWE" in km:
        return "OWE"
    if "WEP" in flags:
        return "WEP"
    return "open"


def band(freq) -> str:
    return "?" if not freq else ("2.4 GHz" if int(freq) < 3000 else "5 GHz")


def bars(dbm) -> int:
    """[BUILDER CHOICE] 4 >= -55, 3 >= -67, 2 >= -75, else 1."""
    if dbm is None:
        return 0
    return 4 if dbm >= -55 else 3 if dbm >= -67 else 2 if dbm >= -75 else 1


def psk_hex(passphrase: str, ssid: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha1", passphrase.encode(), ssid, 4096, 32).hex()


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (ProcessLookupError, ValueError, TypeError, OverflowError):
        return False
    except PermissionError:
        return True
    return True


def _spawn_detached(argv):
    """Fallback guard: a process in its own session (a closed tmux window or SSH does not take it down)."""
    return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, close_fds=True)


class JoinGuard:
    """The old network comes back within GUARD_SECS even if vegas-net dies mid-join (module doc, ruling B2).
    The record holds ids and a token only, never an SSID or a secret."""

    def __init__(self, runner, spawn=None):
        self.r = runner
        self.spawn = spawn or _spawn_detached
        self.proc = None

    def pending(self):
        try:
            rec = json.loads(read(GUARD_REC) or "null")
        except ValueError:
            return None
        return rec if isinstance(rec, dict) and "token" in rec else None

    def busy(self) -> bool:
        """Another live vegas-net (say one over SSH) is in the middle of a join."""
        rec = self.pending()
        return bool(rec) and rec.get("pid") != os.getpid() and pid_alive(rec.get("pid"))

    def arm(self, old, new, added: bool) -> str:
        """Before select_network. Returns how the guard runs: 'systemd', 'sleeper' or 'none' (could not start one;
        vegas-net's own go-back still applies)."""
        token = secrets.token_hex(6)
        rec = {"pid": os.getpid(), "old": old, "new": new, "added": added, "token": token,
               "unit": f"vegas-net-guard-{token}", "pgid": None}
        write_atomic(GUARD_REC, json.dumps(rec) + "\n", 0o600)
        r = self.r.run(["systemd-run", "--quiet", "--collect", f"--unit={rec['unit']}", f"--on-active={GUARD_SECS}",
                        "--timer-property=AccuracySec=1s", VEGAS_NET, "--restore", token], timeout=10)
        if r.ok:
            return "systemd"
        rec["unit"] = None
        try:
            self.proc = self.spawn(["sh", "-c", f"sleep {GUARD_SECS}; exec {VEGAS_NET} --restore {token}"])
            rec["pgid"] = self.proc.pid
            kind = "sleeper"
        except OSError:
            kind = "none"
        write_atomic(GUARD_REC, json.dumps(rec) + "\n", 0o600)
        return kind

    def disarm(self, rec=None) -> None:
        """Remove the record first (a guard that fires now finds nothing to do), then stop the timer or sleeper.
        Only the timer is stopped: a restore already running is idempotent and is left to finish."""
        rec = rec or self.pending()
        try:
            os.remove(P(GUARD_REC))
        except OSError:
            pass
        if not rec:
            return
        if rec.get("unit"):
            self.r.run(["systemctl", "stop", rec["unit"] + ".timer"], timeout=10)
        if rec.get("pgid") and rec.get("token", "?") in (read(f"/proc/{rec['pgid']}/cmdline", "") or ""):
            try:                       # (the cmdline check: never signal a reused pid)
                os.killpg(int(rec["pgid"]), signal.SIGTERM)
            except (OSError, ValueError, TypeError):
                pass
            if self.proc is not None:
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    pass
                self.proc = None


def heal(wpa, guard, token=None, at_start=False) -> str:
    """Finish an interrupted join. token: from `vegas-net --restore <token>` (acts only on that join's record).
    at_start: vegas-net starting up; leaves a join alone whose vegas-net is still alive, otherwise also runs
    enable_network all (a crash between select_network and the go-back left the others disabled).
    Returns 'none' (nothing pending), 'busy', 'stale' (token of an older join), 'kept' (the new network got an
    address: kept and saved like a normal success) or 'restored' (back to the old network)."""
    rec = guard.pending()
    if rec is None or (token is not None and rec.get("token") != token):
        if at_start:
            wpa.cmd("enable_network", "all")
        return "none" if rec is None else "stale"
    if at_start and guard.busy():
        return "busy"
    new, old = rec.get("new"), rec.get("old")
    st = wpa.status()
    if st.get("wpa_state") == "COMPLETED" and st.get("id") == str(new) and st.get("ip_address"):
        wpa.cmd("enable_network", "all")
        if rec.get("added"):
            wpa.cmd("save_config")
        guard.disarm(rec)
        return "kept"
    if rec.get("added") and new is not None:
        wpa.cmd("remove_network", new)
    wpa.back_to(old)
    guard.disarm(rec)
    return "restored"


class Wpa:
    def __init__(self, runner, guard=None):
        self.r = runner
        self.guard = guard       # JoinGuard, or None (no guard: the tests of the plain wpa_cli steps)

    def cmd(self, *args):
        return self.r.run(WPA_CLI + [str(a) for a in args], timeout=8)

    def ok(self, *args) -> bool:
        return self.cmd(*args).last == "OK"

    # --- reading -----------------------------------------------------------------------------------------------
    def status(self) -> dict:
        d = {}
        for line in self.cmd("status").out.splitlines():
            k, sep, v = line.partition("=")
            if sep:
                d[k.strip()] = v.strip()
        if "ssid" in d:
            d["ssid_bytes"] = unescape(d["ssid"])
        return d

    def rssi(self):
        m = re.search(r"^RSSI=(-?\d+)", self.cmd("signal_poll").out, re.M)
        return int(m.group(1)) if m else None

    def networks(self) -> list:
        """Saved networks: [{'id', 'ssid' (bytes), 'flags', 'priority'}] in wpa_supplicant's order."""
        out = []
        for line in self.cmd("list_networks").out.splitlines()[1:]:
            f = line.split("\t")
            if len(f) >= 1 and f[0].strip().isdigit():
                out.append({"id": int(f[0]), "ssid": unescape(f[1]) if len(f) > 1 else b"",
                            "flags": f[3] if len(f) > 3 else ""})
        return out

    def priority(self, nid) -> int:
        v = self.cmd("get_network", nid, "priority").last
        return int(v) if v.lstrip("-").isdigit() else 0

    def scan(self) -> bool:
        return self.cmd("scan").last in ("OK", "FAIL-BUSY")

    def bss_ages(self):
        """Rulings R12/F4: {bssid (lower case): seconds since a scan last saw it} for every entry of wpa_supplicant's
        BSS table, whoever asked for that scan (wpa_supplicant's own scans, wpa_cli, us). BSS RANGE=ALL MASK=0x203
        (WPA_BSS_MASK_ID|BSSID|AGE) prints "id=", "bssid=", "age=" per entry; entries are split on "id=" so the
        field order inside one does not matter. The age counts from the time the driver saw the BSS (nl80211
        seen-ms-ago), so a stale cached entry is not counted as fresh. {} = empty table; None = no answer or an old
        wpa_supplicant (FAIL, UNKNOWN COMMAND). The reply is cut at wpa_supplicant's 4 KiB buffer (~100 entries at
        ~40 bytes each, scan_results itself stops at ~55 lines): a BSS without an age is left out of the median."""
        r = self.cmd("bss", "RANGE=ALL", "MASK=0x203")
        if not r.ok:
            return None
        out, ages, cur = r.out, {}, {}
        for line in out.splitlines() + ["id=end"]:
            k, sep, v = line.strip().partition("=")
            if not sep:
                continue
            if k == "id":
                if "bssid" in cur and cur.get("age", "").isdigit():
                    ages[cur["bssid"].lower()] = int(cur["age"])
                cur = {}
            elif k in ("bssid", "age"):
                cur[k] = v
        if ages or not out.strip():
            return ages
        return None

    def list_age(self):
        """Age of the freshest entry of the BSS table (R12 before F4); None = empty table or no answer."""
        ages = self.bss_ages()
        return min(ages.values()) if ages else None

    def scan_results(self) -> list:
        """Networks in range, strongest BSS per SSID, strongest first, hidden SSIDs left out. 'bssids': every BSS of
        that SSID in the table (F4: a row's age is the age of its freshest BSS)."""
        best = {}
        for line in self.cmd("scan_results").out.splitlines():
            f = line.split("\t")
            if len(f) < 5 or not re.fullmatch(r"[0-9a-fA-F:]{17}", f[0].strip()):
                continue
            ssid = unescape(f[4])
            if not ssid or set(ssid) == {0}:
                continue
            try:
                freq, dbm = int(f[1]), int(f[2])
            except ValueError:
                continue
            seen = best[ssid]["bssids"] if ssid in best else []
            seen.append(f[0].strip().lower())
            if ssid not in best or dbm > best[ssid]["dbm"]:
                best[ssid] = {"ssid": ssid, "freq": freq, "dbm": dbm, "flags": f[3], "sec": security(f[3]),
                              "bssids": seen}
        return sorted(best.values(), key=lambda n: -n["dbm"])

    # --- changing ----------------------------------------------------------------------------------------------
    def _wait(self, nid, progress, timeout):
        """Wait for COMPLETED on nid, then an IPv4. Returns 'ok', 'wrongkey' or 'timeout'."""
        said = None
        deadline = time.monotonic() + timeout   # wall clock too: slow wpa_cli answers must not stretch the wait
        for _ in range(int(timeout)):   # one status poll per second (runner.sleep, so tests run instantly)
            if time.monotonic() > deadline:
                break
            st = self.status()
            if st.get("wpa_state") == "COMPLETED" and st.get("id") == str(nid):
                if st.get("ip_address"):
                    return "ok"
                if said != "addr":
                    progress("getting an address")
                    said = "addr"
            for n in self.networks():
                if n["id"] == nid and "TEMP-DISABLED" in n["flags"]:
                    return "wrongkey"
            self.r.sleep(1)
        return "timeout"

    def current(self):
        """Id of the network wpa_supplicant is on now (COMPLETED), else None."""
        st = self.status()
        cid = st.get("id", "")
        return int(cid) if st.get("wpa_state") == "COMPLETED" and cid.isdigit() else None

    def back_to(self, old, progress=lambda s: None, wait=BACK_SECS) -> bool:
        """Go back to the old network explicitly (select_network old, wait for it), then enable all the others that
        select_network disabled. Enabling all at once instead could let wpa_supplicant pick another saved network.
        True when the old network is back (COMPLETED on it)."""
        back = False
        if old is not None and any(n["id"] == old for n in self.networks()):
            progress("going back to the old network")
            self.cmd("select_network", old)
            for _ in range(int(wait)):
                st = self.status()
                if st.get("wpa_state") == "COMPLETED" and st.get("id") == str(old):
                    back = True
                    break
                self.r.sleep(1)
        self.cmd("enable_network", "all")
        return back

    def _arm(self, old, nid, added):
        if self.guard is not None:
            try:
                self.guard.arm(old, nid, added)
            except OSError:            # no record, no guard: vegas-net's own go-back still runs
                pass

    def _disarm(self):
        if self.guard is not None:
            self.guard.disarm()

    def join_new(self, ssid: bytes, sec: str, passphrase: str = "", hidden=False, progress=lambda s: None,
                 timeout=WAIT_SECS):
        """Add, select, wait; save on success; on failure remove it and go back to the old network. (ok, message)."""
        if sec == "WPA2" and not 8 <= len(passphrase) <= 63:
            return False, "A WPA2 passphrase has 8 to 63 characters."
        if sec not in ("WPA2", "WPA3", "open"):
            return False, f"{sec} networks are not supported yet."
        if self.guard is not None and self.guard.busy():
            return False, "Another vegas-net is joining a network; try again in a minute."
        old = self.current()
        nid = self.cmd("add_network").last
        if not nid.isdigit():
            return False, f"add_network failed: {nid or 'no answer'}"
        steps = [("set_network", nid, "ssid", ssid.hex())]
        if sec == "WPA2":
            steps.append(("set_network", nid, "psk", psk_hex(passphrase, ssid)))
        elif sec == "WPA3":
            steps += [("set", "sae_pwe", "2"), ("set_network", nid, "key_mgmt", "SAE"),
                      ("set_network", nid, "sae_password", f'"{passphrase}"'),
                      ("set_network", nid, "ieee80211w", "2")]
        else:
            steps.append(("set_network", nid, "key_mgmt", "NONE"))
        if hidden:
            steps.append(("set_network", nid, "scan_ssid", "1"))
        for s in steps:
            if not self.ok(*s):
                self.cmd("remove_network", nid)
                return False, f"wpa_supplicant refused {s[0]} {s[2] if len(s) > 2 else ''}".strip()
        # no try/finally on purpose: if this thread dies with an error, the guard stays armed and goes back
        self._arm(old, int(nid), True)
        progress("joining")
        self.cmd("select_network", nid)
        res = self._wait(int(nid), progress, timeout)
        if res == "ok":
            self.cmd("enable_network", "all")
            self.cmd("save_config")
            self._disarm()
            progress("connected")
            return True, "connected"
        self.cmd("remove_network", nid)
        back = self.back_to(old, progress)    # the old network explicitly, then the others select disabled
        self._disarm()
        if res == "wrongkey":
            return False, "Wrong passphrase?"
        return False, f"No connection after {timeout} s; the new entry was removed" + \
            ("; back on the old network." if back else ".")

    def connect(self, nid: int, progress=lambda s: None, timeout=WAIT_SECS):
        if self.guard is not None and self.guard.busy():
            return False, "Another vegas-net is joining a network; try again in a minute."
        old = self.current()
        self._arm(old, nid, False)
        progress("joining")
        self.cmd("select_network", nid)
        res = self._wait(nid, progress, timeout)
        if res == "ok":
            self.cmd("enable_network", "all")   # select_network disabled the others
            self._disarm()
            progress("connected")
            return True, "connected"
        self.back_to(old if old != nid else None, progress)
        self._disarm()
        return False, "Wrong passphrase?" if res == "wrongkey" else f"No connection after {timeout} s."

    def forget(self, nid: int):
        ok = self.ok("remove_network", nid) and self.ok("save_config")
        return ok, "forgotten" if ok else "wpa_supplicant refused"

    def move(self, nid: int, up: bool):
        """Priority above all others (up) or below all others (down, min 0, others raised)."""
        nets = self.networks()
        prio = {n["id"]: self.priority(n["id"]) for n in nets}
        others = [p for i, p in prio.items() if i != nid] or [0]
        if up:
            new = max(others) + 1
        else:
            new = 0
            for i, p in prio.items():   # make room: everyone else at least 1
                if i != nid and p < 1:
                    self.cmd("set_network", i, "priority", 1)
        ok = self.ok("set_network", nid, "priority", new) and self.ok("save_config")
        return ok, "moved" if ok else "wpa_supplicant refused"
