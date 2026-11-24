#!/bin/bash
# VM only (orb -m vegas-deb sudo bash away-test.sh): vegas-away B1 property in throwaway network namespaces.
# "phone" netns: wlan0 (veth to "peer") and usb0 (veth to "peerusb"), a dual-stack listener on port 22.
# Checks real TCP reachability from the peers over IPv4, IPv6 ULA and IPv6 link-local, for: the ip6tables path, the
# disable_ipv6 fallback (ip6tables-legacy stubbed to fail), networkd-style re-enable, a new interface during Away,
# restore on off, and refusal when neither IPv6 path holds. Never touches the VM's own netns or /run.
set -u
O=/path/to/repo/linux/debian/overlay
AWAY=$O/usr/local/sbin/vegas-away
export PYTHONDONTWRITEBYTECODE=1 VEGAS_UI_LIB=$O/usr/lib/vegas/ui
T=$(mktemp -d); export VEGAS_SYSROOT=$T
pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
cleanup(){ kill $LP 2>/dev/null; for n in vaw-phone vaw-peer vaw-peerusb; do ip netns del $n 2>/dev/null; done; rm -rf $T; }
trap cleanup EXIT
for n in vaw-phone vaw-peer vaw-peerusb; do ip netns del $n 2>/dev/null; ip netns add $n; done
PH="ip netns exec vaw-phone"
ip link add wlan0 netns vaw-phone type veth peer name p0 netns vaw-peer
ip link add usb0 netns vaw-phone type veth peer name u0 netns vaw-peerusb
$PH sysctl -qw net.ipv6.conf.default.disable_ipv6=0 net.ipv6.conf.all.disable_ipv6=0
for n in vaw-phone vaw-peer vaw-peerusb; do ip netns exec $n ip link set lo up; done
addrs(){
  $PH ip addr add 10.77.0.1/24 dev wlan0 2>/dev/null; $PH ip -6 addr add fd77::1/64 dev wlan0 nodad 2>/dev/null
  $PH ip addr add 10.78.0.1/24 dev usb0 2>/dev/null; $PH ip -6 addr add fd78::1/64 dev usb0 nodad 2>/dev/null
  $PH ip link set wlan0 up; $PH ip link set usb0 up
}
addrs
ip netns exec vaw-peer ip addr add 10.77.0.2/24 dev p0; ip netns exec vaw-peer ip -6 addr add fd77::2/64 dev p0 nodad
ip netns exec vaw-peer ip link set p0 up
ip netns exec vaw-peerusb ip addr add 10.78.0.2/24 dev u0; ip netns exec vaw-peerusb ip -6 addr add fd78::2/64 dev u0 nodad
ip netns exec vaw-peerusb ip link set u0 up
sleep 2.5   # link-local addresses (DAD)
$PH python3 -c '
import socket
s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM); s.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("::", 22)); s.listen(16)
while True:
    c, _ = s.accept(); c.close()' & LP=$!
sleep 0.5
lladdr(){ $PH ip -6 -o addr show dev wlan0 scope link | awk '{print $4}' | cut -d/ -f1; }
LL=$(lladdr)
reach(){  # netns host -> 0 when a TCP connect to port 22 succeeds within 1 s
  ip netns exec "$1" python3 -c '
import socket, sys
h = sys.argv[1]
fam = socket.AF_INET6 if ":" in h else socket.AF_INET
try:
    s = socket.socket(fam, socket.SOCK_STREAM); s.settimeout(1)
    if "%" in h:
        a, i = h.split("%"); s.connect((a, 22, 0, socket.if_nametoindex(i)))
    else:
        s.connect((h, 22))
    sys.exit(0)
except OSError:
    sys.exit(1)' "$2"
}
wifi4(){ reach vaw-peer 10.77.0.1; }; wifi6(){ reach vaw-peer fd77::1; }; wifill(){ reach vaw-peer "$LL%p0"; }
usb4(){ reach vaw-peerusb 10.78.0.1; }; usb6(){ reach vaw-peerusb fd78::1; }
A(){ $PH env PATH="$STUB:/usr/sbin:/usr/bin:/sbin:/bin" bash $AWAY "$@"; }
STUB=$T/nostub; mkdir -p $STUB
dis(){ $PH cat /proc/sys/net/ipv6/conf/$1/disable_ipv6; }

