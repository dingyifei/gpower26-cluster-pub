#!/usr/bin/env bash
# Upgrade a base-`36.48-22-3-3` moto g power 2026 (e.g. straight after scripts/downgrade.sh) UP to the fleet's common
# version W1WEOS36.48-22-3-3-4-2 — the stock build #1-#6 run and the proven input to route_d.sh. Forward flash only
# (base -> -4-2 raises the AVB rollback index, which is allowed; the blocked direction is -4-3 -> -4-2, which is why
# a -4-3 phone goes via base first: downgrade.sh then this).
#
#   scripts/upgrade.sh <serial> [--from STAGE] [--only STAGE] [--list] [--no-fw-hash]
#                      [--auto [--confirm "UPGRADE <serial>"]]
#
# Flow: in fastboot, locked, slot a -> flash the full -4-2 firmware from its own flashfile.xml, INCLUDING lk_a (we want
# the stock -4-2 bootloader so the phone matches a fresh -4-2 device), but NOT gpt/preloader (keep what's there; a
# -4-2 preloader over a -4-3 preloader is a preloader DOWNGRADE = the worst brick risk on a locked BL) and NOT the
# nvdata erase (device-unique IMEI/RF cal). userdata/metadata are erased as Motorola lists (fresh). The stock -4-2
# md1img is flashed here; route_d.sh re-flashes the SIM-unlock modem afterward.
#
# Leaves the phone in fastboot on a clean, locked stock -4-2. Next: scripts/route_d.sh <serial> for end state D.
#
# The firmware command list is derived from Motorola's own flashfile.xml inside the zip on every run (not hand-kept).
# UNVERIFIED end-to-end until run on hardware; the BL stays locked, so a wrong image is a brick risk and the typed
# confirm is real. Validate on one phone (#7) before the next.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
ROUTE=upgrade
# We run on a base-3-3 phone (post-downgrade) whose modem baseband is not -4-2's P107; the -4-2 flash restores it.
export GATE_BASEBAND_ANY=1
trap 'die "unexpected failure at line $LINENO: $BASH_COMMAND"' ERR
STAGES=(preflight gate-fastboot flash-firmware gate-42)

# Partitions the -4-2 flash must NOT touch: keep the current partition table + preloader (never downgrade the
# preloader; flashing the -4-2 one over a -4-3 phone is a preloader rollback). lk IS flashed (we want stock -4-2 lk).
SKIP_FLASH_PARTS="gpt preloader"   # matched on the flashfile's partition= attribute
SKIP_ERASE_PARTS="nvdata"          # device-unique IMEI/RF-cal region

usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; echo "Stages: ${STAGES[*]}"; exit 1; }
SER=""; FROM=""; ONLY=""; FW_HASH=1; export FARM_AUTO=0 FARM_CONFIRM=""
while (($#)); do
  case "$1" in
    --from) FROM="$2"; shift 2;; --only) ONLY="$2"; shift 2;;
    --no-fw-hash) FW_HASH=0; shift;; --list) echo "${STAGES[*]}"; exit 0;;
    --auto) FARM_AUTO=1; shift;; --confirm) FARM_CONFIRM+="$2"$'\n'; shift 2;;
    -h|--help) usage;; -*) usage;; *) SER="$1"; shift;;
  esac
done
[[ -n "$SER" ]] || usage
for st in "$FROM" "$ONLY"; do [[ -z "$st" || " ${STAGES[*]} " == *" $st "* ]] || { echo "unknown stage: $st"; usage; }; done
S="$SER"
mkdir -p "$ROOT/logs/$S"
exec > >(tee -a "$ROOT/logs/$S/upgrade.log") 2>&1
echo "######## upgrade $S $(date '+%F %T') from=${FROM:-start} only=${ONLY:-} auto=$FARM_AUTO"

WORK="$ROOT/logs/$S/fw42-extract"   # firmware is unzipped here (logs/ is gitignored); removed on success
img_sha() { shasum -a 256 "$1" | awk '{print $1}'; }

# Parse Motorola's flashfile.xml into the filtered, ordered command list. Emits one line per executed step:
#   flash <partition> <filename>   |   erase <partition>
# SKIP_* partitions and the oem/getvar bookkeeping steps are dropped (printed separately for the record).
_fw_plan() {   # <flashfile.xml> <mode: run|skips>
  python3 -I - "$1" "$2" "$SKIP_FLASH_PARTS" "$SKIP_ERASE_PARTS" <<'PY'
import sys, xml.etree.ElementTree as ET  # input is the hash-gated Motorola flashfile.xml (preflight verifies the zip), not untrusted
xml, mode, skip_flash, skip_erase = sys.argv[1], sys.argv[2], set(sys.argv[3].split()), set(sys.argv[4].split())
run, skips = [], []
for s in ET.parse(xml).getroot().iter("step"):
    op, part, fn = s.get("operation"), s.get("partition"), s.get("filename")
    if op == "flash":
        (skips if part in skip_flash else run).append(("flash", part, fn,
            "partition table / preloader — never downgrade" if part in skip_flash else ""))
    elif op == "erase":
        (skips if part in skip_erase else run).append(("erase", part, None, "device-unique nvdata"))
    else:  # getvar / oem fb_mode_* / config unset — Motorola bookkeeping, not partition writes
        skips.append((op, part or s.get("var"), None, "bookkeeping"))
if mode == "run":
    for op, part, fn, _ in run:
        print(f"{op}\t{part}\t{fn or ''}")
else:
    for op, part, fn, why in skips:
        print(f"SKIP {op} {part or ''} {('('+fn+') ' ) if fn else ''}- {why}")
PY
}

