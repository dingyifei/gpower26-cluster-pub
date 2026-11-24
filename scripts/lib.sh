# Shared helpers for the bench/farm scripts. Source it:  source "$ROOT/scripts/lib.sh"
# Callers set ROOT and S (serial). Nothing here runs on source.
#
# Machine-readable lines for scripts/bench.py (TUI); also readable in a plain terminal:
#   ::stage <name> start|done|fail|skip [msg]
#   ::confirm <token>|<text>     -> reads one line from stdin; must equal <token> (token may contain spaces)
#   ::manual <text>              -> reads one line from stdin (Enter = done, "skip" = skip)
# Per-phone stage state: logs/<serial>/stages.json  {"route": "...", "stages": {name: {status, ts, msg}}}

: "${ROOT:?ROOT must be set before sourcing lib.sh}"

# ---------- serial ----------
# pick_serial [serial] -> the serial to use. With an argument it must be attached (adb or fastboot). Without: only if
# exactly ONE phone is attached, so a forgotten argument can never hit the wrong phone when several run in parallel.
pick_serial() {
  local want="${1:-}" list n
  list=$( { adb devices | awk 'NR>1 && $2=="device"{print $1}'; fastboot devices 2>/dev/null | awk '{print $1}'; } | sort -u)
  if [[ -n "$want" ]]; then
    grep -qx "$want" <<<"$list" || { echo "device $want not attached (adb/fastboot devices)" >&2; exit 1; }
    echo "$want"; return
  fi
  n=$(grep -c . <<<"$list" || true)
  [[ "$n" == 1 ]] || { echo "need exactly one attached phone (found $n) — pass a serial" >&2; exit 1; }
  echo "$list"
}

# ---------- adb / fastboot ----------
ash()  { adb -s "$S" shell "$@" </dev/null 2>&1 | tr -d '\r'; }      # </dev/null: never eat a caller's stdin
gprop() { ash getprop "$1"; }
# fbv <var>: fastboot getvar value. Long values come split as "(bootloader) var[0]: ...", "var[1]: ..." + "var: Done".
fbv()  {
  local out; out=$(fastboot -s "$S" getvar "$1" 2>&1)
  if grep -q "^(bootloader) $1\[" <<<"$out"; then sed -n "s/^(bootloader) $1\[[0-9]*\]: //p" <<<"$out" | tr -d '\n'
  else sed -n "s/^$1: //p" <<<"$out" | head -1; fi
}
is_root() { [[ "$(ash id 2>/dev/null)" == *uid=0* ]]; }
in_adb() { adb devices | awk 'NR>1 && $2=="device"{print $1}' | grep -qx "$S"; }
# Concurrent `fastboot devices` calls on macOS can miss a phone (USB claim race, seen 2026-11-20): retry before "no".
in_fastboot() {
  local i; for i in 1 2 3 4 5; do
    fastboot devices 2>/dev/null | awk '{print $1}' | grep -qx "$S" && return 0
    sleep "0.$((RANDOM % 9 + 1))"
  done; return 1
}

# rsh '<command>': run a shell command as root. adbd root (KernelSU ADB Root) -> plain shell; else `su -c`.
# The command travels base64-encoded, so quotes, pipes and $ need no escaping.
rsh() {
  local b64; b64=$(printf %s "$1" | base64 | tr -d '\n')
  if is_root; then ash "echo $b64 | base64 -d | sh"
  else ash "su -c 'echo $b64 | base64 -d | sh'"; fi
}

# ---------- waits (seconds; return 1 on timeout) ----------
wait_until() { local t=$1; shift; local i; for ((i = 0; i < t; i += 2)); do "$@" && return 0; sleep 2; done; return 1; }
wait_adb()      { wait_until "${1:-120}" in_adb; }
wait_fastboot() { wait_until "${1:-90}" in_fastboot; }
_booted() { in_adb && [[ "$(gprop sys.boot_completed)" == 1 ]]; }
wait_boot()     { wait_until "${1:-180}" _booted; }
_setup_done() { in_adb && [[ "$(ash settings get secure user_setup_complete)" == 1 && "$(ash settings get global device_provisioned)" == 1 ]]; }
wait_setup()    { wait_until "${1:-3600}" _setup_done; }

