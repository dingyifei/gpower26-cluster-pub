#!/usr/bin/env bash
# Linux route B, part 1: take ONE expendable phone from end state D to "rebuilt GKI kernel boots Android, and a
# Linux initramfs gives a USB shell on it". Plan: linux/README.md; research: docs/linux-on-vegas.md (sec. 3.4, 6, 7.2).
#
#   scripts/linux_b.sh <serial> [--from STAGE | --only STAGE] [--list]
#
# The unit leaves end state D for good (unlocking is one-way under the report's rules); list it in farm-exclude.txt.
# Writes, each behind a typed token:  UNLOCK <serial>  (lk + oem unlock, wipes data)   FLASH <serial>  (boot_a/init_boot_a)
# Only lk_a (the proven unlock patch, sha 914acfce...), boot_a and init_boot_a are ever written. Never: oem lock, slot
# switch, oem config, vbmeta, vendor_boot, dtbo, misc, super, slot B, NV partitions.
# Stop rule: a boot that does not come back is counted in logs/<serial>/linux_b/failed_boots; at 2 the experiment
# stages refuse to flash until a restore stage has booted Android again (docs/linux-on-vegas.md 6.4).
# Images are built offline first (linux/README.md, phase 0); preflight re-checks them with linux/tools/checkimg.py.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
trap 'die "unexpected failure at line $LINENO: $BASH_COMMAND"' ERR
ROUTE=linux-b
STAGES=(preflight readonly unlock retail-lk setup fbcheck root probe-init-boot restore-init-boot boot-4a boot-4b linux-shell restore
        p2-capture fastbootd-check lp-create chooser-dry chooser-linux   # part 2 (linux/README.md): chooser + Debian in super
        android-capture rootfs-flash debian-boot   # capture needs root and feeds the Debian build (linux/debian/build.sh)
        state-e)   # end state E: unrooted Android (chooser over the stock init_boot); the last write
EXTRA_STAGES=(stock-boot lp-delete chooser-off root-on root-off state-e-check   # --only (stock-boot: stock -4-2 boot_a back)
              datadisk-poc datadisk-create datadisk-check datadisk-grow deb-update)   # Linux main root inside userdata

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; echo "Stages: ${STAGES[*]}  (extra, --only: ${EXTRA_STAGES[*]})"; exit 1; }
SER=""; FROM=""; ONLY=""; export FARM_AUTO=0 FARM_CONFIRM=""
while (($#)); do
  case "$1" in
    --from) FROM="$2"; shift 2;; --only) ONLY="$2"; shift 2;; --list) echo "${STAGES[*]}"; exit 0;;
    -h|--help) usage;; -*) usage;; *) SER="$1"; shift;;
  esac
done
[[ -n "$SER" ]] || usage
for st in "$FROM" "$ONLY"; do [[ -z "$st" || " ${STAGES[*]} ${EXTRA_STAGES[*]} " == *" $st "* ]] || { echo "unknown stage: $st"; usage; }; done
# A phone running Debian is on neither adb nor fastboot. Find it on the USB network (IPv4, then the IPv6 link-local
# address on the "vegas Debian" port) or at $VEGAS_DEBIAN_IP (e.g. its Wi-Fi address); if its bootconfig serial is
# the one asked for, `systemctl reboot` it to Android and wait, so every stage starts from Android as before.
# Exception: --only deb-update works on the running Debian itself (no reboot; DEB_IP is where it was found).
DEB_IP=""
debian_to_android() {  # $1 = serial
  local want=$1 ip ifc own ser i cands=(172.16.42.1)
  local SSHP=(ssh -n -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR
              -o ConnectTimeout=5 -o ServerAliveInterval=2 -o ServerAliveCountMax=3)
  { adb devices | awk 'NR>1 && $2=="device"{print $1}'; fastboot devices 2>/dev/null | awk '{print $1}'; } | grep -qx "$want" && return 0
  ifc=$(networksetup -listallhardwareports 2>/dev/null | awk '/^Hardware Port: vegas Debian$/{f=1; next} f && /^Device:/{print $2; f=0}' | head -1)
  if [[ -n $ifc ]]; then
    own=$(ifconfig "$ifc" 2>/dev/null | awk '/inet6 fe80/{sub(/%.*/, "", $2); print $2; exit}' || true)
    ip=$(ping6 -c2 -i1 "ff02::1%$ifc" 2>/dev/null | awk '/bytes from fe80/{a=$4; sub(/[,:]$/, "", a); print a}' | grep -v "^$own%" | head -1 || true)
    [[ -n $ip ]] && cands+=("$ip")
  fi
  [[ -n ${VEGAS_DEBIAN_IP:-} ]] && cands+=("$VEGAS_DEBIAN_IP")
  for ip in "${cands[@]}"; do
    ser=$("${SSHP[@]}" root@"$ip" 'sed -n "s/^androidboot.serialno = \"\(.*\)\"$/\1/p" /proc/bootconfig' 2>/dev/null) \
      || { echo "  (no Debian SSH at $ip)"; continue; }
    [[ $ser == "$want" ]] || { echo "  Debian at $ip reports serial '${ser:-?}', not $want: left alone"; continue; }
    if [[ $ONLY == deb-update ]]; then echo ">>> $want is running Debian ($ip): deb-update works on it directly"; DEB_IP=$ip; return 0; fi
    echo ">>> $want is running Debian ($ip): systemctl reboot -> Android, then the stage starts"
    echo "    (sway from vegas-sway.service survives this; a sway started by hand would oops mediatek_drm when it exits)"
    timeout 330 "${SSHP[@]}" root@"$ip" 'f=/var/lib/vegas/bootfail; for i in $(seq 1 150); do [ -e $f ] || break
      [ "$(cat $f 2>/dev/null)" = 0 ] && break; sleep 2; done; sync; systemctl reboot' || true
    for ((i = 0; i < 60; i++)); do
      [[ "$(adb -s "$want" shell getprop sys.boot_completed </dev/null 2>/dev/null | tr -d '\r')" == 1 ]] && { echo ">>> Android is up"; return 0; }
      sleep 5
    done
    echo "no Android 300 s after rebooting Debian; check the phone (a long Power press resets it)" >&2; exit 1
  done
  return 0   # not found running Debian: pick_serial reports it as not attached
}
debian_to_android "$SER"
if [[ -n $DEB_IP ]]; then S=$SER; else S=$(pick_serial "$SER"); fi
grep -q "^$S" "$ROOT/farm-exclude.txt" 2>/dev/null || { echo "refusing: $S is not listed in farm-exclude.txt (mark it as the experiment unit first)"; exit 1; }
L="$ROOT/logs/$S/linux_b"; mkdir -p "$L"
exec > >(tee -a "$ROOT/logs/$S/linux_b.log") 2>&1
echo "######## linux_b $S $(date '+%F %T') from=${FROM:-start} only=${ONLY:-}"

W="$ROOT/linux/work"
DUMP=$(ls -d "$ROOT"/vegas-freedom/backups/stock_*_"$S" 2>/dev/null | tail -1)
UNLOCK_LK="$W/unlock/lk.unlock-serial.img"; UNLOCK_LK_SHA=914acfce78939c61a744294ecb686a0865424c36c397878ab6e919be9513eed1
RETAIL_LK="$ROOT/tools/locked/lk-moto2026.img"; RETAIL_LK_SHA=957b7db4d789d19b345668432363190b76fdcd9d6a6323d6dc620bd0678cc945  # route D lk, carrier=retus
IMG_PROBE="$W/img/init_boot_probe.img"; IMG_4A="$W/img/boot_4a.img"; IMG_4B="$W/img/boot_4b.img"
STOCK_BOOT="$W/stock/boot.img"
KSU_IB() { ls "$ROOT"/backups/"${S}"_*_init_boot_ksu.img 2>/dev/null | tail -1; }
PHONE_IP4=172.16.42.1; PHONE_IP=${DEB_IP:-$PHONE_IP4}   # wait_linux_usb may switch PHONE_IP to an IPv6 link-local address

# ---------------- helpers ----------------
fails() { cat "$L/failed_boots" 2>/dev/null || echo 0; }
fail_boot() { echo $(( $(fails) + 1 )) > "$L/failed_boots"; die "$1 (failed boots: $(fails)). Get to fastboot with the key combo (Vol-down + Power), then: scripts/linux_b.sh $S --only ${2:-restore-init-boot}"; }
guard() { (( $(fails) < 2 )) || die "stop rule: $(fails) failed boots since the last good Android boot; run a restore stage first"; }
good_boot() { echo 0 > "$L/failed_boots"; }

slotvars() {  # fastboot view of the boot-control state (read-only), appended to the log
  local v out=""; for v in current-slot slot-successful:a slot-unbootable:a slot-retry-count:a slot-successful:b slot-unbootable:b slot-retry-count:b; do
    out+="$v=$(fbv "$v") "; done
  echo "$out" | tee -a "$L/slotvars.txt"
  [[ "$(fbv current-slot)" == a ]] || die "current slot is not a"
}
misc_snapshot() {  # root: dump misc (read-only) and parse the boot-control block
  local f="$L/misc_$1.img"
  adb -s "$S" exec-out "su -c 'dd if=/dev/block/by-name/misc bs=4096 count=1 2>/dev/null'" > "$f" 2>/dev/null \
    || adb -s "$S" exec-out "dd if=/dev/block/by-name/misc bs=4096 count=1 2>/dev/null" > "$f"
  python3 "$ROOT/linux/tools/bootctrl.py" "$f" | tee -a "$L/bootctrl.txt"
}
to_fastboot() {
  in_fastboot && return 0
  in_adb || die "$S is neither in adb nor fastboot"
  adb -s "$S" reboot bootloader; wait_fastboot 90 || die "no fastboot after reboot bootloader"
}
# flash_exp <partition> <image> <kind>: re-check image + phone, typed token, flash, boot-control before/after.
flash_exp() {
  local part="$1" img="$2" kind="$3"
  [[ -f "$img" ]] || die "missing $img"
  python3 "$ROOT/linux/tools/checkimg.py" "${part%_a}" "$img" ${4:+--differ "$4"} || die "checkimg refused $img"
  to_fastboot
  gate_fastboot flashing_unlocked
  [[ "$FB_SLOT" == a ]] || die "slot $FB_SLOT (want a)"
  info "before: $(slotvars)"
  confirm "FLASH $S" "flash $part <- $(basename "$img") ($kind) on $S"
  fastboot -s "$S" flash "$part" "$img" || die "flash $part refused by lk (nothing written per LG-1); compare with docs/linux-on-vegas.md 2.4"
  info "after flash: $(slotvars)"
  echo "$(date '+%F %T') $part $(shasum -a 256 "$img" | cut -c1-16) $kind" >> "$L/flashes.txt"
}
android_boot() {  # reboot from fastboot into Android and wait; counts a failed boot
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  wait_boot 300 || fail_boot "Android did not finish booting within 300 s after $1" "$2"
  good_boot
  pass "Android booted: $(gprop ro.boot.verifiedbootstate) $(ash uname -r)"
}
lsh() { ( sleep 1.5; printf '%s\n' "$1"; sleep "${2:-4}"; printf 'exit\n' ) | nc -w 8 "$PHONE_IP" 23 2>/dev/null | LC_ALL=C tr -d '\r\377\373\374\375\376\001\003\037' || true; }  # telnetd drops input sent before its shell is up; LC_ALL=C for the 0xff bytes; never fatal (pipefail)
wait_telnet() {  # usb0 answers ping before the rescue telnetd is listening
  local i; for ((i = 0; i < 30; i++)); do nc -z -w 2 "$PHONE_IP" 23 >/dev/null 2>&1 && return 0; sleep 1; done
  info "[WARN] no telnet on $PHONE_IP:23 after 30 s"; return 1
}
# The Mac can miss the DHCP lease (USB link drops once at boot -> it self-assigns 169.254.x and does not retry soon).
# Then use the phone's IPv6 link-local address on the "vegas Debian" interface: ssh/nc/ping6 all take fe80::…%enN.
ncm_if() {  # the gadget's product string names the Mac port: "vegas Debian" (init.linux) or "route-B probe" (part-1 init)
  networksetup -listallhardwareports 2>/dev/null | awk '/^Hardware Port: (vegas Debian|route-B probe)$/{f=1; next} f && /^Device:/{print $2; f=0}' | head -1; }  # no awk exit: SIGPIPE + pipefail
