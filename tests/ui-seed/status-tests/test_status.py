"""Tests for vegas-status + vegasui.readers/charge/swayipc against a fake tree (run in the trixie VM or on macOS).
python3 -m unittest -v test_status   (from this directory)"""
import importlib, json, os, shutil, socket, struct, subprocess, sys, tempfile, threading, time, unittest

REPO = "/path/to/repo"
OV = REPO + "/linux/debian/overlay"
STATUS = OV + "/usr/local/bin/vegas-status"
GUARD = OV + "/usr/lib/vegas/chargeguard"
sys.path.insert(0, OV + "/usr/lib/vegas/ui")


def w(root, path, text):
    p = root + path
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text + "\n")


def tree(**kw):
    root = tempfile.mkdtemp(prefix="vs-")
    v = dict(soc=78, status="Not charging", temp=310, cur=0, online=1, soc_mc=41000)
    v.update(kw)
    b = "/sys/class/power_supply/battery/"
    w(root, b + "capacity", str(v["soc"])); w(root, b + "status", v["status"]); w(root, b + "temp", str(v["temp"]))
    w(root, b + "current_now", str(v["cur"])); w(root, "/sys/class/power_supply/primary_chg/online", str(v["online"]))
    w(root, "/sys/class/thermal/thermal_zone0/type", "soc_max"); w(root, "/sys/class/thermal/thermal_zone0/temp", str(v["soc_mc"]))
    for pol, mx in (("policy0", 2000000), ("policy6", 2400000)):
        w(root, "/sys/devices/system/cpu/cpufreq/%s/cpuinfo_max_freq" % pol, str(mx))
        w(root, "/sys/devices/system/cpu/cpufreq/%s/scaling_max_freq" % pol, str(kw.get(pol, mx)))
    w(root, "/sys/class/net/wlan0/operstate", "up"); w(root, "/sys/class/net/usb0/carrier", "1")
    w(root, "/run/vegas-test/ipv4/wlan0", "192.0.2.57"); w(root, "/run/vegas-test/ipv4/usb0", "172.16.42.1")
    w(root, "/run/vegas-test/iw-link", "Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: harbour-guest\n\tfreq: 5180.0\n\tsignal: -52 dBm")
    w(root, "/etc/hostname", "vegas5"); w(root, "/etc/vegas/root-role", "main"); w(root, "/etc/debian_version", "13.2")
    w(root, "/etc/vegas/chargeguard.conf", open(OV + "/etc/vegas/chargeguard.conf").read())
    w(root, "/proc/uptime", "273120.5 1000.0")
    # one established SSH session 172.16.42.1:22 <- 172.16.42.2:50000 (state 01), one listener (0A)
    w(root, "/proc/net/tcp", "  sl  local_address rem_address   st\n"
      "   0: 00000000:0016 00000000:0000 0A 0\n   1: 012A10AC:0016 022A10AC:C350 01 0")
    w(root, "/proc/net/tcp6", "  sl  local_address rem_address st")
    w(root, "/sbin/vegas-hotspot", "#!/bin/sh\necho 'on: vegas-7k2, 2 device(s)'"); os.chmod(root + "/sbin/vegas-hotspot", 0o755)
    w(root, "/sbin/vegas-usbshare", "#!/bin/sh\necho 'on via wlan0 (123 bytes out)'"); os.chmod(root + "/sbin/vegas-usbshare", 0o755)
    w(root, "/proc_cmd", "")
    return root


def guard(root):
    """Run the real chargeguard once against the fake tree, so want/control/override-state are genuine."""
    env = dict(os.environ, VEGAS_BAT=root + "/sys/class/power_supply/battery", VEGAS_CMD=root + "/proc_cmd",
               VEGAS_QPNP=root + "/none", VEGAS_ST=root + "/run/vegas-chargeguard")
    script = open(GUARD).read().replace("/etc/vegas/chargeguard.conf", root + "/etc/vegas/chargeguard.conf") \
        .replace("systemctl poweroff", "echo POWEROFF")
    subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True)


def run(root, *args, env=None, inp=None, timeout=10):
    e = dict(os.environ, VEGAS_SYSROOT=root, VEGAS_SBIN=root + "/sbin", SWAYSOCK="/nonexistent", TZ="UTC")
    e.update(env or {})
    return subprocess.run([sys.executable, STATUS, *args], env=e, capture_output=True, text=True, input=inp,
                          timeout=timeout)


