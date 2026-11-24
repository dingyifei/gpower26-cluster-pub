#!/bin/bash
# VM only (orb -m vegas-deb bash menu-test.sh, no sudo): the Power off confirm list (designer ruling 2).
# Headless sway at #5's size and scale, the real bemenu behind a wrapper that logs its prompt and rows, a virtual
# keyboard (wtype) as vegas-keys' uinput stand-in. Prints only (never --run). Screenshots next to this script.
set -u
O=/path/to/repo/linux/debian/overlay
D=$(cd "$(dirname "$0")" && pwd); B=$(mktemp -d)
pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
export XDG_RUNTIME_DIR=$B WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LANG=C.UTF-8
printf 'output HEADLESS-1 mode 1080x2388 scale 3 position 0 0 subpixel none bg #1d3b53 solid_color\ngaps left 10\ngaps right 10\ngaps bottom 16\n' > $B/sway.conf
sway -c $B/sway.conf >$B/sway.log 2>&1 & SP=$!
for i in $(seq 50); do ls $B/wayland-? >/dev/null 2>&1 && break; sleep 0.1; done
export WAYLAND_DISPLAY=$(basename $(ls $B/wayland-? | head -1)) SWAYSOCK=$(ls $B/sway-ipc.*.sock)
mkdir -p $B/bin; cat > $B/bin/bemenu <<EOF
#!/bin/bash
rows=\$(cat); prompt=""; a=("\$@")
for ((i=0; i<\${#a[@]}; i++)); do [ "\${a[i]}" = -p ] && prompt=\${a[i+1]}; done
printf 'prompt=%s|rows=%s\n' "\$prompt" "\$(printf '%s' "\$rows" | paste -sd, -)" >> $B/calls
printf '%s\n' "\$rows" | /usr/bin/bemenu "\$@"
EOF
chmod +x $B/bin/bemenu; export PATH=$B/bin:$PATH
wtype -s 60000 -k Shift_L & KB=$!; sleep 0.5
S=$B/sys; mkdir -p $S/sys/class/power_supply/primary_chg
menu_poweroff(){  # $1 = charger online 0|1, $2 = screenshot name; Down x4 = "Power off", then confirm
  echo "$1" > $S/sys/class/power_supply/primary_chg/online; : > $B/calls
  VEGAS_SYSROOT=$S bash $O/usr/lib/vegas/vegas-menu full upright > $B/out & local mp=$!; sleep 1.2
  wtype -k Down -k Down -k Down -k Down -k Return; sleep 1.2; grim $D/$2.png
  wtype -k "${3:-Return}"; wait $mp; echo $? > $B/rc
}
menu_poweroff 1 menu-confirm-cable
echo "  calls: $(cat $B/calls | tr '\n' ' ')"
ok "cable in: confirm prompt is the warning" 'sed -n 2p $B/calls | grep -qx "prompt=Cable in: charges to full|rows=Power off now,Cancel"'
ok "cable in: Enter on the first row = Power off now" '[ "$(cat $B/out)" = "Power off now" ] && [ "$(cat $B/rc)" = 0 ]'
ok "main menu prompt unchanged" 'sed -n 1p $B/calls | grep -q "^prompt=Vol keys move · Power picks|rows=Screen off,Rotate,"'
menu_poweroff 0 menu-confirm-battery
ok "on battery: prompt 'Power off the phone?', two rows" 'sed -n 2p $B/calls | grep -qx "prompt=Power off the phone?|rows=Power off now,Cancel"'
menu_poweroff 1 menu-confirm-cancel Escape
ok "Esc on the confirm list = cancel (exit 1, nothing printed)" '[ "$(cat $B/rc)" = 1 ] && [ ! -s $B/out ]'
echo 1 > $S/sys/class/power_supply/primary_chg/online; : > $B/calls
VEGAS_SYSROOT=$S bash $O/usr/lib/vegas/vegas-menu full upright > $B/out & mp=$!; sleep 1.2
wtype -k Down -k Down -k Down -k Down -k Return; sleep 1; wtype -k Down -k Return; wait $mp; rc=$?
ok "Cancel row on the confirm list = cancel" '[ $rc = 1 ] && [ ! -s $B/out ]'
kill $KB 2>/dev/null; swaymsg exit >/dev/null 2>&1; wait $SP 2>/dev/null
echo "== $pass passed, $fail failed"; rm -rf $B; [ $fail = 0 ]