ll_phone() {  # $1 = interface -> the fe80 address answering ff02::1 that is not the Mac's own
  local own; own=$(ifconfig "$1" 2>/dev/null | awk '/inet6 fe80/{sub(/%.*/, "", $2); print $2; exit}')
  ping6 -c2 -i1 "ff02::1%$1" 2>/dev/null | awk '/bytes from fe80/{a=$4; sub(/[,:]$/, "", a); print a}' | grep -v "^$own%" | head -1 || true
}
phone_ping() {  # macOS ping6 has no reply timeout (waits ~10 s on a miss): bound it to 2 s like ping -t1
  case $PHONE_IP in *:*) perl -e 'alarm 2; exec @ARGV' ping6 -c1 "$PHONE_IP" ;; *) ping -c1 -t1 "$PHONE_IP" ;; esac >/dev/null 2>&1; }
wait_linux_usb() {  # NCM first (IPv4, then IPv6 link-local after 20 s); ACM serial as the fallback signal
  local i ifc ll; PHONE_IP=$PHONE_IP4
  for ((i = 0; i < 90; i++)); do
    ping -c1 -t1 "$PHONE_IP4" >/dev/null 2>&1 && { pass "NCM: $PHONE_IP answers"; return 0; }
    if (( i >= 10 )) && ifc=$(ncm_if) && [ -n "$ifc" ] && ll=$(ll_phone "$ifc") && [ -n "$ll" ]; then
      PHONE_IP=$ll
      pass "NCM: $PHONE_IP answers (IPv6 link-local: the Mac has no lease on $ifc; 'sudo ipconfig set $ifc DHCP' fixes that)"
      return 0
    fi
    sleep 2
  done
  ls /dev/cu.usbmodem* >/dev/null 2>&1 && { info "no NCM, but a USB serial port exists: $(ls /dev/cu.usbmodem*) (screen it)"; return 1; }
  return 1
}
linux_probe() {  # $1 = tag; collect evidence over telnet, then send the phone to fastboot
  local tag="$1" d="$L/$1"; mkdir -p "$d"
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  if ! wait_linux_usb; then
    info "no USB network from the initramfs; its timer sends it to fastboot within 10 min"
    wait_fastboot 720 && slotvars
    fail_boot "$tag: no USB shell" restore-init-boot
  fi
  lsh 'uname -a; cat /tmp/init.log; cat /proc/cmdline; wc -l < /proc/modules' > "$d/summary.txt"
  lsh 'cat /tmp/insmod.fail 2>/dev/null; cat /tmp/insmod.err 2>/dev/null' > "$d/insmod.txt"
  lsh dmesg 9 > "$d/dmesg.txt"
  lsh 'cat /proc/meminfo | head -3; ls /sys/class/udc; ls /dev | wc -l' > "$d/misc.txt"
  lsh 'zcat /proc/config.gz 2>/dev/null | grep -E "^CONFIG_(DEVTMPFS|FHANDLE|AUTOFS_FS)="' > "$d/config.txt"
  cat "$d/summary.txt"
  info "evidence in $d; sending the phone to fastboot (rebootbl)"
  lsh '/bin/rebootbl' >/dev/null
  wait_fastboot 120 || fail_boot "$tag: rebootbl did not reach fastboot" restore-init-boot
  pass "reboot-to-bootloader from Linux works"
  info "$(slotvars)"
  good_boot
}

# ---------------- stages ----------------
st_preflight() {
  STAGE preflight "images + tools"
  for t in fastboot adb nc python3; do command -v "$t" >/dev/null || die "missing tool $t"; done
  [[ -n "$DUMP" ]] || die "no partition dump for $S in vegas-freedom/backups/ (phone.sh backup first)"
  [[ "$(shasum -a 256 "$UNLOCK_LK" | cut -d' ' -f1)" == "$UNLOCK_LK_SHA" ]] || die "unlock lk missing or not 914acfce (linux/README.md)"
  python3 "$ROOT/linux/tools/checkimg.py" init_boot "$IMG_PROBE" --differ "$W/stock/init_boot.img" || die "probe image"
  python3 "$ROOT/linux/tools/checkimg.py" boot "$IMG_4A" --differ "$STOCK_BOOT" || die "4a image"
  [[ -f "$IMG_4B" ]] && { python3 "$ROOT/linux/tools/checkimg.py" boot "$IMG_4B" --differ "$STOCK_BOOT" || die "4b image"; } \
    || info "boot_4b.img not built yet (needed from stage boot-4b)"
  STAGE_DONE "dump $(basename "$DUMP")"
}

# imeis: both IMEIs, one per line. iphonesubinfo txn 4 = getDeviceIdForPhone(int, callingPackage, featureId) on A13;
# txn 5 returns null here. Works as the shell user.
imeis() { local i; for i in 0 1; do ash "service call iphonesubinfo 4 i32 $i s16 com.android.shell s16 null" | grep -o "'.*'" | tr -d "'. \n"; echo; done; }
st_readonly() {
  STAGE readonly "locked phone, temp root: verify dump, boot-control, slot B, IMEIs (no writes)"
  in_adb || die "boot $S into Android and run scripts/reroot.sh $S first"
  is_root || [[ "$(ash su -c id 2>/dev/null)" == *uid=0* ]] || die "no root: run scripts/reroot.sh $S"
  local p bad=0 want got
  for p in nvram nvdata protect1 protect2 persist prodpersist seccfg cid utags hw sp dram_para efuse proinfo \
           lk_a misc vbmeta_a boot_a init_boot_a vendor_boot_a dtbo_a preloader_a preloader_b; do
    [[ -f "$DUMP/$p.img" ]] || { info "no $p.img in dump"; continue; }
    want=$(shasum -a 256 "$DUMP/$p.img" | cut -d' ' -f1)
    got=$(part_sha "$p" "$(stat -f%z "$DUMP/$p.img")")
    if [[ "$want" == "$got" ]]; then pass "$p matches dump"; else info "[DIFF] $p live=${got:0:12} dump=${want:0:12}"; bad=$((bad+1)); fi
  done
  misc_snapshot locked
  local nz=0
  for p in $(rsh 'ls /dev/block/by-name' | tr ' ' '\n' | grep '_b$' | grep -v '^preloader'); do
    [[ "$(rsh "tr -d '\\000' < /dev/block/by-name/$p | head -c1 | wc -c")" == 0 ]] || { info "[NONZERO] $p"; nz=$((nz+1)); }
  done
  ((nz == 0)) && pass "every slot-B partition (except preloader_b) is all zeros" || info "$nz slot-B partitions hold data"
  imeis > "$L/imei_locked.txt"
  info "IMEIs: $(tr '\n' ' ' < "$L/imei_locked.txt")(saved to $L/imei_locked.txt; cross-check with *#06#)"
  ((bad == 0)) || info "$bad partitions differ from the dump (nvcfg/para can be live state); re-dump with phone.sh backup before unlocking if any NV one differs"
  STAGE_DONE "$bad diff, $nz nonzero slot-B"
}

st_unlock() {
  STAGE unlock "flash the proven unlock lk + oem unlock (WIPES DATA, leaves end state D)"
  if in_adb; then
    rsh 'pm set-user-restriction --user 0 no_moto_oem_unlock 0; service call oem_lock 4 i32 1' >/dev/null || die "could not enable OEM unlock (needs root)"
    pass "OEM unlock permission on"
  else
    info "not in adb: assuming OEM unlock permission was already enabled under root"
  fi
  to_fastboot
  gate_fastboot locked
  [[ "$FB_SLOT" == a ]] || die "slot $FB_SLOT"
  info "$(slotvars)"
  confirm "UNLOCK $S" "flash lk <- unlock lk (914acfce) and oem unlock $S: wipes data, the phone leaves end state D for good"
  fastboot -s "$S" flash lk "$UNLOCK_LK" || die "lk flash refused"
  fastboot -s "$S" reboot bootloader; sleep 3; wait_fastboot 90 || die "no fastboot after lk flash"
  [[ "$(fbv serialno)" == "$S" ]] || die "serialno mismatch"
  local key; key=$("$ROOT/.venv/bin/python" "$ROOT/vegas-freedom/bootloader/lk_keygen.py" --secret Valeria --serialno "$S" --count 1 | tail -1 | awk '{print $NF}')
  [[ -n "$key" ]] || die "no unlock key"
  info "oem unlock with the serial-bound key; confirm on the phone screen (Volume to UNLOCK, Power to confirm)"
  fastboot -s "$S" oem unlock "$key" || true
  manual "Confirm UNLOCK on the phone screen; wait until it is back in fastboot (or reboots), then Enter" || true
  wait_fastboot 180 || die "not back in fastboot"
  [[ "$(fbv securestate)" == flashing_unlocked ]] || die "securestate=$(fbv securestate) (want flashing_unlocked)"
  pass "unlocked: $(fbv securestate)"
  info "$(slotvars)"
  STAGE_DONE flashing_unlocked
}

