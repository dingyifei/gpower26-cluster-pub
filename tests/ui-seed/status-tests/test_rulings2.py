"""Follow-up to the 23 Nov rulings (review of the integrated build), status part:
B1 - Away on with /run/vegas-ui/away-ssh = open is never shown as a plain amber AWAY (strip, glance, report);
ruling 8 - the strip's kbd tap is the person's choice (writes kbd AND kbd-user through uictl);
unknown temperatures read "? °C" in the report (the glance keeps a bare "?").
python3 -m unittest -v test_rulings2   (Mac or the trixie VM; PYTHONDONTWRITEBYTECODE=1)"""
import json, os, re, subprocess, sys, time, unittest

from test_status import OV, STATUS, tree, guard, run, load, w, text_of
from test_rulings import blocks, glance, plain, AMBER, RED

AMBER_FILL = re.compile(r'<span [^>]*background="%s"[^>]*>([^<]*)</span>' % AMBER)
RED_FILL = re.compile(r'<span [^>]*background="%s"[^>]*>([^<]*)</span>' % RED)


def away_tree(ssh):
    root = tree(); w(root, "/etc/vegas/away", "")
    if ssh is not None:
        w(root, "/run/vegas-ui/away-ssh", ssh)
    guard(root)
    return root


class StripAwayOpen(unittest.TestCase):
    def fills(self, root, width):
        b = blocks(root, width)
        return (sum((AMBER_FILL.findall(x["full_text"]) for x in b), []),
                sum((RED_FILL.findall(x["full_text"]) for x in b), []), b)

    def test_open_is_red_never_plain_away(self):
        root = away_tree("open")
        amber, red, b = self.fills(root, 796)
        self.assertEqual(red, [" AWAY ssh open "])
        self.assertNotIn(" AWAY ", amber)
        amber, red, b = self.fills(root, 360)                     # upright: shortened, still red, fits the left half
        self.assertEqual(red, [" SSH OPEN "])
        self.assertNotIn(" AWAY ", amber)
        self.assertTrue(text_of(b[0]).startswith(re.match(r"\d\d:\d\d", text_of(b[0])).group(0)))

    def test_open_on_rescue_root_and_pending(self):
        root = away_tree("open"); os.remove(root + "/etc/vegas/root-role")
        for width in (360, 796):
            amber, red, _ = self.fills(root, width)
            self.assertEqual(len(red), 1, width)
            self.assertNotIn(" AWAY ", amber)
        root = away_tree("open"); w(root, "/rescue", "")
        for width in (360, 796):
            self.assertEqual(len(self.fills(root, width)[1]), 1)

    def test_closed_or_unknown_is_the_amber_away(self):
        for ssh in ("closed", None, "garbage"):
            for width in (360, 796):
                amber, red, _ = self.fills(away_tree(ssh), width)
                self.assertIn(" AWAY ", amber, (ssh, width))
                self.assertEqual(red, [], (ssh, width))

    def test_away_off_ignores_the_file(self):
        root = tree(); w(root, "/run/vegas-ui/away-ssh", "open"); guard(root)   # `vegas-away off` writes open
        for width in (360, 796):
            amber, red, b = self.fills(root, width)
            self.assertEqual((amber, red), ([], []))

    def test_upright_left_side_stays_out_of_the_hole(self):
        """Left text width (logical px) <= half the strip minus the hole gap, in every away/open combination."""
        sys.path.insert(0, os.path.dirname(STATUS))
        for ssh in ("open", "closed"):
            for rescue in (False, True):
                root = away_tree(ssh)
                if rescue:
                    os.remove(root + "/etc/vegas/root-role")
                b = blocks(root, 360)
                n = len(text_of(b[0]))
                self.assertLessEqual(n * 8.03, 360 / 2 - 10 - 20 - 2 + 0.5, (ssh, rescue, text_of(b[0])))


