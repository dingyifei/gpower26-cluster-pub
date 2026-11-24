#!/usr/bin/env python3
"""Read-only parser for Android LP (dynamic partition) metadata in a `super` image or a dump of its head.

  lptool.py dump  <super.img|head.bin> [--slot N]     # lpdump-style table, verifies both checksums
  lptool.py check <super.img|head.bin>                # all slots (primary + backup) parse and checksum OK
  lptool.py cmp   <a> <b> [--ignore NAME]             # same partitions/extents in slot 0 of both (NAME skipped)
  lptool.py map   <super.img|head.bin> NAME [--slot N] # dm-linear table lines: "logical_start sectors super_sector"
  lptool.py overlap <super.img|head.bin> [--slot N]    # exit 1 if any two extents overlap or leave the device

Layout (liblp, metadata v10.x): 4096 reserved, geometry at 4096 and backup at 8192, metadata slots from 12288;
slot n primary at 12288 + n*max, backup at 12288 + (count+n)*max. Never writes anything.
"""
import hashlib
import struct
import sys

GEOM_MAGIC = 0x616C4467
HDR_MAGIC = 0x414C5030
SECTOR = 512


def geometry(d):
    for off in (4096, 8192):
        magic, ssize = struct.unpack_from("<II", d, off)
        if magic != GEOM_MAGIC:
            continue
        csum = d[off + 8:off + 40]
        blob = bytearray(d[off:off + ssize]); blob[8:40] = b"\0" * 32
        if hashlib.sha256(blob).digest() != csum:
            continue
        max_size, slots, lbs = struct.unpack_from("<III", d, off + 40)
        return {"max": max_size, "slots": slots, "lbs": lbs, "at": off}
    raise SystemExit("no valid LP geometry")


def cstr(b):
    return b.split(b"\0", 1)[0].decode()


def metadata(d, g, slot, backup=False):
    off = 12288 + ((g["slots"] if backup else 0) + slot) * g["max"]
    magic, major, minor, hsize = struct.unpack_from("<IHHI", d, off)
    if magic != HDR_MAGIC:
        raise ValueError(f"slot {slot}{' backup' if backup else ''}: bad header magic")
    hdr = bytearray(d[off:off + hsize])
    hcsum = bytes(hdr[12:44]); hdr[12:44] = b"\0" * 32
    if hashlib.sha256(hdr).digest() != hcsum:
        raise ValueError(f"slot {slot}: header checksum")
    tsize = struct.unpack_from("<I", d, off + 44)[0]
    tcsum = d[off + 48:off + 80]
    tables = d[off + hsize:off + hsize + tsize]
    if hashlib.sha256(tables).digest() != tcsum:
        raise ValueError(f"slot {slot}: tables checksum")
    descs = [struct.unpack_from("<III", d, off + 80 + 12 * i) for i in range(4)]  # partitions, extents, groups, bdevs
    flags = struct.unpack_from("<I", d, off + 128)[0] if hsize >= 132 else 0

    def table(i):
        o, n, sz = descs[i]
        return [tables[o + k * sz:o + (k + 1) * sz] for k in range(n)]

    parts = [dict(name=cstr(e[:36]), attrs=struct.unpack_from("<I", e, 36)[0],
                  first=struct.unpack_from("<I", e, 40)[0], n=struct.unpack_from("<I", e, 44)[0],
                  group=struct.unpack_from("<I", e, 48)[0]) for e in table(0)]
    exts = [dict(sectors=struct.unpack_from("<Q", e, 0)[0], type=struct.unpack_from("<I", e, 8)[0],
                 data=struct.unpack_from("<Q", e, 12)[0], src=struct.unpack_from("<I", e, 20)[0]) for e in table(1)]
    groups = [dict(name=cstr(e[:36]), flags=struct.unpack_from("<I", e, 36)[0], max=struct.unpack_from("<Q", e, 40)[0])
              for e in table(2)]
    bdevs = [dict(first=struct.unpack_from("<Q", e, 0)[0], size=struct.unpack_from("<Q", e, 16)[0],
                  name=cstr(e[24:60])) for e in table(3)]
    for p in parts:
        p["extents"] = exts[p["first"]:p["first"] + p["n"]]
        p["group_name"] = groups[p["group"]]["name"]
    return {"version": f"{major}.{minor}", "flags": flags, "parts": parts, "groups": groups, "bdevs": bdevs}