# ---------- stages ----------
STAGE_DIR() { echo "$ROOT/logs/$S"; }
_stage_write() {   # name status msg
  mkdir -p "$(STAGE_DIR)"
  python3 -I - "$(STAGE_DIR)/stages.json" "${ROUTE:-}" "$1" "$2" "${3:-}" <<'PY'
import json, sys, time, os
f, route, name, status, msg = sys.argv[1:6]
d = {}
if os.path.exists(f):
    try: d = json.load(open(f))
    except Exception: d = {}
if route: d["route"] = route
d.setdefault("stages", {})[name] = {"status": status, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), "msg": msg}
tmp = f + ".tmp"; json.dump(d, open(tmp, "w"), indent=1); os.replace(tmp, f)
PY
}
stage_status() {   # name -> status or empty
  local f; f="$(STAGE_DIR)/stages.json"; [[ -f "$f" ]] || return 0
  python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1])).get("stages",{}).get(sys.argv[2],{}).get("status",""))' "$f" "$1"
}
CUR_STAGE=""
STAGE() { CUR_STAGE="$1"; printf '\n::stage %s start\n=== [%s] %s ===\n' "$1" "$S" "${2:-$1}"; _stage_write "$1" running "${2:-}"; }
STAGE_DONE() { printf '::stage %s done\n' "$CUR_STAGE"; _stage_write "$CUR_STAGE" done "${1:-}"; CUR_STAGE=""; }
STAGE_SKIP() { printf '::stage %s skip %s\n' "$1" "${2:-}"; _stage_write "$1" skip "${2:-}"; }
die() {
  printf '\n!!! [%s] %s\n' "$S" "$*" >&2
  [[ -n "$CUR_STAGE" ]] && { printf '::stage %s fail %s\n' "$CUR_STAGE" "$*"; _stage_write "$CUR_STAGE" fail "$*"; }
  exit 1
}
pass() { printf '  [PASS] %s\n' "$*"; }
info() { printf '  %s\n' "$*"; }

# ---------- human input ----------
# Non-interactive mode (FARM_AUTO=1, e.g. route_d.sh --auto): no stdin. Confirm tokens must be pre-supplied in
# FARM_CONFIRM (newline-separated, from --confirm "<token>", given only on the human's explicit go-ahead);
# manual steps return immediately and the caller polls for the condition instead.
FARM_AUTO="${FARM_AUTO:-0}"; FARM_CONFIRM="${FARM_CONFIRM:-}"
# confirm <token> <text>: the user must type <token> exactly (e.g. "FLASH ZL8...", "ERASE").
confirm() {
  local token="$1"; shift
  if [[ "$FARM_AUTO" == 1 ]]; then
    grep -qxF "$token" <<<"$FARM_CONFIRM" || die "auto mode: '$token' was not pre-confirmed (pass --confirm \"$token\")"
    printf '::confirmed %s|%s (pre-supplied)\n' "$token" "$*"; return 0
  fi
  printf '::confirm %s|%s\n' "$token" "$*"
  printf '>>> %s\n>>> type exactly: %s\n' "$*" "$token"
  local ans; IFS= read -r ans || die "no input (stdin closed) at confirm '$token'"
  [[ "$ans" == "$token" ]] || die "not confirmed (typed '$ans', wanted '$token') — nothing done"
}
# manual <text>: a step only a human can do. Enter when done; "skip" returns 1.
manual() {
  if [[ "$FARM_AUTO" == 1 ]]; then printf '::manual-auto %s\n>>> MANUAL (auto mode, polling): %s\n' "$*" "$*"; return 0; fi
  printf '::manual %s\n' "$*"
  printf '>>> MANUAL: %s\n>>> press Enter when done (or type skip)\n' "$*"
  local ans; IFS= read -r ans || die "no input (stdin closed) at manual step"
  [[ "$ans" != skip ]]
}

