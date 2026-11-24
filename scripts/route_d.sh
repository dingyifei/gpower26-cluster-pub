#!/usr/bin/env bash
# Route D — the default for phones #2-#8 (decided 2026-11-18).
#   BL stays LOCKED (AVB green). Patched retail lk (tools/locked/lk-moto2026.img: lk reports carrier=retus, so the
#   Tracfone activation/preloads are skipped on first boot). Optional SIM-unlock modem (md1img-unlock.img).
#   Unrooted at rest; temp root (scripts/reroot.sh, DFRoot + KernelSU LKM) only for one-time config and on demand.
#   Charging capped at 80% by Moto Battery protection (no root). OTA: protected-package disable + appops + no internet.
#
#   scripts/route_d.sh <serial> [--from STAGE] [--only STAGE] [--no-modem] [--list]
#                      [--auto [--confirm "FLASH <serial>"] [--confirm "ERASE <serial>"] [--sim-test]]
#   --auto: no stdin (for Claude / unattended). Manual steps poll instead (setup: until setup is done and adb is
#   authorised; sim-test: only with --sim-test, until gsm.sim.state=LOADED). FLASH/ERASE need their --confirm token.
#
# A fresh phone needs NO setup before the flash: power it on holding Vol-down (fastboot) and plug it in.
# Build gate: route D flashes the -4-2 `lk-moto2026.img`, so it accepts only build 36.48-22-3-3 base or -4-2. A phone
# newer than -4-2 (e.g. the -4-3 of #7/#8) is refused at gate-fastboot with a hint to run scripts/downgrade.sh first.
# Human steps (prompted): typed FLASH/ERASE confirms, the offline setup wizard + USB debugging, an optional SIM test.
# Progress: logs/<serial>/stages.json; output also in logs/<serial>/route_d.log. Re-run with --from to resume.
# Phone #1 was converted from A to D on 2026-11-18 (relocked with `fastboot flashing lock`).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
ROUTE=D
trap 'die "unexpected failure at line $LINENO: $BASH_COMMAND"' ERR
NEVER=""   # phone #1 was end state A until 2026-11-18; relocked and converted to D
STAGES=(preflight gate-fastboot flash erase setup gate-android root verify-flash backup clean root-config drop-root verify sim-test record)

LK_IMG="$ROOT/tools/locked/lk-moto2026.img"
MD_IMG="$ROOT/tools/locked/md1img-unlock.img"
# Full-partition sha256 after flashing, as published in P2 #65 (forum; informative, not a gate).
LK_FULL_P2="d2660cc0c4b13cbac241c6b4f068334eb7b46fc46a3c74e4e7106a7256681de2"
MD_FULL_P2="37de8e92352cf4ad44bb8a5b65f028b39ac029b5c96602871032c0c52cfafac4"

usage() { sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'; echo "Stages: ${STAGES[*]}"; exit 1; }
SER=""; FROM=""; ONLY=""; MODEM=1; SIMTEST=0; export FARM_AUTO=0 FARM_CONFIRM=""
while (($#)); do
  case "$1" in
    --from) FROM="$2"; shift 2;; --only) ONLY="$2"; shift 2;;
    --no-modem) MODEM=0; shift;; --list) echo "${STAGES[*]}"; exit 0;;
    --auto) FARM_AUTO=1; shift;; --sim-test) SIMTEST=1; shift;;
    --confirm) FARM_CONFIRM+="$2"$'\n'; shift 2;;
    -h|--help) usage;; -*) usage;; *) SER="$1"; shift;;
  esac
done
[[ -n "$SER" ]] || usage
for st in "$FROM" "$ONLY"; do [[ -z "$st" || " ${STAGES[*]} " == *" $st "* ]] || { echo "unknown stage: $st"; usage; }; done
S="$SER"
[[ " $NEVER " == *" $S "* ]] && { echo "refusing: $S is excluded from route D (phone #1 stays end state A)"; exit 1; }
mkdir -p "$ROOT/logs/$S"
exec > >(tee -a "$ROOT/logs/$S/route_d.log") 2>&1
echo "######## route_d $S $(date '+%F %T') from=${FROM:-start} only=${ONLY:-} modem=$MODEM auto=$FARM_AUTO"

PH="$ROOT/scripts/phone.sh"
slot() { local s; s=$(gprop ro.boot.slot_suffix 2>/dev/null); echo "${s#_}"; }
img_sha() { shasum -a 256 "$1" | awk '{print $1}'; }