class GlanceAwayOpen(unittest.TestCase):
    def test_red_line(self):
        lines = glance(away_tree("open"))
        txt = plain(lines)
        i = [k for k, l in enumerate(txt) if "SSH OPEN on Wi-Fi" in l]
        self.assertEqual(len(i), 1, txt)
        self.assertIn("38;2;255;107;99mSSH OPEN on Wi-Fi", lines[i[0]])
        self.assertLessEqual(len(txt[i[0]].rstrip()), 20)
        self.assertTrue(any(re.match(r"^ main away +up 3d$", l) for l in txt))   # B5 last line unchanged

    def test_closed_no_line(self):
        self.assertFalse(any("SSH OPEN" in l for l in plain(glance(away_tree("closed")))))
        self.assertFalse(any("SSH OPEN" in l for l in plain(glance(away_tree(None)))))

    def test_pin_pad_away_red(self):
        lines = glance(away_tree("open"), mode="pin")
        self.assertTrue(any("38;2;255;107;99mAWAY" in l for l in lines))
        lines = glance(away_tree("closed"), mode="pin")
        self.assertTrue(any("38;2;240;180;41mAWAY" in l for l in lines))


class ReportAwayOpen(unittest.TestCase):
    def test_report(self):
        out = run(away_tree("open"), "--report").stdout
        self.assertIn("away on: SSH OPEN on Wi-Fi", out)
        out = run(away_tree("closed"), "--report").stdout
        self.assertIn("away on\n", out + "\n")
        self.assertNotIn("OPEN", out)


class Degrees(unittest.TestCase):
    def test_unknown(self):
        root = tree(); guard(root)
        R, _ = load(root)
        self.assertEqual(R.fmt_deg(None), "? °C")
        self.assertEqual(R.fmt_deg(None, space=False), "?")
        os.remove(root + "/sys/class/power_supply/battery/temp")
        self.assertRegex(run(root, "--report").stdout, r"battery .* \? °C")


class KbdTap(unittest.TestCase):
    """Ruling 8: a strip tap on kbd is the person's choice: kbd and kbd-user both change (uictl.kbd toggle), so a
    shell window restores what the person last chose from the strip."""
    def test_tap_sets_kbd_and_kbd_user(self):
        root = tree(); guard(root)
        w(root, "/run/vegas-ui/kbd", "shown"); w(root, "/run/vegas-ui/kbd-user", "hidden")
        bindir = root + "/bin"; os.makedirs(bindir)
        with open(bindir + "/pkill", "w") as f:            # record the signal instead of signalling anything
            f.write('#!/bin/sh\necho "$@" >> %s/pkill.log\n' % root)
        os.chmod(bindir + "/pkill", 0o755)
        e = dict(os.environ, VEGAS_SYSROOT=root, VEGAS_SBIN=root + "/sbin", SWAYSOCK="/nonexistent",
                 PATH=bindir + ":" + os.environ["PATH"])
        p = subprocess.Popen([sys.executable, STATUS, "--bar"], env=e, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(3):
                p.stdout.readline()
            rd = lambda n: open(root + "/run/vegas-ui/" + n).read().strip()
            p.stdin.write('[\n{"name":"kbd","button":1}\n'); p.stdin.flush()
            for _ in range(50):
                if rd("kbd") == "hidden":
                    break
                time.sleep(0.1)
            self.assertEqual((rd("kbd"), rd("kbd-user")), ("hidden", "hidden"))
            p.stdin.write(',{"name":"kbd","button":1}\n'); p.stdin.flush()
            for _ in range(50):
                if rd("kbd") == "shown":
                    break
                time.sleep(0.1)
            self.assertEqual((rd("kbd"), rd("kbd-user")), ("shown", "shown"))
            log = open(root + "/pkill.log").read().splitlines()
            self.assertEqual(log, ["-USR1 -x wvkbd-(vegas|mobintl)", "-USR2 -x wvkbd-(vegas|mobintl)"])
        finally:
            p.terminate(); p.wait(5)
        self.assertNotIn("Traceback", p.stderr.read())


if __name__ == "__main__":
    unittest.main()
