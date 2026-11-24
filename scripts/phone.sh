#!/usr/bin/env bash
# Per-phone helper for the moto g power (2026) farm.
#
#   scripts/phone.sh <command> [serial|all]
#
# Commands
#   info        read-only device dump (identity, boot state, users/owners, hw, battery, net)
#   check       BL feasibility gate 1 (adb getprop, read-only) + verdict
#   fastboot    BL feasibility gate 2: reboot to bootloader, getvar only, reboot back (no flashing)
#   ota-off     INIT (no root): global flag + try pm uninstall -k --user 0; if refused, appops bg block +
#               netpolicy + per-app network firewall (firewall resets on reboot -> re-run after every boot)
#   ota-off-root AFTER ROOT: su -c pm disable-user / pm disable com.motorola.ccc.ota, verify
#   ota-status  show OTA package / setting state
#   ota-remove  alias of ota-off
#   ota-on      undo ota-off / ota-remove
#   backup      full partition dump + compress to backups/ — SKIPS if archive for this serial+build exists (needs root)
#   rm-workprofile  remove the sidemdm work profile (needs root)
#   wake           keep screen awake, AOD off, brightness min, muted (burn-in/rack safety)
#   park           rack-safe idle: no stay-on, AOD off, muted, offline, screen off
#   offline        Wi-Fi + mobile data + Bluetooth off (no internet: OTA risk; power)
#   mute           every audio stream to its minimum + ringer SILENT
#   debloat        uninstall BLOAT_PKGS for user 0 (reversible; review the list)
#   apps           install basics from tools/apps (Fossify SMS+Files+Keyboard, Firefox, F-Droid, Aurora), set defaults
#   declutter      disable unused carrier/Moto/Google apps for user 0 (reversible: pm enable)
#   home-clear     remove every home-screen icon/widget (launcher DB; needs root)
#   black          black wallpaper (home+lock) + dark theme (needs root; restarts SystemUI)
#   no-anim        animation scales to 0 (also part of wake)
#   protected      ROOT: disable firmware-protected preloads (ccc.ota, PAKS, TFDevicePulse, Gboard...) via service call
#   ram            ROOT: zRAM writeback off (persist.sys.zram_wb_enabled=false)
#   charge-protect Moto Battery protection: charging capped at 80%, always (no root; enables com.motorola.actions)
#   qs             set the pull-down Quick Settings tiles (QS_TILES: no Wallet/GIF maker/System update)
#   rm-sidemdm  uninstall the leftover sidemdm app copy from the personal profile
#   record      write/refresh devices/<serial>.md (auto snapshot block; manual notes kept)
#   full        info + check + ota-off + fastboot + record
#
# Target: a serial, `all` (every adb device), or omitted (the only connected device).
# Output is also appended to logs/<serial>.log.
set -eu   # no pipefail: grep -m1/head close pipes early (SIGPIPE) by design

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGDIR="$ROOT/logs"
mkdir -p "$LOGDIR"

# Expected values / thresholds (see docs/bl-feasibility.md)
EXP_DEVICE="vegas26"
EXP_SKU="XT2617V"
EXP_FB_PRODUCT="vegas"
PATCH_MAX="2026-09-01"                       # security patch must be <= this
MODEM_BUILD="W1WEOS36.48-22-3-3-4-2"          # build vegas-freedom/modem is verified-live on (Sinclair doc = -4-3, do not use)
MODEM_BASEBAND="MT6835O_NR17.RC.MP.V18.6.6.P107.02.309R"
OTA_PKG="com.motorola.ccc.ota"
SIDEMDM_PKG="com.example.personalprofile"
# Bloat removed for user 0 (reversible: cmd package install-existing). Review per firmware before trusting.
BLOAT_PKGS="com.facebook.katana com.facebook.appmanager com.facebook.services com.facebook.system \
com.fitbit.FitbitMobile com.motorola.ccc.ota com.motorola.ccc.devicemanagement com.motorola.ccc.notification"

# Basic replacement apps (tools/apps/, gitignored; fetch per tools/apps/README.md). file|package|sha256
APPS="messages-26-foss-release.apk|org.fossify.messages|7077dae6613d7a9d775841c4c10be16e255f8af8d5152bc84a5e6984740b56e1
file-manager-16-foss-release.apk|org.fossify.filemanager|6e4656b8947966a2853681691bb0005e802ee89983fb141ec0f7186497dcd5f4
fenix-160.0.1.multi.android-arm64-v8a.apk|org.mozilla.firefox|1c811bbdc8d7488b9340d379889cf04105525596d21a7c596b3a664d833858ea
org.fdroid.fdroid_2000053.apk|org.fdroid.fdroid|dac55a0d17b1edf7e7286b48cfbd70c7c52fbb32a00af062c68830a437c47959
com.aurora.store_76.apk|com.aurora.store|fd9c75d90d0f4a7c132b9b4a5a2cf1992a45e03b8d8ff988b7dcfbc0db2c4d11
keyboard-14-foss-release.apk|org.fossify.keyboard|e326885c08b68212fd9fdda9be8a4fa492d5daba7ff37bb4ff4511826f40a8d0"
# Disabled for user 0 by `declutter` (pm disable-user; undo: pm enable <pkg>). Chosen by the owner 2026-11-18.
# Kept on purpose: GMS, Phone/Contacts/Dialer, Settings, SystemUI, launcher, KernelSU, batterycare,
# com.motorola.actions (owns Moto Battery protection = the 80% charge cap; see charge-protect).
DECLUTTER_CARRIER="com.huub.tiger com.swishme.tracfone com.dti.tracfone com.dti.folderlauncher \
com.tracfone.preload.accountservices com.tracfone.generic.mysites com.verizon.mips.services \
com.handmark.expressweather com.motorola.extensions.tracfone \
com.glance.lockscreenM"   # Glance = lock-screen ads/content feed
DECLUTTER_MOTO="com.motorola.mobiledesktop com.motorola.mobiledesktop.core com.motorola.smartfeed \
com.motorola.gamemode com.motorola.personalize com.motorola.moto \
com.motorola.spaces com.motorola.genie com.motorola.help com.motorola.help.extlog com.motorola.fmplayer \
com.motorola.android.fmradio com.motorola.livewallpaper3 com.motorola.om \
com.motorola.paks com.motorola.playautoinstallext com.motorola.demo com.motorola.timeweatherwidget \
com.motorola.securityhub com.motorola.securityhubext com.motorola.dolby.dolbyui"
# ^ Family Space, Device Help, Moto Feedback(+Assistant), FM Radio(+service), Interactive wallpapers, Moto Unplugged,
#   PAKS + PlayAutoInstallExt (silent preload installers), Retail Mode, Moto Widget, Moto Secure(+ext), Dolby Atmos UI.
DECLUTTER_GOOGLE="com.android.chrome com.google.android.youtube com.google.android.apps.youtube.music \
com.google.android.apps.maps com.google.android.apps.photos com.google.android.gm com.google.android.calendar \
com.google.android.apps.docs com.google.android.apps.tachyon com.google.android.apps.messaging \
com.google.android.apps.walletnfcrel com.google.android.play.games com.google.android.apps.chromecast.app \
com.google.android.projection.gearhead com.google.android.apps.nbu.files com.google.android.apps.wellbeing \
com.google.android.feedback com.google.android.apps.restore com.google.android.videos \
com.google.android.googlequicksearchbox com.google.android.as \
com.google.android.apps.bard com.android.vending \
com.google.android.inputmethod.latin"   # Gemini; Play Store (Aurora replaces it); Gboard (Fossify Keyboard replaces it)
# D5 (full list, 2026-11-18): setup-wizard nag, RSU/OMA-DM carrier agents, ad/ML telemetry, Device Health, AR, print,
# debug/dev toys, Moto diagnostics/enterprise, plus what carrier=retus turns ON (Ignite installer, IQI metrics, inmobi,
# Aura OOBE, Amazon app manager). Only runs after setup is complete (setupwizard is disabled, not the controller).
DECLUTTER_EXTRA="com.google.android.setupwizard com.google.android.partnersetup com.motorola.setup \
com.motorola.setupwizard.devicesetup com.motorola.setupwizard.phoneservice com.motorola.tracfone.rsu com.mediatek.rsu.tfn \
com.motorola.omadm.service com.motorola.omadm.att com.motorola.omadm.vzw com.motorola.ccc.notification \
com.google.android.adservices.api com.google.android.federatedcompute com.google.android.ondevicepersonalization.services \
com.google.android.apps.turbo com.google.android.apps.safetyhub com.google.ar.core com.google.android.gms.location.history \
com.android.printspooler com.android.bips com.android.traceur com.android.egg com.android.dreams.basic \
com.android.hotwordenrollment.okgoogle com.android.hotwordenrollment.xgoogle \
com.motorola.bug2go com.motorola.motocare com.motorola.appforecast com.motorola.iotservice com.motorola.lifetimedata \
com.motorola.enterprise.adapter.service com.motorola.enterprise.service \
com.dti.motorola com.motorola.iqimotmetrics com.inmobi.weather com.aura.oobe.motorola com.amazon.appmanager"
# Firmware-protected preloads: `pm disable` says "package is non-disable" (/system_ext/etc/nondisable, /product/etc/nondisable).
# PackageManagerService.setApplicationEnabledSetting via `service call package 90` (root) bypasses that shell-side list
# and survives reboot (proven on ccc.devicemanagement, phone #1). ccc.ota is additionally PMS-protected: it needs flag
# 0x80000000 + callingPackage "root" (P2 #65) and on tracfone phone #1 it was reset to enabled at boot.
# Transaction numbers 90 (set) / 91 (get) are for THIS framework build only (PROTECTED_BUILD).
PROTECTED_BUILD="W1WEOS36.48-22-3-3-4-2"
PROTECTED_PKGS="com.motorola.ccc.ota com.motorola.ccc.devicemanagement com.motorola.paks com.motorola.paks.notification \
com.motorola.installer com.tracfone.preload.accountservices com.amazon.appmanager.mdip com.motorola.android.fmradio \
com.google.android.inputmethod.latin"
LAUNCHER_PKG="com.motorola.launcher3"
# Quick Settings (pull-down) tiles, in order. Drops Wallet, GIF maker, device controls, Moto System update (ccc.ota),
# and tiles of decluttered apps (Ready For, Unplugged, Dolby, Feedback, Family Space, Wellbeing).
QS_TILES="wifi,cell,bt,dnd,airplane,rotation,flashlight,battery,night,hotspot,screenshot,screenrecord,volume,alarm,mictoggle,cameratoggle,qr_code_scanner"

