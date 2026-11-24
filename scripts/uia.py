#!/usr/bin/env python3
"""Tiny UI-automation helper over adb (uiautomator dump + input tap).
  uia.py [-s SERIAL] dump                      # print text/desc/clickable/bounds of every node
  uia.py [-s SERIAL] find "<text-or-desc>"     # print matching nodes (substring, case-insensitive)
  uia.py [-s SERIAL] tap  "<text-or-desc>"     # tap center of first matching node; exit 0 if tapped
  uia.py [-s SERIAL] wait "<text-or-desc>" [timeout_s]  # wait until it appears (default 15s)
  uia.py [-s SERIAL] set  "<label>" on|off     # switch/radio vertically nearest the label -> tap only if state differs
Matches node text OR content-desc (substring, case-insensitive; prefix "=" for an exact match).
Returns nonzero if not found.
"""
import re, subprocess, sys, time

def adb(serial, *args):
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)

def dump_nodes(serial):
    adb(serial, "shell", "rm", "-f", "/sdcard/uia.xml")   # never parse a stale dump from a previous screen
    adb(serial, "shell", "uiautomator", "dump", "/sdcard/uia.xml")
    xml = adb(serial, "shell", "cat", "/sdcard/uia.xml").stdout
    nodes = []
    for m in re.finditer(r'<node [^>]*?>', xml):
        s = m.group(0)
        g = lambda k: (re.search(k + r'="([^"]*)"', s) or [None, ""])[1]
        b = g("bounds")
        xy = re.findall(r'\[(\d+),(\d+)\]', b)
        center = None
        if len(xy) == 2:
            (x1, y1), (x2, y2) = [(int(a), int(c)) for a, c in xy]
            center = ((x1 + x2) // 2, (y1 + y2) // 2)
        nodes.append(dict(text=g("text"), desc=g("content-desc"),
                          cls=g("class").split(".")[-1], click=g("clickable"),
                          checkable=g("checkable") == "true", checked=g("checked") == "true",
                          bounds=b, center=center))
    return nodes

def match(nodes, q):
    if q.startswith("="):
        ql = q[1:].lower()
        return [n for n in nodes if ql == n["text"].lower() or ql == n["desc"].lower()]
    ql = q.lower()
    return [n for n in nodes if ql in n["text"].lower() or ql in n["desc"].lower()]

def chk(n):
    return (" chk=" + ("on" if n["checked"] else "off")) if n["checkable"] else ""

def main():
    a = sys.argv[1:]
    serial = ""
    if a and a[0] == "-s":
        serial, a = a[1], a[2:]
    if not a:
        print(__doc__); return 2
    cmd = a[0]
    if cmd == "dump":
        for n in dump_nodes(serial):
            if n["text"] or n["desc"] or n["click"] == "true" or n["checkable"]:
                print(f'[{n["click"]:5}] {n["cls"]:12} text={n["text"]!r} desc={n["desc"]!r} {n["bounds"]}{chk(n)}')
        return 0
    q = a[1]
    if cmd in ("find", "tap"):
        ns = match(dump_nodes(serial), q)
        if not ns:
            print(f"not found: {q!r}", file=sys.stderr); return 1
        if cmd == "find":
            for n in ns: print(f'{n["cls"]} text={n["text"]!r} desc={n["desc"]!r} center={n["center"]} {n["bounds"]}')
            return 0
        n = next((m for m in ns if m["center"]), None)
        if not n: print("no tappable center", file=sys.stderr); return 1
        x, y = n["center"]
        adb(serial, "shell", "input", "tap", str(x), str(y))
        print(f'tapped {q!r} at {x},{y}'); return 0
    if cmd == "set":
        want = (a[2] if len(a) > 2 else "on") == "on"
        nodes = dump_nodes(serial)
        labels = [n for n in match(nodes, q) if n["center"]]
        if not labels: print(f"not found: {q!r}", file=sys.stderr); return 1
        ly = labels[0]["center"][1]
        cands = [n for n in nodes if n["checkable"] and n["center"]]
        if not cands: print("no checkable node on screen", file=sys.stderr); return 1
        n = min(cands, key=lambda m: abs(m["center"][1] - ly))
        if abs(n["center"][1] - ly) > 200: print(f"no checkable node near {q!r}", file=sys.stderr); return 1
        if n["checked"] == want: print(f'{q!r} already {"on" if want else "off"}'); return 0
        x, y = n["center"]
        adb(serial, "shell", "input", "tap", str(x), str(y)); time.sleep(1.5)
        n2 = min((m for m in dump_nodes(serial) if m["checkable"] and m["center"]),
                 key=lambda m: abs(m["center"][1] - y), default=None)
        if n2 is None or n2["checked"] != want: print(f"tapped {q!r} but state did not change", file=sys.stderr); return 1
        print(f'set {q!r} {"on" if want else "off"} (tapped {x},{y})'); return 0
    if cmd == "wait":
        timeout = float(a[2]) if len(a) > 2 else 15
        t0 = time.time()
        while time.time() - t0 < timeout:
            if match(dump_nodes(serial), q): print(f'appeared: {q!r}'); return 0
            time.sleep(1)
        print(f'timeout waiting for {q!r}', file=sys.stderr); return 1
    print(__doc__); return 2

if __name__ == "__main__":
    raise SystemExit(main())
