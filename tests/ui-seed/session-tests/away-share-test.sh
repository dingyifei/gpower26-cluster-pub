#!/bin/bash
# VM only (orb -m vegas-deb sudo bash away-share-test.sh): Away survives the two sharing tools (designer, 24 Nov).
# In a throwaway netns + private mount namespace: Away on (ip6tables path), then vegas-usbshare on/off and
# vegas-hotspot run (hostapd stubbed to exit at once, so `run` goes through its full up + teardown), then checks
# that VEGAS-AWAY, its DROP rule and the INPUT jump are still there for IPv4 and IPv6, and that `status` says closed.
# networkctl/resolvectl/hostapd/udhcpd/iw are stubbed; /dev/wmtWifi and /run/systemd/network are private mounts.
set -u
O=/path/to/repo/linux/debian/overlay
SB=$O/usr/local/sbin
T=$(mktemp -d); trap 'ip netns del vas-phone 2>/dev/null; rm -rf $T' EXIT
ip netns del vas-phone 2>/dev/null; ip netns add vas-phone
PH="ip netns exec vas-phone"
$PH ip link set lo up
$PH ip link add wlan0 type dummy; $PH ip link add usb0 type dummy; $PH ip link set wlan0 up; $PH ip link set usb0 up
$PH ip addr add 10.77.0.1/24 dev wlan0
mkdir -p $T/stub $T/sr/etc/vegas $T/net
for c in networkctl resolvectl iw hostapd_cli; do printf '#!/bin/sh\nexit 0\n' > $T/stub/$c; done
printf '#!/bin/sh\nexit 0\n' > $T/stub/hostapd          # the AP "runs" and stops at once: run() tears down
printf '#!/bin/sh\n[ "$1" = udhcpd ] && exec sleep 30\nexec /bin/busybox "$@"\n' > $T/stub/busybox
chmod +x $T/stub/*
: > $T/wmt
cat > $T/inner.sh <<EOF
set -u
mount -t tmpfs none /run/systemd/network 2>/dev/null || { mkdir -p /run/systemd/network; mount -t tmpfs none /run/systemd/network; }
touch /dev/wmtWifi 2>/dev/null; mount --bind $T/wmt /dev/wmtWifi
export PATH=$T/stub:/usr/sbin:/usr/bin:/sbin:/bin VEGAS_SYSROOT=$T/sr PYTHONDONTWRITEBYTECODE=1 VEGAS_UI_LIB=$O/usr/lib/vegas/ui
export VEGAS_HOTSPOT_CONF=$T/hotspot.conf
pass=0 fail=0
ok(){ if eval "\$2"; then echo "PASS \$1"; pass=\$((pass+1)); else echo "FAIL \$1"; fail=\$((fail+1)); fi; }
intact(){ for t in iptables-legacy ip6tables-legacy; do
  \$t -C INPUT -p tcp --dport 22 -j VEGAS-AWAY 2>/dev/null && \$t -C VEGAS-AWAY -p tcp --dport 22 -j DROP 2>/dev/null || return 1
  [ "\$(\$t -S INPUT | grep -c VEGAS-AWAY)" = 1 ] || return 1
  [ "\$(\$t -S INPUT | sed -n 2p)" = "-A INPUT -p tcp -m tcp --dport 22 -j VEGAS-AWAY" ] || return 1   # still first
done; }
printf '1234\n1234\n' | bash $SB/vegas-away setpin >/dev/null; bash $SB/vegas-away on
ok "Away on: chains present v4+v6" intact
ok "status closed" '[[ \$(bash $SB/vegas-away status) == *"SSH closed"* ]]'
mkdir -p /etc/systemd/network; mount -t tmpfs none /etc/systemd/network; cp $O/etc/systemd/network/10-usb0.network /etc/systemd/network/
bash $SB/vegas-usbshare on >/dev/null 2>&1; echo "  usbshare on: \$(bash $SB/vegas-usbshare status)"
ok "after usbshare on: intact" intact
ok "usbshare NAT present" 'iptables-legacy -t nat -C POSTROUTING -s 172.16.42.0/24 -o wlan0 -j MASQUERADE'
bash $SB/vegas-usbshare off >/dev/null 2>&1
ok "after usbshare off: intact" intact
ok "usbshare NAT gone" '! iptables-legacy -t nat -C POSTROUTING -s 172.16.42.0/24 -o wlan0 -j MASQUERADE 2>/dev/null'
ip link add ap0 type dummy; mount -t tmpfs none /run/vegas-hotspot 2>/dev/null || { mkdir -p /run/vegas-hotspot; mount -t tmpfs none /run/vegas-hotspot; }
bash -x $SB/vegas-hotspot run 1 > /tmp/vas-hs.trace 2>&1; out=\$(grep -v -i "psk\\|passphrase\|^+" /tmp/vas-hs.trace); echo "  hotspot run: \$(echo "\$out" | tr '\n' ' ')"
ok "hotspot came up (its NAT was added) and tore down" '[[ \$out == *"hotspot vegas-"*" on channel"* && \$out == *"hotspot off"* ]]'
ok "after hotspot on+off: intact" intact
ok "hotspot NAT gone" '[ -z "\$(iptables-legacy -t nat -S POSTROUTING | grep MASQUERADE)" ]'
ok "status still closed, away-ssh closed" '[[ \$(bash $SB/vegas-away status) == *"SSH closed"* ]] && [ "\$(cat $T/sr/run/vegas-ui/away-ssh)" = closed ]'
bash $SB/vegas-away off >/dev/null 2>&1
ok "Away off removes chains" '! iptables-legacy -n -L VEGAS-AWAY >/dev/null 2>&1 && ! ip6tables-legacy -n -L VEGAS-AWAY >/dev/null 2>&1'
echo "== \$pass passed, \$fail failed"; [ \$fail = 0 ]
EOF
$PH unshare -m --propagation private bash $T/inner.sh