S=""   # current serial
a()  { adb -s "$S" shell "$@" </dev/null 2>&1 | tr -d '\r'; }   # </dev/null: never eat a caller's while-read stdin
gp() { a getprop "$1"; }
hdr() { printf '\n== %s ==\n' "$*"; }
ok()   { printf '  [PASS] %s\n' "$*"; }
bad()  { printf '  [FAIL] %s\n' "$*"; }
warn() { printf '  [WARN] %s\n' "$*"; }

cmd_info() {
  hdr "identity / boot ($S)"
  for p in ro.product.model ro.product.device ro.serialno ro.boot.hardware.sku ro.carrier \
           ro.build.fingerprint ro.build.display.id ro.build.version.release ro.build.version.sdk \
           ro.build.version.security_patch gsm.version.baseband ro.boot.slot_suffix \
           ro.boot.flash.locked ro.boot.verifiedbootstate ro.boot.vbmeta.device_state \
           ro.oem_unlock_supported vendor.gsm.sim.slot.lock.device.lock.remain.count \
           ro.soc.manufacturer ro.soc.model ro.product.cpu.abi gsm.sim.state; do
    printf '  %-52s = [%s]\n' "$p" "$(gp "$p")"
  done
  hdr "users / device policy"
  a pm list users
  a dumpsys device_policy | grep -E "Device Owner|Profile Owner|Enabled Device Admins|Pending System Update" || true
  printf '  sidemdm app present: %s\n' "$(a pm list packages | grep -c "$SIDEMDM_PKG" || true)"
  hdr "hardware"
  a cat /proc/meminfo | head -2
  a df -h /data | tail -1
  a wm size; a wm density
  printf '  cpus: %s\n' "$(a nproc)"
  hdr "battery"
  a dumpsys battery | grep -E "^  (level|status|health|temperature|AC powered|USB powered):"
  hdr "network"
  a ip -4 addr show wlan0 | grep inet || echo "  wlan0: no IPv4"
  printf '  google accounts: %s\n' "$(a dumpsys account | grep -m1 'Accounts:')"
}

cmd_check() {
  hdr "BL gate 1: identity via adb ($S)"
  local model dev sku build patch bb slot locked vbs oem simlock
  model=$(gp ro.product.model); dev=$(gp ro.product.device); sku=$(gp ro.boot.hardware.sku)
  build=$(gp ro.build.display.id); patch=$(gp ro.build.version.security_patch)
  bb=$(gp gsm.version.baseband); slot=$(gp ro.boot.slot_suffix)
  locked=$(gp ro.boot.flash.locked); vbs=$(gp ro.boot.verifiedbootstate)
  oem=$(gp ro.oem_unlock_supported); simlock=$(gp vendor.gsm.sim.slot.lock.device.lock.remain.count)
  printf '  model=%s device=%s sku=%s\n  build=%s patch=%s slot=%s\n  baseband=%s\n  flash.locked=%s verifiedboot=%s oem_unlock_supported=[%s] simlock_remain=%s\n' \
    "$model" "$dev" "$sku" "$build" "$patch" "$slot" "$bb" "$locked" "$vbs" "$oem" "$simlock"

  local bl=1
  hdr "verdict"
  if [[ "$dev" == "$EXP_DEVICE" && "$sku" == "$EXP_SKU" ]]; then ok "model/SKU $dev + $sku"
  else bad "model/SKU mismatch ($dev/$sku) -> STOP, apply no patch"; bl=0; fi

  if [[ -n "$patch" && ! "$patch" > "$PATCH_MAX" ]]; then ok "security patch $patch <= $PATCH_MAX (in window; one OTA closes it)"
  else bad "security patch $patch > $PATCH_MAX -> not unlockable, don't try"; bl=0; fi

  if [[ -z "$oem" ]]; then ok "oem_unlock_supported empty -> lk-patch route only (no official token)"
  else warn "oem_unlock_supported=[$oem] -> official route may exist"; fi

  if [[ "$locked" == "1" && "$vbs" == "green" ]]; then ok "flash.locked=1 + green -> untouched starting point"
  elif [[ "$locked" == "0" || "$vbs" == "orange" ]]; then warn "already unlocked (locked=$locked, $vbs) -> no need to unlock"
  else warn "unexpected boot state locked=$locked vbs=$vbs"; fi

  [[ "$slot" == "_a" ]] && ok "slot _a" || warn "slot is $slot (modem doc expects a)"

  if [[ "$build" == *"$MODEM_BUILD"* && "$bb" == "$MODEM_BASEBAND" ]]; then ok "modem: build+baseband match verified-live $MODEM_BUILD (vegas-freedom)"
  else warn "modem: UNVERIFIED (build $build; verified only on $MODEM_BUILD + $MODEM_BASEBAND). Do not flash modem without full-image check (209715200 bytes + stock SHA256)."; fi

  if (( bl )); then echo "  => BL: unlockable IF you have stock lk.img for build $build (Valhalla needs it next to the script). Confirm with Valhalla 'Check Device'."
  else echo "  => BL: NOT feasible on this phone."; fi
}

