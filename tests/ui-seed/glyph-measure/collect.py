# unique right blocks (full_text, min_width) over every upright and rotated state of test_hole.states(); packs them
# into lines of <= 300 logical px -> blocks.json (for emitw.py)
import sys, json
sys.path.insert(0, "/path/to/scratch/ui/status-tests")
import test_hole as H
from test_status import STATUS
vs = H.load(STATUS, "vs")
u = {}
for s in H.states():
    for wdt in (360, 796):
        for b in vs.strip_blocks(s, "23:59", wdt)[1:]:
            u[b["full_text"]] = b["min_width"]
lines, cur, cw = [], [], 0
for ft, mw in sorted(u.items(), key=lambda x: -x[1]):
    if cw + mw > 300:
        lines.append(cur); cur, cw = [], 0
    cur.append([ft, mw]); cw += mw + 2
lines.append(cur)
json.dump(lines, open(sys.argv[1], "w"), ensure_ascii=False)
print(len(u), "blocks in", len(lines), "lines")
