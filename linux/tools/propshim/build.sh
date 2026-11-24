#!/usr/bin/env bash
# Build linux/work/propshim/libpropshim.so (aarch64, -nostdlib) in the amd64 build VM:
#   orb -m vegas-kbuild linux/tools/propshim/build.sh <serial>
# The property table comes from logs/<serial>/linux_b/p2/capture2/props.txt (scripts/linux_b.sh --only android-capture).
set -Eeuo pipefail
SERIAL=${1:?serial of the phone whose props.txt was captured}
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
OUT=$REPO/linux/work/propshim; mkdir -p "$OUT"
python3 "$HERE/mkprops.py" "$REPO/logs/$SERIAL/linux_b/p2/capture2/props.txt" "$OUT/props.h"
aarch64-linux-gnu-gcc -shared -fPIC -nostdlib -O2 -Wall -fno-stack-protector -I"$OUT" \
  -Wl,-soname,libpropshim.so -Wl,--hash-style=both -Wl,-z,noexecstack -o "$OUT/libpropshim.so" "$HERE/propshim.c"
# must not need any library, and must export the property entry points
! aarch64-linux-gnu-readelf -d "$OUT/libpropshim.so" | grep -q NEEDED || { echo "libpropshim.so has DT_NEEDED" >&2; exit 1; }
for s in __system_property_get __system_property_find __system_property_read __system_property_read_callback \
         __system_property_set; do
  aarch64-linux-gnu-nm -D --defined-only "$OUT/libpropshim.so" | grep -qw "$s" || { echo "missing $s" >&2; exit 1; }
done
ls -l "$OUT/libpropshim.so"
