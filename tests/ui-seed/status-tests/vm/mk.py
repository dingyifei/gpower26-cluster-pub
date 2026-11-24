# fake tree for one scenario: python3 mk.py <dir> <scenario>   (scenario: normal | hidden | ruler | full | busy | awayopen | busyopen)
import sys, os
sys.path.insert(0, "/path/to/scratch/ui/status-tests")
import test_status as T
d, sc = sys.argv[1], sys.argv[2]
busy = dict(soc=12, online=0, soc_mc=82000, policy0=1600000)
root = T.tree(**({"busy": busy, "busyopen": busy}.get(sc, {})))
T.w(root, "/run/vegas-ui/kbd", "hidden" if sc == "hidden" else "shown")
if sc == "ruler": T.w(root, "/run/vegas-ui/strip-ruler", "on")
if sc == "full": T.w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99")
if sc == "busy": os.makedirs(root + "/run/vegas-hotspot"); T.w(root, "/etc/vegas/away", "")
if sc == "awayopen": T.w(root, "/etc/vegas/away", ""); T.w(root, "/run/vegas-ui/away-ssh", "open")   # B1 red
if sc == "busyopen":
    os.makedirs(root + "/run/vegas-hotspot"); T.w(root, "/etc/vegas/away", ""); T.w(root, "/run/vegas-ui/away-ssh", "open")
T.guard(root)
os.system("rm -rf %s && mv %s %s" % (d, root, d))
