#!/usr/bin/env python3
"""Refuse a boot/init_boot image that lk's flash gate (or boot path) is predicted to reject.

Rules (docs/linux-on-vegas.md section 2.4, read from the stock -4-2 lk):
  * Android boot header v4 (magic ANDROID!)
  * boot: kernel is gzip (lk decompresses only gzip / lz4-legacy); init_boot: kernel_size == 0
  * AVB footer present, for the right partition, with vbmeta_offset >= the stock descriptor size
  * image == partition size
  * --differ STOCK: payload hash must differ from stock (a byte-identical repack tests nothing)

Usage: checkimg.py {boot|init_boot} IMAGE [--differ STOCK_IMAGE]
"""
import hashlib
import struct
import sys

STOCK_DESC = {"boot": 21549056, "init_boot": 3096576}
PART_SIZE = {"boot": 67108864, "init_boot": 8388608}


def footer(d):
    f = d[-64:]
    if f[:4] != b"AVBf":
        return None
    _maj, _min, orig, off, size = struct.unpack(">IIQQQ", f[4:36])
    return orig, off, size


def avb_partition_name(d, off, size):
    # vbmeta blob: auxiliary block holds the hash descriptor with the partition name; find it textually
    blob = d[off:off + size]
    for name in ("init_boot", "boot"):
        if name.encode() in blob:
            return name
    return None


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in STOCK_DESC:
        sys.exit(__doc__)
    part, img = a[0], a[1]
    stock = a[a.index("--differ") + 1] if "--differ" in a else None
    d = open(img, "rb").read()
    errs = []
    if d[:8] != b"ANDROID!":
        errs.append("no ANDROID! magic")
    else:
        ksz, rsz = struct.unpack_from("<II", d, 8)
        hv, = struct.unpack_from("<I", d, 40)
        if hv != 4:
            errs.append(f"header_version {hv} != 4")
        if part == "boot":
            if d[4096:4098] != b"\x1f\x8b":
                errs.append("kernel is not gzip")
            if ksz == 0:
                errs.append("no kernel")
        elif ksz != 0:
            errs.append("init_boot carries a kernel")
        if part == "init_boot" and rsz == 0:
            errs.append("no ramdisk")
        # v4 header: ramdisk starts at page 1 when kernel_size == 0. It must be lz4 legacy: lk appends it to the
        # lz4-legacy vendor ramdisk and the kernel's decoder drops a gzip member silently (2026-11-22: probe skipped,
        # Android booted from the vendor ramdisk's own /init).
        if part == "init_boot" and rsz and d[4096:4100] != b"\x02\x21\x4c\x18":
            errs.append("init_boot ramdisk is not lz4 legacy")
    if len(d) != PART_SIZE[part]:
        errs.append(f"size {len(d)} != partition {PART_SIZE[part]}")
    ft = footer(d)
    if not ft:
        errs.append("no AVB footer")
    else:
        orig, off, size = ft
        if off < STOCK_DESC[part]:
            errs.append(f"footer vbmeta_offset {off} < stock descriptor {STOCK_DESC[part]}")
        if avb_partition_name(d, off, size) != part:
            errs.append("footer descriptor is not for this partition")
        print(f"footer: original={orig} vbmeta_offset={off} vbmeta_size={size}")
    if stock:
        s = open(stock, "rb").read()
        so = footer(s)[0]
        mine = hashlib.sha256(d[:ft[0]] if ft else d).hexdigest()
        theirs = hashlib.sha256(s[:so]).hexdigest()
        if mine == theirs:
            errs.append("payload identical to stock")
    for e in errs:
        print("FAIL", e)
    print("OK" if not errs else "REFUSED", img)
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
