#!/usr/bin/env python3
"""Read-only parser for the AOSP boot-control block in a dumped `misc` image (vegas: offset 2048).

Usage: bootctrl.py misc.img [--json]
Never writes. Layout = AOSP bootloader_control (hardware/interfaces/boot/1.1/default/boot_control):
  char slot_suffix[4]; u32 magic 'BCAB'; u8 version; u8 nb_slot:3, recovery_tries:3, merge_status:3 ...;
  slot_metadata slot_info[4] (u16: priority:4 tries_remaining:3 successful_boot:1 verity_corrupted:1);
  u8 reserved1[8]; u32 crc32_le  (32 bytes total)
"""
import json
import struct
import sys
import zlib

OFF = 2048
MAGIC = 0x42414342


def parse(blob):
    b = blob[OFF:OFF + 32]
    magic, = struct.unpack_from("<I", b, 4)
    version = b[8]
    bits, = struct.unpack_from("<H", b, 9)
    slots = []
    for i in range(4):
        v, = struct.unpack_from("<H", b, 12 + 2 * i)
        slots.append({"slot": "abcd"[i], "priority": v & 0xF, "tries": (v >> 4) & 0x7,
                      "successful": (v >> 7) & 1, "verity_corrupted": (v >> 8) & 1})
    crc, = struct.unpack_from("<I", b, 28)
    nb = bits & 0x7
    return {"magic_ok": magic == MAGIC, "version": version, "nb_slot": nb,
            "recovery_tries": (bits >> 3) & 0x7, "merge_status": (bits >> 6) & 0x7,
            "crc_ok": zlib.crc32(b[:28]) & 0xFFFFFFFF == crc, "slots": slots[:nb or 2],
            "bcb_command": blob[:32].split(b"\0", 1)[0].decode(errors="replace")}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    r = parse(open(sys.argv[1], "rb").read())
    if "--json" in sys.argv:
        print(json.dumps(r))
        return
    print(f"magic_ok={r['magic_ok']} crc_ok={r['crc_ok']} version={r['version']} nb_slot={r['nb_slot']} "
          f"bcb_command={r['bcb_command']!r}")
    for s in r["slots"]:
        print(f"  slot {s['slot']}: priority={s['priority']} tries={s['tries']} successful={s['successful']} "
              f"verity_corrupted={s['verity_corrupted']}")
    sys.exit(0 if r["magic_ok"] and r["crc_ok"] else 1)


if __name__ == "__main__":
    main()