# ---------- gates ----------
# Expected identity of this farm's phones (moto g power 2026, Tracfone XT2617V).
EXP_PRODUCT="vegas"; EXP_SKU="XT2617V"; EXP_CID="0x0033"
# All our builds share this family; sub-revisions differ (-4-2 on #1-#6, -4-3 on #7-#8, base after a topic-548192
# downgrade). The exact MBM of the -4-2 phones, kept for reference/logs:
EXP_BUILD_FAMILY="36.48-22-3-3"; EXP_MBM_PART="36.48-22-3-3-4-2-36210f"
# ro.build.id values route D may flash the -4-2 `lk-moto2026.img` onto: the -4-2 sub-rev, and the base downgrade
# target (base <= -4-2). Newer sub-revisions (e.g. -4-3) must be downgraded first (scripts/downgrade.sh).
EXP_BUILDS=("W1WEOS36.48-22-3-3-4-2" "W1WEOS36.48-22-3-3")
EXP_BASEBAND="MT6835O_NR17.RC.MP.V18.6.6.P107.02.309R"

# Topic-548192 downgrade images (gitignored in tools/locked/; see tools/locked/README.md + scripts/downgrade.sh).
LK_ROLLBACK="$ROOT/tools/locked/lk-rollback-3-3.img"     # downgrade allowed, signatures still verified (our default)
LK_NOAVB="$ROOT/tools/locked/lk-no-avb-3-3.img"          # AVB off (persistent root while locked); documented only
MD_UNLOCK_33="$ROOT/tools/locked/md1img-unlock-3-3.img"
FW_BASE_ZIP="$ROOT/tools/locked/XT2617-1_VEGAS_OG_RETUS_16_W1WEOS36.48-22-3-3_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC.xml.zip"
# Full -4-2 retail package ("our common version"); scripts/upgrade.sh flashes it onto a base phone after a downgrade.
FW_42_ZIP="$ROOT/tools/locked/VEGAS_OG_SYS_W1WEOS36.48-22-3-3-4-2_subsidy-DEFAULT_regulatory-DEFAULT_cid50_CFC_Filewale.com.xml.zip"

# build_mbm <version-bootloader or build.id>: the family + sub-rev portion, e.g. "36.48-22-3-3-4-3" (base -> family).
build_mbm() { local s="$1" r="${1##*$EXP_BUILD_FAMILY}"; [[ "$r" =~ ^(-[0-9]+-[0-9]+) ]] && echo "$EXP_BUILD_FAMILY${BASH_REMATCH[1]}" || echo "$EXP_BUILD_FAMILY"; }
# build_subrev <string>: the "-N-M" sub-revision after the family, as "N M" (base/none -> "0 0").
build_subrev() { local r="${1##*$EXP_BUILD_FAMILY}"; [[ "$r" =~ ^-([0-9]+)-([0-9]+) ]] && echo "${BASH_REMATCH[1]} ${BASH_REMATCH[2]}" || echo "0 0"; }
# subrev_gt "N M" "N M": true if the first sub-rev is strictly newer than the second.
subrev_gt() { local a=($1) b=($2); (( a[0] > b[0] || (a[0] == b[0] && a[1] > b[1]) )); }