st_retail_lk() {
  STAGE retail-lk "lk_a <- route D retail lk (carrier=retus) + erase userdata/metadata: no Tracfone activation, offline setup"
  # Community "Variant 2" (docs/community-notes.md: unlock -> flash retus lk; P2 #65 on 4 phones, #31/#161). The unlock
  # state lives in seccfg, not lk; the retus lk drops the unlock-serial check, which only matters for a re-unlock after relock.
  [[ "$(shasum -a 256 "$RETAIL_LK" | cut -d' ' -f1)" == "$RETAIL_LK_SHA" ]] || die "retail lk hash mismatch"
  to_fastboot
  gate_fastboot flashing_unlocked
  [[ "$FB_SLOT" == a ]] || die "slot $FB_SLOT"
  confirm "FLASH $S" "flash lk_a <- lk-moto2026.img (carrier=retus; #5 ran it in end state D) and erase userdata + metadata (fresh /data so the retus rules apply)"
  fastboot -s "$S" flash lk_a "$RETAIL_LK" || die "lk_a flash refused"
  fastboot -s "$S" reboot bootloader; sleep 3; wait_fastboot 90 || die "no fastboot after lk flash"
  [[ "$(fbv serialno)" == "$S" ]] || die "serialno mismatch"
  [[ "$(fbv securestate)" == flashing_unlocked ]] || die "securestate=$(fbv securestate) after lk swap (want flashing_unlocked)"
  pass "lk_a = retail lk, still $(fbv securestate)"
  fastboot -s "$S" erase userdata || die "erase userdata failed"
  fastboot -s "$S" erase metadata || die "erase metadata failed"
  pass "userdata + metadata erased"
  STAGE_DONE "retus lk, unlocked"
}
st_setup() {
  STAGE setup "first boot OFFLINE, OTA off, IMEI check"
  in_fastboot && fastboot -s "$S" reboot >/dev/null 2>&1 || true
  manual "No SIM, Wi-Fi OFF. Finish setup offline (retail lk: no activation page), enable Developer options + USB debugging, accept the Mac's key" || true
  wait_setup 3600 || die "setup not completed"
  "$ROOT/scripts/phone.sh" offline "$S" || true
  "$ROOT/scripts/phone.sh" ota-off "$S" || die "ota-off failed"
  info "carrier=$(gprop ro.carrier) verifiedbootstate=$(gprop ro.boot.verifiedbootstate) flash.locked=$(gprop ro.boot.flash.locked) slot=$(gprop ro.boot.slot_suffix)"
  manual "Dial *#06# and check both IMEIs are present and match the label (unlock may erase nvdata). Type skip if an IMEI is missing" \
    || die "IMEI missing: restore this phone's own nvdata from its dump before going on (never another phone's)"
  STAGE_DONE
}

st_fbcheck() {
  STAGE fbcheck "fastboot vars + key combination from power-off"
  to_fastboot
  gate_fastboot flashing_unlocked
  info "$(slotvars)"
  fastboot -s "$S" getvar all 2>&1 | grep -iE 'secure|warrant|unlock|avb|slot|rollback' > "$L/getvar_unlocked.txt" || true
  manual "Power the phone OFF (fastboot: select Power off), then hold Vol-down + Power. Enter when the fastboot screen shows; type skip if it does not" \
    || die "key combination did not reach fastboot: do not flash experiment images until a way into fastboot is confirmed"
  wait_fastboot 60 || die "not in fastboot"
  pass "key combination reaches fastboot from power-off"
  fastboot -s "$S" reboot >/dev/null 2>&1 || true; wait_boot 300 || die "Android did not boot"
  STAGE_DONE
}

st_root() {
  STAGE root "temp root -> KernelSU init_boot_a (permroot.sh) + archive"
  in_adb || die "not in adb"
  if [[ -z "$(KSU_IB)" ]] || ! is_root; then
    "$ROOT/scripts/reroot.sh" "$S" || die "reroot failed"
    "$ROOT/scripts/permroot.sh" "$S" || die "permroot failed"
    wait_boot 300 || die "no boot after permroot"
  fi
  is_root || die "adb is not root after permroot"
  local p; for p in seccfg misc metadata lk_a boot_a init_boot_a vbmeta_a; do
    echo "$p $(rsh "sha256sum /dev/block/by-name/$p" | cut -c1-64)"; done | tee "$L/post_unlock_hashes.txt"
  adb -s "$S" exec-out "dd if=/dev/block/by-name/lk_a bs=4M 2>/dev/null" > "$L/lk_a.unlocked.img"
  misc_snapshot unlocked_rooted
  pass "KSU init_boot: $(KSU_IB)"
  good_boot
  STAGE_DONE
}

st_probe_init_boot() {
  STAGE probe-init-boot "stock kernel + Linux initramfs in init_boot_a -> USB shell -> fastboot"
  guard
  [[ -n "$(KSU_IB)" ]] || die "no KSU init_boot archived (stage root) to restore afterwards"
  flash_exp init_boot_a "$IMG_PROBE" "probe initramfs on stock kernel" "$W/stock/init_boot.img"
  linux_probe probe-stock-kernel
  STAGE_DONE
}

st_restore_init_boot() {
  STAGE restore-init-boot "KernelSU init_boot_a back, Android boots"
  local img; img=$(KSU_IB); [[ -n "$img" ]] || die "no KSU init_boot image"
  to_fastboot; gate_fastboot flashing_unlocked
  confirm "FLASH $S" "restore init_boot_a <- $(basename "$img")"
  fastboot -s "$S" flash init_boot_a "$img"
  android_boot "init_boot restore" stock-boot
  is_root && misc_snapshot after_restore || true
  STAGE_DONE
}

st_boot_4a() {
  STAGE boot-4a "footered repack of the STOCK kernel in boot_a (hash differs from stock) -> Android"
  guard
  flash_exp boot_a "$IMG_4A" "stock kernel, recompressed" "$STOCK_BOOT"
  android_boot "boot-4a" stock-boot
  [[ "$(gprop ro.boot.verifiedbootstate)" == orange ]] || info "verifiedbootstate=$(gprop ro.boot.verifiedbootstate)"
  misc_snapshot after_4a
  STAGE_DONE "$(ash uname -r)"
}

st_boot_4b() {
  STAGE boot-4b "REBUILT kernel in boot_a, KSU init_boot_a -> Android must boot with all vendor modules"
  guard
  flash_exp boot_a "$IMG_4B" "rebuilt GKI (route B fragment)" "$STOCK_BOOT"
  android_boot "boot-4b" stock-boot
  local d="$L/boot-4b"; mkdir -p "$d"
  rsh 'uname -a; lsmod | wc -l; zcat /proc/config.gz | grep -E "^CONFIG_(DEVTMPFS|FHANDLE)="' | tee "$d/summary.txt"
  rsh 'dmesg' > "$d/dmesg.txt"
  local bad; bad=$(grep -ciE 'disagrees about version|Unknown symbol|module verification failed|Invalid module format|exec format' "$d/dmesg.txt" || true)
  info "module errors in dmesg: $bad (see $d/dmesg.txt)"
  [[ "$(ash uname -r)" == 5.15.180* ]] || die "unexpected kernel $(ash uname -r)"
  misc_snapshot after_4b
  ((bad == 0)) || die "$bad module load errors on the rebuilt kernel"
  STAGE_DONE "$(ash uname -r)"
}

st_linux_shell() {
  STAGE linux-shell "rebuilt kernel + Linux initramfs -> first Linux USB shell"
  guard
  [[ "$(stage_status boot-4b 2>/dev/null)" == done ]] || info "stage boot-4b is not recorded done"
  flash_exp init_boot_a "$IMG_PROBE" "probe initramfs on rebuilt kernel" "$W/stock/init_boot.img"
  linux_probe linux-shell-rebuilt
  grep -q 'CONFIG_DEVTMPFS=y' "$L/linux-shell-rebuilt/config.txt" && pass "Linux on the rebuilt kernel (devtmpfs present)" \
    || info "config.gz check inconclusive: see $L/linux-shell-rebuilt/"
  STAGE_DONE
}

# ---------- part 2 ----------
P2="$L/p2"
st_p2_capture() {
  STAGE p2-capture "part 2, read-only: keys, super metadata, Wi-Fi daemons, NVRAM copy, battery/thermal"
  in_adb || die "boot Android first"; is_root || die "adb is not root (KernelSU ADB root)"
  mkdir -p "$P2"
  # super metadata head (first 1 MiB holds geometry + 3 slots x 2 copies)
  adb -s "$S" exec-out "dd if=/dev/block/by-name/super bs=1048576 count=1 2>/dev/null" > "$P2/super_head.bin"
  python3 "$ROOT/linux/tools/lptool.py" check "$P2/super_head.bin" > "$P2/lp_check.txt" || die "live super metadata fails its checksums"
  python3 "$ROOT/linux/tools/lptool.py" dump "$P2/super_head.bin" > "$P2/lp_dump.txt"
  [[ -n "$DUMP" && -f "$DUMP/super.img" ]] && { python3 "$ROOT/linux/tools/lptool.py" cmp "$P2/super_head.bin" "$DUMP/super.img" \
    && pass "live super metadata = 2026-11-20 dump" || info "[DIFF] live super metadata differs from the dump"; }
  ash 'lpdump' > "$P2/lpdump.txt"; ash 'ls -l /dev/block/mapper; cat /proc/bootconfig' > "$P2/mapper_bootconfig.txt"
  # input devices
  ash 'getevent -lp' > "$P2/getevent_lp.txt"
  ash 'for d in /sys/class/input/input*; do echo "$d $(cat $d/name) $(readlink -f $d/device)"; done' > "$P2/input_devices.txt"
  # Wi-Fi / connectivity
  rsh 'cat /vendor/etc/init/hw/init_connectivity.rc /vendor/etc/init/init.wlan_drv.rc 2>/dev/null' > "$P2/wifi_rc.txt"
  rsh 'grep -rlE "wmt|wlan|connsys|wifi" /vendor/etc/init 2>/dev/null' > "$P2/wifi_rc_files.txt"
  rsh 'for n in wmt_loader wmt_launcher wlan_assistant; do for p in $(pidof $n); do echo "== $n $p"; tr "\0" " " < /proc/$p/cmdline; echo; ls -l /proc/$p/fd 2>/dev/null; grep -E "^(Uid|Gid|Groups)" /proc/$p/status; cat /proc/$p/attr/current; echo; done; done' > "$P2/wifi_procs.txt"
  ash 'getprop' | grep -iE 'connsys|wifi|wmt|wlan|ccci|md' > "$P2/wifi_props.txt" || true
  rsh 'dmesg' | grep -iE 'wmt|wlan|conn|ccci|stp|gen4m|fw|firmware' > "$P2/wifi_dmesg.txt" || true
  rsh 'cat /proc/modules' > "$P2/modules_live.txt"
  ash 'ip link show wlan0; ls -l /dev/stpwmt /dev/wmtWifi /dev/wmtdetect /dev/ccci* 2>/dev/null; ls /proc/driver 2>/dev/null' > "$P2/wifi_devs.txt"
  # NVRAM Wi-Fi files: read-only copy (never written back from here)
  rsh 'ls -lR /mnt/vendor/nvdata/APCFG/APRDEB 2>/dev/null | head -80' > "$P2/nvram_aprdeb_ls.txt"
  mkdir -p "$P2/nvram"
  local f; for f in $(rsh 'ls /mnt/vendor/nvdata/APCFG/APRDEB 2>/dev/null' | grep -i wifi); do
    adb -s "$S" exec-out "cat /mnt/vendor/nvdata/APCFG/APRDEB/$f" > "$P2/nvram/$f"; done
  (cd "$P2/nvram" && shasum -a 256 * > SHA256SUMS 2>/dev/null) || true
  # battery, charger, thermal
  rsh 'for d in /sys/class/power_supply/*; do echo "== $d"; for f in $d/*; do [ -f $f ] && [ -r $f ] && echo "$(basename $f)=$(cat $f 2>/dev/null | head -c 200)"; done; done' > "$P2/power_supply.txt" || true
  rsh 'ls -ld /proc/mtk_battery_cmd /proc/mtk_battery* /sys/devices/platform/*charger* /sys/class/power_supply/*/device/driver 2>/dev/null; for f in /proc/mtk_battery_cmd/*; do echo "== $f"; cat $f 2>/dev/null | head -20; done' > "$P2/mtk_battery_cmd.txt" || true
  rsh 'for z in /sys/class/thermal/thermal_zone*; do echo "$(basename $z) $(cat $z/type) $(cat $z/temp) $(cat $z/mode 2>/dev/null)"; for t in $z/trip_point_*_temp; do [ -f $t ] && echo "  $(basename $t)=$(cat $t) $(cat ${t%_temp}_type 2>/dev/null)"; done; done' > "$P2/thermal.txt" || true
  info "Wi-Fi NVRAM files copied: $(ls "$P2/nvram" | grep -vc SHA256SUMS)"
  info "input devices: $(grep -o '/dev/input/event[0-9]*\|name: .*' "$P2/getevent_lp.txt" | paste -sd' ' - | head -c 400)"
  STAGE_DONE "captured to $P2"
}

