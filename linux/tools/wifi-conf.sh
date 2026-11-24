#!/usr/bin/env bash
# Add (or replace) a Wi-Fi network for Debian on the phone (over SSH, Debian running): linux/tools/wifi-conf.sh <SSID>
# The passphrase is read from the terminal (not echoed), hashed with wpa_passphrase ON THE PHONE, and never stored
# in the repo. Other saved networks are kept; an entry with the same SSID is replaced. With Wi-Fi up (vegas-wifi
# active) the network goes in through wpa_cli and save_config, the same path an on-phone settings page uses;
# otherwise the conf file is edited and the network joins at the next boot. The conf keeps update_config=1 so wpa_cli
# can save. Prefer the USB address (default): a reconfigure (only when update_config had to be fixed) drops Wi-Fi.
set -Eeuo pipefail
SSID=${1:?SSID}; IP=${PHONE_IP:-172.16.42.1}
IFS= read -rsp "passphrase for '$SSID': " PSK; echo
SSH=(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@"$IP")
printf '%s\n%s\n' "$SSID" "$PSK" | "${SSH[@]}" 'set -e; IFS= read -r s; IFS= read -r p; umask 077; mkdir -p /etc/wpa_supplicant
  net=$(wpa_passphrase "$s" "$p") || { echo "wpa_passphrase refused the SSID/passphrase (8-63 chars?)" >&2; exit 1; }
  psk=$(sed -n "s/^[[:space:]]*psk=\([0-9a-f]\{64\}\)$/\1/p" <<<"$net")
  [ -n "$psk" ] || { echo "no hashed psk from wpa_passphrase" >&2; exit 1; }
  hex=$(printf %s "$s" | od -An -tx1 | tr -d " \n")
  f=/etc/wpa_supplicant/wpa_supplicant-wlan0.conf
  [ -s "$f" ] || printf "ctrl_interface=DIR=/run/wpa_supplicant GROUP=root\nupdate_config=1\n" > "$f"
  fixed=0; grep -qx "update_config=1" "$f" || { fixed=1
    if grep -q "^update_config=" "$f"; then sed -i "s/^update_config=.*/update_config=1/" "$f"; else sed -i "1a update_config=1" "$f"; fi; }
  if ! systemctl is-active -q vegas-wifi; then
    # drop blocks for this SSID (quoted or hex form), then append; SSID passed through ENVIRON (no awk escape processing)
    S="$s" H="$hex" awk "
      /^[[:space:]]*network=\\{/ { inb=1; blk=\$0 \"\\n\"; drop=0; next }
      inb { blk=blk \$0 \"\\n\"; l=\$0; sub(/^[[:space:]]+/, \"\", l)
            if (l == \"ssid=\\\"\" ENVIRON[\"S\"] \"\\\"\" || l == \"ssid=\" ENVIRON[\"H\"]) drop=1
            if (l ~ /^\\}/) { if (!drop) printf \"%s\", blk; else n++; inb=0 } ; next }
      { print }
      END { if (n) print \"replaced \" n \" saved block(s)\" > \"/dev/stderr\" }" "$f" > "$f.new"
    grep -v "^[[:space:]]*#psk=" <<<"$net" >> "$f.new"; mv "$f.new" "$f"
    echo "vegas-wifi not active: written to $f, joins at the next boot"; exit 0
  fi
  systemctl is-active -q wpa_supplicant@wlan0 || systemctl start wpa_supplicant@wlan0
  W="wpa_cli -i wlan0"
  up() { for i in $(seq 1 20); do $W ping 2>/dev/null | grep -q PONG && return 0; sleep 0.5; done; echo "wpa_supplicant not answering" >&2; exit 1; }
  up
  if [ "$fixed" = 1 ]; then $W reconfigure >/dev/null; up; fi   # the running supplicant must see update_config=1
  for id in $($W list_networks | awk "NR>1 {print \$1}"); do
    cur=$($W get_network "$id" ssid | tail -1)
    if [ "$cur" = "\"$s\"" ] || [ "$cur" = "$hex" ]; then $W remove_network "$id" >/dev/null; echo "replaced saved network $id"; fi
  done
  id=$($W add_network | tail -1); [[ "$id" =~ ^[0-9]+$ ]] || { echo "add_network failed: $id" >&2; exit 1; }
  ok() { [ "$($W "$@" | tail -1)" = OK ] || { echo "wpa_cli $1 failed" >&2; exit 1; }; }
  ok set_network "$id" ssid "$hex"; ok set_network "$id" psk "$psk"; ok enable_network "$id"; ok save_config
  echo "network $id saved to $f; wpa_supplicant joins it when in range"'