echo "== baseline (Away off); link-local $LL"
ok "wifi v4 open" wifi4; ok "wifi v6 open" wifi6; ok "wifi v6 link-local open" wifill; ok "usb v4 open" usb4; ok "usb v6 open" usb6
ok "on refused without a PIN" '! A on 2>/dev/null && [ ! -e $T/etc/vegas/away ]'
printf '1234\n1234\n' | A setpin >/dev/null

echo "== path 1: ip6tables-legacy works"
out=$(A on); echo "  on: $out"
ok "on succeeded, flag set" '[ -e $T/etc/vegas/away ]'
ok "wifi v4 closed" '! wifi4'; ok "wifi v6 closed" '! wifi6'; ok "wifi v6 link-local closed" '! wifill'
ok "usb v4 still open" usb4; ok "usb v6 still open" usb6
ok "IPv6 left on (rule path)" '[ "$(dis wlan0)" = 0 ] && [ ! -e $T/run/vegas-away.ipv6off ]'
st=$(A status); echo "  status: $st"; ok "status closed" '[[ $st == "on (SSH closed on Wi-Fi; PIN set"* ]]'
ok "away-ssh file closed" '[ "$(cat $T/run/vegas-ui/away-ssh)" = closed ]'
$PH ip6tables-legacy -D INPUT -p tcp --dport 22 -j VEGAS-AWAY
st=$(A status); echo "  status with the v6 jump removed: $st"
ok "status says OPEN over IPv6 when the v6 rule is gone" '[[ $st == *"SSH OPEN on Wi-Fi over IPv6"* ]] && [ "$(cat $T/run/vegas-ui/away-ssh)" = open ]'
A apply >/dev/null; ok "apply restores the v6 rule" '! wifi6 && [[ $(A status) == *"SSH closed on Wi-Fi;"* ]]'
out=$(A off); ok "off: all open again" 'wifi4 && wifi6 && wifill && [ ! -e $T/etc/vegas/away ]'
ok "off: chains gone" '! $PH iptables-legacy -n -L VEGAS-AWAY >/dev/null 2>&1 && ! $PH ip6tables-legacy -n -L VEGAS-AWAY >/dev/null 2>&1'
st=$(A status); ok "status off/open" '[[ $st == "off (SSH open;"* ]]'