def load(root):
    os.environ["VEGAS_SYSROOT"] = root
    os.environ["VEGAS_SBIN"] = root + "/sbin"
    import vegasui.readers as R, vegasui.charge as C
    importlib.reload(R); R._zone = None
    return R, C


class Charge(unittest.TestCase):
    def word(self, setup=None, **kw):
        root = tree(**kw)
        if setup:
            setup(root)
        guard(root)
        R, C = load(root)
        return C.word(R.battery(), R.guard())[:2]

    def test_holding_in_band(self):
        def was_full(root):   # the guard stopped at 80 before; 78 is inside the band -> holding (hysteresis)
            w(root, "/run/vegas-chargeguard/want", "off")
        self.assertEqual(self.word(was_full, soc=78), ("holding", "ok"))
        self.assertEqual(self.word(soc=78), ("charging", "ok"))   # fresh guard: charges on up to STOP

    def test_charging_below_resume(self):
        self.assertEqual(self.word(soc=60), ("charging", "ok"))

    def test_on_battery(self):
        self.assertEqual(self.word(soc=60, online=0), ("on battery", "warn"))

    def test_paused_warm(self):
        self.assertEqual(self.word(soc=60, temp=425), ("paused: warm", "warn"))

    def test_no_gauge(self):
        self.assertEqual(self.word(soc=-1), ("no gauge", "limit"))

    def test_no_control(self):
        root = tree(soc=60); env = dict(os.environ, VEGAS_BAT=root + "/sys/class/power_supply/battery",
                                        VEGAS_CMD=root + "/nope", VEGAS_QPNP=root + "/nope", VEGAS_ST=root + "/run/vegas-chargeguard")
        script = open(GUARD).read().replace("/etc/vegas/chargeguard.conf", root + "/etc/vegas/chargeguard.conf")
        subprocess.run(["bash", "-c", script], env=env, check=True, capture_output=True)
        R, C = load(root)
        self.assertEqual(C.word(R.battery(), R.guard())[:2], ("no charge control", "limit"))

    def test_starting(self):
        R, C = load(tree())
        self.assertEqual(C.word(R.battery(), R.guard())[:2], ("starting", "dim"))

    def test_override_full_and_band(self):
        def ov(root):
            w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99")
        self.assertEqual(self.word(ov, soc=100), ("full", "ok"))
        root = tree(soc=90); ov(root); guard(root); R, C = load(root)
        g = R.guard()
        self.assertEqual((g["stop"], g["resume"], g["override"]), (100, 99, True))
        self.assertEqual(C.word(R.battery(), g)[0], "charging")
        self.assertEqual(R.band(g), "99-100 %")
        os.remove(root + "/run/vegas-chargeguard/override")     # switched back, guard not yet run: band again
        self.assertFalse(R.guard()["override"])


class Readers(unittest.TestCase):
    def test_values(self):
        root = tree(policy6=1800000); guard(root); R, _ = load(root)
        self.assertEqual(R.soc_temp(), 41)
        self.assertEqual(R.cpu_cap(), (75, 2000, 1800))
        self.assertEqual(R.ssh_sessions(), [("172.16.42.1", "172.16.42.2")])
        self.assertEqual(R.wifi_link(), {"ssid": "harbour-guest", "freq": 5180, "dbm": -52})
        self.assertIsNone(R.hotspot())
        os.makedirs(root + "/run/vegas-hotspot")
        self.assertEqual(R.hotspot()["devices"], 2)
        self.assertEqual(R.fmt_uptime(273120), "3d 03:52")
        self.assertEqual(R.root_role(), "main")

    def test_ipv6_mapped(self):
        R, _ = load(tree())
        self.assertEqual(R._hexaddr("0000000000000000FFFF0000012A10AC:0016"), "172.16.42.1")