# ---------------- stages ----------------
st_preflight() {
  STAGE preflight "-4-2 firmware + tools"
  [[ -f "$FW_42_ZIP" ]] || die "missing -4-2 firmware zip $FW_42_ZIP"
  if ((FW_HASH)); then
    info "hashing the 5.7 GB -4-2 firmware (pass --no-fw-hash to skip)…"
    (cd "$ROOT/tools/locked" && grep -E "  $(basename "$FW_42_ZIP")\$" SHA256SUMS | shasum -a 256 -c -) \
      || die "-4-2 firmware hash mismatch (see tools/locked/SHA256SUMS)"
  else
    info "skipping -4-2 firmware hash (--no-fw-hash)"
  fi
  command -v fastboot >/dev/null || die "fastboot not on PATH"
  command -v unzip >/dev/null || die "unzip not on PATH"
  command -v python3 >/dev/null || die "python3 not on PATH (flashfile.xml parser)"
  in_adb || in_fastboot || die "$S not attached (boot it into fastboot: hold Vol-down while powering on)"
  STAGE_DONE
}

st_gate_fastboot() {
  STAGE gate-fastboot "identity in fastboot, BL must be locked, slot a (about to overwrite the system)"
  if ! in_fastboot; then
    in_adb || die "$S is in neither fastboot nor adb"
    info "$S is in adb -> rebooting to bootloader"
    adb -s "$S" reboot bootloader; wait_fastboot 90 || die "did not reach fastboot"
  fi
  if [[ "$(fbv is-userspace)" == yes ]]; then
    info "$S is in fastbootd -> rebooting to the bootloader's fastboot"
    fastboot -s "$S" reboot bootloader >/dev/null 2>&1; sleep 3; wait_fastboot 90 || die "did not reach bootloader fastboot"
  fi
  gate_fastboot locked any          # "any": post-downgrade version-bootloader is a base/mixed report; we overwrite it
  [[ "$FB_SLOT" == a ]] || die "current-slot=$FB_SLOT; flashfile.xml targets slot a only. Switch the active slot to a first."
  echo "$FB_SLOT" > "$ROOT/logs/$S/slot"
  STAGE_DONE "slot=$FB_SLOT"
}

st_flash_firmware() {
  STAGE flash-firmware "-4-2 firmware via Motorola flashfile.xml (incl. lk; skipping gpt/preloader + nvdata erase)"
  in_fastboot || die "not in fastboot"
  gate_fastboot locked any
  rm -rf "$WORK"; mkdir -p "$WORK"
  info "extracting -4-2 firmware to $WORK (5.7 GB — one-time)…"
  unzip -o -q "$FW_42_ZIP" -d "$WORK" || die "unzip failed"
  [[ -f "$WORK/flashfile.xml" ]] || die "no flashfile.xml in firmware zip"
  echo "  --- steps SKIPPED (kept from the current phone) ---"
  _fw_plan "$WORK/flashfile.xml" skips | sed 's/^/    /'
  echo "  --- steps TO RUN ---"
  local plan; plan=$(_fw_plan "$WORK/flashfile.xml" run)
  [[ -n "$plan" ]] || die "empty flash plan (parser/flashfile problem)"
  echo "$plan" | awk -F'\t' '{printf "    %s %s %s\n",$1,$2,$3}'
  confirm "UPGRADE $S" "flash the stock -4-2 firmware above (incl. lk_$FB_SLOT) to $S while LOCKED (gpt/preloader + nvdata skipped)"
  local op part fn
  while IFS=$'\t' read -r op part fn; do
    if [[ "$op" == flash ]]; then
      [[ -f "$WORK/$fn" ]] || die "firmware file missing: $fn"
      fastboot -s "$S" flash "$part" "$WORK/$fn" || die "flash $part ($fn) failed"
    else
      fastboot -s "$S" erase "$part" || die "erase $part failed"
    fi
  done <<< "$plan"
  rm -rf "$WORK"   # reclaim the 5.7 GB (set KEEP_EXTRACT=1 to keep)
  [[ "${KEEP_EXTRACT:-0}" == 1 ]] && info "(KEEP_EXTRACT=1: left $WORK in place)"
  pass "-4-2 firmware flashed (stock lk_$FB_SLOT in place)"
  STAGE_DONE
}

st_gate_42() {
  STAGE gate-42 "confirm still locked; -4-2 bootloader in place; hand off to route_d"
  in_fastboot || die "not in fastboot"
  local ss mbm; ss=$(fbv securestate); mbm=$(build_mbm "$(fbv version-bootloader)")
  [[ "$ss" == oem_locked || "$ss" == flashing_locked ]] || die "securestate=$ss (expected still locked)"
  pass "locked ($ss); bootloader reports $mbm (exact build confirmed after first boot by route_d's gate-android)"
  info "Upgrade done. Next: scripts/route_d.sh $S  (flashes lk-moto2026.img carrier=retus + unlock modem, erases, configures -> end state D)"
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
  if [[ "$st" == flash-firmware ]] && [[ -z "${FB_SLOT:-}" ]]; then
    in_fastboot && FB_SLOT=$(fbv current-slot)
  fi
  "st_${st//-/_}"
done
echo "######## upgrade $S finished (${ONLY:-${FROM:-all}})"
