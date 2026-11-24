#!/usr/bin/env bash
# Extract the stock -4-2 kernel config and every stock kernel module, offline.
# Run inside the Linux build VM (needs lz4, cpio, fsck.erofs, python3). Inputs are produced on the Mac by:
#   unzip boot/init_boot/vendor_boot.img from FW_42_ZIP; unpack_bootimg each into <name>/;
#   lpunpack -p vendor_dlkm_a -p system_dlkm_a <phone dump>/super.img
# Usage: linux/tools/extract_stock.sh [linux/work/stock]
set -Eeuo pipefail
W=$(cd "${1:-$(dirname "$0")/../work/stock}" && pwd)
cd "$W"

# 1. vendor ramdisk (lz4 legacy) -> vendor_ramdisk/
rm -rf vendor_ramdisk && mkdir vendor_ramdisk
lz4 -dc vendor_boot/vendor_ramdisk00 | (cd vendor_ramdisk && cpio -idm --quiet)

# 2. generic ramdisk from init_boot -> generic_ramdisk/ (compression autodetected)
rm -rf generic_ramdisk && mkdir generic_ramdisk
case "$(head -c4 init_boot/ramdisk | od -An -tx1 | tr -d ' ')" in
  1f8b*) gzip -dc init_boot/ramdisk ;;
  02214c18) lz4 -dc init_boot/ramdisk ;;
  *) cat init_boot/ramdisk ;;
esac | (cd generic_ramdisk && cpio -idm --quiet)

# 3. erofs dlkm partitions -> vendor_dlkm/, system_dlkm/
for p in vendor_dlkm system_dlkm; do
  rm -rf "$p" && fsck.erofs --extract="$W/$p" "${p}_a.img" >/dev/null
done

# 4. stock kernel config (embedded IKCONFIG) and decompressed Image
gzip -dc boot/kernel > Image.stock
python3 - <<'PY'
import gzip
d = open("Image.stock", "rb").read()
i = d.find(b"IKCFG_ST")
assert i >= 0, "no IKCONFIG in stock kernel"
open("config.stock", "wb").write(gzip.decompress(d[i + 8:d.find(b"IKCFG_ED", i)]))
PY

# 5. module inventory
{
  find vendor_ramdisk -name '*.ko' | sed 's/^/vendor_boot /'
  find vendor_dlkm -name '*.ko' | sed 's/^/vendor_dlkm /'
  find system_dlkm -name '*.ko' | sed 's/^/system_dlkm /'
} | sort > modules.list
awk '{print $1}' modules.list | sort | uniq -c
grep -E '^CONFIG_(LOCALVERSION|DEVTMPFS|FHANDLE|PID_NS|MODULE_SIG_PROTECT|TRIM_UNUSED_KSYMS|BT_HCIVHCI|IKCONFIG_PROC)[ =]|^# CONFIG_(DEVTMPFS|FHANDLE|PID_NS|BT_HCIVHCI) ' config.stock || true
strings Image.stock | grep -m1 'Linux version'
