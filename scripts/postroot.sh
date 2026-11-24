#!/usr/bin/env bash
# Standard cleanup after re-root (BL unlocked, temp-rooted via scripts/reroot.sh).
#   scripts/postroot.sh [serial]
# Does: wake (awake/AOD off/min brightness/mute/no animations), offline, remove work profile (UI), uninstall
# sidemdm, debloat, basics (Fossify SMS+Files, Firefox, F-Droid, Aurora), declutter, Moto 80% charge cap, empty home screen,
# black wallpaper + dark theme, KSU modules, OTA block, record, park.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
S=$(pick_serial "${1:-}")
[[ "$(adb -s "$S" shell id | tr -d '\r')" == *uid=0* ]] || { echo "not root — run scripts/reroot.sh first"; exit 1; }
"$ROOT/scripts/phone.sh" wake "$S" >/dev/null 2>&1 || true
"$ROOT/scripts/phone.sh" offline "$S" || true
"$ROOT/scripts/phone.sh" rm-workprofile "$S" || true
"$ROOT/scripts/phone.sh" rm-sidemdm     "$S" || true
"$ROOT/scripts/phone.sh" debloat        "$S" || true
"$ROOT/scripts/phone.sh" apps           "$S" || true   # basics first (SMS handler before Messages is disabled)
"$ROOT/scripts/phone.sh" declutter      "$S" || true
"$ROOT/scripts/phone.sh" charge-protect "$S" || true   # Moto Battery protection 80% (no root needed)
"$ROOT/scripts/phone.sh" home-clear     "$S" || true
"$ROOT/scripts/phone.sh" black          "$S" || true
"$ROOT/scripts/phone.sh" qs             "$S" || true
"$ROOT/scripts/install_modules.sh" "$S" || echo "!! install_modules FAILED — rerun it"
"$ROOT/scripts/phone.sh" ota-off-root   "$S" || true
"$ROOT/scripts/phone.sh" record         "$S" || true
"$ROOT/scripts/phone.sh" park           "$S" || true
echo "postroot done for $S"
