#!/system/bin/sh
# Runs as root at late_start (KernelSU). Re-applies the OTA egress block that reboots clear.
until [ "$(getprop sys.boot_completed)" = "1" ]; do sleep 2; done

# 1) Egress DROP for the Motorola OTA app (protected priv-app; pm cannot remove it).
P=com.motorola.ccc.ota
uid=$(stat -c %u "/data/data/$P" 2>/dev/null)
[ -n "$uid" ] || uid=$(dumpsys package "$P" | grep -m1 -oE 'appId=[0-9]+' | cut -d= -f2)
# -w waits for the xtables lock (netd holds it around late_start); -C first so reruns don't stack duplicates.
for u in "$uid" "10$uid"; do
  [ -n "$u" ] || continue
  for t in iptables ip6tables; do
    for try in 1 2 3 4 5; do
      $t -w -C OUTPUT -m owner --uid-owner "$u" -j DROP 2>/dev/null && break
      $t -w -I OUTPUT -m owner --uid-owner "$u" -j DROP 2>/dev/null && break
      sleep 2
    done
  done
done

# 2) Disable automatic system updates (settings-level).
settings put global ota_disable_automatic_update 1

# 3) Stop the A/B OTA apply daemon. It idles running from boot; with ccc.ota egress dropped and
#    auto-update off nothing feeds it a payload, but we stop it so it cannot apply one if triggered.
#    (A payload is only applied by update_engine; killing it blocks the apply stage outright.)
setprop ctl.stop update_engine 2>/dev/null

# 4) Hosts-based domain block (defense-in-depth). KernelSU v3.3.1 does not reliably overlay a
#    hand-registered module's system/, so bind-mount our hosts over /system/etc/hosts directly
#    (AdAway technique; works on ro /system, needs the source labeled system_file). Authoritative
#    farm-wide block is LAN DNS (AdGuard) — see docs/ota.md. No wildcards in hosts, so list is explicit.
HOSTS="$MODDIR/system/etc/hosts"
[ -n "$MODDIR" ] || HOSTS=/data/adb/modules/ota_block/system/etc/hosts
if [ -f "$HOSTS" ] && ! grep -q svcmot /system/etc/hosts 2>/dev/null; then
  chcon u:object_r:system_file:s0 "$HOSTS" 2>/dev/null
  mount -o bind "$HOSTS" /system/etc/hosts 2>/dev/null
fi
