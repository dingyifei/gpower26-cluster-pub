# R6 fake trees: python3 mk_r6.py <dir> <scenario>
# normal | hidden | crowd (AWAY+AP 12+cap+charge-to-full 100, SoC 100 %, 105 degC) | crowdap (same, 5 %, 41 degC: AP kept)
# crowdresc (rescue root: RESC) | crowdpend (rescue pending) | crowdopen (pending + AWAY ssh open) | crowdrescopen
# fallback (sysfs only, for the swaystatus shell line: 100 %, Charging, 105 degC)
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import test_status as T
d, sc = sys.argv[1], sys.argv[2]
crowd = sc.startswith("crowd")
if sc == "crowdap":
    root = T.tree(soc=5, soc_mc=41000, policy0=1600000)
elif crowd or sc == "fallback":
    root = T.tree(soc=100, status="Charging", soc_mc=105000, policy0=1600000)
else:
    root = T.tree()
T.w(root, "/run/vegas-ui/kbd", "hidden" if sc == "hidden" else "shown")
if crowd:
    T.w(root, "/run/vegas-chargeguard/override", "STOP=100\nRESUME=99")
    os.makedirs(root + "/run/vegas-hotspot")
    T.w(root, "/sbin/vegas-hotspot", "#!/bin/sh\necho 'on: vegas-7k2, %d device(s)'" % (2 if sc == "crowdap" else 12))
    T.w(root, "/etc/vegas/away", "")
    if sc in ("crowdresc", "crowdrescopen"):
        os.remove(root + "/etc/vegas/root-role")
    if sc in ("crowdpend", "crowdopen"):
        T.w(root, "/rescue", "")
    if sc in ("crowdopen", "crowdrescopen"):
        T.w(root, "/run/vegas-ui/away-ssh", "open")
T.guard(root)
os.system("rm -rf %s && mv %s %s" % (d, root, d))
