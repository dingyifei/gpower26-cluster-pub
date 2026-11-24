#!/usr/bin/env bash
# Install the repo's KernelSU modules (ksu-modules/*) onto a rooted phone. They run at every boot.
#   scripts/install_modules.sh [serial]     (serial optional only when exactly one phone is attached)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/lib.sh"
S=$(pick_serial "${1:-}")
[[ "$(adb -s "$S" shell id | tr -d '\r')" == *uid=0* ]] || { echo "not root — run scripts/reroot.sh/permroot.sh first"; exit 1; }
# Retired modules: drop them from phones that still carry them (KernelSU deletes a module with a `remove` flag at next boot).
#   charge_limit (57-60% charge-off) -> replaced 2026-11-18 by Moto Battery protection 80% (phone.sh charge-protect)
for id in charge_limit; do
  if adb -s "$S" shell "[ -d /data/adb/modules/$id ]" 2>/dev/null; then
    adb -s "$S" shell "pkill -f '[m]odules/$id/monitor.sh'; touch /data/adb/modules/$id/remove; echo '0 0' > /proc/mtk_battery_cmd/current_cmd" || true
    echo "retired module: $id (stopped, flagged for removal at next boot, charging handed back to the system)"
  fi
done
for m in "$ROOT"/ksu-modules/*/; do
  id=$(basename "$m")
  tmp="/data/local/tmp/_mod_$id"
  dst="/data/adb/modules/$id"
  adb -s "$S" shell "rm -rf $tmp"                      # clean, so push can't nest into a leftover dir
  adb -s "$S" push "${m%/}" "$tmp" >/dev/null
  # adbd is root (ksud --enable-adbd), so plain shell commands run as root; no su -c quoting needed.
  adb -s "$S" shell "rm -rf $dst && mkdir -p $dst && cp -r $tmp/. $dst/ && chmod -R 755 $dst && rm -rf $tmp" \
    || { echo "FAILED to install module $id"; exit 1; }
  # stop an old copy of a long-running monitor before starting the new one
  # ('[m]' so the pattern does not match the sh running pkill itself)
  [ -f "$m/monitor.sh" ] && adb -s "$S" shell "pkill -f '[m]odules/$id/monitor.sh'" >/dev/null 2>&1 || true
  # start now (detached) so it applies without waiting for a reboot
  [ -f "$m/service.sh" ] && adb -s "$S" shell "setsid sh $dst/service.sh </dev/null >/dev/null 2>&1 &" >/dev/null 2>&1 || true
  # verify every file landed (incl. nested system/etc/hosts)
  want=$(cd "$m" && find . -type f | sort)
  have=$(adb -s "$S" shell "cd $dst && find . -type f | sort" | tr -d '\r')
  [[ "$want" == "$have" ]] || { echo "module $id file mismatch:"; diff <(echo "$want") <(echo "$have") || true; exit 1; }
  echo "installed module: $id ($(echo "$want" | wc -l | tr -d ' ') files)"
done
