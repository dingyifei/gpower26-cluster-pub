#!/usr/bin/env bash
# LEGACY (end state A only): needs an UNLOCKED bootloader. Do not run on D phones (BL locked: flashing init_boot
# would fail or, if it went through, break AVB). Since 2026-11-18 every phone is D; see scripts/route_d.sh.
# Turn root off/on inside end state A. The bootloader stays UNLOCKED either way:
#   rooted    : KernelSU LKM in init_boot_a (scripts/permroot.sh). KSU modules run (ota_block, hide_apps).
#   unrooted  : stock init_boot_a flashed back. No root, no KSU modules. BL still unlocked (orange),
#               modem/SIM unlock kept (md1img is independent of init_boot).
#
#   scripts/root_toggle.sh <serial> unroot [--dry-run] [--yes]
#   scripts/root_toggle.sh <serial> reroot [--dry-run] [--yes]
#
# Both flash ONLY init_boot_a, from images permroot.sh saved in backups/:
#   unroot -> backups/<serial>_<build>_init_boot_a.stock.img
#   reroot -> backups/<serial>_<build>_init_boot_ksu.img     (no exploit/DFRoot needed)
# --dry-run checks every precondition and prints what it would do, but does not reboot or flash.
# Without --yes you must type the serial to confirm the flash.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
[ $# -ge 2 ] || { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
S=$(pick_serial "$1"); MODE="$2"; shift 2
DRY=0; YES=0
for x in "$@"; do case "$x" in --dry-run) DRY=1;; --yes) YES=1;; *) echo "unknown flag $x"; exit 1;; esac; done
[[ "$MODE" == unroot || "$MODE" == reroot ]] || { echo "mode must be unroot|reroot"; exit 1; }

sh(){ adb -s "$S" shell "$@" | tr -d '\r'; }
PHONE="$ROOT/scripts/phone.sh"
BUILD=$(sh getprop ro.build.display.id | grep -oE 'W1WEOS[0-9.-]+' | head -1)
STOCK="$ROOT/backups/${S}_${BUILD}_init_boot_a.stock.img"
KSU="$ROOT/backups/${S}_${BUILD}_init_boot_ksu.img"
sha(){ shasum -a 256 "$1" | cut -c1-16; }

echo "== preconditions ($S, $BUILD, mode=$MODE) =="
[ -n "$BUILD" ] || { echo "cannot read build"; exit 1; }
[ "$(sh getprop ro.boot.slot_suffix)" = "_a" ] || { echo "active slot is not _a"; exit 1; }
[ "$(sh getprop ro.boot.flash.locked)" = "0" ] || { echo "bootloader is locked — nothing to toggle"; exit 1; }
for f in "$STOCK" "$KSU"; do
  [ -f "$f" ] || { echo "missing $f (made by permroot.sh for this serial+build)"; exit 1; }
  [ "$(head -c8 "$f")" = "ANDROID!" ] || { echo "not a boot image: $f"; exit 1; }
done
[ "$(sha "$STOCK")" != "$(sha "$KSU")" ] || { echo "stock and ksu images are identical — stock fallback is bad"; exit 1; }
IS_ROOT=0; [[ "$(sh id)" == *uid=0* ]] && IS_ROOT=1
if [ "$MODE" = unroot ]; then IMG="$STOCK"; [ $IS_ROOT = 1 ] || echo "  note: phone is already unrooted (adb is not root)"
else IMG="$KSU"; [ $IS_ROOT = 0 ] || echo "  note: phone is already rooted"; fi
if [ $IS_ROOT = 1 ]; then
  live=$(sh "head -c $(stat -f %z "$IMG") /dev/block/by-name/init_boot_a | sha256sum" | cut -c1-16)
  echo "  live init_boot_a: $live  (stock $(sha "$STOCK"), ksu $(sha "$KSU"))"
fi
echo "  would flash init_boot_a <- $(basename "$IMG") ($(sha "$IMG"))"
if [ "$MODE" = unroot ]; then
  cat <<'EOF'
  effects of unroot (KSU modules are run by KernelSU from the patched init_boot; stock init_boot runs none):
    - LOST until reroot (kept on disk in /data/adb/modules, so reroot restores them):
        ota_block    ccc.ota DROP, update_engine stop, hosts null-route
        hide_apps    TFDevicePulse, PAKSFinance and Gboard come back (protected: can't be disabled without root)
    - KEPT (plain Android state in /data): apps disabled/uninstalled by declutter/debloat, default SMS/browser/
      keyboard, empty home screen, black wallpaper, dark theme, QS tiles, AOD/brightness/animation/mute settings,
      mobile data/Wi-Fi/BT off, ota_disable_automatic_update. BL stays unlocked, modem/SIM unlock stays.
    - OTA guard after unroot = non-root layers only (phone.sh ota-off: auto-update flag, appops, netpolicy,
      firewall chain3 which resets on reboot -> rerun ota-off after every boot) + keep the phone OFFLINE.
    - charging: unchanged. The 80% cap is Moto Battery protection (system setting, phone.sh charge-protect), not root.
EOF
fi
[ $DRY = 1 ] && { echo "dry run: nothing changed"; exit 0; }

if [ $YES = 0 ]; then
  read -r -p "Type the serial to confirm flashing init_boot_a on $S: " c
  [ "$c" = "$S" ] || { echo "aborted"; exit 1; }
fi

echo "== flash init_boot_a =="
adb -s "$S" reboot bootloader
for _ in $(seq 1 60); do fastboot devices 2>/dev/null | grep -q "$S" && break; sleep 1; done
[ "$(fastboot -s "$S" getvar securestate 2>&1 | sed -n 's/^securestate: //p')" = "flashing_unlocked" ] || { echo "not flashing_unlocked — rebooting, nothing flashed"; fastboot -s "$S" reboot; exit 1; }
[ "$(fastboot -s "$S" getvar current-slot 2>&1 | sed -n 's/^current-slot: //p')" = "a" ] || { echo "fastboot slot is not a — rebooting, nothing flashed"; fastboot -s "$S" reboot; exit 1; }
fastboot -s "$S" flash init_boot_a "$IMG"
fastboot -s "$S" reboot
adb -s "$S" wait-for-device
for _ in $(seq 1 90); do [ "$(sh getprop sys.boot_completed)" = 1 ] && break; sleep 2; done

echo "== verify =="
"$PHONE" wake "$S" >/dev/null 2>&1 || true
"$PHONE" offline "$S" >/dev/null 2>&1 || true
if [ "$MODE" = unroot ]; then
  [[ "$(sh id)" != *uid=0* ]] || { echo "STILL ROOT — unroot did not take"; exit 1; }
  "$PHONE" ota-off "$S" || true
  echo "UNROOTED: $(sh id | cut -d' ' -f1); BL $(sh getprop ro.boot.verifiedbootstate); re-root: $0 $S reroot"
else
  [[ "$(sh id)" == *uid=0* ]] || { echo "NOT ROOT — reroot did not take (restore: $0 $S unroot)"; exit 1; }
  echo "REROOTED: $(sh id | cut -d' ' -f1); modules: $(sh ls /data/adb/modules | tr '\n' ' ')"
fi
"$PHONE" record "$S" >/dev/null 2>&1 || true