echo "== path 2: ip6tables-legacy fails -> IPv6 off on Wi-Fi"
STUB=$T/stub6; mkdir -p $STUB; printf '#!/bin/sh\nexit 1\n' > $STUB/ip6tables-legacy; chmod +x $STUB/ip6tables-legacy
out=$(A on 2>$T/err); echo "  on: $out / $(cat $T/err)"
ok "on succeeded with fallback" '[ -e $T/etc/vegas/away ] && [[ $out == *"IPv6 off on Wi-Fi"* ]]'
ok "wifi v4 closed" '! wifi4'; ok "wifi v6 unreachable" '! wifi6'; ok "wifi v6 link-local unreachable" '! wifill'
ok "usb v4 open" usb4; ok "usb v6 open (usb0 exempt)" usb6
ok "disable_ipv6: wlan0=1 default=1 usb0=0 lo=0" '[ "$(dis wlan0)$(dis default)$(dis usb0)$(dis lo)" = 1100 ]'
ok "networkd drop-in written" 'grep -qx LinkLocalAddressing=no $T/run/systemd/network/20-wlan0.network.d/vegas-away.conf'
st=$(A status); echo "  status: $st"; ok "status closed, IPv6 off" '[[ $st == "on (SSH closed on Wi-Fi, IPv6 off; PIN set"* ]]'
$PH ip link add ap0 type dummy
ok "an interface made during Away is born without IPv6" '[ "$(dis ap0)" = 1 ] && [[ $(A status) == *"SSH closed"* ]]'
$PH sh -c 'echo 0 > /proc/sys/net/ipv6/conf/wlan0/disable_ipv6'; $PH ip -6 addr add fd77::1/64 dev wlan0 nodad; sleep 2.5
st=$(A status); echo "  status after IPv6 came back on wlan0 (as networkd would): $st"
ok "status never says closed while v6 is reachable" 'wifi6 && [[ $st == *"SSH OPEN on Wi-Fi over IPv6"* ]] && [ "$(cat $T/run/vegas-ui/away-ssh)" = open ]'
A apply >/dev/null 2>&1; ok "apply closes it again" '! wifi6 && [ "$(dis wlan0)" = 1 ] && [[ $(A status) == *"SSH closed"* ]]'
out=$(A off); echo "  off: $out"
ok "off restores disable_ipv6 (wlan0, default, ap0 made during Away)" '[ "$(dis wlan0)$(dis default)$(dis ap0)" = 000 ]'
ok "off removes drop-in and saved values" '[ ! -e $T/run/systemd/network/20-wlan0.network.d/vegas-away.conf ] && [ ! -e $T/run/vegas-away.ipv6off ]'
addrs; sleep 2.5; LL=$(lladdr)
ok "after off: wifi v4/v6/link-local open" 'wifi4 && wifi6 && wifill'
$PH ip link del ap0

echo "== path 3: neither (ip6tables fails, disable_ipv6 cannot be written) -> refuse"
out=$($PH unshare -m bash -c "mount --bind -o ro /proc/sys/net/ipv6/conf/default/disable_ipv6 /proc/sys/net/ipv6/conf/default/disable_ipv6 2>/dev/null || mount -o remount,ro,bind /proc/sys/net/ipv6/conf/default/disable_ipv6; mount -o remount,ro,bind /proc/sys/net/ipv6/conf/default/disable_ipv6 2>/dev/null; echo 1 > /proc/sys/net/ipv6/conf/default/disable_ipv6 2>/dev/null && echo WRITABLE; env PATH=$STUB:/usr/sbin:/usr/bin:/sbin:/bin bash $AWAY on" 2>&1); rc=$?
echo "  on: rc=$rc $out"
ok "refused: flag not set, no rules left, IPv6 restored" '[ $rc != 0 ] && [ ! -e $T/etc/vegas/away ] && ! $PH iptables-legacy -n -L VEGAS-AWAY >/dev/null 2>&1 && [ "$(dis wlan0)" = 0 ] && [[ $out != *WRITABLE* ]]'
ok "after refusal: wifi reachable (nothing half-done)" 'addrs; sleep 2.5; wifi4 && wifi6'

echo "== IPv4 failure: iptables-legacy stubbed to fail"
STUB=$T/stub4; mkdir -p $STUB; printf '#!/bin/sh\nexit 1\n' > $STUB/iptables-legacy; chmod +x $STUB/iptables-legacy
ok "on refused (Away stays off)" '! A on 2>/dev/null && [ ! -e $T/etc/vegas/away ]'
: > $T/etc/vegas/away
ok "apply with the flag set fails (boot unit fails)" '! A apply 2>/dev/null'
st=$(A status); echo "  status: $st"; ok "status says OPEN over IPv4" '[[ $st == *"SSH OPEN on Wi-Fi over IPv4"* ]] && [ "$(cat $T/run/vegas-ui/away-ssh)" = open ]'
STUB=$T/nostub; A off >/dev/null
echo "== $pass passed, $fail failed"
[ $fail = 0 ]
