#!/usr/bin/env bash
# Build a chooser init_boot ramdisk in the VM:  linux/initramfs/build_chooser.sh dry|linux|e <serial>
#   ramdisk = base ramdisk (bytes untouched) ++ overlay (lz4 legacy cpio, unpacked after it, so it wins):
#     /init      = chooser (dry: -DDRY, always Android, logs the key)
#     /init.next = the base ramdisk's own /init (the chooser renames it over /init and execs it)
#     /linux/*   = busybox, init.linux, lpmap, vegasdisk, rebootbl          (linux and e variants)
#   base:  dry, linux = the archived KernelSU init_boot (ksuinit -> rooted Android)
#          e          = the archived STOCK init_boot (stock first-stage init -> unrooted Android: end state E)
# Then on the Mac:  linux/tools/mkimg.sh init_boot linux/work/img/chooser-<v>.ramdisk linux/work/img/init_boot_chooser_<v>.img
#                   python3 linux/tools/checkimg.py init_boot linux/work/img/init_boot_chooser_<v>.img --differ <base image>
set -Eeuo pipefail
V=${1:?dry|linux|e}; SERIAL=${2:?serial of the phone whose archived init_boot is the base}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
W=$REPO/linux/work/chooser-$V; OUT=$REPO/linux/work/img
case "$V" in
  dry|linux) BASE_GLOB="$REPO/backups/${SERIAL}_*_init_boot_ksu.img"; KIND=ksu ;;
  e)         BASE_GLOB="$REPO/backups/${SERIAL}_*_init_boot_a.stock.img"; KIND=stock ;;
  *) echo "variant must be dry, linux or e" >&2; exit 2 ;;
esac
BASE=$(ls $BASE_GLOB 2>/dev/null | head -1)
[ -f "$BASE" ] || { echo "no base image: $BASE_GLOB" >&2; exit 1; }
echo "base ($KIND): $BASE"
rm -rf "$W"; mkdir -p "$W/ov" "$W/base" "$OUT"

# base ramdisk out of the boot image (header v4: page 4096, kernel_size 0, ramdisk_size at offset 12)
python3 - "$BASE" "$W/base.ramdisk" <<'PY'
import struct, sys
d = open(sys.argv[1], 'rb').read()
assert d[:8] == b'ANDROID!' and struct.unpack_from('<I', d, 40)[0] == 4, 'not a v4 boot image'
ksz, rsz = struct.unpack_from('<II', d, 8)
assert ksz == 0 and rsz > 0, 'init_boot must have no kernel and a ramdisk'
r = d[4096:4096 + rsz]
assert r[:4] == b'\x02\x21\x4c\x18', 'base ramdisk is not lz4 legacy (a gzip init_boot ramdisk is silently dropped)'
open(sys.argv[2], 'wb').write(r)
PY
lz4 -dc "$W/base.ramdisk" | cpio -it --quiet > "$W/base_listing.txt"
(cd "$W/base" && lz4 -dc "$W/base.ramdisk" | cpio -id --quiet init)
[ -x "$W/base/init" ] || { echo "base ramdisk has no executable /init" >&2; exit 1; }
if [ "$KIND" = ksu ]; then
  grep -qx init.real "$W/base_listing.txt" && grep -qx kernelsu.ko "$W/base_listing.txt" \
    || { echo "KSU base lacks init.real/kernelsu.ko" >&2; exit 1; }
else
  ! grep -qE '^(init\.real|kernelsu\.ko)$' "$W/base_listing.txt" || { echo "stock base contains KernelSU files" >&2; exit 1; }
  grep -qx 'system/bin/snapuserd' "$W/base_listing.txt" || { echo "stock base does not look like a generic ramdisk" >&2; exit 1; }
fi

CFLAGS=(-static -Os -Wall -Wno-format-truncation)
[ "$V" = dry ] && CFLAGS+=(-DDRY)
aarch64-linux-gnu-gcc "${CFLAGS[@]}" -o "$W/ov/init" "$HERE/chooser.c"
cp "$W/base/init" "$W/ov/init.next"
chmod 0750 "$W/ov/init" "$W/ov/init.next"
if [ "$V" != dry ]; then
  mkdir -p "$W/ov/linux"
  cp "$REPO/linux/work/initramfs/root/bin/busybox" "$W/ov/linux/busybox"
  cp "$HERE/init.linux" "$W/ov/linux/init.linux"
  aarch64-linux-gnu-gcc -static -Os -Wall -o "$W/ov/linux/lpmap" "$HERE/lpmap.c"
  aarch64-linux-gnu-gcc -static -Os -Wall -Wno-format-truncation -o "$W/ov/linux/vegasdisk" "$REPO/linux/tools/vegasdisk.c"
  aarch64-linux-gnu-gcc -static -Os -o "$W/ov/linux/rebootbl" "$HERE/rebootbl.c"
  chmod 0755 "$W/ov/linux" "$W/ov/linux/"*
fi
# overlay cpio: no "." entry (would re-chmod the rootfs root), root-owned
(cd "$W/ov" && find . -mindepth 1 | sed 's#^\./##' | LC_ALL=C sort | cpio -o -H newc --owner=0:0 --quiet | lz4 -l -12 --favor-decSpeed) > "$W/overlay.lz4"
cat "$W/base.ramdisk" "$W/overlay.lz4" > "$OUT/chooser-$V.ramdisk"
# self-check: cpio tools stop at the first TRAILER, the kernel does not. So check the parts: the combined stream
# decodes to exactly the base archive followed by the overlay archive, and the overlay lists what we put in.
lz4 -dc "$OUT/chooser-$V.ramdisk" > "$W/all.cpio"; lz4 -dc "$W/base.ramdisk" > "$W/base.cpio"; lz4 -dc "$W/overlay.lz4" > "$W/ov.cpio"
cmp -s "$W/all.cpio" <(cat "$W/base.cpio" "$W/ov.cpio") || { echo "combined ramdisk != base ++ overlay" >&2; exit 1; }
cpio -it --quiet < "$W/ov.cpio" > "$W/listing.txt"
grep -qx init "$W/listing.txt" && grep -qx init.next "$W/listing.txt" || { echo "overlay lacks init/init.next" >&2; exit 1; }
[ "$V" = dry ] || { grep -qx linux/init.linux "$W/listing.txt" && grep -qx linux/vegasdisk "$W/listing.txt"; } \
  || { echo "overlay lacks linux/init.linux or linux/vegasdisk" >&2; exit 1; }
cmp -s "$W/ov/init.next" "$W/base/init" || { echo "init.next != base /init" >&2; exit 1; }
rm -f "$W/all.cpio" "$W/base.cpio" "$W/ov.cpio"
echo "$BASE" > "$W/base_image.txt"
ls -l "$W/base.ramdisk" "$W/overlay.lz4" "$OUT/chooser-$V.ramdisk"
