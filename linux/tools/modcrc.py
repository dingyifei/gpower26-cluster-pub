#!/usr/bin/env python3
"""Offline gate: do the stock vendor modules match a built kernel's symbol CRCs?

For every stock .ko, read its imported symbol CRCs (__versions) and compare them with the
built kernel's Module.symvers. Imports that vmlinux does not export must be exported by
another stock module (__ksymtab_strings), otherwise they count as missing.

Usage: modcrc.py <Module.symvers> <dir-with-.ko> [<dir> ...]
Exit 0 only with 0 mismatches and 0 missing. No dependencies beyond the stdlib.
"""
import struct
import sys
from pathlib import Path


def sections(path):
    d = path.read_bytes()
    if d[:4] != b"\x7fELF" or d[4] != 2 or d[5] != 1:
        raise ValueError(f"{path}: not ELF64 LE")
    shoff, = struct.unpack_from("<Q", d, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x3A)
    hdrs = [struct.unpack_from("<IIQQQQIIQQ", d, shoff + i * shentsize) for i in range(shnum)]
    stroff, strsize = hdrs[shstrndx][4], hdrs[shstrndx][5]
    names = d[stroff:stroff + strsize]
    out = {}
    for h in hdrs:
        n = names[h[0]:names.index(b"\0", h[0])].decode()
        out[n] = d[h[4]:h[4] + h[5]]
    return out


def versions(sec):
    # struct modversion_info { unsigned long crc; char name[56]; }  (64 bytes on arm64)
    for i in range(0, len(sec), 64):
        crc, = struct.unpack_from("<Q", sec, i)
        name = sec[i + 8:i + 64].split(b"\0", 1)[0].decode()
        yield name, crc & 0xFFFFFFFF


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    symvers = {}
    for line in open(sys.argv[1]):
        f = line.rstrip("\n").split("\t")
        symvers[f[1]] = (int(f[0], 16), f[2])
    kos = sorted(p for d in sys.argv[2:] for p in Path(d).rglob("*.ko"))
    mods, mod_exports = {}, set()
    for ko in kos:
        s = sections(ko)
        mods[ko] = list(versions(s.get("__versions", b"")))
        mod_exports.update(x.decode() for x in s.get("__ksymtab_strings", b"").split(b"\0") if x)
    checked = mismatch = missing = 0
    bad = []
    for ko, imps in mods.items():
        for name, crc in imps:
            if name in symvers:
                checked += 1
                if symvers[name][0] != crc:
                    mismatch += 1
                    bad.append(f"MISMATCH {ko.name}: {name} module={crc:#010x} kernel={symvers[name][0]:#010x}")
            elif name not in mod_exports:
                missing += 1
                bad.append(f"MISSING  {ko.name}: {name}")
    for b in bad[:200]:
        print(b)
    nover = sum(1 for v in mods.values() if not v)
    print(f"modules={len(kos)} without__versions={nover} kernel_imports_checked={checked} "
          f"mismatch={mismatch} missing={missing}")
    sys.exit(0 if not (mismatch or missing) and kos else 1)


if __name__ == "__main__":
    main()
