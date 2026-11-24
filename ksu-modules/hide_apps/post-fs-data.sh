#!/system/bin/sh
# KernelSU post-fs-data: runs before system_server/PackageManager. Mounting an empty dir over an app's code dir
# makes PackageManager find no APK at boot, so it drops the package (its /data stays; removing the module and
# rebooting brings it back). Same bind-mount technique ota_block uses for /system/etc/hosts.
MODDIR="${0%/*}"
EMPTY="$MODDIR/empty"
chcon u:object_r:system_file:s0 "$EMPTY" 2>/dev/null
LOG="$MODDIR/last_run.log"; : > "$LOG"
while read -r d; do
  case "$d" in ''|\#*) continue;; esac
  [ -d "$d" ] || { echo "skip (missing) $d" >> "$LOG"; continue; }
  mount -o bind "$EMPTY" "$d" && echo "hid $d" >> "$LOG" || echo "FAIL $d" >> "$LOG"
done < "$MODDIR/hidden.list"