# ---------------- stages ----------------
st_preflight() {
  STAGE preflight "files + tools"
  (cd "$ROOT/tools/locked" && grep -E ' (lk-moto2026|md1img-unlock)\.img$' SHA256SUMS | shasum -a 256 -c -) \
    || die "tools/locked images missing or hash mismatch (see tools/locked/README.md)"
  ls "$ROOT"/tools/root-apks/KernelSU_v3.3.1_*.apk "$ROOT"/tools/root-apks/DFRoot_*.apk >/dev/null 2>&1 \
    || die "tools/root-apks/ not populated (KernelSU + DFRoot; see its README)"
  [[ -x "$ROOT/.venv/bin/python" ]] || die ".venv missing (uia.py needs it)"
  command -v sqlite3 >/dev/null || die "sqlite3 missing on the Mac (home-clear)"
  in_adb || in_fastboot || die "$S not attached (boot it into fastboot: hold Vol-down while powering on)"
  STAGE_DONE
}

st_gate_fastboot() {
  STAGE gate-fastboot "identity in fastboot, BL must be locked"
  if ! in_fastboot; then
    in_adb || die "$S is in neither fastboot nor adb"
    info "$S is in adb -> rebooting to bootloader"
    adb -s "$S" reboot bootloader; wait_fastboot 90 || die "did not reach fastboot"
  fi
  if [[ "$(fbv is-userspace)" == yes ]]; then   # fastbootd (recovery): no lk flashing, most getvars unknown
    info "$S is in fastbootd -> rebooting to the bootloader's fastboot"
    fastboot -s "$S" reboot bootloader >/dev/null 2>&1; sleep 3; wait_fastboot 90 || die "did not reach bootloader fastboot"
    [[ "$(fbv is-userspace)" != yes ]] || die "still in fastbootd"
  fi
  gate_fastboot locked
  echo "$FB_SLOT" > "$ROOT/logs/$S/slot"
  STAGE_DONE "slot=$FB_SLOT"
}

st_flash() {
  STAGE flash "patched lk$( ((MODEM)) && echo ' + SIM-unlock modem') -> slot ${FB_SLOT:-?}"
  in_fastboot || die "not in fastboot (run from gate-fastboot)"
  gate_fastboot locked
  confirm "FLASH $S" "flash lk_$FB_SLOT$( ((MODEM)) && echo " + md1img_$FB_SLOT") on $S while LOCKED (route D)"
  fastboot -s "$S" flash "lk_$FB_SLOT" "$LK_IMG" || die "flash lk_$FB_SLOT failed"
  if ((MODEM)); then fastboot -s "$S" flash "md1img_$FB_SLOT" "$MD_IMG" || die "flash md1img_$FB_SLOT failed"; fi
  fastboot -s "$S" reboot-bootloader; sleep 6   # the old USB session lingers a moment: don't read it
  wait_fastboot 90 || die "did not come back to fastboot after flashing"
  local ss="" i; for i in $(seq 1 15); do ss=$(fbv securestate); [[ -n "$ss" ]] && break; sleep 2; done
  [[ "$ss" == "$FB_SECURE" ]] || die "securestate=$ss after flash (was $FB_SECURE before)"
  pass "flashed; still $ss"
  STAGE_DONE
}

st_erase() {
  STAGE erase "wipe userdata + metadata (carrier rules apply on first boot)"
  in_fastboot || die "not in fastboot"
  confirm "ERASE $S" "erase userdata + metadata on $S (factory reset; nvdata/IMEI partitions untouched)"
  fastboot -s "$S" erase userdata || die "erase userdata failed"
  fastboot -s "$S" erase metadata || die "erase metadata failed"
  fastboot -s "$S" reboot
  STAGE_DONE
}

st_setup() {
  STAGE setup "offline setup wizard + USB debugging (manual)"
  if [[ "$FARM_AUTO" == 1 ]]; then
    manual "On $S: finish setup OFFLINE, enable USB debugging, accept RSA" || true
    wait_setup 3600 || die "setup not done within 60 min"
  fi
  until _setup_done; do
    manual "On $S: finish setup OFFLINE (no SIM, skip Wi-Fi, skip Google, decline Smart updates if offered); Settings > About phone > tap Build number 7x; Developer options > USB debugging ON; accept the RSA prompt" \
      || die "setup skipped"
    wait_adb 60 || info "not in adb yet (USB debugging on? RSA accepted?)"
  done
  STAGE_DONE
}

st_gate_android() {
  STAGE gate-android "identity, build, locked/green, carrier"
  gate_android
  [[ "$(gprop ro.boot.flash.locked)" == 1 ]] || die "flash.locked=$(gprop ro.boot.flash.locked) (want 1)"
  [[ "$(gprop ro.boot.verifiedbootstate)" == green ]] || die "verifiedbootstate=$(gprop ro.boot.verifiedbootstate) (want green)"
  [[ "$(gprop ro.carrier)" == retus ]] || die "ro.carrier=$(gprop ro.carrier) (want retus: patched lk not active?)"
  STAGE_DONE
}