# gate_fastboot <securestate|locked|any> [build-policy: routed|any]: identity + bootloader version in fastboot.
# Prints FB_SLOT/FB_SECURE. build-policy "routed" (default) refuses builds newer than -4-2 with a downgrade hint;
# "any" accepts any sub-revision of the family (scripts/downgrade.sh, which is about to overwrite everything).
gate_fastboot() {
  local want="${1:-any}" policy="${2:-routed}" v mbm sr
  in_fastboot || die "$S is not in fastboot"
  v=$(fbv product);  [[ "$v" == "$EXP_PRODUCT" ]] || die "fastboot product=$v (want $EXP_PRODUCT)"
  v=$(fbv sku);      [[ "$v" == "$EXP_SKU" ]]     || die "fastboot sku=$v (want $EXP_SKU)"
  v=$(fbv cid);      [[ "$v" == "$EXP_CID" ]]     || die "fastboot cid=$v (want $EXP_CID)"
  v=$(fbv version-bootloader); [[ "$v" == *"$EXP_BUILD_FAMILY"* ]] || die "version-bootloader=$v (want family *$EXP_BUILD_FAMILY*: other models are not supported)"
  mbm=$(build_mbm "$v"); sr=$(build_subrev "$v")
  if [[ "$policy" == routed ]] && subrev_gt "$sr" "4 2"; then
    die "bootloader is ${mbm} (newer than -4-2); route D can't flash it. Downgrade first: scripts/downgrade.sh $S"
  fi
  # Baseband: normally pin to -4-2's P107. GATE_BASEBAND_ANY=1 relaxes this for a caller that is deliberately on a
  # different-baseband intermediate about to be overwritten (scripts/upgrade.sh runs on base 3-3, whose modem is not
  # P107; the -4-2 flash restores it).
  v=$(fbv version-baseband);   [[ "${GATE_BASEBAND_ANY:-0}" == 1 || -z "$v" || "$v" == *P107* ]] || die "version-baseband=$v (want P107)"
  FB_SECURE=$(fbv securestate)
  # "locked" = either locked flavour: a fresh phone reports oem_locked, one relocked with
  # `fastboot flashing lock` (phone #1, 2026-11-18) reports flashing_locked
  if [[ "$want" == locked ]]; then
    [[ "$FB_SECURE" == oem_locked || "$FB_SECURE" == flashing_locked ]] || die "securestate=$FB_SECURE (want oem_locked/flashing_locked)"
  else
    [[ "$want" == any || "$FB_SECURE" == "$want" ]] || die "securestate=$FB_SECURE (want $want)"
  fi
  FB_SLOT=$(fbv current-slot); [[ "$FB_SLOT" == a || "$FB_SLOT" == b ]] || die "current-slot=$FB_SLOT"
  pass "fastboot: $EXP_PRODUCT/$EXP_SKU cid $EXP_CID, bootloader ${mbm}, securestate=$FB_SECURE, slot=$FB_SLOT"
}

# gate_android: identity, build, baseband, setup done, user 0, fastboot<->adb serial is the same phone.
gate_android() {
  in_adb || die "$S is not in adb"
  local v
  v=$(gprop ro.boot.hardware.sku); [[ "$v" == "$EXP_SKU" ]] || die "sku=$v (want $EXP_SKU)"
  local bid; bid=$(gprop ro.build.id); local okb=0 b; for b in "${EXP_BUILDS[@]}"; do [[ "$bid" == "$b" ]] && okb=1; done
  ((okb)) || die "build=$bid (want one of: ${EXP_BUILDS[*]})"
  v=$(gprop gsm.version.baseband); [[ "$v" == "$EXP_BASEBAND"* ]] || die "baseband=$v (want $EXP_BASEBAND)"
  v=$(gprop ro.serialno);          [[ "$v" == "$S" ]] || die "ro.serialno=$v differs from adb serial $S"
  [[ "$(ash settings get secure user_setup_complete)" == 1 ]] || die "setup wizard not complete"
  [[ "$(ash settings get global device_provisioned)" == 1 ]]  || die "device not provisioned"
  [[ "$(ash am get-current-user)" == 0 ]] || die "current user is not 0"
  AN_SLOT=$(gprop ro.boot.slot_suffix); AN_SLOT=${AN_SLOT#_}
  pass "android: $EXP_SKU $bid, baseband P107, setup done, user 0, slot=$AN_SLOT, carrier=$(gprop ro.carrier), $(gprop ro.boot.verifiedbootstate)/locked=$(gprop ro.boot.flash.locked)"
}

# sha of the first N bytes of a partition (N = size of the image we flashed). Root.
part_sha() { rsh "head -c $2 /dev/block/by-name/$1 | sha256sum" | awk '{print $1}'; }
