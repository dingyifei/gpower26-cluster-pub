"""uictl keyboard rule (designer ruling 8). Run on the Mac or in the VM:
    PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_uictl_kbd
"""
import os
import subprocess
import sys
import tempfile
import unittest

OVERLAY = "/path/to/repo/linux/debian/overlay"
sys.path.insert(0, OVERLAY + "/usr/lib/vegas/ui")
from vegasui import uictl  # noqa: E402
from vegasui.host import Result  # noqa: E402

SHOW = ("pkill", "-USR2", "-x", "wvkbd-(vegas|mobintl)")
HIDE = ("pkill", "-USR1", "-x", "wvkbd-(vegas|mobintl)")


class Runner:
    """tmux answers with self.window (None = tmux not answering); records every call."""

    def __init__(self, window=None):
        self.window, self.calls = window, []

    def run(self, argv, timeout=10, input=None):
        self.calls.append(tuple(argv))
        if argv[:2] == ["tmux", "display-message"]:
            return Result(0, f"{self.window}\n") if self.window is not None else Result(1, "", "no server")
        return Result(0)

    def last_signal(self):
        sig = [c for c in self.calls if c[:1] == ("pkill",)]
        return sig[-1] if sig else None


class KbdRule(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["VEGAS_SYSROOT"] = self.tmp.name

    def tearDown(self):
        os.environ.pop("VEGAS_SYSROOT", None)
        self.tmp.cleanup()

    def f(self, name):
        return uictl.ui_read(name)

    def test_user_verbs_set_both_files(self):
        r = Runner(window=2)
        uictl.kbd(r, "hide")
        self.assertEqual((self.f("kbd"), self.f("kbd-user")), ("hidden", "hidden"))
        self.assertEqual(r.last_signal(), HIDE)
        uictl.kbd(r, "toggle")
        self.assertEqual((self.f("kbd"), self.f("kbd-user")), ("shown", "shown"))
        self.assertEqual(r.last_signal(), SHOW)
        uictl.kbd(r, "show")
        self.assertEqual(r.last_signal(), SHOW)

    def test_home_hides_and_shell_restores(self):
        r = Runner()
        uictl.kbd(r, "window", "0")                      # first Home visit, keyboard shown (default)
        self.assertEqual(self.f("kbd"), "hidden")
        self.assertEqual(self.f("kbd-user"), "shown")    # remembered what to restore
        self.assertEqual(r.last_signal(), HIDE)
        uictl.kbd(r, "window", "1")
        self.assertEqual(self.f("kbd"), "hidden")
        uictl.kbd(r, "window", "2")
        self.assertEqual(self.f("kbd"), "shown")
        self.assertEqual(r.last_signal(), SHOW)
        self.assertEqual(self.f("kbd-window"), "2")

    def test_shell_restores_hidden_choice(self):
        r = Runner()
        uictl.kbd(r, "hide")
        uictl.kbd(r, "window", "0")
        uictl.kbd(r, "window", "3")
        self.assertEqual(self.f("kbd"), "hidden")
        self.assertEqual(r.last_signal(), HIDE)

    def test_first_visit_remembers_hidden(self):
        uictl.ui_write("kbd", "hidden")                  # hidden before any choice was recorded
        r = Runner()
        uictl.kbd(r, "window", "0")
        uictl.kbd(r, "window", "2")
        self.assertEqual(self.f("kbd"), "hidden")

    def test_strip_tap_on_home_sets_user_choice(self):
        r = Runner(window=0)
        uictl.kbd(r, "window", "0")
        uictl.kbd(r, "toggle")                           # strip tap while Home keeps it down -> shows
        self.assertEqual((self.f("kbd"), self.f("kbd-user")), ("shown", "shown"))
        uictl.kbd(r, "window", "2")
        self.assertEqual(self.f("kbd"), "shown")

    def test_field_on_off_in_front(self):
        r = Runner(window=1)
        uictl.kbd(r, "window", "1")
        uictl.kbd_field(r, "net", True)
        self.assertEqual(self.f("kbd"), "shown")
        self.assertEqual(self.f("kbd-field-net"), str(os.getpid()))
        uictl.kbd(r, "window", "2")                      # leave with the field still open: the person's choice
        uictl.kbd(r, "window", "1")                      # back: the field still has focus
        self.assertEqual(self.f("kbd"), "shown")
        uictl.kbd(r, "window", "0")                      # Home has no field
        self.assertEqual(self.f("kbd"), "hidden")
        r.window = 1
        uictl.kbd_field(r, "net", False)
        self.assertEqual(self.f("kbd"), "hidden")
        self.assertIsNone(self.f("kbd-field-net"))

    def test_field_does_not_change_user_choice(self):
        r = Runner(window=0)
        uictl.kbd(r, "hide")
        uictl.kbd_field(r, "home", True)
        self.assertEqual(self.f("kbd"), "shown")
        uictl.kbd_field(r, "home", False)
        r.window = 2
        uictl.kbd(r, "auto")
        self.assertEqual((self.f("kbd"), self.f("kbd-user")), ("hidden", "hidden"))

    def test_field_of_a_dead_process_counts_as_none(self):
        p = subprocess.Popen(["true"]); p.wait()
        uictl.ui_write("kbd-field-home", str(p.pid))     # a page that died with a dialog open
        r = Runner()
        uictl.kbd(r, "window", "0")
        self.assertEqual(self.f("kbd"), "hidden")

    def test_field_without_tmux_falls_back_to_request(self):
        r = Runner(window=None)                          # tmux not answering (tests, SSH without the session)
        uictl.kbd_field(r, "net", True)
        self.assertEqual(r.last_signal(), SHOW)
        uictl.kbd_field(r, "net", False)
        self.assertEqual(r.last_signal(), HIDE)

    def test_auto_ignores_another_sessions_window_switch(self):
        """Review 23 Nov: the hook is global, so the Mac's grouped session switching its own windows also runs
        `auto`. main's window is the same then: a keyboard swiped up on Home stays up, and a strip-tap choice on a
        shell window is not re-applied under the person's finger."""
        r = Runner(window=0)
        uictl.kbd(r, "auto")                             # main went to Home: hidden
        self.assertEqual(self.f("kbd"), "hidden")
        uictl.kbd(r, "show")                             # the person swipes it up on Home
        n = len(r.calls)
        uictl.kbd(r, "auto")                             # the Mac switched windows; main still on Home
        self.assertEqual(self.f("kbd"), "shown")
        self.assertIsNone(next((c for c in r.calls[n:] if c[:1] == ("pkill",)), None))
        r.window = 2
        uictl.kbd(r, "auto")                             # main itself changed: the rule applies
        self.assertEqual((self.f("kbd"), self.f("kbd-window")), ("shown", "2"))
        uictl.kbd(r, "toggle")                           # strip tap on the shell: hide (the person's choice)
        uictl.kbd(r, "auto")                             # Mac switch again: nothing
        self.assertEqual((self.f("kbd"), self.f("kbd-user")), ("hidden", "hidden"))
        r.window = 0; uictl.kbd(r, "auto"); r.window = 2; uictl.kbd(r, "auto")
        self.assertEqual(self.f("kbd"), "hidden")        # Home and back: the strip-tap choice is restored

    def test_field_verbs_record_the_window(self):
        r = Runner(window=1)
        uictl.kbd_field(r, "net", True)
        self.assertEqual(self.f("kbd-window"), "1")
        n = len(r.calls)
        uictl.kbd(r, "auto")                             # same window: no second signal
        self.assertIsNone(next((c for c in r.calls[n:] if c[:1] == ("pkill",)), None))

    @unittest.skipUnless(os.path.exists("/proc/self/cmdline"), "needs Linux /proc (run it in the VM)")
    def test_keyboard_change_pokes_the_strip_feed_only(self):
        """The kbd badge follows at once: SIGUSR1 to the pid in strip.pid, only while it is a `vegas-status --bar`
        (never a reused pid), and only when the keyboard state changed."""
        import time
        feed = os.path.join(self.tmp.name, "vegas-status")
        got = os.path.join(self.tmp.name, "got")
        with open(feed, "w") as f:
            f.write("import signal, sys, time\n"
                    "signal.signal(signal.SIGUSR1, lambda *a: open(%r, 'a').write('x'))\n"
                    "print('ready', flush=True)\n"
                    "time.sleep(30)\n" % got)
        p = subprocess.Popen([sys.executable, feed, "--bar"], stdout=subprocess.PIPE, text=True)
        other = subprocess.Popen(["sleep", "30"])
        try:
            p.stdout.readline()
            r = Runner(window=2)
            uictl.ui_write("strip.pid", str(p.pid))
            uictl.kbd(r, "hide")
            uictl.kbd(r, "hide")                         # no change: no second poke
            time.sleep(0.3)
            self.assertEqual(open(got).read(), "x")
            uictl.ui_write("strip.pid", str(other.pid))  # a pid that is not a feed: left alone
            uictl.kbd(r, "show")
            time.sleep(0.3)
            self.assertIsNone(other.poll())
        finally:
            p.kill(); other.kill(); p.wait(); other.wait()

    def test_auto_without_tmux_changes_nothing(self):
        r = Runner(window=None)
        uictl.kbd(r, "auto")
        self.assertIsNone(r.last_signal())

    def test_field_while_shell_in_front_keeps_user_choice(self):
        r = Runner(window=2)
        uictl.kbd(r, "hide")
        uictl.kbd_field(r, "net", True)
        self.assertEqual(self.f("kbd"), "hidden")

    def test_compat_keyboard(self):
        r = Runner(window=None)
        uictl.keyboard(r, True, app="net")
        self.assertEqual(self.f("kbd-field-net"), str(os.getpid()))
        uictl.keyboard(r, False, app="net")
        self.assertIsNone(self.f("kbd-field-net"))
        uictl.keyboard(r, False)                         # not a page (argv[0] is the test runner): the person's choice
        self.assertEqual(self.f("kbd-user"), "hidden")
        old = sys.argv[0]
        try:
            sys.argv[0] = "/usr/local/bin/vegas-home"
            uictl.keyboard(r, True)
            self.assertEqual(self.f("kbd-field-home"), str(os.getpid()))
        finally:
            sys.argv[0] = old

    def test_bad_verbs(self):
        with self.assertRaises(ValueError):
            uictl.kbd(Runner(), "nope")
        with self.assertRaises(ValueError):
            uictl.kbd(Runner(), "field-on", "shell")
        self.assertEqual(uictl._main(["kbd", "window"]), 2)
        self.assertEqual(uictl._main([]), 2)

    def test_files_are_private(self):
        uictl.kbd(Runner(), "hide")
        st = os.stat(self.tmp.name + "/run/vegas-ui/kbd-user")
        self.assertEqual(st.st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