gate_fastbootd() {  # userspace fastboot (fastbootd) on this serial, unlocked, no snapshot update pending
  in_fastboot || die "not in fastboot(d)"
  [[ "$(fbv is-userspace)" == yes ]] || die "not fastbootd (is-userspace=$(fbv is-userspace))"
  [[ "$(fbv serialno)" == "$S" ]] || die "serialno mismatch"
  [[ "$(fbv super-partition-name)" == super ]] || die "super-partition-name=$(fbv super-partition-name)"
  local su; su=$(fbv snapshot-update-status); [[ "$su" == none ]] || die "snapshot-update-status=$su (want none)"
  pass "fastbootd: userspace, super, snapshot-update-status=none, current-slot=$(fbv current-slot)"
}
st_fastbootd_check() {
  STAGE fastbootd-check "Android -> fastbootd -> Android, no writes (does fastbootd work with this init_boot?)"
  in_adb && is_root || die "boot Android with root first"
  mkdir -p "$P2"; misc_snapshot before_fastbootd
  adb -s "$S" reboot fastboot
  wait_fastboot 120 || die "no fastboot(d) after 'adb reboot fastboot': check the screen; Vol-down + Power reaches lk fastboot, then 'fastboot reboot'"
  fastboot -s "$S" getvar all 2>&1 | tee "$P2/fastbootd_getvar.txt" | grep -iE "is-userspace|super|snapshot|slot|partition-size:(linux|system_a|vendor_a)" | head -20 || true
  gate_fastbootd
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  wait_boot 300 || die "Android did not come back from fastbootd"
  misc_snapshot after_fastbootd
  cmp -s <(tail -c +2049 "$L/misc_before_fastbootd.img" | head -c 2048) <(tail -c +2049 "$L/misc_after_fastbootd.img" | head -c 2048) \
    && pass "boot-control block unchanged" || info "[DIFF] boot-control block changed (see bootctrl.txt)"
  good_boot
  STAGE_DONE "fastbootd works"
}

LP_NAME=linux; LP_BYTES=3221225472; LP_FREE_FROM=13495800   # 3 GiB; first free sector of super on #5 (2026-11-22)
super_head() {  # $1 = tag: back up the LP metadata head of super from Android root, check it parses
  adb -s "$S" exec-out "dd if=/dev/block/by-name/super bs=1048576 count=1 2>/dev/null" > "$P2/super_head_$1.bin"
  python3 "$ROOT/linux/tools/lptool.py" check "$P2/super_head_$1.bin" >/dev/null || die "super head ($1) fails checksums"
  shasum -a 256 "$P2/super_head_$1.bin" | tee -a "$P2/super_heads.sha256"
}
lp_verify() {  # $1 = head tag: linux = LP_BYTES of linear extents, no overlaps, all new space
  local h="$P2/super_head_$1.bin" t="$P2/linux_extents.txt"
  python3 "$ROOT/linux/tools/lptool.py" overlap "$h" || die "extent overlap in super metadata"
  python3 "$ROOT/linux/tools/lptool.py" map "$h" "$LP_NAME" > "$t" || die "$LP_NAME not mappable"
  local total; total=$(awk '{s+=$2} END{print s*512}' "$t")
  (( total == LP_BYTES )) || die "$LP_NAME is $total B, want $LP_BYTES"
  pass "$LP_NAME: $(wc -l < "$t" | tr -d ' ') linear extents, $total B, no overlaps (dm table in $t)"
}
st_lp_create() {
  STAGE lp-create "fastbootd: create-logical-partition $LP_NAME ($LP_BYTES B) in super free space"
  in_adb && is_root || die "boot Android with root first"
  mkdir -p "$P2"; super_head now
  if python3 "$ROOT/linux/tools/lptool.py" dump "$P2/super_head_now.bin" | grep -q " $LP_NAME "; then
    info "$LP_NAME already exists: verifying only"; lp_verify now
    rsh "ls -l /dev/block/mapper/$LP_NAME" || die "/dev/block/mapper/$LP_NAME missing"; good_boot; STAGE_DONE "existing"; return; fi
  cp "$P2/super_head_now.bin" "$P2/super_head_before_create.bin"
  adb -s "$S" reboot fastboot; wait_fastboot 120 || die "no fastbootd"
  gate_fastbootd
  [[ -z "$(fbv partition-size:$LP_NAME)" ]] || die "$LP_NAME already exists in fastbootd"
  confirm "FLASH $S" "fastbootd create-logical-partition $LP_NAME $LP_BYTES on $S (writes super LP metadata; backup in $P2)"
  fastboot -s "$S" create-logical-partition "$LP_NAME" "$LP_BYTES" || die "create-logical-partition failed"
  local sz; sz=$(fbv "partition-size:$LP_NAME"); info "partition-size:$LP_NAME=$sz"
  [[ $((sz)) -eq $LP_BYTES ]] || die "size $sz != $LP_BYTES"
  echo "$(date '+%F %T') create-logical-partition $LP_NAME $LP_BYTES" >> "$L/flashes.txt"
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  wait_boot 300 || fail_boot "no Android after lp-create" lp-delete
  is_root || die "no root after reboot"
  super_head after_create
  python3 "$ROOT/linux/tools/lptool.py" cmp "$P2/super_head_before_create.bin" "$P2/super_head_after_create.bin" --ignore "$LP_NAME" \
    || die "an existing partition changed: restore the head (see linux/README.md)"
  pass "existing partitions unchanged"
  lp_verify after_create
  python3 "$ROOT/linux/tools/lptool.py" dump "$P2/super_head_after_create.bin" | tee "$P2/lp_dump_after_create.txt" | grep " $LP_NAME "
  rsh "ls -l /dev/block/mapper/$LP_NAME" || die "/dev/block/mapper/$LP_NAME missing in Android"
  good_boot
  STAGE_DONE "$LP_NAME created"
}
st_lp_delete() {
  STAGE lp-delete "fastbootd: delete-logical-partition $LP_NAME"
  if in_adb; then adb -s "$S" reboot fastboot; fi
  wait_fastboot 120 || die "no fastbootd"
  gate_fastbootd
  confirm "FLASH $S" "fastbootd delete-logical-partition $LP_NAME on $S"
  fastboot -s "$S" delete-logical-partition "$LP_NAME" || die "delete failed"
  echo "$(date '+%F %T') delete-logical-partition $LP_NAME" >> "$L/flashes.txt"
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  wait_boot 300 || die "no Android after lp-delete"
  STAGE_DONE
}

