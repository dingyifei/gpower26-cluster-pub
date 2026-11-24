# R6: measure the strip PNGs from r6.sh. Upright: no non-background pixel in x 498-582 px of the bar rows (0-107);
# prints the free gap around the centre (540) per scenario. Also writes <scenario>-<tr>-bar.png (the bar rows only).
import sys, glob, os
from PIL import Image
D = sys.argv[1]; BAND = (498, 582); fails = 0
for p in sorted(glob.glob(D + "/*-normal.png")) + sorted(glob.glob(D + "/*-90.png")):
    if p.endswith("-bar.png"): continue
    im = Image.open(p).convert("RGB"); W, H = im.size
    bar = im.crop((0, 0, W, 108)); bar.save(p[:-4] + "-bar.png")
    px = bar.load(); bg = (0, 0, 0)
    ink = [any(px[x, y] != bg for y in range(108)) for x in range(W)]
    name = os.path.basename(p)[:-4]
    if W == 1080:
        l = max((x for x in range(0, 540) if ink[x]), default=-1); r = min((x for x in range(540, W) if ink[x]), default=W)
        inband = [x for x in range(BAND[0], BAND[1] + 1) if ink[x]]
        ok = not inband; fails += not ok
        print("%-22s free px %d-%d (%d px = %.1f logical); last left ink x %d, first right ink x %d; band 498-582 %s"
              % (name, l + 1, r - 1, r - l - 1, (r - l - 1) / 3, l, r, "CLEAR" if ok else "INK at %s" % inband[:5]))
    else:
        first = min(x for x in range(W) if ink[x]); last = max(x for x in range(W) if ink[x])
        print("%-22s landscape %dx%d, ink x %d-%d" % (name, W, H, first, last))
print("FAILED" if fails else "ALL UPRIGHT CLEAR")
