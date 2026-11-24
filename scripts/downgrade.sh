#!/usr/bin/env bash
# Downgrade a newer / OTA'd moto g power 2026 back to base retail W1WEOS36.48-22-3-3 (patch 2025-12-01), so the
# -4-2 route-D tooling works on it again. Source: USCardForum topic 548192.
#
#   scripts/downgrade.sh <serial> [--no-avb] [--from STAGE] [--only STAGE] [--list] [--no-fw-hash]
#                        [--auto [--confirm "DOWNGRADE <serial>"] [--confirm "FLASHFW <serial>"]]
#
# Flow (faithful to the post): flash a downgrade `lk` -> reboot bootloader -> flash the full base firmware but NOT its
# lk/gpt/preloader partitions and NOT the nvdata erase -> flash the SIM-unlock modem. The phone is left in fastboot on
# the base build; run `scripts/route_d.sh <serial>` next for end state D (it flashes lk-moto2026.img + erases + configs).
#
# `lk` choice: default `lk-rollback-3-3.img` (downgrade allowed, signatures still verified — our default, keeps us on
# an AVB-enforcing posture). `--no-avb` uses `lk-no-avb-3-3.img` (AVB fully off; only for a persistent-root-while-locked
# end state, which is NOT built here). Both keep AVB green and flash while the BL stays LOCKED.
#
# VERIFIED 2026-11-20 (default lk) on #7 and #8: -4-3 -> base booted green, still locked; then
# scripts/upgrade.sh -> -4-2 -> route_d.sh -> end state D, no brick. The base build's baseband is NOT P107 (it returns
# after the -4-2 upgrade). --no-avb is UNVERIFIED (never run). BL stays locked throughout, so a wrong image is a brick
# risk — the typed confirms are real.
# The firmware command list is derived from Motorola's own flashfile.xml inside the zip on every run (not hand-kept).
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
ROUTE=downgrade
trap 'die "unexpected failure at line $LINENO: $BASH_COMMAND"' ERR
STAGES=(preflight gate-fastboot flash-lk flash-firmware flash-modem gate-base)

# Partitions the base-firmware flash must NOT touch (keep our downgrade lk; never overwrite the partition table,
# the preloader, or the device-unique nvdata). Everything else in flashfile.xml is flashed/erased as Motorola lists it.
SKIP_FLASH_PARTS="lk lk_a lk_b gpt preloader"   # matched on the flashfile's partition= attribute
SKIP_ERASE_PARTS="nvdata"                       # device-unique IMEI/RF-cal region (see tools/locked/README.md)

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; echo "Stages: ${STAGES[*]}"; exit 1; }
SER=""; FROM=""; ONLY=""; FW_HASH=1; export FARM_AUTO=0 FARM_CONFIRM=""
LK_IMG="$LK_ROLLBACK"; LK_LABEL="rollback (AVB-verifying)"
while (($#)); do
  case "$1" in
    --no-avb) LK_IMG="$LK_NOAVB"; LK_LABEL="no-avb (AVB OFF)"; shift;;
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
exec > >(tee -a "$ROOT/logs/$S/downgrade.log") 2>&1
echo "######## downgrade $S $(date '+%F %T') lk=$LK_LABEL from=${FROM:-start} only=${ONLY:-} auto=$FARM_AUTO"

WORK="$ROOT/logs/$S/fw-extract"   # firmware is unzipped here (logs/ is gitignored); removed on success
img_sha() { shasum -a 256 "$1" | awk '{print $1}'; }

# ---------------- stages ----------------
st_preflight() {
  STAGE preflight "downgrade files + tools"
  [[ -f "$LK_IMG" ]] || die "missing $LK_IMG (see tools/locked/README.md)"
  [[ -f "$MD_UNLOCK_33" ]] || die "missing $MD_UNLOCK_33"
  [[ -f "$FW_BASE_ZIP" ]] || die "missing base firmware zip $FW_BASE_ZIP"
  (cd "$ROOT/tools/locked" && grep -E ' (lk-rollback-3-3|lk-no-avb-3-3|md1img-unlock-3-3)\.img$' SHA256SUMS | shasum -a 256 -c -) \
    || die "downgrade images missing or hash mismatch (see tools/locked/README.md)"
  if ((FW_HASH)); then
    info "hashing the 5.6 GB base firmware (pass --no-fw-hash to skip)…"
    (cd "$ROOT/tools/locked" && grep -E "  $(basename "$FW_BASE_ZIP")\$" SHA256SUMS | shasum -a 256 -c -) \
      || die "base firmware hash mismatch (see tools/locked/SHA256SUMS)"
  else
    info "skipping base-firmware hash (--no-fw-hash)"
  fi
  command -v fastboot >/dev/null || die "fastboot not on PATH"
  command -v unzip >/dev/null || die "unzip not on PATH"
  command -v python3 >/dev/null || die "python3 not on PATH (flashfile.xml parser)"
  in_adb || in_fastboot || die "$S not attached (boot it into fastboot: hold Vol-down while powering on)"
  STAGE_DONE
}

st_gate_fastboot() {
  STAGE gate-fastboot "identity in fastboot, BL must be locked (any build — about to overwrite)"
  if ! in_fastboot; then
    in_adb || die "$S is in neither fastboot nor adb"
    info "$S is in adb -> rebooting to bootloader"
    adb -s "$S" reboot bootloader; wait_fastboot 90 || die "did not reach fastboot"
  fi
  if [[ "$(fbv is-userspace)" == yes ]]; then
    info "$S is in fastbootd -> rebooting to the bootloader's fastboot"
    fastboot -s "$S" reboot bootloader >/dev/null 2>&1; sleep 3; wait_fastboot 90 || die "did not reach bootloader fastboot"
  fi
  gate_fastboot locked any          # build-policy "any": accept -4-3 etc.; this flow is the downgrade
  [[ "$FB_SLOT" == a ]] || die "current-slot=$FB_SLOT; flashfile.xml targets slot a only. Switch the active slot to a first."
  echo "$FB_SLOT" > "$ROOT/logs/$S/slot"
  STAGE_DONE "slot=$FB_SLOT"
}

st_flash_lk() {
  STAGE flash-lk "downgrade lk ($LK_LABEL) -> lk_${FB_SLOT:-?}"
  in_fastboot || die "not in fastboot (run from gate-fastboot)"
  gate_fastboot locked any
  confirm "DOWNGRADE $S" "flash downgrade lk ($LK_LABEL) to lk_$FB_SLOT on $S while LOCKED (topic 548192)"
  fastboot -s "$S" flash "lk_$FB_SLOT" "$LK_IMG" || die "flash lk_$FB_SLOT failed (did the lk take? see post pitfall 1)"
  fastboot -s "$S" reboot-bootloader; sleep 6
  wait_fastboot 90 || die "did not come back to fastboot after flashing lk"
  local ss="" i; for i in $(seq 1 15); do ss=$(fbv securestate); [[ -n "$ss" ]] && break; sleep 2; done
  [[ "$ss" == oem_locked || "$ss" == flashing_locked ]] || die "securestate=$ss after lk flash (expected still locked)"
  pass "downgrade lk flashed; still $ss"
  STAGE_DONE
}

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
            "keep our downgrade lk" if part.startswith("lk") else "partition table / preloader — never downgrade"))
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