cmd_fastboot() {
  hdr "BL gate 2: fastboot getvar ($S) — rebooting to bootloader, no flashing"
  adb -s "$S" reboot bootloader
  for _ in $(seq 1 60); do fastboot devices | grep -q "^$S" && break; sleep 1; done
  fastboot devices | grep -q "^$S" || { bad "device did not appear in fastboot"; return 1; }
  local v out
  for v in product sku securestate current-slot partition-size:md1img_a; do
    out=$(fastboot -s "$S" getvar "$v" 2>&1 | grep -m1 "^$v:" || true)
    printf '  %s\n' "${out:-$v: <none>}"
  done
  local prod sku ss slot
  prod=$(fastboot -s "$S" getvar product 2>&1 | sed -n 's/^product: //p')
  sku=$(fastboot -s "$S" getvar sku 2>&1 | sed -n 's/^sku: //p')
  ss=$(fastboot -s "$S" getvar securestate 2>&1 | sed -n 's/^securestate: //p')
  slot=$(fastboot -s "$S" getvar current-slot 2>&1 | sed -n 's/^current-slot: //p')
  [[ "$prod" == "$EXP_FB_PRODUCT" ]] && ok "product=$prod" || bad "product=$prod (want $EXP_FB_PRODUCT)"
  [[ "$sku" == "$EXP_SKU" ]] && ok "sku=$sku" || bad "sku=$sku (want $EXP_SKU)"
  case "$ss" in
    flashing_unlocked) ok "securestate=flashing_unlocked (modem precondition met)";;
    locked|oem_locked) ok "securestate=$ss (still locked; must become flashing_unlocked before modem flash)";;
    *) warn "securestate=$ss";;
  esac
  [[ "$slot" == "a" ]] && ok "current-slot=a" || warn "current-slot=$slot (modem doc expects a)"
  echo "  rebooting back to Android..."
  fastboot -s "$S" reboot >/dev/null 2>&1
  adb -s "$S" wait-for-device
  for _ in $(seq 1 90); do [[ "$(gp sys.boot_completed)" == "1" ]] && break; sleep 1; done
  echo "  boot_completed=$(gp sys.boot_completed)"
}

ota_uid() { a dumpsys package "$OTA_PKG" | grep -m1 -oE 'appId=[0-9]+' | cut -d= -f2; }

cmd_ota_status() {
  hdr "OTA status ($S)"
  a pm list packages | grep -iE 'ota|update|ccc' || true
  printf '  installed for user 0: %s\n' "$(a pm list packages "$OTA_PKG" | grep -c "$OTA_PKG" || true)"
  printf '  disabled list: %s\n' "$(a pm list packages -d | grep -i "$OTA_PKG" || echo none)"
  printf '  dumpsys: %s\n' "$(a dumpsys package "$OTA_PKG" | grep -m1 -oE 'enabled=[0-9]+ .*suspended=[a-z]+|suspended=[a-z]+' || echo '?')"
  printf '  appops RUN_ANY_IN_BACKGROUND: %s\n' "$(a cmd appops get "$OTA_PKG" RUN_ANY_IN_BACKGROUND)"
  printf '  netpolicy restrict-background blacklist: %s (uid %s)\n' "$(a cmd netpolicy list restrict-background-blacklist)" "$(ota_uid)"
  printf '  global ota_disable_automatic_update = %s\n' "$(a settings get global ota_disable_automatic_update)"
  printf '  firewall chain3: %s / %s\n' "$(a cmd connectivity get-chain3-enabled)" "$(a cmd connectivity get-package-networking-enabled "$OTA_PKG")"
}

# Standard init step: remove the OTA app for user 0 (pm uninstall -k --user 0; system partition untouched,
# restore with ota-on) + global auto-update flag. If the uninstall is refused, fall back to the soft layers.
cmd_ota_off() {
  hdr "OTA off ($S)"
  echo "  1) settings put global ota_disable_automatic_update 1  (= Developer options > Automatic system updates OFF)"
  a settings put global ota_disable_automatic_update 1 || true
  if a pm list packages "$OTA_PKG" | grep -q "$OTA_PKG"; then
    echo "  2) pm uninstall -k --user 0 $OTA_PKG"
    a pm uninstall -k --user 0 "$OTA_PKG" | sed 's/^/     /' || true
  else
    echo "  2) $OTA_PKG already removed for user 0"
  fi
  if a pm list packages "$OTA_PKG" | grep -q "$OTA_PKG"; then
    local uid; uid=$(ota_uid)
    echo "  uninstall refused -> fallback layers"
    a pm disable-user --user 0 "$OTA_PKG" | sed 's/^/     /' || true
    a cmd appops set "$OTA_PKG" RUN_ANY_IN_BACKGROUND ignore || true
    [[ -n "$uid" ]] && a cmd netpolicy add restrict-background-blacklist "$uid" || true
    echo "  network firewall: FIREWALL_CHAIN_OEM_DENY_3 deny for $OTA_PKG (all networks; RESETS ON REBOOT -> re-run ota-off after boot)"
    a cmd connectivity set-chain3-enabled true || true
    a cmd connectivity set-package-networking-enabled false "$OTA_PKG" | sed 's/^/     /' || true
  fi
  hdr "verify"
  if a pm list packages "$OTA_PKG" | grep -q "$OTA_PKG"; then
    warn "$OTA_PKG still installed for user 0 (firmware: 'package is non-disable'); fallback layers applied"
    [[ "$(a cmd appops get "$OTA_PKG" RUN_ANY_IN_BACKGROUND)" == *ignore* ]] && ok "background run blocked (persists)" || bad "appops not set"
    [[ "$(a cmd connectivity get-chain3-enabled)" == *enabled* && "$(a cmd connectivity get-package-networking-enabled "$OTA_PKG")" == *deny* ]] \
      && ok "network denied on all networks (until reboot)" || bad "network firewall not active"
  else ok "$OTA_PKG removed for user 0"; fi
  [[ "$(a settings get global ota_disable_automatic_update)" == "1" ]] && ok "ota_disable_automatic_update=1" || bad "global setting not written"
  echo "  Manual: Settings > search 'update' > Smart updates OFF (if still present). Keep phone off WAN Wi-Fi."
}

# Alias kept for compatibility: ota-remove == ota-off now.
cmd_ota_remove() { cmd_ota_off; }