IMG_CHOOSER_DRY="$W/img/init_boot_chooser_dry.img"; IMG_CHOOSER="$W/img/init_boot_chooser_linux.img"
IMG_CHOOSER_E="$W/img/init_boot_chooser_e.img"   # state E: chooser over the STOCK init_boot ramdisk (unrooted Android)
STOCK_IB() { ls "$ROOT"/backups/"${S}"_*_init_boot_a.stock.img 2>/dev/null | tail -1; }
chooser_prev() {  # $1 = tag: chooser lines of the PREVIOUS boot (pstore console) -> $P2/chooser_<tag>.txt
  adb -s "$S" exec-out "cat /sys/fs/pstore/console-ramoops-0" 2>/dev/null > "$P2/pstore_$1.txt" || true
  LC_ALL=C grep -a -E 'chooser:|linux:|Kernel panic|Call trace' "$P2/pstore_$1.txt" > "$P2/chooser_$1.txt" || true
  sed 's/^/    /' "$P2/chooser_$1.txt"
  LC_ALL=C grep -aq 'Kernel panic' "$P2/pstore_$1.txt" && die "the $1 boot ended in a kernel panic (full log: $P2/pstore_$1.txt)" || true
}
live_matches() {  # $1 = partition, $2 = image: the live partition starts with the image's bytes
  local n; n=$(stat -f%z "$2")
  [[ "$(rsh "head -c $n /dev/block/by-name/$1 | sha256sum" | cut -c1-64)" == "$(shasum -a 256 "$2" | cut -c1-64)" ]]
}
reboot_android() {  # $1 = why
  adb -s "$S" reboot; sleep 8; wait_boot 300 || fail_boot "no Android after reboot ($1)" chooser-off; good_boot
}
st_chooser_dry() {
  STAGE chooser-dry "init_boot_a <- KernelSU ramdisk + chooser (DRY: always Android, logs Vol-up)"
  guard; mkdir -p "$P2"
  [[ -n "$(KSU_IB)" ]] || die "no KSU init_boot archived to restore"
  if in_adb && is_root && live_matches init_boot_a "$IMG_CHOOSER_DRY"; then
    info "init_boot_a already holds the DRY chooser: no flash"
  else
    flash_exp init_boot_a "$IMG_CHOOSER_DRY" "chooser DRY over KernelSU ramdisk" "$(KSU_IB)"
    android_boot "chooser-dry" chooser-off
  fi
  is_root || die "no KernelSU root through the chooser (ksuinit chain broken)"
  pass "KernelSU root works through the chooser"
  # dmesg wraps within ~20 s, so read each boot's chooser lines from pstore after the next reboot
  info "reboot 1 (no key) ..."; reboot_android nokey
  chooser_prev boot_before_nokey
  manual "Key test: press Enter; the phone reboots. Do NOT hold Vol-up during the orange warning (lk would enter fastboot). As soon as the orange screen ends, TAP Vol-up repeatedly for ~5 s" || true
  reboot_android vol-up
  chooser_prev nokey
  grep -q 'Vol-up not held' "$P2/chooser_nokey.txt" || die "no chooser key report for the no-key boot (pstore: $P2/chooser_nokey.txt)"
  pass "no-key boot: chooser reported Vol-up not held, booted Android"
  info "reboot 3 (no key) to read the Vol-up boot ..."; reboot_android read-key
  chooser_prev key
  grep -q 'Vol-up HELD' "$P2/chooser_key.txt" && pass "chooser saw Vol-up (DRY: still booted Android)" \
    || info "[WARN] chooser did not see Vol-up (see $P2/chooser_key.txt for key events)"
  ash 'getevent -lp' | grep -q '"mtk-kpd"' && pass "Android still has the mtk-kpd (Vol-up) input device" || die "mtk-kpd input missing in Android"
  is_root || die "root lost"
  misc_snapshot after_chooser_dry
  STAGE_DONE
}
DEB_SIMG="$W/debian/debian.simg"
key_boot() {  # $1 = what: reboot from Android and have the user tap Vol-up after lk's orange screen
  manual "$1: press Enter; the phone reboots. Leave Vol-up alone during the orange warning, then TAP Vol-up repeatedly for ~5 s" || true
  adb -s "$S" reboot
}
ssh_deb() { ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=8 root@"$PHONE_IP" "$@"; }
st_chooser_linux() {
  STAGE chooser-linux "init_boot_a <- chooser (real): no key = Android; Vol-up = Linux branch (rescue shell while linux is empty)"
  guard; mkdir -p "$P2"
  if in_adb && is_root && live_matches init_boot_a "$IMG_CHOOSER"; then info "init_boot_a already holds the chooser: no flash"
  else
    flash_exp init_boot_a "$IMG_CHOOSER" "chooser over KernelSU ramdisk" "$(KSU_IB)"
    android_boot "chooser-linux (no key)" chooser-off
  fi
  is_root || die "no KernelSU root through the chooser"
  pass "no key: Android + KernelSU root"
  key_boot "Linux branch test"
  if ! wait_linux_usb; then
    info "no USB network: either the key was missed (then Android boots) or the Linux branch failed (it reboots to Android within 10 min)"
    wait_boot 900 || fail_boot "neither Linux nor Android after the key boot" chooser-off
    good_boot; chooser_prev keyboot_missed; die "Linux branch not reached (see $P2/chooser_keyboot_missed.txt); rerun to retry the key"
  fi
  local d="$P2/linux-branch" i port=; mkdir -p "$d"
  # linux holds Debian -> its sshd answers (port 22); linux empty or not bootable -> the initramfs rescue telnetd (23)
  for ((i = 0; i < 150; i++)); do   # ~5 min: a slow first Debian boot still reaches sshd
    nc -z -w 2 "$PHONE_IP" 22 >/dev/null 2>&1 && { port=22; break; }
    nc -z -w 2 "$PHONE_IP" 23 >/dev/null 2>&1 && { port=23; break; }
    sleep 2
  done
  if [[ -z $port ]]; then   # never fail_boot a phone that is still up: that would point at chooser-off for nothing
    phone_ping && die "the Linux branch answers ping but neither SSH (22) nor telnet (23) after ~5 min; inspect it (ACM serial), then reboot it"
    wait_boot 300 || fail_boot "the Linux branch went away and Android did not come back" chooser-off
    good_boot; die "the Linux branch went away and Android booted (a crash or the 10-min rescue timer?); see pstore"
  fi
  if [[ $port == 22 ]]; then
    for i in $(seq 1 20); do ssh_deb true 2>/dev/null && break; sleep 3; done
    ssh_deb true || die "Debian's sshd answers on $PHONE_IP but SSH login fails (image built without PUBKEY?); Debian is still running"
    ssh_deb 'uname -a; findmnt -n -o SOURCE /; cat /var/log/vegas/init.log' > "$d/summary.txt" 2>&1 || true
    ssh_deb dmesg > "$d/dmesg.txt" 2>&1 || true
  else
    lsh 'uname -a; cat /tmp/init.log; cat /tmp/lpmap.txt; ls -l /dev/mapper; cat /tmp/insmod.fail 2>/dev/null' 6 > "$d/summary.txt"
    lsh 'dmesg' 9 > "$d/dmesg.txt"
  fi
  sed -n '/linux:/p;/ -> /p;/^\/dev/p' "$d/summary.txt"
  grep -q 'lpmap ok' "$d/summary.txt" && pass "Linux branch: lpmap mapped super partitions" || info "[WARN] lpmap did not report ok"
  if [[ $port == 22 ]]; then
    pass "Linux branch booted Debian ($(ssh_deb 'findmnt -n -o SOURCE /' 2>/dev/null))"
    debian_reboot
  else
    info "sending the Linux branch to reboot -> Android"
    lsh 'sync; reboot -f' 2 >/dev/null || true
    wait_boot 300 || fail_boot "no Android after the Linux branch reboot" chooser-off
  fi
  good_boot; is_root || die "root lost"
  misc_snapshot after_chooser_linux
  STAGE_DONE
}
st_rootfs_flash() {
  STAGE rootfs-flash "fastbootd: flash linux <- Debian trixie ext4 (sparse)"
  [[ -f "$DEB_SIMG" ]] || die "missing $DEB_SIMG (linux/debian/build.sh)"
  [[ "$(xxd -p -l 4 "$DEB_SIMG")" == 3aff26ed ]] || die "$DEB_SIMG is not an Android sparse image"
  [[ "$(cat "$W/debian/debian.serial" 2>/dev/null)" == "$S" ]] \
    || die "$DEB_SIMG was built for '$(cat "$W/debian/debian.serial" 2>/dev/null)', not $S (VEGAS_SERIAL=$S linux/debian/build.sh)"
  # the rescue root holds the only copy init.linux reads of the main root's anchor/uuid: never flash one without it
  local want=none; [[ -s "$L/datadisk/vegasdisk.conf" ]] && want=$(cat "$L/datadisk/vegasdisk.conf")
  [[ "$(cat "$W/debian/debian.vegasdisk" 2>/dev/null)" == "$want" ]] \
    || die "$DEB_SIMG carries vegasdisk.conf '$(cat "$W/debian/debian.vegasdisk" 2>/dev/null | paste -sd' ' -)', this phone needs '$(paste -sd' ' - <<<"$want")': rebuild (VEGAS_SERIAL=$S linux/debian/build.sh)"
  in_adb && ! is_root && die "Android is unrooted (state E): run --only root-on first (this stage verifies the flash as root)"
  if in_adb; then adb -s "$S" reboot fastboot; fi
  wait_fastboot 120 || die "no fastbootd"
  gate_fastbootd
  [[ $(( $(fbv "partition-size:$LP_NAME") )) -eq $LP_BYTES ]] || die "partition $LP_NAME missing or wrong size"
  [[ "$(fbv "is-logical:$LP_NAME")" == yes ]] || die "$LP_NAME is not logical"
  confirm "FLASH $S" "fastbootd flash $LP_NAME <- $(basename "$DEB_SIMG") ($(du -h "$DEB_SIMG" | cut -f1) sparse)"
  fastboot -s "$S" flash "$LP_NAME" "$DEB_SIMG" || die "flash $LP_NAME failed"
  echo "$(date '+%F %T') $LP_NAME $(shasum -a 256 "$DEB_SIMG" | cut -c1-16) debian" >> "$L/flashes.txt"
  fastboot -s "$S" reboot >/dev/null 2>&1 || true
  wait_boot 300 || fail_boot "no Android after rootfs flash" lp-delete
  good_boot; is_root || die "no root"
  rsh "blkid /dev/block/mapper/$LP_NAME" | tee "$P2/linux_blkid.txt"
  grep -q 'vegas-root' "$P2/linux_blkid.txt" && pass "linux holds ext4 vegas-root" || die "label not seen on /dev/block/mapper/$LP_NAME"
  STAGE_DONE
}
st_debian_boot() {
  STAGE debian-boot "Vol-up -> Debian systemd; SSH over USB; checks; reboot -> Android"
  guard; mkdir -p "$P2/debian"
  in_adb || die "start from Android"
  key_boot "Debian boot"
  wait_linux_usb || { wait_boot 900 && { good_boot; chooser_prev debian_missed; die "Debian not reached (key missed or branch fell back); see $P2/chooser_debian_missed.txt"; }; fail_boot "neither Debian nor Android" chooser-off; }
  local i; for i in $(seq 1 100); do ssh_deb true 2>/dev/null && break; sleep 3; done   # ~5 min: sshd may start late (Wi-Fi, first boot)
  ssh_deb true || { info "no SSH: trying the rescue telnet"; wait_telnet || true; lsh 'cat /tmp/init.log' 4 | tee "$P2/debian/rescue.txt"; die "Debian not up (rescue log above)"; }
  pass "SSH root@$PHONE_IP"
  ssh_deb 'uname -a; cat /etc/vegas/build-info; systemctl is-system-running; systemctl --failed --no-legend; findmnt -rn -o TARGET,SOURCE,FSTYPE,OPTIONS; free -m; cat /var/log/vegas/init.log' | tee "$P2/debian/summary.txt"
  ssh_deb 'journalctl -b --no-pager' > "$P2/debian/journal.txt" 2>&1 || true
  ssh_deb 'dmesg' > "$P2/debian/dmesg.txt" 2>&1 || true
  grep -qE 'nvdata|nvram|protect|persist|userdata|metadata' <(awk '{print $2}' "$P2/debian/summary.txt") && die "an NV/userdata partition is mounted in Debian" || pass "no NV/userdata mounts"
  info "failed units: $(ssh_deb 'systemctl --failed --no-legend | wc -l')"
  debian_reboot
  if is_root; then misc_snapshot after_debian; else info "Android unrooted (state E): misc checked from Debian by state-e-check"; fi
  STAGE_DONE "Debian booted"
}

