# status_command: python3 emitw.py blocks.json <line>: that line's blocks, no min_width, alternating fills with a
# 2 px black gap (an empty block of min_width 2) between them
import json, sys, time
line = json.load(open(sys.argv[1]))[int(sys.argv[2])]
cols = ["#ff0000", "#00ff00", "#0000ff", "#ff00ff"]
bl = []
for i, (ft, mw) in enumerate(line):
    bl.append({"full_text": ft, "markup": "pango", "background": cols[i % 4], "separator": False, "separator_block_width": 0})
    bl.append({"full_text": "<span size=\"1024\"> </span>", "markup": "pango", "min_width": 2, "separator": False, "separator_block_width": 0})
print(json.dumps({"version": 1}) + "\n[", flush=True)
while True:
    print(json.dumps(bl) + ",", flush=True); time.sleep(30)