# After BL unlock + root: the real disable (pm disable + iptables DROP on the OTA uid, v4+v6).
# Requires `su`. The iptables rules don't survive reboot on their own — install a KernelSU boot
# module to replay them (see docs/unlock-root-runbook.md), or re-run this after each boot.
cmd_ota_off_root() {
  hdr "OTA off with root ($S)"
  if [[ "$(a su -c id 2>&1)" != *"uid=0"* ]]; then bad "no root (su -c id failed) -> use ota-off"; return 1; fi
  a su -c "pm disable-user --user 0 $OTA_PKG" | sed 's/^/     /' || true
  a su -c "pm disable --user 0 $OTA_PKG" | sed 's/^/     /' || true
  a settings put global ota_disable_automatic_update 1 || true
  local uid; uid=$(ota_uid)
  if [[ -n "$uid" ]]; then
    echo "  iptables DROP for uid $uid (and 10$uid work-profile uid if present), IPv4 + IPv6"
    for u in "$uid" "10$uid"; do
      a su -c "iptables  -I OUTPUT -m owner --uid-owner $u -j DROP" || true
      a su -c "ip6tables -I OUTPUT -m owner --uid-owner $u -j DROP" || true
    done
  fi
  hdr "verify"
  a dumpsys package "$OTA_PKG" | grep -qE 'enabled=(2|3)' && ok "$OTA_PKG disabled (enabled=2/3)" \
    || bad "$OTA_PKG still enabled: $(a dumpsys package "$OTA_PKG" | grep -m1 -oE 'enabled=[0-9]+')"
  a su -c "iptables -S OUTPUT" | grep -q "uid-owner $uid" && ok "iptables DROP active (replay on boot via KSU module)" || warn "iptables rule not found"
  a pm list packages -d | grep -q "$OTA_PKG" && ok "in disabled list" || warn "not in disabled list"
}

cmd_ota_on() {
  hdr "OTA on ($S)"
  local uid
  a cmd package install-existing --user 0 "$OTA_PKG" || true
  uid=$(ota_uid)
  a pm enable --user 0 "$OTA_PKG" || true
  a pm unsuspend --user 0 "$OTA_PKG" || true
  a cmd appops set "$OTA_PKG" RUN_ANY_IN_BACKGROUND allow || true
  [[ -n "$uid" ]] && a cmd netpolicy remove restrict-background-blacklist "$uid" || true
  a cmd connectivity set-package-networking-enabled true "$OTA_PKG" || true
  if [[ "$(a su -c id 2>&1)" == *"uid=0"* && -n "$uid" ]]; then
    for u in "$uid" "10$uid"; do
      a su -c "iptables  -D OUTPUT -m owner --uid-owner $u -j DROP" 2>/dev/null || true
      a su -c "ip6tables -D OUTPUT -m owner --uid-owner $u -j DROP" 2>/dev/null || true
    done
  fi
  a settings put global ota_disable_automatic_update 0 || true
  cmd_ota_status
}

cmd_rm_sidemdm() {
  hdr "uninstall sidemdm leftover ($S)"
  if a pm list packages | grep -q "$SIDEMDM_PKG"; then adb -s "$S" uninstall "$SIDEMDM_PKG"; else echo "  not installed"; fi
}

# Silence every audio stream (rack phones must be quiet). cmd media_session is the portable
# path on this build (`media` binary is gone; `cmd audio` has no volume verb). Streams:
# 1=SYSTEM 2=RING 3=MUSIC 4=ALARM 5=NOTIFICATION. Idempotent.
# Every stream to its own minimum. Some streams (VOICE_CALL 0, ALARM 4, BT_SCO 6, ACCESSIBILITY 10) have
# min 1, and "--set 0" is silently rejected for them, so read the [min..max] range and set the min.
cmd_mute() {
  local s r min
  for s in 0 1 2 3 4 5 6 8 9 10 11; do
    r=$(a cmd media_session volume --stream "$s" --get 2>/dev/null | grep -oE 'range \[[0-9]+' | grep -oE '[0-9]+$' || true)
    min=${r:-0}
    a cmd media_session volume --stream "$s" --set "$min" >/dev/null 2>&1 || true
  done
  a cmd audio set-ringer-mode SILENT >/dev/null 2>&1 || true
}
mute_state() {   # "s0=1 s1=0 ..." current volume per stream
  local s; for s in 0 1 2 3 4 5 6 8 9 10 11; do
    printf 's%s=%s ' "$s" "$(a cmd media_session volume --stream "$s" --get 2>/dev/null | grep -oE 'volume is [0-9]+' | grep -oE '[0-9]+$')"
  done
}
# Hash the first N bytes of md1img_a/_b (N = size of the patched image) and compare with the
# vegas-freedom verified-live patched hash.
MODEM_PATCHED_SHA="f6bd718ffb5c734c"; MODEM_PATCHED_LEN=76088448
modem_state() {
  local x h out=""
  for x in a b; do
    # needs root adbd (ksud --enable-adbd); on an unrooted phone this just reads "stock/other"
    h=$(a "head -c $MODEM_PATCHED_LEN /dev/block/by-name/md1img_$x 2>/dev/null | sha256sum" | cut -c1-16)
    [[ "$h" == "$MODEM_PATCHED_SHA" ]] && out+="${x}=unlocked " || out+="${x}=stock/other "
  done
  echo "${out% }"
}

# Animations off (= Developer options x0 / Accessibility "Remove animations"): faster, more deterministic UI automation.
cmd_no_anim() {
  local k; for k in window_animation_scale transition_animation_scale animator_duration_scale; do
    a settings put global "$k" 0 >/dev/null 2>&1 || true
  done
}

# No internet: Wi-Fi off + mobile data off + Bluetooth off (a foreign SIM can otherwise bring data up -> OTA risk).
cmd_offline() {
  a svc wifi disable >/dev/null 2>&1 || true
  a svc data disable >/dev/null 2>&1 || true
  a svc bluetooth disable >/dev/null 2>&1 || true
  a settings put global mobile_data 0 >/dev/null 2>&1 || true
}

# Keep screen awake for interactive automation + force Always-On Display off (burn-in safety).
cmd_wake() {
  hdr "wake ($S)"
  a svc power stayon true
  a settings put system screen_off_timeout 2147483647 >/dev/null 2>&1 || true
  a settings put secure doze_always_on 0 >/dev/null 2>&1 || true        # AOSP/GMS AOD off
  a settings put secure aod_enabled 0 >/dev/null 2>&1 || true           # some Moto builds
  a settings put system screen_brightness_mode 0 >/dev/null 2>&1 || true # manual
  a settings put system screen_brightness 1 >/dev/null 2>&1 || true      # minimum (burn-in/power)
  a settings put system accelerometer_rotation 0 >/dev/null 2>&1 || true # portrait lock: UI automation
  a settings put system user_rotation 0 >/dev/null 2>&1 || true          #   assumes the 1080-wide layout
  cmd_mute                                                              # all streams muted
  cmd_no_anim                                                           # animations off: snappier UI automation
  a input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true
  a wm dismiss-keyguard >/dev/null 2>&1 || true
  ok "screen awake, AOD off, brightness min, muted, animations off (doze_always_on=$(a settings get secure doze_always_on | tr -d '\r'))"
}

# Rack-safe idle: no stay-on, AOD off, short timeout, screen off. Use before leaving phones on the rack.
cmd_park() {
  hdr "park ($S)"
  a svc power stayon false
  a settings put secure doze_always_on 0 >/dev/null 2>&1 || true
  a settings put secure aod_enabled 0 >/dev/null 2>&1 || true
  a settings put system screen_brightness_mode 0 >/dev/null 2>&1 || true
  a settings put system screen_brightness 1 >/dev/null 2>&1 || true
  a settings put system screen_off_timeout 30000 >/dev/null 2>&1 || true
  cmd_mute                                                              # all streams muted
  cmd_offline
  # turn the screen off if it is currently on (KEYCODE_SLEEP is a no-op when already off)
  a input keyevent KEYCODE_SLEEP >/dev/null 2>&1 || true
  sleep 1
  local scr; scr=$(a dumpsys power | grep -oE 'mWakefulness=[A-Za-z]+' | head -1)
  ok "parked: stayon off, AOD off, 30s timeout, muted, offline, $scr (rack-safe)"
}