bootok_wait() {  # main root: let vegas-bootok clear init.linux's boot-failure counter before a scripted reboot, or this
  # boot counts as a failed one (2 in a row -> the next Vol-up boot uses the rescue root). No counter file: no wait.
  ssh_deb 'f=/var/lib/vegas/bootfail; [ -e $f ] || exit 0
    for i in $(seq 1 150); do [ "$(cat $f 2>/dev/null)" = 0 ] && exit 0; sleep 2; done; exit 1' \
    || info "[WARN] boot-failure counter not cleared after 5 min (multi-user.target not reached? systemctl list-jobs): this boot counts as failed"
}
debian_reboot() {  # from a running Debian: systemctl reboot -> Android; reports how long it took
  bootok_wait
  local t0=$SECONDS
  ssh_deb 'systemctl reboot' || true
  info "waiting for Debian to shut down and Android to boot (shutdown should take < 15 s) ..."
  local i; for ((i = 0; i < 120; i++)); do phone_ping || break; sleep 1; done
  info "Debian off the network after $((SECONDS - t0)) s"
  wait_boot 300 || fail_boot "no Android after Debian reboot" chooser-off
  good_boot; pass "Android back $((SECONDS - t0)) s after 'systemctl reboot'"
}

# ---------------- end state E ----------------
rcat() {  # binary-safe root read of one file (rsh/ash strip \r, which corrupts binary data)
  if is_root; then adb -s "$S" exec-out "cat '$1'"; else adb -s "$S" exec-out "su -c \"cat '$1'\""; fi
}
st_android_capture() {  # read-only; needs root. Everything Debian needs from Android before root goes away.
  STAGE android-capture "rooted Android: modules, gauge/Wi-Fi daemons + libraries, charge nodes, NVRAM/gauge copies"
  in_adb && is_root || die "boot Android with root first"
  local d="$P2/capture2" rt="$W/android-rt" f p; mkdir -p "$d/bin" "$d/nvcfg_fg" "$d/nvram" "$rt"
  rsh 'cat /proc/modules' > "$d/android_modules.txt"
  rsh 'ps -A -o USER,PID,PPID,NAME,ARGS' | grep -iE 'fuelg|wmt|wlan|wifi|supplicant|batt|charg|thermal|health' > "$d/procs.txt" || true
  rsh 'grep -rn -A5 -E "fuelgauged|wmt_|wlan_assistant" /vendor/etc/init/' > "$d/vendor_rc.txt" || true
  ash getprop | grep -iE 'wlan|wifi|connsys|wmt|nvram|fuelg' > "$d/props.txt" || true
  for f in fuelgauged fuelgauged_nvram wmt_loader wmt_launcher wlan_assistant; do adb -s "$S" pull "/vendor/bin/$f" "$d/bin/" >/dev/null; done
  for f in libfgauge_gm30.so mt6835/libmtk_drvb.so; do adb -s "$S" pull "/vendor/lib64/$f" "$d/bin/" >/dev/null; done
  # exact runtime closure of the vendor daemons (linker64, bionic, VNDK) -> shipped in the Debian image at the same paths
  : > "$d/maps.txt"
  for p in fuelgauged wlan_assistant wmt_launcher; do rsh "cat /proc/\$(pidof $p)/maps" | awk '{print $6}' | grep '^/' >> "$d/maps.txt" || true; done
  sort -u "$d/maps.txt" | grep -E '^/apex/|^/system/lib64/' > "$rt/files.txt"
  while read -r f; do mkdir -p "$rt$(dirname "$f")"; rcat "$f" > "$rt$f"
    [[ "$(head -c4 "$rt$f" | xxd -p)" == 7f454c46 ]] || die "copy of $f is not an ELF (read failed?)"; done < "$rt/files.txt"
  chmod 755 "$rt/apex/com.android.runtime/bin/linker64"
  adb -s "$S" exec-out "cat /linkerconfig/ld.config.txt" > "$rt/ld.config.android.txt"
  # gauge state (nvcfg/fg) and Wi-Fi NVRAM: COPIES, read-only. Debian uses these copies, never the NV partitions.
  for f in $(rsh 'ls /mnt/vendor/nvcfg/fg/'); do rcat "/mnt/vendor/nvcfg/fg/$f" > "$d/nvcfg_fg/$f"; done
  for f in WIFI WIFI_CUSTOM WIFI_VEGAS; do rcat "/mnt/vendor/nvdata/APCFG/APRDEB/$f" > "$d/nvram/$f"; done
  (cd "$d/nvram" && shasum -a 256 WIFI* > SHA256SUMS)
  rsh 'for f in /sys/module/qpnp_adaptive_charge/parameters/* /proc/mtk_battery_cmd/*; do echo "$f=$(cat $f)"; done' > "$d/charge_nodes.txt" || true
  info "Moto cap (charging_upper_limit): $(ash content query --uri content://com.motorola.batteryconfiguration/config | grep -oE 'charging_upper_limit=-?[0-9]+' || echo unknown)"
  pass "runtime closure: $(wc -l < "$rt/files.txt") files in $rt; gauge state: $(ls "$d/nvcfg_fg" | paste -sd' ' -)"
  STAGE_DONE "captured to $d"
}

need_bootok() {  # choosers built from init.linux with the boot-failure counter: the main root must clear it
  grep -q bootfail "$ROOT/linux/initramfs/init.linux" || return 0
  [[ -s "$L/datadisk/vegasdisk.conf" ]] || return 0   # no main root on this phone: the counter never runs
  [[ -s "$L/bootok_main" ]] || die "the chooser's init.linux counts main-root boots, but vegas-bootok was never enabled on the main root: run --only deb-update on the main root first"
}
boot_ctrl_block() { tail -c +2049 "$1" | head -c 2048; }   # misc offset 2048 = A/B boot-control (bootctrl.py)
st_state_e() {
  STAGE state-e "init_boot_a <- chooser over STOCK init_boot: unrooted Android by default, Vol-up = Debian"
  guard
  [[ -f "$IMG_CHOOSER_E" ]] || die "missing $IMG_CHOOSER_E (linux/initramfs/build_chooser.sh e $S)"
  [[ -n "$(STOCK_IB)" ]] || die "no stock init_boot archived for $S"
  [[ "$(stage_status android-capture 2>/dev/null)" == done ]] || die "run android-capture first (it needs root, which state E removes)"
  need_bootok
  in_adb || die "start from Android"
  local esha; esha=$(shasum -a 256 "$IMG_CHOOSER_E" | cut -c1-16)
  if ! is_root && [[ "$(grep ' init_boot_a ' "$L/flashes.txt" 2>/dev/null | tail -1 | awk '{print $4}')" == "$esha" ]]; then
    info "unrooted and the last init_boot_a flash was this E image ($esha): no flash (state-e-check verifies it from Debian)"
  else
    if is_root; then misc_snapshot before_state_e; else info "unrooted: keeping the last misc snapshot"; fi
    flash_exp init_boot_a "$IMG_CHOOSER_E" "chooser over stock init_boot (state E)" "$(STOCK_IB)"
    android_boot "state-e (no key)" root-on
  fi
  ! is_root || die "Android still has root through adb"
  [[ -z "$(ash 'command -v su')" ]] && pass "unrooted: no su, adbd not root" || die "su still present: $(ash 'command -v su')"
  info "Moto cap (charging_upper_limit): $(ash content query --uri content://com.motorola.batteryconfiguration/config | grep -oE 'charging_upper_limit=-?[0-9]+' || echo unknown) (want 80; scripts/phone.sh charge-protect sets it)"
  st_state_e_check
  CUR_STAGE=state-e; STAGE_DONE "end state E"
}
st_state_e_check() {  # no flash: Vol-up -> Debian; from Debian (read-only) check init_boot_a + misc; reboot -> Android
  STAGE state-e-check "Vol-up -> Debian; read-only checks of init_boot_a and misc from Debian; reboot -> Android"
  guard; mkdir -p "$P2/state-e"
  in_adb || die "start from Android"
  key_boot "state E Debian boot"
  wait_linux_usb || { wait_boot 900 && { good_boot; die "Debian not reached (key missed?); rerun --only state-e-check"; }; fail_boot "neither Debian nor Android" root-on; }
  local i; for i in $(seq 1 100); do ssh_deb true 2>/dev/null && break; sleep 3; done   # ~5 min: sshd may start late (Wi-Fi, first boot)
  ssh_deb true || die "no SSH to Debian"
  local n; n=$(stat -f%z "$IMG_CHOOSER_E")
  # by-PARTNAME lookup; every access below is a read
  local pdev='pdev() { for u in /sys/class/block/*/uevent; do grep -qx "PARTNAME=$1" "$u" && echo /dev/$(basename $(dirname $u)); done; true; }'
  [[ "$(ssh_deb "$pdev; head -c $n \$(pdev init_boot_a) | sha256sum" | cut -c1-64)" == "$(shasum -a 256 "$IMG_CHOOSER_E" | cut -c1-64)" ]] \
    && pass "init_boot_a holds the state-E chooser" || die "init_boot_a does not match $IMG_CHOOSER_E"
  ssh_deb "$pdev; dd if=\$(pdev misc) bs=4096 count=1 2>/dev/null" > "$L/misc_state_e.img"
  python3 "$ROOT/linux/tools/bootctrl.py" "$L/misc_state_e.img" | tee -a "$L/bootctrl.txt"
  local ref="" c; for c in "$L"/misc_before_state_e.img "$L"/misc_after_debian.img; do
    [[ -f "$c" ]] && { [[ -z "$ref" || "$c" -nt "$ref" ]] && ref=$c; }; done
  [[ -n "$ref" ]] && { cmp -s <(boot_ctrl_block "$ref") <(boot_ctrl_block "$L/misc_state_e.img") \
    && pass "boot-control block unchanged vs $(basename "$ref")" || info "[DIFF] boot-control block changed vs $(basename "$ref")"; }
  ssh_deb 'cat /var/log/vegas/init.log; systemctl is-system-running; systemctl --failed --no-legend' | tee "$P2/state-e/debian.txt"
  debian_reboot
  ! is_root || info "[WARN] Android has root: init_boot_a is not the state-E image?"
  STAGE_DONE
}
st_root_on() {  # temp root in state E: the rooted chooser (KernelSU base); undo with root-off
  STAGE root-on "init_boot_a <- chooser over KernelSU init_boot (temp root)"
  need_bootok
  flash_exp init_boot_a "$IMG_CHOOSER" "chooser over KernelSU (root-on)" "$(KSU_IB)"
  android_boot "root-on" chooser-off
  is_root && pass "root (KernelSU)" || die "no root after root-on"
  STAGE_DONE
}
st_root_off() {  # back to state E: unrooted
  STAGE root-off "init_boot_a <- state-E chooser (unrooted)"
  need_bootok
  flash_exp init_boot_a "$IMG_CHOOSER_E" "chooser over stock init_boot (root-off)" "$(STOCK_IB)"
  android_boot "root-off" root-on
  ! is_root && pass "unrooted" || die "still root after root-off"
  STAGE_DONE
}

