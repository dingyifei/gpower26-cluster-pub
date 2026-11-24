# VM test for vegas-keys: fake mtk-kpd / mtk-pmic-keys / ILITEK_TDDI via uinput, fake sysroot, stub clients.
import evdev, hashlib, os, shutil, subprocess, sys, time
from evdev import ecodes as E, UInput, AbsInfo
HERE = os.path.dirname(os.path.abspath(__file__))
OV = "/path/to/repo/linux/debian/overlay"
KEYS = OV + "/usr/lib/vegas/vegas-keys"
sys.path.insert(0, OV + "/usr/lib/vegas/ui")
def until(cond, limit=2.0):
    t = time.time()
    while not cond() and time.time() - t < limit: time.sleep(0.05)
    return cond()
R = "/tmp/vk-root"
fails = []
def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name, flush=True)
    if not cond: fails.append(name)
def rd(p, d=""):
    try: return open(R + p).read().strip()
    except OSError: return d

shutil.rmtree(R, ignore_errors=True)
for d in ["/sys/class/backlight/ktd3136-bl", "/etc/vegas", "/var/lib/vegas", "/run"]: os.makedirs(R + d)
open(R + "/sys/class/backlight/ktd3136-bl/brightness", "w").write("889\n")
open(R + "/etc/vegas/root-role", "w").write("main\n")
salt = "abc123"; h = hashlib.pbkdf2_hmac("sha256", b"1234", salt.encode(), 1000).hex()
open(R + "/etc/vegas/away-pin", "w").write(f"pbkdf2_sha256$1000${salt}${h}\n")

kpd = UInput({E.EV_KEY: [E.KEY_VOLUMEUP]}, name="mtk-kpd")
pmic = UInput({E.EV_KEY: [E.KEY_POWER, E.KEY_VOLUMEDOWN]}, name="mtk-pmic-keys")
touch = UInput({E.EV_KEY: [E.BTN_TOUCH, E.KEY_POWER],
                E.EV_ABS: [(E.ABS_MT_SLOT, AbsInfo(0, 0, 9, 0, 0, 0)), (E.ABS_MT_TRACKING_ID, AbsInfo(0, -1, 65535, 0, 0, 0)),
                           (E.ABS_MT_POSITION_X, AbsInfo(0, 0, 2159, 0, 0, 0)), (E.ABS_MT_POSITION_Y, AbsInfo(0, 0, 4775, 0, 0, 0))]},
               name="ILITEK_TDDI")
def mknodes():  # the VM has no udev: make /dev/input/eventN from sysfs
    import glob
    for dv in glob.glob("/sys/class/input/event*/dev"):
        mj, mn = map(int, open(dv).read().split(":")); node = "/dev/input/" + dv.split("/")[-2]
        try:
            if os.stat(node).st_rdev == os.makedev(mj, mn): continue
            os.unlink(node)
        except FileNotFoundError: pass
        os.mknod(node, 0o660 | 0o020000, os.makedev(mj, mn))
time.sleep(0.3); mknodes(); time.sleep(0.2)

def key(dev, code, hold=0.05):
    dev.write(E.EV_KEY, code, 1); dev.syn(); time.sleep(hold); dev.write(E.EV_KEY, code, 0); dev.syn()
def tap(px, py):  # panel pixels upright
    x, y = int(px * 2), int(py * 2)
    for ev in [(E.EV_ABS, E.ABS_MT_SLOT, 0), (E.EV_ABS, E.ABS_MT_TRACKING_ID, 7), (E.EV_ABS, E.ABS_MT_POSITION_X, x),
               (E.EV_ABS, E.ABS_MT_POSITION_Y, y), (E.EV_KEY, E.BTN_TOUCH, 1)]: touch.write(*ev)
    touch.syn(); time.sleep(0.05)
    touch.write(E.EV_ABS, E.ABS_MT_TRACKING_ID, -1); touch.write(E.EV_KEY, E.BTN_TOUCH, 0); touch.syn(); time.sleep(0.15)
def cmds(): return rd("/cmds")
def clear(): open(R + "/cmds", "w").close()

env = dict(os.environ, VEGAS_SYSROOT=R, VEGAS_KEYS_DRYRUN="1", VEGAS_MENU=HERE + "/bin/menu",
           VEGAS_GLANCE=HERE + "/bin/glance", VEGAS_UI_LIB=OV + "/usr/lib/vegas/ui", PATH=HERE + "/bin:" + os.environ["PATH"])
