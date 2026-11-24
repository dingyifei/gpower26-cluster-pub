#!/usr/bin/env bash
# Permanent root via KernelSU LKM baked into init_boot. Run AFTER temp root (scripts/reroot.sh).
# Survives reboot with NO exploit; --enable-adbd makes adb shell root on every boot.
#   scripts/permroot.sh [serial]
# Uses the on-device ksud + LKM shipped in the KernelSU APK. Keeps a stock init_boot_a fallback.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
[ -n "${1:-}" ] || { echo "usage: permroot.sh <serial>  (explicit serial required: this flashes)"; exit 1; }
S=$(pick_serial "$1")
a(){ adb -s "$S" "$@"; }
sh(){ a shell "$@" | tr -d '\r'; }
[[ "$(sh id)" == *uid=0* ]] || { echo "not root — run scripts/reroot.sh first"; exit 1; }
BUILD=$(sh getprop ro.build.display.id | grep -oE 'W1WEOS[0-9.-]+' | head -1)
OUTDIR="$ROOT/backups"; mkdir -p "$OUTDIR"
[ "$(sh getprop ro.boot.slot_suffix)" = "_a" ] || { echo "active slot is not _a — this script only handles init_boot_a"; exit 1; }
"$ROOT/scripts/phone.sh" wake "$S" >/dev/null 2>&1 || true
STOCK="$OUTDIR/${S}_${BUILD}_init_boot_a.stock.img"

echo "== stage ksud + LKM from the KernelSU apk =="
KSUD=$(sh 'ls /data/app/*/me.weishu.kernelsu*/lib/arm64/libksud.so' | head -1)
[ -n "$KSUD" ] || { echo "KernelSU apk not found"; exit 1; }
sh "su -c 'cp $KSUD /data/local/tmp/ksud && chmod 755 /data/local/tmp/ksud'"

echo "== dump stock init_boot_a (fallback) =="
if [ -f "$STOCK" ]; then
  # Never overwrite the fallback: on a rerun the live partition may already be the KSU-patched image.
  echo "stock fallback already saved, keeping it: $STOCK"
else
  a exec-out "su -c 'dd if=/dev/block/by-name/init_boot_a bs=4M 2>/dev/null'" > "$STOCK.part"
  [ "$(head -c8 "$STOCK.part")" = "ANDROID!" ] || { echo "bad init_boot dump"; rm -f "$STOCK.part"; exit 1; }
  mv "$STOCK.part" "$STOCK"
fi
# Patch from the saved STOCK image (not the live partition, which may already be patched).
a push "$STOCK" /data/local/tmp/init_boot_a.img >/dev/null

echo "== ksud boot-patch (allow-shell + enable-adbd) =="
sh "su -c '/data/local/tmp/ksud boot-patch -b /data/local/tmp/init_boot_a.img --partition init_boot --kmi android13-5.15 --allow-shell --enable-adbd -o /data/local/tmp --out-name init_boot_ksu.img'" | tail -3
a pull /data/local/tmp/init_boot_ksu.img "$OUTDIR/${S}_${BUILD}_init_boot_ksu.img" >/dev/null 2>&1
[ "$(head -c8 "$OUTDIR/${S}_${BUILD}_init_boot_ksu.img")" = "ANDROID!" ] || { echo "patch failed"; exit 1; }

echo "== flash init_boot_a (fastboot) =="
a reboot bootloader
for _ in $(seq 1 40); do fastboot devices 2>/dev/null | grep -q "$S" && break; sleep 1; done
[ "$(fastboot -s "$S" getvar securestate 2>&1 | sed -n 's/^securestate: //p')" = "flashing_unlocked" ] || { echo "not unlocked"; exit 1; }
fastboot -s "$S" flash init_boot_a "$OUTDIR/${S}_${BUILD}_init_boot_ksu.img"
fastboot -s "$S" reboot
a wait-for-device
for _ in $(seq 1 90); do [ "$(sh getprop sys.boot_completed)" = 1 ] && break; sleep 2; done
"$ROOT/scripts/phone.sh" wake "$S" >/dev/null 2>&1 || true

echo "== verify permanent root (no exploit) =="
if [[ "$(sh id)" == *uid=0* ]] && ! sh 'ls /dev/df' 2>/dev/null | grep -q df; then
  echo "PERMANENT ROOT OK: $(sh id)"
  echo "fallback stock: $OUTDIR/${S}_${BUILD}_init_boot_a.stock.img  (restore: fastboot flash init_boot_a <that>)"
else
  echo "VERIFY FAILED — if bootlooping, restore: fastboot flash init_boot_a $OUTDIR/${S}_${BUILD}_init_boot_a.stock.img"; exit 1
fi