st_chooser_off() { st_restore_init_boot; }  # put the plain KernelSU init_boot back (leaves Android ROOTED)

st_restore() {
  STAGE restore "KernelSU init_boot_a back; Android on the rebuilt kernel"
  st_restore_init_boot
  CUR_STAGE=restore; STAGE_DONE "$(ash uname -r)"
}

st_stock_boot() {
  STAGE stock-boot "stock -4-2 boot_a back (from the zip)"
  to_fastboot; gate_fastboot flashing_unlocked
  confirm "FLASH $S" "restore boot_a <- stock -4-2 boot.img"
  fastboot -s "$S" flash boot_a "$STOCK_BOOT"
  local img; img=$(KSU_IB)
  [[ -n "$img" ]] && { info "also restoring KSU init_boot_a"; fastboot -s "$S" flash init_boot_a "$img"; }
  android_boot "stock-boot" stock-boot
  STAGE_DONE
}

# ---------------- Linux main root inside Android's /data (vegasdisk; docs/linux-on-vegas.md section 12) ----------------
# Pinned files in /data (f2fs pin + fallocate, as Android's DSU/libfiemap). Debian reaches them through the RAW userdata
# partition, after vegasdisk has checked the extent table CRCs, uuid, bounds and every canary. Android's encryption is
# never touched: f2fs never reads these files' contents, and the raw blocks hold Linux's plaintext.
VD_LOCAL="$W/vegasdisk"; VD_PHONE=/data/local/tmp/vegasdisk
DD_DIR=/data/vegas; POC_DIR=/data/vegas-poc; DD="$L/datadisk"
DEB_PDEV='pdev() { for u in /sys/class/block/*/uevent; do grep -qx "PARTNAME=$1" "$u" && echo /dev/$(basename $(dirname $u)); done; true; }'
vd_push() {   # the same static binary runs in Android, the initramfs and Debian
  [[ -x "$VD_LOCAL" ]] || die "missing $VD_LOCAL (orb -m vegas-kbuild aarch64-linux-gnu-gcc -static -Os -o linux/work/vegasdisk linux/tools/vegasdisk.c)"
  adb -s "$S" push "$VD_LOCAL" "$VD_PHONE" >/dev/null || die "push vegasdisk"
  rsh "chmod 755 $VD_PHONE"
}
vd_deb_push() { ssh_deb 'cat > /usr/local/sbin/vegasdisk && chmod 755 /usr/local/sbin/vegasdisk' < "$VD_LOCAL" || die "push vegasdisk to Debian"; }
vd_parse() {  # $1 = vegasdisk output -> VD_ANCHOR VD_UUID
  local l; l=$(grep -oE 'anchor=[0-9]+ uuid=[0-9a-f]{32}' <<<"$1" | tail -1) || true
  VD_ANCHOR=$(sed -n 's/^anchor=\([0-9]*\) .*/\1/p' <<<"$l"); VD_UUID=$(sed -n 's/.*uuid=\([0-9a-f]*\)$/\1/p' <<<"$l")
  [[ -n "$VD_ANCHOR" && -n "$VD_UUID" ]]
}
vd_android() {  # $1 = vegasdisk arguments (root); prints the output, dies on failure
  local out; out=$(rsh "$VD_PHONE $1; echo \"rc=\$?\"" 2>&1) || true
  echo "$out" | grep -v '^rc=' | tee -a "$DD/vegasdisk.log"
  [[ "$(tail -1 <<<"$out")" == rc=0 ]] || die "vegasdisk $1 failed"
}
android_sha() {  # $1 = dm name, $2 = bytes: sha256 of the start of an Android-side vegasdisk mapping
  rsh "echo 3 > /proc/sys/vm/drop_caches; dd if=/dev/mapper/$1 bs=1048576 count=$(( $2 / 1048576 )) 2>/dev/null | sha256sum" | cut -c1-64
}
deb_up() {  # $1 = why: Vol-up boot to Debian and wait for SSH
  key_boot "$1"
  wait_linux_usb || { wait_boot 900 && { good_boot; die "Debian not reached (key missed?); rerun"; }; fail_boot "neither Debian nor Android" chooser-off; }
  local i; for i in $(seq 1 100); do ssh_deb true 2>/dev/null && break; sleep 3; done   # ~5 min: sshd may start late (Wi-Fi, first boot)
  ssh_deb true || die "no SSH to Debian"
  info "Debian root: $(ssh_deb 'findmnt -n -o SOURCE /')"
}