class Report(unittest.TestCase):
    def test_report(self):
        root = tree(); w(root, "/run/vegas-chargeguard/want", "off"); guard(root)
        r = run(root, "--report")
        self.assertEqual(r.returncode, 0, r.stderr)
        print("\n" + r.stdout)
        self.assertIn("vegas5 Debian 13 main root up 3d 03:52", r.stdout)
        self.assertIn("holding", r.stdout); self.assertIn("band 70-80 %", r.stdout)
        self.assertIn("-52 dBm 192.0.2.57 harbour-guest", r.stdout)
        self.assertIn("1 session", r.stdout)
        for l in r.stdout.splitlines():
            self.assertLessEqual(len(l), 60, l)

    def test_report_long_ssid(self):
        root = tree(); guard(root)
        w(root, "/run/vegas-test/ipv4/wlan0", "192.168.100.157")
        w(root, "/run/vegas-test/iw-link", "Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: " + "S" * 32 +
          "\n\tsignal: -52 dBm")
        r = run(root, "--report")
        line = [l for l in r.stdout.splitlines() if l.startswith("wifi")][0]
        self.assertTrue(line.endswith("~") and len(line) == 60, line)

    def test_report_broken_tree(self):
        r = run(tempfile.mkdtemp(), "--report")
        self.assertEqual(r.returncode, 0, r.stderr)
        print("\n" + r.stdout)
        self.assertIn("rescue root", r.stdout)


def text_of(block):
    import re
    return re.sub(r"<[^>]+>", "", block["full_text"]).replace("&amp;", "&").replace("&lt;", "<")


class Strip(unittest.TestCase):
    def blocks(self, root, width=360):
        r = run(root, "--bar-once", str(width))
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_upright(self):
        root = tree(); guard(root)
        b = self.blocks(root)
        txt = [text_of(x) for x in b]
        print("\n", txt, [x.get("min_width") for x in b])
        self.assertEqual([x["name"] for x in b], ["home", "net", "soc", "bat", "kbd"])
        self.assertEqual(txt[0][5:], " vegas5 MAIN ")                  # host fits upright
        self.assertEqual("".join(txt[1:]), "wifi 41° 78%▲ kbd ")       # usb dropped (camera hole)
        land = [text_of(x) for x in self.blocks(root, 796)]
        self.assertEqual(land[0][5:], " vegas5 MAIN ")
        self.assertEqual("".join(land[1:]), "wifi usb 41° 78%▲ kbd ")   # ruling 3a: no band top in normal running
        for x in b:
            self.assertEqual((x["markup"], x["separator"], x["separator_block_width"]), ("pango", False, 0))
        self.assertTrue(self.clear_of_hole(b, 360))

    def clear_of_hole(self, b, width, hole=20, pad=20, char=8.03):
        """Neither side's text reaches the centre gap (right group measured with ▲/▼ at 1.5 cells). The left text
        starts where min_width puts it: width - pad - right - min_width (= pad + SAFETY)."""
        w = lambda t: sum(char * (1.5 if c in "▲▼" else 1) for c in t)
        left, right = w(text_of(b[0])), sum(w(text_of(x)) for x in b[1:])
        lstart = width - pad - right - b[0]["min_width"]
        return lstart + left <= width / 2 - hole / 2 and width - pad - right >= width / 2 + hole / 2

    def test_badges_and_shrink(self):
        root = tree(soc=12, online=0, soc_mc=72000, policy0=1600000)
        os.makedirs(root + "/run/vegas-hotspot"); w(root, "/etc/vegas/away", ""); guard(root)
        b = self.blocks(root)
        txt = "".join(text_of(x) for x in b[1:])
        print("\n", [text_of(x) for x in b])
        self.assertIn("AWAY", text_of(b[0])); self.assertNotIn("vegas5", text_of(b[0]))  # host dropped first
        self.assertEqual(txt, " 72° 12%▼ AP  kbd ")    # cap block dropped upright: SoC turns red instead
        soc = [x for x in b if x["name"] == "soc"][0]
        self.assertIn("#FF6B63", soc["full_text"])     # red = a limit (the cap) is active, though 72 < 80
        self.assertIn("#F0B429", [x for x in b if x["name"] == "bat"][0]["full_text"])   # battery <= 15 amber
        self.assertTrue(self.clear_of_hole(b, 360))
        # landscape: everything fits, AP count, cap and host come back
        b = self.blocks(root, 796)
        t = "".join(text_of(x) for x in b)
        self.assertIn("AP 2", t); self.assertIn("cap 80%", t); self.assertIn("vegas5", text_of(b[0]))
        self.assertIn("#F0B429", [x for x in b if x["name"] == "soc"][0]["full_text"])   # 72 amber, cap shown apart

    def test_rescue(self):
        root = tree(); os.remove(root + "/etc/vegas/root-role"); w(root, "/rescue", "")
        self.assertIn("rescue", text_of(self.blocks(root)[0]))
        b = self.blocks(root, 796)
        self.assertIn("rescue pending", text_of(b[0]))
        os.remove(root + "/rescue")
        b = self.blocks(root)
        self.assertIn("RESCUE", text_of(b[0])); self.assertIn("#F0B429", b[0]["full_text"])

    def test_full_override_amber_100(self):
        root = tree(soc=90); w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99"); guard(root)
        b = self.blocks(root)
        bat = [x for x in b if x["name"] == "bat"][0]
        self.assertIn("90%▲", text_of(bat)); self.assertIn('foreground="#F0B429">100<', bat["full_text"])
        self.assertIn("kbd", text_of(b[-1]))           # "wifi" goes before the keyboard button shrinks
        self.assertTrue(Strip.clear_of_hole(self, b, 360))