st_flash_firmware() {
  STAGE flash-firmware "base firmware via Motorola flashfile.xml (skipping lk/gpt/preloader + nvdata erase)"
  in_fastboot || die "not in fastboot"
  gate_fastboot locked any
  rm -rf "$WORK"; mkdir -p "$WORK"
  info "extracting base firmware to $WORK (5.6 GB — one-time)…"
  unzip -o -q "$FW_BASE_ZIP" -d "$WORK" || die "unzip failed"
  [[ -f "$WORK/flashfile.xml" ]] || die "no flashfile.xml in firmware zip"
  echo "  --- steps SKIPPED (kept from the current phone / not downgraded) ---"
  _fw_plan "$WORK/flashfile.xml" skips | sed 's/^/    /'
  echo "  --- steps TO RUN ---"
  local plan; plan=$(_fw_plan "$WORK/flashfile.xml" run)
  [[ -n "$plan" ]] || die "empty flash plan (parser/flashfile problem)"
  echo "$plan" | awk -F'\t' '{printf "    %s %s %s\n",$1,$2,$3}'
  confirm "FLASHFW $S" "flash the base firmware above to $S while LOCKED (lk/gpt/preloader + nvdata are skipped)"
  local op part fn
  while IFS=$'\t' read -r op part fn; do
    if [[ "$op" == flash ]]; then
      [[ -f "$WORK/$fn" ]] || die "firmware file missing: $fn"
      fastboot -s "$S" flash "$part" "$WORK/$fn" || die "flash $part ($fn) failed"
    else
      fastboot -s "$S" erase "$part" || die "erase $part failed"
    fi
  done <<< "$plan"
  rm -rf "$WORK"   # reclaim the 5.6 GB (set KEEP_EXTRACT=1 to keep)
  [[ "${KEEP_EXTRACT:-0}" == 1 ]] && info "(KEEP_EXTRACT=1: left $WORK in place)"
  pass "base firmware flashed (lk kept = downgrade lk)"
  STAGE_DONE
}

st_flash_modem() {
  STAGE flash-modem "SIM-unlock modem -> md1img_${FB_SLOT:-?}"
  in_fastboot || die "not in fastboot"
  fastboot -s "$S" flash "md1img_$FB_SLOT" "$MD_UNLOCK_33" || die "flash md1img_$FB_SLOT failed"
  pass "md1img-unlock-3-3.img flashed"
  STAGE_DONE
}

st_gate_base() {
  STAGE gate-base "confirm still locked; hand off to route_d (UNVERIFIED read)"
  in_fastboot || die "not in fastboot"
  local ss mbm; ss=$(fbv securestate); mbm=$(build_mbm "$(fbv version-bootloader)")
  [[ "$ss" == oem_locked || "$ss" == flashing_locked ]] || die "securestate=$ss (expected still locked)"
  pass "locked ($ss); bootloader reports $mbm (lk not downgraded by the firmware; exact base build confirmed later by route_d's gate-android)"
  info "Downgrade done. Next: scripts/route_d.sh $S  (flashes lk-moto2026.img carrier=retus, erases, configures -> end state D)"
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
  if [[ "$st" == flash-lk || "$st" == flash-firmware || "$st" == flash-modem ]] && [[ -z "${FB_SLOT:-}" ]]; then
    in_fastboot && FB_SLOT=$(fbv current-slot)
  fi
  "st_${st//-/_}"
done
echo "######## downgrade $S finished (${ONLY:-${FROM:-all}})"
