# colour runs along the bar's middle row of meas-*.png: prints (colour, x0, x1, width px, width/3 logical)
import sys
from PIL import Image
for p in sys.argv[1:]:
    im = Image.open(p).convert("RGB"); px = im.load(); W = im.size[0]
    print(p.rsplit("/", 1)[-1])
    for y in (4, 103):
        runs, x = [], 0
        while x < W:
            c = px[x, y]; x0 = x
            while x < W and px[x, y] == c: x += 1
            if c != (0, 0, 0): runs.append((c, x0, x - 1, x - x0))
        print("  row %d:" % y, " ".join("%s %d-%d w%d(%.3f)" % ("#%02x%02x%02x" % c, a, b, w, w / 3) for c, a, b, w in runs))
