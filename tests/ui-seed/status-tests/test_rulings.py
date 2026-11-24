"""Designer rulings for the status part (3a, 3b, B3, B5, the strip ruler), against fake trees.
python3 -m unittest -v test_rulings   (from this directory; Mac or the trixie VM; PYTHONDONTWRITEBYTECODE=1)"""
import json, os, re, signal, subprocess, sys, time, unittest

from test_status import OV, STATUS, tree, guard, run, load, w, text_of

GLANCE = OV + "/usr/lib/vegas/vegas-glance"
AMBER, RED, DIM, BUTTON, TEXT = "#F0B429", "#FF6B63", "#7F8B99", "#2B3746", "#D5DBE3"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def blocks(root, width=360):
    r = run(root, "--bar-once", str(width))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def named(b, name):
    return [x for x in b if x["name"] == name][0]


def glance(root, cols=20, rows=22, mode="glance"):
    e = dict(os.environ, VEGAS_SYSROOT=root, VEGAS_SBIN=root + "/sbin", VEGAS_UI_LIB=OV + "/usr/lib/vegas/ui",
             COLS=str(cols), ROWS=str(rows), TZ="UTC", LANG="C.UTF-8", PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, GLANCE, "--once", "--mode=" + mode], env=e, capture_output=True, text=True,
                       timeout=10)
    assert r.returncode == 0, r.stderr
    return r.stdout.splitlines()


def plain(lines):
    return [ANSI.sub("", l) for l in lines]


# ------------------------------------------------------------------------------------------------ strip
class Strip3a(unittest.TestCase):
    def test_no_band_top_in_normal_running(self):
        root = tree(); guard(root)
        for width in (360, 796):
            bat = text_of(named(blocks(root, width), "bat"))
            self.assertEqual(bat, " 78%▲", width)

    def test_band_top_amber_100_only_while_charge_to_full(self):
        root = tree(soc=90); w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99"); guard(root)
        for width in (360, 796):
            bat = named(blocks(root, width), "bat")
            self.assertEqual(text_of(bat), " 90%▲100", width)
            self.assertIn('foreground="%s">100<' % AMBER, bat["full_text"])


class Strip3b(unittest.TestCase):
    def test_kbd_shown_slate_like_main(self):
        root = tree(); guard(root); w(root, "/run/vegas-ui/kbd", "shown")
        b = blocks(root)
        kbd = named(b, "kbd")
        self.assertEqual(text_of(kbd), " kbd ")                    # r6b: measured widths fit "kbd" with wifi upright
        self.assertEqual(text_of(named(blocks(root, 796), "kbd")), " kbd ")
        self.assertIn('background="%s"' % BUTTON, kbd["full_text"])
        self.assertIn('foreground="%s"' % TEXT, kbd["full_text"])
        main = re.search(r'<span ([^>]*)> MAIN </span>', b[0]["full_text"]).group(1)
        self.assertIn('background="%s"' % BUTTON, main)            # same slate as MAIN

    def test_kbd_hidden_plain_dim(self):
        root = tree(); guard(root); w(root, "/run/vegas-ui/kbd", "hidden")
        kbd = named(blocks(root), "kbd")
        self.assertEqual(text_of(kbd), " kbd ")                    # same width as shown: nothing else moves
        self.assertEqual(text_of(named(blocks(root, 796), "kbd")), " kbd ")
        self.assertNotIn("background", kbd["full_text"])
        self.assertIn('foreground="%s"' % DIM, kbd["full_text"])

    def test_amber_fill_only_for_things_switched_on(self):
        """Every amber-filled span in any scenario is AWAY, AP..., RESCUE/RESC; normal running has none."""
        ok = re.compile(r"^ (AWAY|AP( \d+| usb)?|RESCUE|RESC) $")
        scenarios = []
        root = tree(); guard(root); scenarios.append(("normal", root, 0))
        root = tree(soc=12, online=0, soc_mc=82000, policy0=1600000); guard(root)
        os.makedirs(root + "/run/vegas-hotspot"); w(root, "/etc/vegas/away", "")
        w(root, "/run/vegas-ui/kbd", "shown"); scenarios.append(("busy+ap+away", root, None))
        root = tree(); os.remove(root + "/etc/vegas/root-role"); guard(root); scenarios.append(("rescue root", root, None))
        root = tree(); w(root, "/rescue", ""); guard(root); scenarios.append(("rescue pending", root, None))
        root = tree(soc=90); w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99"); guard(root)
        scenarios.append(("full", root, 0))
        for name, root, expect in scenarios:
            for width in (360, 796):
                fills = []
                for x in blocks(root, width):
                    fills += re.findall(r'<span [^>]*background="%s"[^>]*>([^<]*)</span>' % AMBER, x["full_text"])
                for f in fills:
                    self.assertRegex(f, ok, (name, width))
                if expect is not None:
                    self.assertEqual(len(fills), expect, (name, width, fills))