st_datadisk_poc() {
  STAGE datadisk-poc "256 MiB pinned test disk: Android writes -> Debian reads + writes -> Android reads; GC stress; delete"
  guard; mkdir -p "$DD"
  in_adb && is_root || die "needs rooted Android (before state-e, or after root-on)"
  vd_push
  rsh "[ -e $POC_DIR ]" && die "$POC_DIR exists (an earlier PoC): inspect it, then '$VD_PHONE delete $POC_DIR <uuid>'"
  confirm "FLASH $S" "create a 256 MiB pinned test disk in $POC_DIR; raw userdata writes ONLY inside its own extents"
  local out; out=$(vd_android "create $POC_DIR 256 --piece-mib 128"); vd_parse "$out" || die "no anchor/uuid from create"
  vd_android "verify $POC_DIR" >/dev/null
  local n=$((8 << 20)) s1 s2
  head -c $n /dev/urandom > "$DD/pat1"; head -c $n /dev/urandom > "$DD/pat2"
  s1=$(shasum -a 256 < "$DD/pat1" | cut -c1-64); s2=$(shasum -a 256 < "$DD/pat2" | cut -c1-64)
  adb -s "$S" push "$DD/pat1" /data/local/tmp/vd_pat1 >/dev/null
  vd_android "map /dev/block/by-name/userdata $VD_ANCHOR $VD_UUID vdpoc" >/dev/null
  rsh "dd if=/data/local/tmp/vd_pat1 of=/dev/mapper/vdpoc bs=1048576 conv=fsync 2>&1 | tail -1"
  [[ "$(android_sha vdpoc $n)" == "$s1" ]] && pass "Android: pattern 1 written and read back" || die "Android readback differs"
  vd_android "unmap vdpoc" >/dev/null
  rsh "rm -f /data/local/tmp/vd_pat1"

  deb_up "PoC: Debian boot"
  vd_deb_push
  local deb; deb=$(ssh_deb "$DEB_PDEV; UD=\$(pdev userdata); vegasdisk map --ro \$UD $VD_ANCHOR $VD_UUID vdpoc >/dev/null &&
    dd if=/dev/mapper/vdpoc bs=1M count=8 iflag=direct 2>/dev/null | sha256sum | cut -c1-64; vegasdisk unmap vdpoc >/dev/null") || true
  [[ "$deb" == "$s1" ]] && pass "Debian reads Android's pattern through the raw userdata extents" || die "Debian read '$deb', want $s1"
  ssh_deb "$DEB_PDEV; UD=\$(pdev userdata); cat > /tmp/pat2 && vegasdisk map \$UD $VD_ANCHOR $VD_UUID vdpoc >/dev/null &&
    dd if=/tmp/pat2 of=/dev/mapper/vdpoc bs=1M oflag=direct conv=fsync 2>/dev/null && vegasdisk unmap vdpoc >/dev/null" < "$DD/pat2" \
    || die "Debian write failed"
  pass "Debian wrote pattern 2"
  debian_reboot

  vd_android "verify $POC_DIR" | grep -q 'verify OK' && pass "Android: pieces still pinned, unchanged, canaries intact" || die "verify after Debian"
  vd_android "map --ro /dev/block/by-name/userdata $VD_ANCHOR $VD_UUID vdpoc" >/dev/null
  [[ "$(android_sha vdpoc $n)" == "$s2" ]] && pass "Android reads Debian's pattern" || die "Android read of pattern 2 differs"
  vd_android "unmap vdpoc" >/dev/null
  info "f2fs idle maintenance (GC) ..."; ash 'sm idle-maint run' >/dev/null || true; sleep 90
  vd_android "verify $POC_DIR" | grep -q 'verify OK' && pass "verify after idle maintenance" || die "moved by idle maintenance"
  local errs; errs=$(rsh 'dmesg | grep -iE "f2fs.*(error|fail|corrupt|inconsistent)"' || true)
  [[ -z "$errs" ]] && pass "no f2fs errors in dmesg" || { echo "$errs"; die "f2fs errors"; }
  vd_android "delete $POC_DIR $VD_UUID"
  STAGE_DONE "pinned-file disk works both ways"
}

st_datadisk_create() {  # VEGAS_DISK_MIB (default 32768)
  STAGE datadisk-create "Linux main root: pinned disk in $DD_DIR, ext4 vegas-root2, a copy of the rescue root"
  guard; mkdir -p "$DD"
  in_adb && is_root || die "needs rooted Android (before state-e, or after root-on)"
  local mib=${VEGAS_DISK_MIB:-32768}
  vd_push
  if rsh "[ -e $DD_DIR/disk.0000 ]"; then
    info "$DD_DIR exists: reusing it"; local out; out=$(vd_android "verify $DD_DIR"); vd_parse "$out" || die "no anchor"
  else
    local freek; freek=$(rsh "df -k /data | tail -1" | awk '{print $4}')
    (( freek / 1024 > mib + 16384 )) || die "/data has $(( freek / 1024 )) MiB free; need $mib + 16384"
    confirm "FLASH $S" "create a $mib MiB Linux disk in $DD_DIR (pinned files; raw userdata writes only inside them)"
    local out; out=$(vd_android "create $DD_DIR $mib"); vd_parse "$out" || die "no anchor/uuid from create"
    vd_android "verify $DD_DIR" >/dev/null
  fi
  # $DD/vegasdisk.conf (baked into debian.simg by build.sh) is written only once the main root is complete
  pass "disk: anchor $VD_ANCHOR uuid $VD_UUID"

  deb_up "Debian (rescue root): build the main root"
  [[ "$(ssh_deb 'findmnt -n -o SOURCE /')" == /dev/mapper/linux ]] || die "Debian did not boot the rescue root"
  vd_deb_push
  # pdev returns 0 always (its loop ends on a failed grep, which `set -e` turned into a silent exit on 2026-11-23)
  ssh_deb "set -e; $DEB_PDEV; UD=\$(pdev userdata); [ -b \"\$UD\" ] || { echo 'no userdata block device'; exit 1; }
    vegasdisk map \$UD $VD_ANCHOR $VD_UUID vegas-disk
    L=\$(blkid -o value -s LABEL /dev/mapper/vegas-disk || true); T=\$(blkid -o value -s TYPE /dev/mapper/vegas-disk || true)
    if [ -z \"\$T\" ]; then
      mkfs.ext4 -q -E nodiscard -L vegas-root2 /dev/mapper/vegas-disk
      mkdir -p /mnt/main; mount /dev/mapper/vegas-disk /mnt/main
      cp -ax / /mnt/main/          # one filesystem: the rescue root only, mount points stay empty
      rm -f /mnt/main/etc/vegas/root-role /mnt/main/etc/vegas/vegasdisk.conf
      sed -i 's/^LABEL=vegas-root /LABEL=vegas-root2 /' /mnt/main/etc/fstab; grep -q '^LABEL=vegas-root2 ' /mnt/main/etc/fstab
      sync; echo main > /mnt/main/etc/vegas/root-role; sync   # completion marker, written last
      umount /mnt/main
    elif [ \"\$L\" = vegas-root2 ]; then
      mkdir -p /mnt/main; mount -o ro /dev/mapper/vegas-disk /mnt/main
      R=\$(cat /mnt/main/etc/vegas/root-role 2>/dev/null || true); umount /mnt/main
      if [ \"\$R\" != main ]; then
        echo 'refusing: vegas-root2 without the completion marker (an interrupted copy?). Inspect it; to start over:'
        echo '  vegasdisk map ..., wipefs -a /dev/mapper/vegas-disk, then rerun datadisk-create'
        vegasdisk unmap vegas-disk; exit 1
      fi
      echo 'main root already exists (marker present): kept as it is (no copy); only vegasdisk.conf is rewritten'
    else echo \"refusing: the disk holds \$T '\$L'\"; vegasdisk unmap vegas-disk; exit 1; fi
    vegasdisk unmap vegas-disk
    printf 'ANCHOR=%s\nUUID=%s\n' $VD_ANCHOR $VD_UUID > /etc/vegas/vegasdisk.conf.new
    mv /etc/vegas/vegasdisk.conf.new /etc/vegas/vegasdisk.conf; sync
    echo main-root-ready" | tee "$DD/create_debian.txt" | tail -3 || true   # failure: the grep below dies with the log path
  grep -q main-root-ready "$DD/create_debian.txt" || die "main root setup failed (see $DD/create_debian.txt)"
  printf 'ANCHOR=%s\nUUID=%s\n' "$VD_ANCHOR" "$VD_UUID" > "$DD/vegasdisk.conf"
  debian_reboot
  info "next: rebuild the chooser (build_chooser.sh linux $S) and --only chooser-linux, so init.linux boots the main root"
  info "rebuild debian.simg before any later rootfs-flash: build.sh now bakes $DD/vegasdisk.conf into the rescue root"
  STAGE_DONE "main root ready on the userdata disk"
}

st_datadisk_check() {  # Android verify (if rooted) + which root Debian boots
  STAGE datadisk-check "Android: vegasdisk verify (when rooted); Debian: booted root + vegasdisk log"
  guard; mkdir -p "$DD"
  in_adb || die "start from Android"
  if is_root; then vd_push; vd_android "verify $DD_DIR" | grep -q 'verify OK' && pass "Android: disk verified" || die "verify failed"
  else info "[WARN] Android unrooted: NO Android-side verify (FIEMAP + pin + GC count). Debian only checks the table,
       the f2fs superblock and the canaries, which cannot see a pinned piece that f2fs moved. Verify after root-on."; fi
  deb_up "datadisk-check: Debian boot"
  ssh_deb 'findmnt -n -o SOURCE,SIZE,USED /; cat /var/log/vegas/vegasdisk.txt 2>/dev/null; grep -E "root:|vegasdisk|rescue" /var/log/vegas/init.log || true' | tee "$DD/check.txt"
  grep -q '^/dev/mapper/vegas-disk' "$DD/check.txt" && pass "Debian runs on the main root" || info "[WARN] Debian is on the rescue root"
  debian_reboot
  STAGE_DONE
}

st_datadisk_grow() {  # VEGAS_DISK_MIB = new total size
  STAGE datadisk-grow "grow the Linux disk in $DD_DIR to \$VEGAS_DISK_MIB MiB (Debian grows ext4 at its next boot)"
  guard; mkdir -p "$DD"
  in_adb && is_root || die "needs rooted Android: --only root-on first (state E)"
  local mib=${VEGAS_DISK_MIB:?set VEGAS_DISK_MIB to the new total size in MiB}
  vd_push; vd_android "verify $DD_DIR" >/dev/null
  confirm "FLASH $S" "grow $DD_DIR to $mib MiB (new pinned pieces; the table on raw userdata is rewritten)"
  vd_android "grow $DD_DIR $mib"
  vd_android "verify $DD_DIR" | grep -q 'verify OK' || die "verify after grow"
  STAGE_DONE "grown; vegas-diskgrow.service runs resize2fs at the next Debian boot"
}

st_deb_update() {  # no token: writes only Debian's booted root
  STAGE deb-update "copy linux/debian/overlay + the property shim into the running Debian; daemon-reload"
  ssh_deb true 2>/dev/null || { in_adb || die "start from Android or a running Debian"; deb_up "deb-update: Debian boot"; }
  local troot; troot=$(ssh_deb 'findmnt -n -o SOURCE /'); info "target root: $troot"
  COPYFILE_DISABLE=1 tar -C "$ROOT/linux/debian/overlay" --no-mac-metadata --exclude ./etc/fstab \
      --exclude __pycache__ --exclude '*.pyc' -cf - . \
    | ssh_deb 'tar -C / --no-same-owner -xf - 2>&1 | grep -v "Ignoring unknown extended header" || true'
  [[ -s "$W/propshim/libpropshim.so" ]] && ssh_deb 'install -D -m 644 /dev/stdin /odm/lib64/libpropshim.so' < "$W/propshim/libpropshim.so"
  # the overlay can need packages the phone's root predates (build.sh PKGS, e.g. the screen UI's python3-evdev that
  # vegas-keys needs): install them with apt-get before the units are enabled. Needs the phone online (Wi-Fi or USB
  # sharing); a failure is reported, not fatal (the image rebuild/flash path installs them too).
  # Only the network steps run under timeout: killing dpkg mid-unpack would leave half-installed packages on the live
  # root, so the install itself runs from the downloaded cache with no timer. dpkg --configure -a first finishes any
  # earlier interrupted run (a half-installed package is not 'ok installed', so it lands in $miss again).
  local want miss; want=$(sed -n 's/^PKGS+\{0,1\}=,\{0,1\}//p' "$ROOT/linux/debian/build.sh" | tr ',\n' '  ')
  miss=$(ssh_deb "for p in $want; do dpkg-query -W -f='\${Status}' \$p 2>/dev/null | grep -q 'ok installed' || echo \$p; done" | tr '\n' ' ') || true
  if [[ -n "${miss// }" ]]; then
    info "packages in build.sh but not on the phone: $miss-> apt-get install"
    if ssh_deb "export DEBIAN_FRONTEND=noninteractive; dpkg --configure -a >/dev/null 2>&1
        timeout 300 apt-get update -qq && timeout 1200 apt-get install -y -q --download-only --no-install-recommends $miss &&
        apt-get install -y -q --no-install-recommends $miss" 2>&1 | tail -n 5; then
      pass "installed: $miss"
    else
      info "[WARN] apt-get install failed (phone offline?): $miss- install them by hand (apt-get install), or rebuild/flash the image;
       if apt says dpkg was interrupted, run 'dpkg --configure -a' on the phone first (the next deb-update also does)"
    fi
  fi
  # keyboard v2 (opt-in: /etc/vegas/kbd-v2): its .deb is a local build (linux/ui-src/wvkbd/build.sh), not in apt
  local kdeb; kdeb=$(ls "$W"/wvkbd-vegas/wvkbd-vegas_*_arm64.deb 2>/dev/null | tail -1) || true
  if [[ -n "$kdeb" ]] && ! ssh_deb "[ \"\$(dpkg-query -W -f='\${Version}' wvkbd-vegas 2>/dev/null)\" = '$(basename "$kdeb" | cut -d_ -f2)' ]"; then
    if ssh_deb 'cat > /tmp/wvkbd-vegas.deb && dpkg -i /tmp/wvkbd-vegas.deb >/dev/null; r=$?; rm -f /tmp/wvkbd-vegas.deb; exit $r' < "$kdeb"; then
      pass "wvkbd-vegas installed ($(basename "$kdeb"); used only with /etc/vegas/kbd-v2)"
    else info "[WARN] dpkg -i $(basename "$kdeb") failed: the stock keyboard stays"; fi
  fi
  # vegas-keys/vegas-away: screen UI key daemon and Away's boot rules (main root only through their Conditions)
  ssh_deb 'chmod 755 /usr/lib/vegas/*; systemctl daemon-reload
    systemctl enable vegas-thermal vegas-diskgrow vegas-fuelgauged vegas-chargeguard.timer vegas-wifi vegas-bootok vegas-sway vegas-keys vegas-away 2>&1 | grep -v "^Created" || true
    systemctl disable serial-getty@ttyGS0 wpa_supplicant@wlan0 2>/dev/null || true; systemctl --failed --no-legend'
  info "sway config, vegas-keys and the screen session take effect at the next boot (never swaymsg reload, D10)"
  # the chooser's boot-failure counter needs vegas-bootok on the MAIN root (state-e/root-on refuse to flash without it)
  if [[ $troot == /dev/mapper/vegas-disk ]] && ssh_deb 'systemctl is-enabled -q vegas-bootok'; then
    date '+%F %T' > "$L/bootok_main"; pass "vegas-bootok enabled on the main root"
  elif ssh_deb '[ -e /etc/vegas/vegasdisk.conf ]'; then
    info "[WARN] this is the rescue root: the main root was NOT updated (it needs vegas-bootok before a counter chooser)"
  fi
  pass "overlay applied"
  STAGE_DONE
}

# ---------------- run ----------------
started=0; [[ -z "$FROM" ]] && started=1
if [[ -n "$ONLY" ]]; then "st_${ONLY//-/_}"; echo "######## linux_b $S finished ($ONLY)"; exit 0; fi
for st in "${STAGES[@]}"; do
  [[ "$st" == "$FROM" ]] && started=1
  ((started)) || continue
  [[ "$(stage_status "$st" 2>/dev/null)" == done && -z "$FROM" ]] && { info "stage $st already done (use --from/--only to redo)"; continue; }
  "st_${st//-/_}"
done
echo "######## linux_b $S finished (${FROM:-all})"