# Remove the sidemdm work profile. sidemdm makes an ORG-OWNED managed profile, so pm remove-user and
# dpm remove-active-admin are both refused (even as root). Only the DPC's own wipeData works -> we drive
# its "Remove Work Profile" button via UI automation (scripts/uia.py). Needs root to launch it in user N.
cmd_rm_workprofile() {
  hdr "remove work profile ($S)"
  local wp; wp=$(a pm list users | grep -i "Work profile" | grep -oE 'UserInfo\{[0-9]+' | grep -oE '[0-9]+' | head -1)
  if [[ -z "$wp" ]]; then ok "no work profile present"; return 0; fi
  echo "  work profile = user $wp (org-owned); driving sidemdm Remove Work Profile via UI"
  [[ "$(a su -c id 2>&1)" == *"uid=0"* ]] || { bad "needs root to launch the DPC in user $wp — run scripts/reroot.sh first"; return 1; }
  a svc power stayon true >/dev/null 2>&1 || true
  a su -c "am start --user $wp -n $SIDEMDM_PKG/.MainActivity" >/dev/null 2>&1; sleep 2
  local U="$ROOT/.venv/bin/python $ROOT/scripts/uia.py -s $S"
  $U tap "Remove Work Profile" >/dev/null 2>&1 || true; sleep 2   # main button
  $U tap "Continue"            >/dev/null 2>&1 || true; sleep 2   # dialog 1
  $U tap "Remove Work Profile" >/dev/null 2>&1 || true; sleep 4   # dialog 2 (final)
  a pm list users | grep -qi "Work profile" && { warn "work profile still present (check screen)"; return 1; } || ok "work profile removed"
}

# Debloat: uninstall BLOAT_PKGS for user 0 (reversible with install-existing). Review the list first.
cmd_debloat() {
  hdr "debloat ($S)"
  for p in $BLOAT_PKGS; do
    a pm list packages | grep -qx "package:$p" || { echo "  -    $p (absent)"; continue; }
    local out; out=$(a pm uninstall -k --user 0 "$p")
    # a() reports tr's exit status, so judge by the result: is the package still installed for user 0?
    if a pm list packages | grep -qx "package:$p"; then
      echo "  KEEP $p (refused: ${out:-no output} — protected priv-app, or re-provisioned at boot)"
    else echo "  rm   $p"; fi
  done
  echo "  restore one: adb -s $S shell cmd package install-existing --user 0 <pkg>"
}

# Install the basic replacement apps (SMS, files, browser, F-Droid, Aurora) and make them the defaults.
# Run BEFORE declutter so SMS never goes without a handler.
cmd_apps() {
  hdr "apps ($S)"
  local line f pkg want got
  while IFS='|' read -r f pkg want; do
    [[ -n "$f" ]] || continue
    if a pm list packages | grep -qx "package:$pkg"; then echo "  ok   $pkg (installed)"; continue; fi
    [[ -f "$ROOT/tools/apps/$f" ]] || { bad "missing tools/apps/$f (see tools/apps/README.md)"; continue; }
    got=$(shasum -a 256 "$ROOT/tools/apps/$f" | awk '{print $1}')
    [[ "$got" == "$want" ]] || { bad "$f sha256 mismatch ($got) — not installing"; continue; }
    adb -s "$S" install -r "$ROOT/tools/apps/$f" </dev/null >/dev/null 2>&1 && a pm list packages | grep -qx "package:$pkg" \
      && echo "  inst $pkg" || bad "install failed: $pkg"
  done <<<"$APPS"
  a cmd role add-role-holder android.app.role.SMS org.fossify.messages 0 >/dev/null 2>&1 || true
  a cmd role add-role-holder android.app.role.BROWSER org.mozilla.firefox 0 >/dev/null 2>&1 || true
  # keyboard: enable + select Fossify Keyboard (must happen before declutter disables Gboard)
  local ime; ime=$(a ime list -a -s | grep '^org.fossify.keyboard/' | head -1)
  if [[ -n "$ime" ]]; then a ime enable "$ime" >/dev/null; a ime set "$ime" >/dev/null; fi
  ok "default SMS: $(a cmd role get-role-holders android.app.role.SMS) · browser: $(a cmd role get-role-holders android.app.role.BROWSER) · keyboard: $(a settings get secure default_input_method)"
}

# Disable unused apps for user 0 (reversible: adb shell pm enable <pkg>). Frees RAM, removes their icons/widgets.
cmd_declutter() {
  hdr "declutter ($S)"
  local p n=0 k=0
  [[ "$(a settings get secure user_setup_complete)" == 1 ]] || { bad "setup not complete -- finish the setup wizard first"; return 1; }
  local ime; ime=$(a settings get secure default_input_method)
  for p in $DECLUTTER_CARRIER $DECLUTTER_MOTO $DECLUTTER_GOOGLE $DECLUTTER_EXTRA; do
    a pm list packages | grep -qx "package:$p" || { echo "  -    $p (absent)"; continue; }
    if a pm list packages -d | grep -qx "package:$p"; then echo "  ok   $p (already disabled)"; n=$((n+1)); continue; fi
    [[ "$ime" == "$p/"* ]] && { echo "  KEEP $p (current keyboard -- run apps first)"; k=$((k+1)); continue; }
    a pm clear --user 0 "$p" >/dev/null 2>&1 || true   # D8: drop its data first (frees storage, nothing here needs it)
    a pm disable-user --user 0 "$p" >/dev/null 2>&1 || true
    if a pm list packages -d | grep -qx "package:$p"; then echo "  off  $p"; n=$((n+1)); continue; fi
    # some preloads refuse disable-user but allow a user-0 uninstall (undo: cmd package install-existing <pkg>)
    a pm uninstall -k --user 0 "$p" >/dev/null 2>&1 || true
    if ! a pm list packages | grep -qx "package:$p"; then echo "  rm   $p (disable refused -> uninstalled for user 0)"; n=$((n+1))
    else echo "  KEEP $p (disable + uninstall refused)"; k=$((k+1)); fi
  done
  ok "disabled $n, refused $k (undo one: adb -s $S shell pm enable <pkg>)"
}

# Empty home screen: delete every desktop/hotseat/folder item and widget from the launcher DB, and stop the
# launcher adding icons for newly installed apps. Apps stay in the drawer. Needs root adb. A copy of the old DB
# is kept in logs/. The DB is edited on the Mac (sqlite3); this phone has no sqlite3.
cmd_home_clear() {
  hdr "home-clear ($S)"
  [[ "$(a id)" == *uid=0* ]] || { bad "needs root adb"; return 1; }
  command -v sqlite3 >/dev/null || { bad "sqlite3 not found on the Mac"; return 1; }
  local D="/data/data/$LAUNCHER_PKG" w; w=$(mktemp -d)
  local own; own=$(a stat -c %u:%g "$D")
  a am force-stop "$LAUNCHER_PKG"
  adb -s "$S" pull "$D/databases/launcher.db" "$w/launcher.db" >/dev/null || { bad "pull failed"; return 1; }
  cp "$w/launcher.db" "$LOGDIR/$S.launcher.db.$(date +%Y%m%d_%H%M%S).bak"
  local before; before=$(sqlite3 "$w/launcher.db" 'select count(*) from favorites;')
  sqlite3 "$w/launcher.db" 'delete from favorites;' || { bad "sqlite edit failed"; return 1; }
  adb -s "$S" push "$w/launcher.db" /data/local/tmp/launcher.db >/dev/null
  a "cp /data/local/tmp/launcher.db $D/databases/launcher.db && rm -f $D/databases/launcher.db-journal /data/local/tmp/launcher.db && chown $own $D/databases/launcher.db && chmod 660 $D/databases/launcher.db && restorecon $D/databases/launcher.db"
  # don't auto-add icons for apps installed later (AOSP Launcher3 key; harmless if this build ignores it)
  local P="$D/shared_prefs/com.android.launcher3.prefs.xml"
  a am force-stop "$LAUNCHER_PKG"
  a "grep -q pref_add_icon_to_home $P || sed -i 's#</map>#<boolean name=\"pref_add_icon_to_home\" value=\"false\" /></map>#' $P"
  a input keyevent KEYCODE_HOME >/dev/null
  rm -rf "$w"
  sleep 3
  ok "home screen cleared ($before items/widgets removed); backup in logs/"
}