class Ruler(unittest.TestCase):
    def test_ruler_blocks_upright(self):
        r = run(tree(), "--ruler-once", "360")
        self.assertEqual(r.returncode, 0, r.stderr)
        b = json.loads(r.stdout)
        self.assertEqual(len(b), 35)                               # 360 - status_edge_padding 18 = 34 cells + 2 px
        trail = b.pop()
        self.assertEqual((trail["instance"], trail["min_width"]), ("trail", 2))   # cell n stays at x 10n
        self.assertEqual([int(text_of(x)) for x in b], list(range(34)))
        for i, x in enumerate(b):
            self.assertEqual((x["name"], x["min_width"], x["separator_block_width"], x["separator"]),
                             ("ruler", 10, 0, False))
            self.assertNotEqual(x["background"], b[i - 1]["background"] if i else None)
            self.assertEqual(AMBER in x["full_text"], i % 5 == 0)
        # the label must fit in its 10 px cell: two digits at 5.5 pt (DejaVu Sans Mono advance 0.602 em)
        size_pt = int(re.search(r'size="(\d+)"', b[17]["full_text"]).group(1)) / 1024
        self.assertLessEqual(2 * 0.602 * size_pt * 96 / 72, 10)

    def test_ruler_landscape(self):
        b = json.loads(run(tree(), "--ruler-once", "796").stdout)
        self.assertEqual(len(b), 78)                               # 796 - 18 = 77 cells + an 8 px trail
        self.assertEqual((b[-1]["instance"], b[-1]["min_width"]), ("trail", 8))

    def test_ruler_flag_on_off_cli(self):
        root = tree()
        r = run(root, "--ruler", "on")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(root + "/run/vegas-ui/strip-ruler"))
        self.assertIn("ruler on", r.stdout)
        r = run(root, "--ruler", "off")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(root + "/run/vegas-ui/strip-ruler"))
        self.assertEqual(run(root, "--ruler", "bogus").returncode, 2)

    def test_feed_switches_on_signal(self):
        """The running feed draws the ruler while the flag exists; SIGUSR1 makes it redraw at once (well under the
        5 s file poll), both ways; a tap on the ruler does nothing; the feed survives the signal."""
        root = tree(); guard(root)
        e = dict(os.environ, VEGAS_SYSROOT=root, VEGAS_SBIN=root + "/sbin", SWAYSOCK="/nonexistent",
                 PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.Popen([sys.executable, STATUS, "--bar"], env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        try:
            p.stdout.readline(); p.stdout.readline()
            first = json.loads(p.stdout.readline())
            self.assertEqual(first[0]["name"], "home")
            time.sleep(0.5)        # the handler is installed before the first line; let the loop settle in wait()
            w(root, "/run/vegas-ui/strip-ruler", "on")
            t0 = time.monotonic(); p.send_signal(signal.SIGUSR1)
            line = p.stdout.readline()
            self.assertLess(time.monotonic() - t0, 2.0)
            got = json.loads(line.lstrip(","))
            self.assertEqual(got[0]["name"], "ruler")
            p.stdin.write('[\n{"name":"ruler","instance":"17","button":1}\n'); p.stdin.flush()
            time.sleep(0.5)
            os.remove(root + "/run/vegas-ui/strip-ruler")
            t0 = time.monotonic(); p.send_signal(signal.SIGUSR1)
            got = json.loads(p.stdout.readline().lstrip(","))
            self.assertLess(time.monotonic() - t0, 2.0)
            self.assertEqual(got[0]["name"], "home")
            self.assertIsNone(p.poll())
        finally:
            p.terminate(); p.wait(5)
        err = p.stderr.read()
        self.assertNotIn("Traceback", err)


# ------------------------------------------------------------------------------------------------ B3 formats
class Formats(unittest.TestCase):
    def test_fmt_amps(self):
        R, _ = load(tree())
        cases = {None: "? A", 0: "0.0 A", 0.0: "0.0 A", 0.04: "0.0 A", -0.04: "0.0 A", -0.0: "0.0 A",
                 1.1: "+1.1 A", 0.3617: "+0.4 A", -0.29: "-0.3 A", -1.25: "-1.2 A"}
        for a, want in cases.items():
            self.assertEqual(R.fmt_amps(a), want, a)

    def test_roles(self):
        R, _ = load(tree())
        self.assertEqual([R.bat_temp_role(t) for t in (None, 39.9, 40, 41.9, 42)], [None, None, "warn", "warn", "limit"])
        self.assertEqual(R.bat_temp_role(35, "paused: warm"), "warn")
        self.assertEqual([R.soc_temp_role(t) for t in (None, 69, 70, 80)], [None, None, "warn", "limit"])
        self.assertEqual([R.cap_role(p) for p in (None, 100, 99)], [None, None, "limit"])
        self.assertEqual([R.bat_level_role(s) for s in (None, 5, 15, 16)], ["limit", "limit", "warn", None])
        self.assertEqual([R.charger(o) for o in (1, 0, None)],
                         [("charger in", None), ("on battery", "warn"), ("charger ?", "warn")])

    def test_soc_zone_is_soc_max_not_zone0(self):
        root = tree(soc_mc=41000)
        w(root, "/sys/class/thermal/thermal_zone0/type", "cpu-0-0"); w(root, "/sys/class/thermal/thermal_zone0/temp", "55000")
        w(root, "/sys/class/thermal/thermal_zone7/type", "soc_max"); w(root, "/sys/class/thermal/thermal_zone7/temp", "41000")
        R, _ = load(root)
        self.assertEqual(R.soc_temp(), 41)
        self.assertIn("41°C", "\n".join(plain(glance(root))))
        self.assertIn("41 °C", run(root, "--report").stdout)

    def test_soc_zone_fallback_zone0(self):
        root = tree(); w(root, "/sys/class/thermal/thermal_zone0/type", "cpu-0-0")
        R, _ = load(root)
        self.assertEqual(R.soc_temp(), 41)


class CurrentEverywhere(unittest.TestCase):
    """B3: the same current on Home (uistatus), the report and the glance (the strip shows no current)."""
    def check(self, ua, want):
        root = tree(cur=ua); guard(root)
        rep = run(root, "--report").stdout
        self.assertIn(want, rep)
        self.assertNotIn("+0.0", rep)
        g = "\n".join(plain(glance(root)))
        self.assertIn(want, g)
        R, _ = load(root)
        import vegasui.uistatus as U
        self.assertEqual(U.fmt_amps(U.battery()["amps"]), want)
        self.assertIn((want, None), U.battery_detail(U.battery(), U.guard()))

    def test_zero(self):
        self.check(0, "0.0 A")

    def test_charging(self):
        self.check(1100000, "+1.1 A")

    def test_discharging(self):
        self.check(-290000, "-0.3 A")


class GlanceAgrees(unittest.TestCase):
    def test_same_values_as_report(self):
        root = tree(soc=12, online=0, temp=405, soc_mc=72000, policy6=1800000, cur=-290000); guard(root)
        g = plain(glance(root))
        text = "\n".join(g)
        print("\n" + text)
        R, C = load(root)
        word = C.word(R.battery(), R.guard())[0]
        self.assertEqual(word, "on battery")
        for want in ("12%", word, "70-80%", "on battery", "-0.3 A", "40°C", "72°C", "cap 75 %",
                     "192.0.2.57", "172.16.42.1", "1 session", "main root", "up 3d"):
            self.assertIn(want, text)

    def test_colours(self):
        root = tree(soc=12, online=0, temp=425, soc_mc=82000, policy0=1600000); guard(root)
        raw = "\n".join(glance(root))
        amber, red = "38;2;240;180;41m", "38;2;255;107;99m"
        self.assertIn(amber + "12%", raw)            # battery <= 15
        self.assertIn(red + "42°C", raw)             # battery temp at 42
        self.assertIn(red + "82°C", raw)             # SoC at 80+
        self.assertIn(red + "cap 80 %", raw)
        self.assertIn(amber + "on battery", raw)

    def test_charger_unknown(self):
        root = tree(); os.remove(root + "/sys/class/power_supply/primary_chg/online"); guard(root)
        self.assertIn("charger ?", "\n".join(plain(glance(root))))
        self.assertIn("charger ?", run(root, "--report").stdout)

    def test_no_gauge_tree(self):
        """The 06-glance.png question: an empty tree (like the VM's real sysfs) gives the same words as Home."""
        import tempfile
        root = tempfile.mkdtemp()
        text = "\n".join(plain(glance(root)))
        print("\n" + text)
        for want in ("no gauge", "charger ?", "rescue root"):
            self.assertIn(want, text)


class GlanceAway(unittest.TestCase):
    """B5: with Away on the last line keeps the root word and adds amber "away": "main away   up 3d"."""
    def last(self, root, cols=20):
        lines = glance(root, cols=cols)
        i = max(k for k, l in enumerate(plain(lines)) if l.strip())
        return lines[i], plain(lines)[i]

    def test_away_main(self):
        root = tree(); guard(root); w(root, "/etc/vegas/away", "")
        raw, txt = self.last(root)
        self.assertRegex(txt, r"^ main away +up 3d$")
        self.assertEqual(len(txt), 19)                              # 1-cell margins both sides
        self.assertIn("38;2;240;180;41maway", raw)                  # "away" amber
        self.assertNotIn("38;2;240;180;41mmain", raw)               # "main" stays plain

    def test_away_rescue_root(self):
        root = tree(); os.remove(root + "/etc/vegas/root-role"); w(root, "/etc/vegas/away", ""); guard(root)
        raw, txt = self.last(root)
        self.assertRegex(txt, r"^ rescue away +up 3d$")

    def test_away_off(self):
        root = tree(); guard(root)
        _, txt = self.last(root)
        self.assertRegex(txt, r"^ main root +up 3d$")

    def test_away_wide(self):
        root = tree(); guard(root); w(root, "/etc/vegas/away", "")
        self.assertTrue(any(re.search(r"main away +up 3d", l) for l in plain(glance(root, cols=44, rows=12))))


# ------------------------------------------------------------------------------------------------ Home helpers
class HomeHelpers(unittest.TestCase):
    def test_battery_detail_and_warnings(self):
        root = tree(temp=405, cur=1100000); guard(root)
        R, _ = load(root)
        import importlib, vegasui.uistatus as U
        importlib.reload(U)
        segs = U.battery_detail(U.battery(), U.guard(), "charging")
        self.assertEqual(U.plain(segs), "charger in · +1.1 A · band 70-80 % · 40 °C")
        self.assertEqual([r for _, r in segs], [None, None, None, "warn"])
        root = tree(temp=420); guard(root); load(root)
        self.assertEqual(U.battery_detail(U.battery(), U.guard())[-1], ("42 °C", "limit"))
        root = tree(online=0); guard(root); load(root)
        self.assertEqual(U.battery_detail(U.battery(), U.guard())[0], ("on battery", "warn"))
        os.remove(root + "/sys/class/power_supply/primary_chg/online")
        self.assertIsNone(U.battery()["online"])
        self.assertEqual(U.battery_detail(U.battery(), U.guard())[0], ("charger ?", "warn"))

    def test_cpu_and_root_detail(self):
        import vegasui.uistatus as U
        self.assertEqual(U.cpu_detail(80, "1600 / 2400 MHz"), [("cap 80 %", "limit"), ("1600 / 2400 MHz", None)])
        self.assertEqual(U.plain(U.cpu_detail(100, "2000 / 2400 MHz")), "no cap · 2000 / 2400 MHz")
        self.assertEqual(U.cpu_detail(100, "x")[0][1], None)
        self.assertEqual(U.root_detail(True, "12 GB free"),
                         [("rescue pending", "warn"), ("disk in /data", None), ("12 GB free", None)])
        self.assertEqual(U.plain(U.root_detail(False, "12 GB free")), "disk in /data · 12 GB free")


if __name__ == "__main__":
    unittest.main()
