#!/usr/bin/env bash
# Pack a test image the way lk's flash gate is predicted to accept it (docs/linux-on-vegas.md 2.4),
# then run checkimg.py on it. Runs on the Mac (mkbootimg + avbtool are installed there).
#
#   mkimg.sh boot      <Image.gz>        <out.img>   # header v4, empty cmdline, gzip kernel
#   mkimg.sh init_boot <ramdisk.cpio.lz4> <out.img>  # header v4, ramdisk only (lz4 legacy, like the vendor ramdisk)
#
# The payload is zero-padded to at least the stock descriptor size before the hash footer is added, so the
# footer's vbmeta_offset never lands below it (the KernelSU-image pattern; a padded small image is untested).
# The footer carries the same properties as stock. Algorithm NONE, like stock.
set -Eeuo pipefail
PART=${1:?part}; IN=${2:?payload}; OUT=${3:?out}
HERE=$(cd "$(dirname "$0")" && pwd)
STOCK=$HERE/../work/stock
case "$PART" in
  boot)      MIN=21549056; PSIZE=67108864; ARGS=(--kernel "$IN") ;;
  init_boot) MIN=3096576;  PSIZE=8388608;  ARGS=(--ramdisk "$IN") ;;
  *) echo "part must be boot or init_boot" >&2; exit 2 ;;
esac
case "$(head -c2 "$IN" | od -An -tx1 | tr -d ' ')" in 1f8b|0221) ;; *) echo "$IN is not gzip/lz4" >&2; exit 1 ;; esac

mkbootimg --header_version 4 --cmdline '' "${ARGS[@]}" --output "$OUT"
sz=$(stat -f%z "$OUT" 2>/dev/null || stat -c%s "$OUT")
[ "$sz" -lt "$MIN" ] && { truncate -s "$MIN" "$OUT"; echo "padded $sz -> $MIN"; }

avbtool add_hash_footer --image "$OUT" --partition_name "$PART" --partition_size "$PSIZE" \
  --prop "com.android.build.$PART.os_version:13" \
  --prop "com.android.build.$PART.fingerprint:motorola/vegas_og_hal/vegas:13/W1WEOS36.48-22-3-3-4-2/36210f:user/release-keys" \
  --prop "com.android.build.$PART.security_patch:2024-05-05"

python3 "$HERE/checkimg.py" "$PART" "$OUT" --differ "$STOCK/$PART.img"
shasum -a 256 "$OUT"