# Black wallpaper (home + lock: lock falls back to the system wallpaper) + dark theme, for OLED power/burn-in.
# There's no shell API to set a wallpaper, so with root write a black PNG as the system wallpaper files and
# restart SystemUI to reload it (no reboot). `cmd wallpaper set-dim-amount 1` was tried and does not render black.
cmd_black() {
  hdr "black wallpaper + dark theme ($S)"
  [[ "$(a id)" == *uid=0* ]] || { bad "needs root adb"; return 1; }
  local sz w h png; sz=$(a wm size | grep -oE '[0-9]+x[0-9]+' | tail -1); w=${sz%x*}; h=${sz#*x}
  png=$(mktemp).png
  python3 -I - "$png" "${w:-1080}" "${h:-2400}" <<'PY'
import zlib, struct, sys
f, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
raw = (b"\x00" + b"\x00\x00\x00" * w) * h
ch = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
open(f, "wb").write(b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                    + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b""))
PY
  adb -s "$S" push "$png" /data/local/tmp/black.png >/dev/null; rm -f "$png"
  a 'D=/data/system/users/0; for f in wallpaper wallpaper_orig; do cp /data/local/tmp/black.png $D/$f && chown system:system $D/$f && chmod 600 $D/$f; done; restorecon $D/wallpaper $D/wallpaper_orig; rm -f $D/wallpaper_lock $D/wallpaper_lock_orig /data/local/tmp/black.png' >/dev/null 2>&1
  a cmd uimode night yes >/dev/null 2>&1 || true
  a pkill -f com.android.systemui >/dev/null 2>&1 || true
  sleep 6
  ok "black wallpaper ${w}x${h} installed, dark theme $(a cmd uimode night), SystemUI restarted (pid $(a pidof com.android.systemui))"
}

# Set the Quick Settings tile list (QS_TILES). Must go through SystemUI (cmd statusbar set-tiles): a plain
# `settings put secure sysui_qs_tiles` is overwritten by the running SystemUI at once.
cmd_qs() {
  hdr "quick settings tiles ($S)"
  a "cmd statusbar set-tiles '$QS_TILES'" >/dev/null; sleep 2
  ok "tiles: $(a settings get secure sysui_qs_tiles)"
}

# One-time root config for protected preloads (see PROTECTED_PKGS). Idempotent; re-run in any root session.
svc_state() { a service call package 91 s16 "$1" i32 0 | sed -n 's/.*Parcel([[:space:]]*00000000 \([0-9a-f]\{8\}\).*/\1/p' | sed 's/^0*//;s/^$/0/'; }   # 0 default, 3 disabled_user
cmd_protected() {
  hdr "protected: disable firmware-protected preloads via PackageManagerService ($S)"
  [[ "$(a id)" == *uid=0* ]] || { bad "needs root adb (scripts/reroot.sh)"; return 1; }
  [[ "$(gp ro.build.id)" == "$PROTECTED_BUILD" ]] || { bad "build $(gp ro.build.display.id) != $PROTECTED_BUILD: binder transaction numbers unverified"; return 1; }
  local ime p st r n=0 f=0; ime=$(a settings get secure default_input_method)
  for p in $PROTECTED_PKGS; do
    a pm list packages -u | grep -qx "package:$p" || { echo "  -    $p (absent)"; continue; }
    [[ "$ime" == "$p/"* ]] && { echo "  KEEP $p (current keyboard)"; continue; }
    st=$(a dumpsys package "$p" | grep -m1 -E '^ +User 0:' | grep -oE 'enabled=[0-9]+' | cut -d= -f2)
    [[ "$st" == 3 || "$st" == 2 ]] && { echo "  ok   $p (enabled=$st)"; n=$((n+1)); continue; }
    a pm clear --user 0 "$p" >/dev/null 2>&1 || true
    r=$(a service call package 90 s16 "$p" i32 3 i32 0 i32 0 s16 shell)
    if grep -q ffffffff <<<"$r"; then   # SecurityException ("Cannot disable a protected package") -> P2 #65 form
      a service call package 90 s16 "$p" i32 3 i32 -2147483648 i32 0 s16 root >/dev/null
    fi
    st=$(a dumpsys package "$p" | grep -m1 -E '^ +User 0:' | grep -oE 'enabled=[0-9]+' | cut -d= -f2)
    if [[ "$st" == 3 ]]; then echo "  off  $p"; n=$((n+1)); else echo "  FAIL $p (enabled=$st)"; f=$((f+1)); fi
  done
  # OTA belt and braces: no automatic updates, no background running, no background data
  a settings put global ota_disable_automatic_update 1
  a cmd appops set --user 0 "$OTA_PKG" RUN_IN_BACKGROUND ignore >/dev/null 2>&1 || true
  a cmd appops set --user 0 "$OTA_PKG" RUN_ANY_IN_BACKGROUND ignore >/dev/null 2>&1 || true
  a am force-stop "$OTA_PKG" >/dev/null 2>&1 || true
  ((f == 0)) && ok "protected disabled: $n (ota getter=$(svc_state $OTA_PKG); auto-update off, OTA appops ignore)" || { bad "$f failed"; return 1; }
}

# D4: no zRAM writeback to flash (flash wear; ~5 GB RAM free after declutter). Root (persist.* prop).
cmd_ram() {
  hdr "ram: zRAM writeback off ($S)"
  [[ "$(a id)" == *uid=0* ]] || { bad "needs root adb"; return 1; }
  a setprop persist.sys.zram_wb_enabled false
  ok "persist.sys.zram_wb_enabled=$(gp persist.sys.zram_wb_enabled) (moto_swap_supported=$(gp ro.config.moto_swap_supported); applies from next boot)"
}