st_root() {
  STAGE root "temp root (DFRoot + KernelSU LKM; gone at next reboot)"
  is_root || "$ROOT/scripts/reroot.sh" "$S" || die "temp root failed"
  is_root || die "not root after reroot.sh"
  STAGE_DONE "$(ash id | cut -c1-40)"
}

st_verify_flash() {
  STAGE verify-flash "read back lk$( ((MODEM)) && echo ' + modem') from the live partitions"
  is_root || die "needs root (run stage root)"
  local s n want got full; s=$(slot)
  n=$(stat -f %z "$LK_IMG"); want=$(img_sha "$LK_IMG"); got=$(part_sha "lk_$s" "$n")
  [[ "$got" == "$want" ]] || die "lk_$s first $n B = $got (want $want)"
  full=$(rsh "sha256sum /dev/block/by-name/lk_$s" | awk '{print $1}')
  pass "lk_$s = lk-moto2026.img; full partition ${full:0:12}… $([[ $full == "$LK_FULL_P2" ]] && echo '(= P2 #65)' || echo '(differs from P2 #65 value)')"
  if ((MODEM)); then
    n=$(stat -f %z "$MD_IMG"); want=$(img_sha "$MD_IMG"); got=$(part_sha "md1img_$s" "$n")
    [[ "$got" == "$want" ]] || die "md1img_$s first $n B = $got (want $want)"
    full=$(rsh "sha256sum /dev/block/by-name/md1img_$s" | awk '{print $1}')
    pass "md1img_$s = md1img-unlock.img; full ${full:0:12}… $([[ $full == "$MD_FULL_P2" ]] && echo '(= P2 #65)' || echo '(differs from P2 #65 value)')"
  fi
  STAGE_DONE
}

st_backup() {
  STAGE backup "full partition dump (device-unique nvdata/nvram/proinfo/protect*) -> backups/"
  is_root || die "needs root"
  "$PH" backup "$S" || die "backup failed"
  STAGE_DONE
}

st_clean() {
  STAGE clean "rack settings, basics, declutter, 80% charge cap, QS"
  local c
  for c in wake offline mute apps declutter charge-protect qs no-anim; do "$PH" "$c" "$S" || info "!! phone.sh $c reported a problem"; done
  STAGE_DONE
}

st_root_config() {
  STAGE root-config "one-time root config: protected preloads + OTA, zRAM writeback, empty home, black wallpaper"
  is_root || die "needs root (re-run stage root: the reboot dropped it)"
  "$PH" protected "$S" || die "protected failed"
  "$PH" ram "$S" || info "!! ram failed"
  "$PH" home-clear "$S" || info "!! home-clear failed"
  "$PH" black "$S" || info "!! black failed"
  STAGE_DONE
}

st_drop_root() {
  STAGE drop-root "uninstall DFRoot + KernelSU manager, reboot (LKM root is gone after it)"
  ash pm uninstall df.root >/dev/null || true
  ash pm uninstall me.weishu.kernelsu >/dev/null || true
  adb -s "$S" reboot
  sleep 5; wait_boot 240 || die "did not boot back"
  STAGE_DONE
}