log = open(R + "/daemon.log", "w")
d = subprocess.Popen([sys.executable, HERE + "/run.py", KEYS], env=env, stderr=log)
time.sleep(1.0)
bl = lambda: rd("/sys/class/backlight/ktd3136-bl/brightness")
st = lambda: rd("/run/vegas-ui/state")

# the virtual keyboard
import atexit; atexit.register(lambda: d.poll() is None and d.kill())
for _ in range(80):
    mknodes()
    vk = next((evdev.InputDevice(p) for p in evdev.list_devices() if evdev.InputDevice(p).name == "vegas-keys"), None)
    if vk: break
    time.sleep(0.1)
vk.grab()
while open(R + "/daemon.log").read().count("found") < 3: time.sleep(0.2)
if st() != "on":   # VM start delay (no udev) let the test's 2 s idle timer run: wake it
    with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
    time.sleep(0.3); key(pmic, E.KEY_POWER); time.sleep(1.0); key(kpd, E.KEY_VOLUMEUP); time.sleep(0.3)
def emitted():
    out = []
    while True:
        try: out += [E.KEY[e.code] for e in vk.read() if e.type == E.EV_KEY and e.value == 1]
        except BlockingIOError: return out

check("start: state on", st() == "on")
check("start: ctl fifo", os.path.exists(R + "/run/vegas-ui/ctl"))
def grabbed(name):
    dv = next(evdev.InputDevice(p) for p in evdev.list_devices() if evdev.InputDevice(p).name == name)
    try: dv.grab(); dv.ungrab(); return False
    except OSError: return True
