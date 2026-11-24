"""R6 (camera hole, measured on #5 with the ruler: the hole lies within x 170-190 logical, centred on 180): nothing is
drawn in the forbidden band x 166-194 logical (498-582 px at scale 3) in ANY upright state, and landscape (796 wide)
shows the same text as before R6 (vegas-status.pre-r6). Exhaustive over the strip's inputs, in-process (no fork per state).
The model: monospace 10 = 8.03 logical px per character (measured 8.0271-8.0294), ▲/▼ one cell (measured), a right
block whose first character carries the letter_spacing trim 0.3 narrower (measured 0.328-0.355), its leading blank
0.4 narrower; right ink must be past px 582 (x >= 194 1/3). The VM PNGs (vm/r6.sh, r6b) check this against pixels. python3 -m unittest -v test_hole   (Mac or the trixie VM; PYTHONDONTWRITEBYTECODE=1)"""
import importlib.machinery, importlib.util, itertools, os, re, subprocess, sys, tempfile, unittest

from test_status import OV, STATUS, REPO, tree

CH, BAND, PAD, RPAD = 8.03, (166, 194), 20, 18


def load(path, name):
    os.environ["VEGAS_SYSROOT"] = tree()
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    m = importlib.util.module_from_spec(spec)
    loader.exec_module(m)
    return m


def text(block):
    return re.sub(r"<[^>]+>", "", block["full_text"]).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def w(t):
    return sum(CH for c in t)


def trimmed(block):
    return "letter_spacing" in block["full_text"] and len(text(block)) >= 2


def states():
    for (host, soc, glyph, override, soc_t, cap, wifi, hot, away, away_open, rescue, role, kbd) in itertools.product(
            ("vegas5", "vegas12"), (5, 78, 100), ("▲", "▼", "="), (False, True), (None, 41, 105),
            (None, (75, 2000, 1500)), (True, False),
            (None, {"kind": "wifi", "devices": 2}, {"kind": "wifi", "devices": 12}, {"kind": "wifi", "devices": None},
             {"kind": "usb", "devices": None}),
            (False, True), (False, True), (False, True), ("main", "rescue"), (True, False)):
        yield {"bat": {"soc": soc}, "guard": {"override": override, "stop": 100}, "word": "x", "role": "ok",
               "glyph": glyph, "soc_t": soc_t, "cap": cap, "wifi": {"up": wifi}, "usb": {"link": True}, "hot": hot,
               "away": away, "away_open": away and away_open, "rescue": rescue, "role_root": role, "host": host,
               "kbd": kbd}


def crowded():
    """The most crowded upright state the task names: AWAY + AP + cap + charge-to-full amber 100 + rescue variants."""
    base = dict(next(states()))
    base.update(bat={"soc": 100}, guard={"override": True, "stop": 100}, glyph="▲", soc_t=105,
                cap=(75, 2000, 1500), hot={"kind": "wifi", "devices": 12}, away=True)
    out = []
    for rescue, role, away_open in itertools.product((False, True), ("main", "rescue"), (False, True)):
        s = dict(base, rescue=rescue, role_root=role, away_open=away_open)
        out.append(s)
    return out


class Hole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vs = load(STATUS, "vs_new")
        # the strip as it was before R6 (vegas-status from the first public commit), kept beside this file
        cls.old = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vegas-status.pre-r6"), "vs_old")

    def check_upright(self, b, s):
        right = b[1:]
        for x in right:
            self.assertEqual(x["align"], "right")
            self.assertGreaterEqual(x["min_width"], w(text(x)) - (0.3 if trimmed(x) else 0), x)   # min_width rules
        rw = sum(x["min_width"] for x in right)
        lstart = 360 - RPAD - rw - b[0]["min_width"]
        self.assertEqual(lstart, PAD, s)                                   # left text starts exactly at x 20
        self.assertLessEqual(lstart + w(text(b[0])), BAND[0], (s, text(b[0])))
        first = right[0]
        lead = 0 if "background=" in first["full_text"] else len(text(first)) - len(text(first).lstrip(" "))
        lead_px = max(0, lead * CH - (0.4 if lead and trimmed(first) else 0))
        self.assertGreaterEqual(360 - RPAD - rw + lead_px, BAND[1] + 1 / 3, (s, [text(x) for x in right]))

    def test_every_upright_state_clear_of_band(self):
        n = no_net = 0
        for s in states():
            b = self.vs.strip_blocks(s, "23:59", 360)
            self.check_upright(b, s)
            n += 1
            left, names, right = text(b[0]), [x["name"] for x in b], "".join(text(x) for x in b[1:])
            # no amber item ever drops upright (review of R6): rescue word, RESCUE/RESC, AWAY/SSH, AP, amber 100
            if s["rescue"]:
                self.assertIn("resc", left, s)
            elif s["role_root"] == "rescue":
                self.assertIn(" RESC", left, s)
            if s["away"]:
                self.assertIn(" SSH " if s["away_open"] else " AWAY ", left, s)
            if s["hot"]:
                self.assertIn("ap", names, (s, right))
            if s["guard"]["override"]:
                self.assertIn('foreground="#F0B429">100<', [x for x in b if x["name"] == "bat"][0]["full_text"], s)
            # normal running (no hotspot, no cap, no charge-to-full, 2-digit SoC % and temperature): wifi stays
            if not s["hot"] and not s["cap"] and not s["guard"]["override"] and s["bat"]["soc"] < 100 \
                    and s["soc_t"] in (None, 41):
                self.assertIn("net", names, (s, right))
            no_net += "net" not in names
        print("\n%d upright states clear of x 166-194, no amber item dropped; wifi word dropped in %d" % (n, no_net))

    def test_crowded(self):
        for s in crowded():
            b = self.vs.strip_blocks(s, "23:59", 360)
            self.check_upright(b, s)
            right = sum(x["min_width"] for x in b[1:])
            print("\n%-48s|%s|  left ends x %.1f, right ink from x %.1f" % (
                text(b[0]), "".join(text(x) for x in b[1:]), PAD + w(text(b[0])), 360 - RPAD - right + (
                    0 if "background=" in b[1]["full_text"] else max(0, (len(text(b[1])) - len(text(b[1]).lstrip())) * CH - 0.4))))
            amber = [x for x in b if 'background="#F0B429"' in x["full_text"] or "#F0B429" in x["full_text"]]
            self.assertTrue(amber)                                          # something amber always stays

    def test_landscape_text_unchanged(self):
        n = 0
        for s in states():
            new = [(x["name"], text(x)) for x in self.vs.strip_blocks(s, "23:59", 796)]
            old = [(x["name"], text(x)) for x in self.old.strip_blocks(s, "23:59", 796)]
            self.assertEqual(new, old, s)
            n += 1
        print("\n%d landscape states: same text as before R6" % n)

    def test_band_env(self):
        self.assertEqual(self.vs.hole_band(), (166, 194))


if __name__ == "__main__":
    unittest.main()