def load(path):
    with open(path, "rb") as f:
        return f.read(1 << 20)  # metadata fits in the first 1 MiB (405,504 B on vegas)


def layout(m):
    return [(p["name"], p["group_name"], p["attrs"], [(e["sectors"], e["type"], e["data"]) for e in p["extents"]])
            for p in m["parts"]]


def main(a):
    if len(a) < 2:
        raise SystemExit(__doc__)
    cmd, path = a[0], a[1]
    slot = int(a[a.index("--slot") + 1]) if "--slot" in a else 0
    d = load(path); g = geometry(d)
    if cmd == "dump":
        m = metadata(d, g, slot)
        print(f"geometry: max={g['max']} slots={g['slots']} lbs={g['lbs']}  metadata {m['version']} flags={m['flags']:#x}")
        for b in m["bdevs"]:
            print(f"block device {b['name']}: size {b['size']} first_logical_sector {b['first']}")
        for gr in m["groups"]:
            print(f"group {gr['name']}: max {gr['max']}")
        end = 0
        for p in m["parts"]:
            ex = ", ".join(f"{e['data']}+{e['sectors']}" for e in p["extents"]) or "-"
            print(f"  {p['name']:<16} {p['group_name']:<8} attrs={p['attrs']} {ex}")
            for e in p["extents"]:
                end = max(end, e["data"] + e["sectors"])
        size = m["bdevs"][0]["size"] // SECTOR
        print(f"last used sector {end}; free after it {size - end} sectors ({(size - end) * SECTOR / 2**30:.2f} GiB)")
    elif cmd == "check":
        bad = 0
        for s in range(g["slots"]):
            for bk in (False, True):
                try:
                    m = metadata(d, g, s, bk); print(f"slot {s} {'backup ' if bk else 'primary'} OK ({len(m['parts'])} partitions)")
                except ValueError as e:
                    print(f"slot {s} {'backup ' if bk else 'primary'} FAIL: {e}"); bad += 1
        sys.exit(1 if bad else 0)
    elif cmd == "cmp":
        d2 = load(a[2]); g2 = geometry(d2)
        ign = a[a.index("--ignore") + 1] if "--ignore" in a else None
        la = [x for x in layout(metadata(d, g, slot)) if x[0] != ign]
        lb = [x for x in layout(metadata(d2, g2, slot)) if x[0] != ign]
        if la == lb:
            print("same layout"); return
        for x in la:
            if x not in lb: print("only in a:", x)
        for x in lb:
            if x not in la: print("only in b:", x)
        sys.exit(1)
    elif cmd == "map":
        name = a[2]
        m = metadata(d, g, slot)
        p = [p for p in m["parts"] if p["name"] == name]
        if not p or not p[0]["extents"] or any(e["type"] != 0 or e["src"] != 0 for e in p[0]["extents"]):
            raise SystemExit(f"{name}: missing, empty, or not all linear extents on super")
        pos = 0
        for e in p[0]["extents"]:
            print(pos, e["sectors"], e["data"]); pos += e["sectors"]
    elif cmd == "overlap":
        m = metadata(d, g, slot); end = m["bdevs"][0]["size"] // SECTOR
        iv = sorted((e["data"], e["data"] + e["sectors"], p["name"]) for p in m["parts"] for e in p["extents"] if e["type"] == 0)
        bad = [(x, y) for x, y in zip(iv, iv[1:]) if y[0] < x[1]] + [(x, "end") for x in iv if x[1] > end or x[0] < m["bdevs"][0]["first"]]
        for b in bad: print("BAD", b)
        print(f"{len(iv)} extents, {len(bad)} problems"); sys.exit(1 if bad else 0)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
