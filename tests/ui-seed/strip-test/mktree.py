# make a fake tree for one scenario: python3 mktree.py <dir> <scenario>
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../status-tests")
import test_status as T
d, sc = sys.argv[1], sys.argv[2]
kw = {"normal": {}, "busy": dict(soc=12, online=0, soc_mc=82000, policy0=1600000),
      "full": dict(soc=90)}[sc.split("+")[0]]
root = T.tree(**kw)
if "+ap" in sc: os.makedirs(root + "/run/vegas-hotspot")
if "+away" in sc: T.w(root, "/etc/vegas/away", "")
if "+ov" in sc: T.w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99")
if "+rescue" in sc: os.remove(root + "/etc/vegas/root-role"); T.w(root, "/rescue", "")
T.guard(root)
os.system("rm -rf %s && mv %s %s" % (d, root, d))
