# status_command for advance measurement: python3 emit.py <case>; one line of coloured blocks, no min_width
import json, sys, time
B = "<span weight=\"bold\">%s</span>"
CASES = {
 "adv": ["A" * 30, "▲" * 10, "▼" * 10, "A" * 10, "°" * 10],
 "mix": ["A" * 10 + "▲", "A" * 10, "A" * 10 + "▼", B % ("A" * 30)],
 "n34": ["A" * 34], "n37": ["A" * 37], "n41": ["A" * 41], "n36t": ["A" * 30 + "▲▼▲▼▲▼"], "n34b": [B % ("A" * 34)], "n33t": ["A" * 33 + "▲"], "n33d": ["A" * 33 + "▼"], "n33deg": ["A" * 33 + "°"],
 "n17": ["A" * 17, "A" * 17], "n1": ["A", "▲", "AA", "A▲", "AAA", "AA▲"],
 "ls1": ["wif<span letter_spacing=\"-100\">i</span>", "wif<span letter_spacing=\"-200\">i</span>", "wif<span letter_spacing=\"-400\">i</span>", "wif<span letter_spacing=\"-800\">i</span>", "wif<span letter_spacing=\"-1600\">i</span>"],
 "ls2": ["<span letter_spacing=\"-200\"> </span>41°", "<span letter_spacing=\"-400\"> </span>41°", " 78%<span letter_spacing=\"-400\">▲</span>", "<span letter_spacing=\"-400\"> </span>78%▲", "wifi"],
 "real": ["wifi", " 41°", " 78%▲", B % " kbd ", " 100%▲100", B % " AP ", " 105°", B % " k "],
}
if sys.argv[1].startswith("trim"):     # trim<L>_<a>_<b>: 'A'*n for n in a..b, first char letter_spacing -L
    L, a, b = map(int, sys.argv[1][4:].split("_"))
    CASES[sys.argv[1]] = ["<span letter_spacing=\"-%d\">A</span>" % L + "A" * (n - 1) for n in range(a, b + 1)]
cols = ["#ff0000", "#00ff00", "#0000ff", "#ffff00", "#ff00ff", "#00ffff", "#ff8000", "#8000ff"]
print(json.dumps({"version": 1}) + "\n[", flush=True)
bl = [{"full_text": t, "markup": "pango", "background": cols[i % len(cols)], "color": "#ffffff",
       "separator": False, "separator_block_width": 0} for i, t in enumerate(CASES[sys.argv[1]])]
while True:
    print(json.dumps(bl) + ",", flush=True); time.sleep(30)
