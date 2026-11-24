#!/bin/bash
# the glance subset of test-glue.sh (no sway, no /run writes outside a temp tree)
set -u; export PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8
O=/path/to/repo/linux/debian/overlay; T=$(mktemp -d); pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
export VEGAS_UI_LIB=$O/usr/lib/vegas/ui VEGAS_SYSROOT=$T/root; R=$T/root
mkdir -p $R/sys/class/power_supply/battery $R/sys/class/power_supply/primary_chg $R/sys/class/thermal/thermal_zone0 $R/run/vegas-chargeguard $R/proc $R/sys/class/net/usb0 $R/run/vegas-ui $R/etc/vegas
echo 78 > $R/sys/class/power_supply/battery/capacity; echo 310 > $R/sys/class/power_supply/battery/temp; echo 0 > $R/sys/class/power_supply/battery/current_now
echo 1 > $R/sys/class/power_supply/primary_chg/online; echo 41000 > $R/sys/class/thermal/thermal_zone0/temp; echo off > $R/run/vegas-chargeguard/want
echo "300000.00 1" > $R/proc/uptime; echo main > $R/etc/vegas/root-role; echo 1 > $R/sys/class/net/usb0/carrier
G=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); echo "$G"
ok "glance holding band" 'echo "$G" | grep -q "holding *70-80%"'
ok "glance width<=20" '! echo "$G" | awk "length>20" | grep -q .'
ok "glance main root" 'echo "$G" | grep -q "main root *up 3d"'
ok "glance 0.0 A" 'echo "$G" | grep -q "charger in *0.0 A"'
echo 39 > $R/sys/class/power_supply/battery/temp; echo on > $R/run/vegas-chargeguard/want
printf 'STOP=100\nRESUME=99\n' > $R/run/vegas-chargeguard/override; echo "override: STOP=100 RESUME=99" > $R/run/vegas-chargeguard/override-state
G=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); ok "glance charging 99-100" 'echo "$G" | grep -q "charging *99-100%"'
touch $R/etc/vegas/away
G=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); ok "glance main away (B5)" 'echo "$G" | grep -q "main away *up 3d"'
echo "n=2 max=6 hl=4 msg=wrong PIN" > $R/run/vegas-ui/pin
P=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once --mode=pin | sed 's/\x1b\[[0-9;]*m//g'); echo "$P"
ok "pin dots" 'echo "$P" | grep -q "● ● ○ ○ ○ ○"'
ok "pin keys row" 'echo "$P" | grep -q "1 .* 2 .* 3"'
L=$(COLS=44 ROWS=9 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); echo "$L"
ok "landscape <=44" '! echo "$L" | awk "length>44" | grep -q .'
rm -rf $T; echo "== $pass passed, $fail failed"