check("key devices grabbed by daemon", grabbed("mtk-kpd") and grabbed("mtk-pmic-keys"))
check("touch not grabbed while on", not grabbed("ILITEK_TDDI"))
# Vol in terminal -> PageUp/PageDown
emitted(); key(kpd, E.KEY_VOLUMEUP); key(pmic, E.KEY_VOLUMEDOWN); time.sleep(0.5)
check("on/term vol -> PAGEUP, PAGEDOWN", emitted() == ["KEY_PAGEUP", "KEY_PAGEDOWN"])
open(R + "/win", "w").write("0\n")
key(kpd, E.KEY_VOLUMEUP); time.sleep(0.4)
check("on/home vol -> UP", emitted() == ["KEY_UP"])
open(R + "/run/vegas-ui/home", "w").write("highlight=1\n")
key(pmic, E.KEY_POWER); time.sleep(0.4)
check("on/home highlight -> Power = ENTER", emitted() == ["KEY_ENTER"] and st() == "on")
os.unlink(R + "/win")
# Power press -> off
clear(); key(pmic, E.KEY_POWER); time.sleep(0.5)
check("press -> off, backlight 0", st() == "off" and bl() == "0")
check("off -> no swaymsg mute while the grab works", "events disabled" not in cmds())
check("off: touch grabbed by daemon", grabbed("ILITEK_TDDI"))
tap(500, 500); time.sleep(0.3)
check("tap on dark screen does nothing", st() == "off" and bl() == "0")
# Power press -> glance (backlight only after map)
key(pmic, E.KEY_POWER); time.sleep(0.15)
check("glance: still dark before map", bl() == "0")
time.sleep(1.0)
check("glance: lit after map", st() == "glance" and bl() == "889")
key(kpd, E.KEY_VOLUMEUP); time.sleep(0.5)
check("glance + vol -> on, unmuted", st() == "on" and not grabbed("ILITEK_TDDI") and not os.path.exists(R + "/glance-mapped"))
# idle dim / off
time.sleep(2.3)
check("idle -> dim 205", st() == "dim" and bl() == "205")
tap(300, 300); time.sleep(0.4)
check("touch wakes dim -> on", st() == "on" and bl() == "889")
time.sleep(3.4)
check("idle -> off", st() == "off" and bl() == "0")
# glance times out
key(pmic, E.KEY_POWER); time.sleep(3.2)
check("glance 2 s (test) -> off", until(lambda: st() == "off", 1.0))
# hold -> menu, answer Home
open(R + "/menu-answer", "w").write("Home\n"); clear()
key(pmic, E.KEY_POWER, hold=1.0); time.sleep(0.3)
check("hold 0.8 -> menu (full upright)", "menu full upright" in cmds() and st() == "menu" and bl() == "889")
time.sleep(0.8)
check("menu Home -> on + workspace 1 + main:0", st() == "on" and "workspace number 1" in cmds() and "select-window -t main:0" in cmds())
# menu + power press = ENTER, hold = ESC (while menu open)
open(R + "/menu-answer", "w").write("")
open(R + "/menu-answer", "w").write("Reboot to Android\n"); clear(); emitted()
key(pmic, E.KEY_POWER, hold=1.0); time.sleep(1.0)
check("menu Reboot to Android -> (dryrun) systemctl reboot", until(lambda: "DRYRUN: systemctl reboot" in open(R + "/daemon.log").read(), 3))
time.sleep(2.5)   # the reboot row's sync (capped at 2 s) holds the daemon's main loop; nothing else to wait for
# workspace 2 -> full-prog
open(R + "/ws", "w").write("2"); open(R + "/menu-answer", "w").write("Cancel\n"); clear()
key(pmic, E.KEY_POWER, hold=1.0); time.sleep(0.1)
key(kpd, E.KEY_VOLUMEUP); time.sleep(0.1); key(pmic, E.KEY_POWER); time.sleep(0.2)
check("menu variant full-prog on ws 2", "menu full-prog upright" in cmds()); print(cmds())
check("menu keys: vol UP, power ENTER", emitted()[-2:] == ["KEY_UP", "KEY_ENTER"])
time.sleep(0.6)
check("menu Cancel -> on", until(lambda: st() == "on"))
os.unlink(R + "/ws")
# ctl brightness
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("brightness up\n")
time.sleep(0.4)
check("ctl brightness up -> 1200", until(lambda: bl() == "1200" and rd("/run/vegas-ui/brightness") == "1200"))
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
time.sleep(0.4)
check("ctl screen off", st() == "off" and bl() == "0")
# Away: glance + vol -> pin pad, taps 1 2 3 4 OK
open(R + "/etc/vegas/away", "w").close()
key(pmic, E.KEY_POWER); time.sleep(1.0); key(kpd, E.KEY_VOLUMEUP); time.sleep(0.4)
check("Away: glance + vol -> pin", st() == "pin")
from vegasui import pad
L = pad.layout(1080 // 54, 2388 // 119)       # no glance-geom file: the planned 54x119 cells
def kxy(i): _, _, x, y, w, h = L[i]; return ((x + w / 2) * 54, (y + h / 2) * 119)
for i in [0, 1, 2, 3]: tap(*kxy(i))
check("pin file shows 4 digits", rd("/run/vegas-ui/pin").startswith("n=4"))
tap(*kxy(11))
check("right PIN -> on", until(lambda: st() == "on" and bl() == "1200"))
# wrong PIN x5 -> lockout
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
time.sleep(0.4); key(pmic, E.KEY_POWER); time.sleep(1.0); key(kpd, E.KEY_VOLUMEUP); time.sleep(0.4)
for n in range(5): tap(*kxy(8)); tap(*kxy(11)); time.sleep(0.2)
check("5 wrong -> lockout", "wait" in rd("/run/vegas-ui/pin") and rd("/var/lib/vegas/away-fails").startswith("fails=5"))
# keys-only pad: vol-down highlights key 0 ('1'), power presses it
key(pmic, E.KEY_VOLUMEDOWN); time.sleep(0.3)
check("pin vol-down highlights 0", "hl=0" in rd("/run/vegas-ui/pin"))
# Away locked hold -> short menu
open(R + "/menu-answer", "w").write("Cancel\n"); clear()
key(pmic, E.KEY_POWER, hold=1.0); time.sleep(0.2)
check("Away locked hold -> short menu", "menu short upright" in cmds())
time.sleep(0.8)
check("short menu cancel -> off", st() == "off")
# Away set from Home while on: the holder is unlocked (full menu), next screen-off locks
os.unlink(R + "/var/lib/vegas/away-fails")
key(pmic, E.KEY_POWER); time.sleep(1.0); key(kpd, E.KEY_VOLUMEUP); time.sleep(0.4)   # pin pad
for i in [0, 1, 2, 3, 11]: tap(*kxy(i))
until(lambda: st() == "on")
os.unlink(R + "/etc/vegas/away")
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("away changed\n")
open(R + "/etc/vegas/away", "w").close()
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("away changed\n")
time.sleep(0.3); clear(); open(R + "/menu-answer", "w").write("Cancel\n")
key(pmic, E.KEY_POWER, hold=1.0); time.sleep(0.2)
check("Away turned on from Home: full menu", "menu full upright" in cmds())
until(lambda: st() == "on")
os.unlink(R + "/etc/vegas/away")
# sway hung: every swaymsg/tmux call blocks
open(R + "/hang", "w").close()
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("brightness set 889\n")
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
until(lambda: st() == "off")
key(pmic, E.KEY_POWER)
check("hung sway: glance not mapped, lit anyway (not Away)", until(lambda: st() == "glance" and bl() == "889", 4))
key(kpd, E.KEY_VOLUMEUP)
check("hung sway: vol -> on, lit", until(lambda: st() == "on" and bl() == "889", 4))
t0 = time.time(); key(pmic, E.KEY_POWER)
while bl() != "0" and time.time() - t0 < 5: time.sleep(0.05)
check("hung sway: Power press -> dark within 2.5 s (%.1f s)" % (time.time() - t0), bl() == "0" and time.time() - t0 < 2.5)
# review: a quick press queued while the main loop is blocked (glance wait, sway hung) is a press, not a hold
until(lambda: st() == "off"); clear()
key(pmic, E.KEY_POWER); time.sleep(0.3); key(pmic, E.KEY_POWER)
time.sleep(4.5)
check("review: quick press during blocked glance wait = press (no menu)", "menu " not in cmds() and st() == "off")
n0 = open(R + "/daemon.log").read().count("would sync")
t0 = time.time(); pmic.write(E.EV_KEY, E.KEY_POWER, 1); pmic.syn()
while open(R + "/daemon.log").read().count("would sync") == n0 and time.time() - t0 < 8: time.sleep(0.05)
dt = time.time() - t0; pmic.write(E.EV_KEY, E.KEY_POWER, 0); pmic.syn()
check("hung sway: 5 s reboot on time (%.2f s)" % dt, 4.9 < dt < 5.4)
os.unlink(R + "/hang"); time.sleep(3)
# review: Away + glance window slow to map: dark at first, lit once it maps (was: dark for the whole glance)
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
until(lambda: st() == "off")
open(R + "/etc/vegas/away", "w").close(); open(R + "/glance-delay", "w").write("2.0\n")
key(pmic, E.KEY_POWER); time.sleep(1.8)
check("review: Away, glance not yet mapped -> dark", st() == "glance" and bl() == "0")
check("review: Away, glance maps late -> lit", until(lambda: bl() != "0", 1.5) and st() == "glance")
os.unlink(R + "/glance-delay")
# review: Away + glance window dies while lit -> screen off (never a lit shell while Away)
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
until(lambda: st() == "off"); key(pmic, E.KEY_POWER); until(lambda: bl() != "0", 2)
subprocess.run(["pkill", "-f", HERE + "/bin/glance"])
check("review: Away, glance gone -> off", until(lambda: st() == "off" and bl() == "0", 1.5))
os.unlink(R + "/etc/vegas/away")
# restart while dark stays dark
with open(R + "/run/vegas-ui/ctl", "w") as f: f.write("screen off\n")
until(lambda: st() == "off"); d.kill(); d.wait()
d = subprocess.Popen([sys.executable, HERE + "/run.py", KEYS], env=env, stderr=log)
time.sleep(1.5)
check("restart while off stays off", st() == "off" and bl() == "0" and d.poll() is None)
key(pmic, E.KEY_POWER); time.sleep(1.0); key(kpd, E.KEY_VOLUMEUP)
until(lambda: st() == "on")
# 5 s hold -> emergency
key(pmic, E.KEY_POWER, hold=5.3); time.sleep(0.3)
check("5 s hold -> emergency reboot (dryrun)", "would sync + reboot" in open(R + "/daemon.log").read())
check("daemon alive", d.poll() is None)
d.terminate(); d.wait()
print(open(R + "/daemon.log").read()[-1500:])
print("FAILED:", fails if fails else "none")