# Moto Battery protection (com.motorola.actions -> BatteryService AdaptiveCharging -> Moto health HAL): charging stops at
# 80%. Works unrooted. The setting lives in actions' own prefs (UI only), exposed read-only at
# content://com.motorola.batteryconfiguration/config. BatteryService only binds it if actions was enabled at boot.
CHG_URI=content://com.motorola.batteryconfiguration/config
chg_upper() { a content query --uri "$CHG_URI" | grep -oE 'charging_upper_limit=-?[0-9]+' | cut -d= -f2; }
cmd_charge_protect() {
  hdr "charge-protect: Moto Battery protection 80% ($S)"
  local U="$ROOT/.venv/bin/python $ROOT/scripts/uia.py -s $S" was_disabled=0
  a pm list packages -d | grep -qx 'package:com.motorola.actions' && was_disabled=1
  a pm enable com.motorola.actions >/dev/null
  if [[ "$(chg_upper)" != 80 ]]; then
    a input keyevent KEYCODE_WAKEUP >/dev/null; a wm dismiss-keyguard >/dev/null; sleep 1   # parked phones sit on the lock screen
    a settings put system accelerometer_rotation 0 >/dev/null; a settings put system user_rotation 0 >/dev/null
    if ! a am start -n com.motorola.actions/.ui.androidsettings.battery.protection.BatteryProtectionActivity | grep -q Error; then sleep 3
    else   # fallback: through Settings > Battery (Settings caches injected tiles: restart it after enabling actions)
      a am force-stop com.android.settings >/dev/null
      a am start -a android.intent.action.POWER_USAGE_SUMMARY >/dev/null; sleep 3
      $U tap "=Battery protection" >/dev/null || { bad "no 'Battery protection' entry in Settings > Battery"; return 1; }
      sleep 2
    fi
    $U set "=Use Battery protection" on || { bad "could not switch on 'Use Battery protection'"; return 1; }
    sleep 1
    $U find "=Manual schedule" >/dev/null 2>&1 || { a input swipe 540 1700 540 900 300 >/dev/null; sleep 1; }   # below the fold?
    $U set "=Manual schedule" on || { bad "could not select 'Manual schedule'"; return 1; }   # Run time defaults to Always
    sleep 1
    $U find "Run time: Always" >/dev/null || warn "did not see 'Run time: Always' under Manual schedule -- check the screen"
    a input keyevent KEYCODE_HOME >/dev/null
  fi
  # The provider can still report -1 right after the UI toggle; on phones #3/#4 it read 80 after the next boot
  # (route_d verify checks mUpperLimit then). Poll briefly, then only warn.
  local i; for i in 1 2 3 4 5; do [[ "$(chg_upper)" == 80 ]] && break; sleep 2; done
  if [[ "$(chg_upper)" == 80 ]]; then ok "actions config: charging_upper_limit=80"
  else warn "charging_upper_limit=$(chg_upper) right after the toggle (often applies after reboot; verify checks mUpperLimit)"; fi
  sleep 3
  local st; st=$(a dumpsys battery | grep -oE 'mUpperLimit:-?[0-9]+')
  if [[ "$st" == mUpperLimit:80 ]]; then ok "BatteryService enforcing ($st); battery $(a cat /sys/class/power_supply/battery/status) at $(a cat /sys/class/power_supply/battery/capacity)%"
  else warn "BatteryService not bound yet ($st)$( ((was_disabled)) && echo ': actions was disabled at boot') -> REBOOT, then re-run to verify"; fi
}

# Full partition backup — ONLY if backups/ has no archive for this serial+build yet.
# Needs temp root (DirtyFrag+KernelSU). Dumps via vegas-freedom, then compresses into backups/.
cmd_backup() {
  hdr "backup ($S)"
  local build existing
  build=$(gp ro.build.display.id)
  existing=$(ls "$ROOT"/backups/"${S}_${build}"_stock_*.tar.zst "$ROOT"/backups/"${S}_${build}"_delta_*.tar.zst 2>/dev/null | head -1 || true)
  if [[ -n "$existing" ]]; then
    ok "archive already present for $S + $build -> skip dump"
    echo "  $existing"
    return 0
  fi
  local other
  other=$(ls "$ROOT"/backups/"${S}"_*_stock_*.tar.zst 2>/dev/null | head -1 || true)
  [[ -n "$other" ]] && warn "have an archive for $S but a DIFFERENT build: $(basename "$other") -> dumping current build $build"
  if [[ "$(a su -c id 2>&1)" != *"uid=0"* ]]; then
    bad "no root: temp-root first (DFRoot Run exploit), then re-run. See docs/unlock-root-runbook.md"
    return 1
  fi
  echo "  no archive for $S + $build -> running full dump (read-only, ~12.5 GB)"
  # Live partitions (NV config caches) change between dd and verify -> backup_partitions.py flags them.
  # That's a snapshot, not a bad read. Auto-recover ONLY these; anything else stays a hard failure.
  local LIVE_OK="nvcfg metadata frp"
  # One dump at a time across phones (route_d runs in parallel on the bench): two full dumps compete for USB/disk.
  local lock="$ROOT/logs/.backup.lock"
  until mkdir "$lock" 2>/dev/null; do
    [[ -f "$lock/pid" ]] && ! kill -0 "$(cat "$lock/pid")" 2>/dev/null && { rm -rf "$lock"; continue; }   # stale
    echo "  waiting for another phone's dump ($(cat "$lock/serial" 2>/dev/null))..."; sleep 30
  done
  echo $$ > "$lock/pid"; echo "$S" > "$lock/serial"
  # Explicit per-phone dump dir: "newest stock_* dir" is wrong when two phones dump at once.
  local dir; dir="$ROOT/vegas-freedom/backups/stock_$(date +%Y%m%d_%H%M%S)_$S"
  local rc=0; ANDROID_SERIAL="$S" "$ROOT/.venv/bin/python" "$ROOT/vegas-freedom/scripts/backup_partitions.py" "$dir" || rc=$?
  rm -rf "$lock"
  if [[ $rc -ne 0 && -f "$dir/FAILED" ]]; then
    local bad_parts; bad_parts=$(awk '{print $1}' "$dir/FAILED")
    local unexpected=""
    for p in $bad_parts; do grep -qw "$p" <<<"$LIVE_OK" || unexpected+=" $p"; done
    if [[ -n "$unexpected" ]]; then bad "non-live partition(s) failed:$unexpected — dump kept, not archived"; return 1; fi
    warn "live partition(s) failed verify (expected): $bad_parts — recording point-in-time snapshots"
    for p in $bad_parts; do
      adb -s "$S" exec-out "su -c 'dd if=/dev/block/by-name/$p bs=4M 2>/dev/null'" > "$dir/$p.img" 2>/dev/null || { bad "re-dump $p failed"; return 1; }
      local h; h=$(shasum -a 256 "$dir/$p.img" | awk '{print $1}')
      grep -qw "$p.img" "$dir/SHA256SUMS" || echo "$h  $p.img" >> "$dir/SHA256SUMS"
    done
    { echo "Live partitions snapshotted after verify-fail (changing during read): $bad_parts"; } >> "$dir/NOTES.txt"
    rm -f "$dir/FAILED"; rc=0
  fi
  [[ $rc -eq 0 ]] || { bad "dump failed"; return 1; }
  "$ROOT/scripts/archive_backup.sh" "$dir" || { bad "archive failed (dump dir kept)"; return 1; }
  ok "backup archived for $S + $build"
}