st_verify() {
  STAGE verify "end state D (live read)"
  local bad=0 v
  chk() { if eval "$2"; then pass "$1"; else printf '  [FAIL] %s\n' "$1"; bad=$((bad+1)); fi; }
  "$PH" wake "$S" >/dev/null 2>&1 || true
  chk "unrooted (adbd uid 2000, no su)" '[[ "$(ash id)" == *uid=2000* && -z "$(ash which su)" ]]'
  chk "BL locked + green" '[[ "$(gprop ro.boot.flash.locked)" == 1 && "$(gprop ro.boot.verifiedbootstate)" == green ]]'
  chk "carrier retus" '[[ "$(gprop ro.carrier)" == retus ]]'
  v=$(ash dumpsys package com.motorola.ccc.ota | grep -m1 -E '^ +User 0:' | grep -oE 'enabled=[0-9]+' || true)
  chk "ccc.ota disabled after reboot ($v)" '[[ "$v" == enabled=3 ]]'
  [[ "$v" == enabled=3 ]] || info "   (on tracfone #1 the ota disable was reset at boot; on D rely on appops + no internet; recorded)"
  chk "OTA appops RUN_ANY_IN_BACKGROUND ignore" '[[ "$(ash cmd appops get com.motorola.ccc.ota RUN_ANY_IN_BACKGROUND)" == *ignore* ]]'
  chk "auto-update off" '[[ "$(ash settings get global ota_disable_automatic_update)" == 1 ]]'
  for v in com.motorola.ccc.devicemanagement com.motorola.paks com.tracfone.preload.accountservices; do
    local e; e=$(ash dumpsys package "$v" | grep -m1 -E '^ +User 0:' | grep -oE 'enabled=[0-9]+|installed=false' | head -1 || true)
    chk "$v off or absent (${e:-absent})" '[[ -z "$e" || "$e" == enabled=3 || "$e" == enabled=2 || "$e" == installed=false ]]'
  done
  v=$(ash dumpsys battery | grep -oE 'mUpperLimit:-?[0-9]+' || true)
  [[ "$v" == mUpperLimit:80 ]] || { "$PH" charge-protect "$S" >/dev/null 2>&1 || true; v=$(ash dumpsys battery | grep -oE 'mUpperLimit:-?[0-9]+' || true); }
  chk "charge cap 80% ($v)" '[[ "$v" == mUpperLimit:80 ]]'
  # D4: persist.sys.zram_wb_enabled is labelled zram_control_prop, which the unrooted shell may NOT read
  # (avc denied; getprop returns ""). So it can't be verified here; check it in a root session (farm.py run root).
  info "[INFO] zRAM writeback: not readable unrooted (SELinux zram_control_prop); set to false in root-config, verify under root"
  chk "keyboard = Fossify" '[[ "$(ash settings get secure default_input_method)" == org.fossify.keyboard/* ]]'
  chk "launcher running" '[[ -n "$(ash pidof com.motorola.launcher3)" ]]'
  v=$(ash logcat -b crash -d | grep -c 'FATAL EXCEPTION' || true)
  chk "no app crashes since boot ($v)" '[[ "$v" == 0 ]]'
  ((bad == 0)) || die "$bad check(s) failed (see above)"
  STAGE_DONE
}

st_sim_test() {
  STAGE sim-test "foreign SIM test of the modem unlock (optional)"
  ((MODEM)) || { STAGE_SKIP sim-test "no modem flashed"; CUR_STAGE=""; return 0; }
  if [[ "$FARM_AUTO" == 1 && "$SIMTEST" == 0 ]]; then STAGE_SKIP sim-test "auto mode without --sim-test"; CUR_STAGE=""; return 0; fi
  if [[ "$FARM_AUTO" == 1 ]]; then
    manual "Insert a NON-Tracfone SIM into $S" || true
    wait_until 900 bash -c "[[ \"\$(adb -s $S shell getprop gsm.sim.state </dev/null | tr -d '\r')\" == LOADED* ]]" \
      || die "gsm.sim.state=$(gprop gsm.sim.state) after 15 min (want LOADED)"
  elif ! manual "Insert a NON-Tracfone SIM into $S (hot-plug is fine), then press Enter; type skip to skip"; then
    STAGE_SKIP sim-test "skipped by user"; CUR_STAGE=""; return 0
  fi
  [[ "$FARM_AUTO" == 1 ]] || wait_until 90 bash -c "[[ \"\$(adb -s $S shell getprop gsm.sim.state </dev/null | tr -d '\r')\" == LOADED* ]]" \
    || die "gsm.sim.state=$(gprop gsm.sim.state) (want LOADED)"
  pass "SIM LOADED ($(gprop gsm.sim.operator.alpha) / $(gprop gsm.operator.alpha))"
  ash svc data disable >/dev/null || true
  STAGE_DONE "LOADED"
}

st_record() {
  STAGE record "devices/$S.md + park"
  "$PH" record "$S" || true
  local f="$ROOT/devices/$S.md"
  grep -q "End state D" "$f" 2>/dev/null || printf '\n- **End state D** (route_d.sh, %s): BL locked/green, carrier=retus, modem=%s, unrooted at rest, Moto 80%% cap. Stages: logs/%s/stages.json\n' "$(date +%F)" "$( ((MODEM)) && echo unlocked || echo stock)" "$S" >> "$f"
  "$PH" park "$S" || true
  STAGE_DONE
}

# ---------------- run ----------------
started=0; [[ -z "$FROM" ]] && started=1
for st in "${STAGES[@]}"; do
  if [[ -n "$ONLY" ]]; then [[ "$st" == "$ONLY" ]] || continue
  else
    [[ "$st" == "$FROM" ]] && started=1
    ((started)) || continue
  fi
  # fastboot stages need the slot even when resuming
  if [[ "$st" == flash && -z "${FB_SLOT:-}" ]]; then in_fastboot && FB_SLOT=$(fbv current-slot); fi
  "st_${st//-/_}"
done
echo "######## route_d $S finished (${ONLY:-${FROM:-all}})"
