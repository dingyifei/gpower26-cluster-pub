#!/usr/bin/env bash
# Build the probe initramfs (lz4 legacy cpio: lk concatenates it after the lz4-legacy vendor ramdisk, and the kernel decoder stops at a gzip member) in the Linux VM, then pack it on the Mac with mkimg.sh:
#   (VM)  linux/initramfs/build.sh            -> linux/work/img/probe-initramfs.cpio.gz
#   (Mac) linux/tools/mkimg.sh init_boot linux/work/img/probe-initramfs.cpio.gz linux/work/img/init_boot_probe.img
# Needs: aarch64-linux-gnu-gcc (static), an arm64 busybox-static binary (fetched from Ubuntu ports).
set -Eeuo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$HERE/../work/initramfs
OUT=$HERE/../work/img
rm -rf "$W/root" && mkdir -p "$W/root/bin" "$OUT"

BB=$W/busybox.arm64
if [ ! -x "$BB" ]; then
  cd "$W"
  apt-get download -o APT::Architecture=arm64 busybox-static:arm64 2>/dev/null || {
    echo "enable arm64 ports: see linux/README.md" >&2; exit 1; }
  dpkg-deb -x busybox-static_*_arm64.deb bbx && cp bbx/usr/bin/busybox "$BB" && rm -rf bbx busybox-static_*_arm64.deb
fi
file "$BB" | grep -q 'ARM aarch64.*statically linked' || { echo "busybox is not static arm64" >&2; exit 1; }

cp "$BB" "$W/root/bin/busybox"
aarch64-linux-gnu-gcc -static -Os -s -o "$W/root/bin/rebootbl" "$HERE/rebootbl.c"
install -m 0755 "$HERE/init" "$W/root/init"
(cd "$W/root" && find . | LC_ALL=C sort | cpio -o -H newc --owner=0:0 --quiet | lz4 -l -12 --favor-decSpeed) > "$OUT/probe-initramfs.cpio.lz4"
ls -l "$OUT/probe-initramfs.cpio.lz4"
