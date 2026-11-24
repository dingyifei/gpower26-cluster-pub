#!/usr/bin/env bash
# Automated temp-root after a factory wipe (BL already unlocked). You do the on-phone setup only
# up to: finish setup wizard (OFFLINE) -> enable Developer options -> USB debugging ON -> accept RSA.
# Everything below is driven over adb (installs, UI taps via scripts/uia.py).
#   scripts/reroot.sh [serial]
# Proven on phone #1 (XT2617V / W1WEOS36.48-22-3-3-4-2). Needs tools/root-apks/ populated (see its README).
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APKDIR="$ROOT/tools/root-apks"
PY="$ROOT/.venv/bin/python"
source "$ROOT/scripts/lib.sh"
S=$(pick_serial "${1:-}")
a(){ adb -s "$S" "$@"; }
sh(){ a shell "$@" | tr -d '\r'; }
uia(){ "$PY" "$ROOT/scripts/uia.py" -s "$S" "$@"; }
is_root(){ [[ "$(sh id 2>/dev/null)" == *uid=0* ]]; }

echo "== wake: stay awake, AOD off, brightness min, muted, offline =="
"$ROOT/scripts/phone.sh" wake "$S" >/dev/null 2>&1 || true
"$ROOT/scripts/phone.sh" offline "$S" >/dev/null 2>&1 || true

echo "== dismiss keyguard =="
sh input keyevent KEYCODE_WAKEUP; sh wm dismiss-keyguard >/dev/null 2>&1 || true; sh input swipe 540 1800 540 600 150 || true

echo "== ensure KernelSU + DFRoot installed =="
sh pm list packages | grep -q me.weishu.kernelsu || a install "$APKDIR"/KernelSU_v3.3.1_*.apk
sh pm list packages | grep -q df.root          || a install "$APKDIR"/DFRoot_*.apk
sh monkey -p me.weishu.kernelsu -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 1

# Modal system dialogs (e.g. Moto "TurboPower connected" when on a fast charger) sit on top of every app
# and swallow the taps below -> root silently fails. Dismiss any we know before each UI sequence.
dismiss_popups(){
  local b
  for b in "=Got it" "=OK" "=Dismiss"; do uia tap "$b" >/dev/null 2>&1 && sleep 1 || true; done
}

run_exploit(){
  echo "== DFRoot: select KernelSU + LAUNCH ROOT =="
  dismiss_popups
  sh monkey -p df.root -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 2
  dismiss_popups
  if uia find "Working" >/dev/null 2>&1; then echo "  exploit already loaded (Working)"; return 0; fi
  # The SU-manager Spinner shows only an icon when collapsed, so text checks can't tell whether KernelSU is
  # selected (fresh install = placeholder "Select a SU Manager" -> exploit runs without loading KernelSU).
  # Always open it and pick KernelSU explicitly.
  local sp; sp=$(uia dump | awk '/ Spinner /' | grep -oE '\[[0-9]+,[0-9]+\]\[[0-9]+,[0-9]+\]' | head -1)
  if [[ -n "$sp" ]]; then
    read -r x1 y1 x2 y2 <<<"$(echo "$sp" | tr -c '0-9' ' ')"
    sh input tap $(( (x1 + x2) / 2 )) $(( (y1 + y2) / 2 )); sleep 1
    uia tap "=KernelSU" >/dev/null 2>&1 || echo "  !! KernelSU not offered in DFRoot's SU-manager list"; sleep 1
  fi
  uia tap "LAUNCH ROOT" >/dev/null 2>&1 || true
  # poll instead of a fixed sleep: done when adb is root or DFRoot reports "Working" (up to ~40 s)
  for _ in $(seq 1 20); do
    is_root && return 0
    uia find "Working" >/dev/null 2>&1 && { sleep 2; return 0; }
    sleep 2
  done
}

enable_adb_root(){
  # The reliable wiring on this GKI LKM setup: KernelSU Settings -> ADB Root (adbd runs as root).
  echo "== KernelSU: enable ADB Root =="
  sh monkey -p me.weishu.kernelsu -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 2
  dismiss_popups
  uia tap "Settings" >/dev/null 2>&1 || true; sleep 1   # bottom-nav Settings (first match = nav item on this KSU build)
  # scroll until the ADB Root row is in the tappable band: a fixed swipe can park it under the sticky
  # "Settings" title (y < ~250), where uiautomator still reports it but taps hit the header (phone #1, 2026-11-18)
  local y i
  for i in 1 2 3 4 5 6; do
    y=$(uia find "=ADB Root" 2>/dev/null | grep -oE 'center=\([0-9]+, [0-9]+\)' | head -1 | grep -oE '[0-9]+\)$' | tr -d ')')
    if [[ -z "$y" || "$y" -gt 2000 ]]; then sh input swipe 540 1600 540 1000 300
    elif [[ "$y" -lt 400 ]]; then sh input swipe 540 900 540 1300 300
    else break; fi
    sleep 1
  done
  # tap the switch (not the label: the label row isn't clickable). adbd restarts as root right away, so the
  # read-back inside `uia set` usually fails with the connection drop; is_root below is the real check.
  uia set "=ADB Root" on >/dev/null 2>&1 || true
  sleep 4; a wait-for-device
  # KSU keeps the ADB Root setting in /data across reboots, so after drop-root the switch can already read
  # "on" while adbd runs as shell (it only restarts adbd on a toggle). Cycle it off -> on (phone #1, 2026-11-18).
  if ! is_root; then
    echo "  ADB Root already on but adbd not root -> cycling the switch"
    uia set "=ADB Root" off >/dev/null 2>&1 || true; sleep 3; a wait-for-device
    uia set "=ADB Root" on  >/dev/null 2>&1 || true; sleep 4; a wait-for-device
  fi
}

run_exploit
if ! is_root; then enable_adb_root; fi
if ! is_root; then
  echo "== retry: reboot + exploit again (first-run gotcha) =="
  a reboot; a wait-for-device
  for _ in $(seq 1 90); do [ "$(sh getprop sys.boot_completed)" = 1 ] && break; sleep 2; done
  sh input keyevent KEYCODE_WAKEUP; sh wm dismiss-keyguard >/dev/null 2>&1 || true; sh input swipe 540 1800 540 600 150 || true
  "$ROOT/scripts/phone.sh" wake "$S" >/dev/null 2>&1 || true
  run_exploit; is_root || enable_adb_root
fi

if is_root; then echo "ROOT OK: $(sh id)"; else echo "ROOT FAILED — open DFRoot/KernelSU and check manually"; exit 1; fi
