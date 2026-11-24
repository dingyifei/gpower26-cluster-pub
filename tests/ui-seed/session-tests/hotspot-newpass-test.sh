#!/bin/bash
# VM only (orb -m vegas-deb sudo bash hotspot-newpass-test.sh): vegas-hotspot newpass (designer B7). Uses a temp
# conf via VEGAS_HOTSPOT_CONF; never starts a hotspot.
set -u
O=/path/to/repo/linux/debian/overlay
H=$O/usr/local/sbin/vegas-hotspot
T=$(mktemp -d); trap 'rm -rf $T' EXIT
export VEGAS_HOTSPOT_CONF=$T/hotspot.conf
pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
psk(){ sed -n 's/^PSK=//p' $VEGAS_HOTSPOT_CONF; }
ssid(){ sed -n 's/^SSID=//p' $VEGAS_HOTSPOT_CONF; }

out=$(bash $H newpass 2>&1); rc=$?
ok "missing file: created (rc 0, says only 'new passphrase set')" '[ $rc = 0 ] && [ "$out" = "new passphrase set" ]'
ok "mode 0600, root-owned" '[ "$(stat -c %a:%U $VEGAS_HOTSPOT_CONF)" = 600:root ]'
ok "SSID vegas-xxx, PSK 16 of the set" '[[ $(ssid) =~ ^vegas-[a-z0-9]{3}$ ]] && [[ $(psk) =~ ^[a-km-zA-HJ-NP-Z2-9]{16}$ ]]'
p1=$(psk); s1=$(ssid)
chmod 644 $VEGAS_HOTSPOT_CONF
out=$(bash $H newpass 2>&1); rc=$?
ok "second newpass: new PSK, same SSID" '[ $rc = 0 ] && [ "$(ssid)" = "$s1" ] && [ "$(psk)" != "$p1" ] && [[ $(psk) =~ ^[a-km-zA-HJ-NP-Z2-9]{16}$ ]]'
ok "loose old mode not kept (600 again)" '[ "$(stat -c %a $VEGAS_HOTSPOT_CONF)" = 600 ]'
ok "output never holds the passphrase" '[[ $out != *"$(psk)"* ]] && [[ $out != *"$p1"* ]]'
ok "no temp file left" '[ ! -e $VEGAS_HOTSPOT_CONF.new ]'
ok "show still reads it" '[ "$(bash $H show | sed -n "s/^passphrase //p")" = "$(psk)" ]'
# passphrase never in any argv: trace every exec of a newpass run
if command -v strace >/dev/null; then
  strace -f -qq -s 256 -e trace=execve -o $T/trace bash $H newpass >/dev/null 2>&1
  ok "new passphrase in no exec argv" '! grep -qF "$(psk)" $T/trace'
fi
# refuses while the hotspot runs (systemctl stubbed: unit active)
mkdir -p $T/bin; printf '#!/bin/sh\n[ "$1" = is-active ] && exit 0\nexit 1\n' > $T/bin/systemctl; chmod +x $T/bin/systemctl
p2=$(psk); out=$(PATH=$T/bin:$PATH bash $H newpass 2>&1); rc=$?
ok "refused while on, file unchanged" '[ $rc != 0 ] && [[ $out == *"turn the hotspot off first"* ]] && [ "$(psk)" = "$p2" ]'
# non-root refused
out=$(setpriv --reuid=nobody --regid=nogroup --clear-groups env VEGAS_HOTSPOT_CONF=$T/x.conf bash $H newpass 2>&1); rc=$?
ok "non-root refused" '[ $rc != 0 ] && [[ $out == *"run as root"* ]] && [ ! -e $T/x.conf ]'
# a broken file (no PSK line) gets a clear error, not a silent rewrite of the name
printf 'SSID=bad name!\n' > $VEGAS_HOTSPOT_CONF
out=$(bash $H newpass 2>&1); rc=$?
ok "invalid file refused" '[ $rc != 0 ] && [[ $out == *"needs SSID="* ]]'
echo "== $pass passed, $fail failed"; [ $fail = 0 ]