# Write/refresh devices/<serial>.md. Only the block between AUTO markers is regenerated;
# the manual sections (label, timeline, notes) are kept.
cmd_record() {
  local f="$ROOT/devices/$S.md" tmp; tmp=$(mktemp)
  mkdir -p "$ROOT/devices"
  local dev sku build patch bb locked vbs oem users owners side otapkg otadis otaapp otaglob uid otanet bl modem
  dev=$(gp ro.product.device); sku=$(gp ro.boot.hardware.sku); build=$(gp ro.build.display.id)
  patch=$(gp ro.build.version.security_patch); bb=$(gp gsm.version.baseband)
  locked=$(gp ro.boot.flash.locked); vbs=$(gp ro.boot.verifiedbootstate); oem=$(gp ro.oem_unlock_supported)
  users=$(a pm list users | grep -oE 'UserInfo\{[^}]*\}' | tr '\n' ' ')
  owners=$(a dumpsys device_policy | grep -E 'Device Owner:|Profile Owner' | sed 's/^ *//' | tr '\n' ' ')
  side=$(a pm list packages "$SIDEMDM_PKG" | grep -c "$SIDEMDM_PKG" || true)
  otapkg=$(a pm list packages "$OTA_PKG" | grep -c "$OTA_PKG" || true)
  otadis=$(a pm list packages -d "$OTA_PKG" | grep -c "$OTA_PKG" || true)
  otaapp=$(a cmd appops get "$OTA_PKG" RUN_ANY_IN_BACKGROUND | sed 's/.*: //')
  otaglob=$(a settings get global ota_disable_automatic_update)
  uid=$(ota_uid)
  [[ -n "$uid" && "$(a cmd netpolicy list restrict-background-blacklist)" == *"$uid"* ]] && otanet=yes || otanet=no
  if [[ "$dev" == "$EXP_DEVICE" && "$sku" == "$EXP_SKU" && -n "$patch" && ! "$patch" > "$PATCH_MAX" ]]; then
    bl="feasible (needs stock lk.img for $build; confirm with Valhalla Check Device)"
  else bl="NOT feasible (model/SKU or patch outside window)"; fi
  [[ "$locked" == "0" || "$vbs" == "orange" ]] && bl="already unlocked"
  [[ "$locked" == "1" && "$vbs" == "green" && "$(gp ro.carrier)" == "retus" ]] && bl="route D: stays locked (patched retail lk, carrier=retus)"
  [[ "$build" == *"$MODEM_BUILD"* && "$bb" == "$MODEM_BASEBAND" ]] && modem="build verified-live (-4-2); live slots: $(modem_state)" || modem="UNVERIFIED (full-image check first)"
  if [[ "$(gp ro.carrier)" == "retus" ]]; then   # route D: modem readback needs root -> report the SIM test instead
    modem="route D (md1img-unlock.img, verified at flash by route_d.sh); SIM now: $(gp gsm.sim.state) $(gp gsm.sim.operator.alpha)"
  fi
  {
    echo "<!-- AUTO:BEGIN — regenerated by scripts/phone.sh record; edit outside this block -->"
    echo "## Snapshot ($(date '+%F %T'))"
    echo
    echo "| Field | Value |"
    echo "|---|---|"
    echo "| Model / device / SKU | $(gp ro.product.model) / $dev / $sku |"
    echo "| Carrier | $(gp ro.carrier) (SIM lock tries left: $(gp vendor.gsm.sim.slot.lock.device.lock.remain.count); SIM: $(gp gsm.sim.state)) |"
    echo "| Build | \`$build\` |"
    echo "| Security patch | $patch |"
    echo "| Baseband | \`$bb\` |"
    echo "| Slot | $(gp ro.boot.slot_suffix) |"
    echo "| Bootloader | flash.locked=$locked, verifiedboot=$vbs, oem_unlock_supported=[$oem] |"
    echo "| Users | $users |"
    echo "| Device/profile owners | ${owners:-none} |"
    echo "| sidemdm app installed | $side |"
    echo "| OTA app installed / disabled | $otapkg / $otadis |"
    echo "| OTA appops bg / netpolicy / global flag | $otaapp / $otanet / $otaglob |"
    echo "| OTA network firewall (chain3, resets on reboot) | $(a cmd connectivity get-package-networking-enabled "$OTA_PKG" | sed 's/.*://') |"
    echo "| BL verdict | $bl |"
    echo "| Modem patch | $modem |"
    echo "| RAM / storage | $(a cat /proc/meminfo | awk '/MemTotal/{printf "%.1f GB", $2/1048576}') / $(a df -h /data | awk 'NR==2{print $3" used of "$2}') |"
    echo "| Battery | $(a dumpsys battery | awk '/^  level:/{l=$2} /^  temperature:/{t=$2/10} END{print l"%, "t"°C"}') |"
    echo "| Root / KSU modules | $(a id | grep -oE 'uid=[0-9]+') / $( [[ "$(a id)" == *uid=0* ]] && a ls /data/adb/modules 2>/dev/null | tr '\n' ' ' || echo 'n/a (unrooted)') |"
    echo "| update_engine / OTA hosts lines | $(gp init.svc.update_engine) / $(a "grep -cE 'motorola|svcmot' /system/etc/hosts") |"
    echo "| Charging (Moto Battery protection) | $(a cat /sys/class/power_supply/battery/status), $(a dumpsys battery | grep -oE 'mUpperLimit:-?[0-9]+|mChargingDisabled:[a-z]+' | tr '\n' ' ') |"
    echo "| Volumes (stream=level) | $(mute_state) |"
    echo "| Mobile data / Wi-Fi on | $(a settings get global mobile_data) / $(a settings get global wifi_on) |"
    echo "| Wi-Fi IPv4 | $(a ip -4 addr show wlan0 | awk '/inet /{print $2}' | head -1) |"
    echo "<!-- AUTO:END -->"
  } > "$tmp"
  if [[ ! -f "$f" ]]; then
    sed "s/{{SERIAL}}/$S/g" "$ROOT/devices/_template.md" > "$f"
  fi
  python3 -I - "$f" "$tmp" <<'PY'
import re, sys
f, t = sys.argv[1], sys.argv[2]
doc, block = open(f, encoding="utf-8").read(), open(t, encoding="utf-8").read().rstrip("\n")
pat = re.compile(r"<!-- AUTO:BEGIN.*?<!-- AUTO:END -->", re.S)
doc = pat.sub(lambda m: block, doc) if pat.search(doc) else doc.rstrip("\n") + "\n\n" + block + "\n"
open(f, "w", encoding="utf-8").write(doc)
PY
  rm -f "$tmp"
  echo "  wrote devices/$S.md"
}

cmd_full() { cmd_info; cmd_check; cmd_ota_off; cmd_fastboot; cmd_record; }

usage() { sed -n '2,37p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

main() {
  local cmd="${1:-}"; local target="${2:-}"
  case "$cmd" in info|check|fastboot|ota-off|ota-off-root|ota-remove|ota-status|ota-on|backup|wake|park|offline|mute|rm-workprofile|debloat|apps|declutter|home-clear|black|no-anim|qs|charge-protect|protected|ram|rm-sidemdm|record|full) ;; *) usage;; esac
  local serials=()
  if [[ "$target" == "all" ]]; then
    while IFS= read -r l; do serials+=("$l"); done < <(adb devices | awk 'NR>1 && $2=="device"{print $1}')
  elif [[ -n "$target" ]]; then
    serials=("$target")
  else
    while IFS= read -r l; do serials+=("$l"); done < <(adb devices | awk 'NR>1 && $2=="device"{print $1}')
    (( ${#serials[@]} == 1 )) || { echo "Need exactly one device (found ${#serials[@]}); pass a serial or 'all'." >&2; exit 1; }
  fi
  (( ${#serials[@]} )) || { echo "No adb devices." >&2; exit 1; }
  local fn="cmd_${cmd//-/_}"
  local rc=0
  for S in "${serials[@]}"; do
    { printf '\n######## %s  %s  %s ########\n' "$cmd" "$S" "$(date '+%F %T')"; "$fn"; } 2>&1 | tee -a "$LOGDIR/$S.log"
    # without this the exit status was tee's, so callers (route_d.sh: backup/protected || die) never saw a failure
    (( PIPESTATUS[0] == 0 )) || rc=1
  done
  return $rc
}

main "$@"