class Bar(unittest.TestCase):
    def test_feed_and_taps(self):
        root = tree(); guard(root)
        e = dict(os.environ, VEGAS_SYSROOT=root, VEGAS_SBIN=root + "/sbin", SWAYSOCK="/nonexistent")
        p = subprocess.Popen([sys.executable, STATUS, "--bar"], env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        hdr = json.loads(p.stdout.readline()); self.assertEqual(hdr, {"version": 1, "click_events": True})
        self.assertEqual(p.stdout.readline().strip(), "[")
        first = json.loads(p.stdout.readline())
        self.assertEqual(first[0]["name"], "home")
        # tap kbd with no wvkbd running: no crash; the tap is the person's choice (ruling 8: uictl records kbd and
        # kbd-user even with no keyboard to signal), so the badge goes dim in one new line; then a tap with junk
        p.stdin.write('[\n{"name":"kbd","button":1}\n,{"name":"net","button":1}\n,garbage\n'); p.stdin.flush()
        line = p.stdout.readline()
        self.assertTrue(line.startswith(",["), line)
        kbd = [x for x in json.loads(line[1:]) if x["name"] == "kbd"][0]
        self.assertNotIn("background", kbd["full_text"])
        self.assertEqual(open(root + "/run/vegas-ui/kbd-user").read().strip(), "hidden")
        time.sleep(1.5)
        # a change in a 10 s value appears after the next tick only, as one new ",[...]" line
        w(root, "/sys/class/net/wlan0/operstate", "down")
        p.stdin.write(',{"name":"soc","button":3}\n'); p.stdin.flush()   # wakes the loop (button 3 ignored)
        line = p.stdout.readline()
        self.assertTrue(line.startswith(",["), line)
        net = [x for x in json.loads(line[1:]) if x["name"] == "net"][0]
        self.assertIn('#7F8B99">wifi', net["full_text"])
        p.terminate(); p.wait(5)
        err = p.stderr.read()
        self.assertIn("click", err)                    # the junk event was reported, not fatal
        self.assertNotIn("Traceback", err)


class SwayIPC(unittest.TestCase):
    def test_width_and_refusal(self):
        d = tempfile.mkdtemp(); path = d + "/sway.sock"
        srv = socket.socket(socket.AF_UNIX); srv.bind(path); srv.listen(4); got = []

        def serve():
            for _ in range(2):
                c, _ = srv.accept()
                head = c.recv(14); n, kind = struct.unpack("=II", head[6:]); body = c.recv(n) if n else b""
                got.append((kind, body))
                reply = json.dumps([{"name": "DSI-1", "active": True, "rect": {"width": 796}}] if kind == 3
                                   else [{"success": True}]).encode()
                c.sendall(b"i3-ipc" + struct.pack("=II", len(reply), kind) + reply); c.close()
        threading.Thread(target=serve, daemon=True).start()
        os.environ["SWAYSOCK"] = path
        import vegasui.swayipc as S
        self.assertEqual(S.output_width(), 796)
        self.assertIsNotNone(S.command("workspace number 1"))
        for bad in ("exit", "reload", "output DSI-1 dpms off", "output DSI-1 power off", "output DSI-1 disable"):
            self.assertIsNone(S.command(bad))           # refused before anything is sent
        self.assertEqual([k for k, _ in got], [3, 0])


if __name__ == "__main__":
    unittest.main()
