#!/bin/bash
# VM tests for session glue (run as root in vegas-deb). No phone.
set -u
O=/path/to/repo/linux/debian/overlay
T=$(mktemp -d); pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
# --- vegas-session (isolated tmux server via TMUX_TMPDIR)
export TMUX_TMPDIR=$T/tmux; mkdir -p $TMUX_TMPDIR
mkdir -p /run/vegas-ui; mkdir -p /etc/vegas; cp $O/etc/vegas/tmux-vegas.conf /etc/vegas/
sh $O/usr/lib/vegas/vegas-session
sh $O/usr/lib/vegas/vegas-session   # idempotent
W=$(tmux list-windows -t main -F '#I:#W' | tr '\n' ' ')
ok "session windows" '[ "$W" = "0:home 1:net 2:sh 3:logs " ]'
ok "current window 2" '[ "$(tmux display -p -t main "#{window_index}")" = 2 ]'
ok "status top" '[ "$(tmux show -gv status-position)" = top ]'
tmux new-session -d -s mac -t main
ok "group attach count fmt" 'tmux display -p -t main "#{session_group_attached}" >/dev/null'
ok "mac sees same windows" '[ "$(tmux list-windows -t mac | wc -l)" = 4 ]'
sleep 3; ok "home window: not installed, or Home running" 'tmux capture-pane -p -t main:0 | grep -q "not installed\|vegas-home\|Battery"'
# a lost window comes back on the next run; the current window is not moved
tmux select-window -t main:0; tmux kill-window -t main:2; sh $O/usr/lib/vegas/vegas-session
W=$(tmux list-windows -t main -F '#I:#W' | tr '\n' ' ')
ok "lost sh window restored" '[ "$W" = "0:home 1:net 2:sh 3:logs " ]'
ok "current window kept" '[ "$(tmux display -p -t main "#{window_index}")" = 0 ]'
ok "session env has wayland" 'tmux show-environment -t main WAYLAND_DISPLAY | grep -qx WAYLAND_DISPLAY=wayland-1'
tmux kill-server
# server started by a bare tmux first (SSH): main still gets the sway client env
XDG_RUNTIME_DIR=/run/user/0 tmux new-session -d -s 0; sh $O/usr/lib/vegas/vegas-session
ok "pre-existing server: env" 'tmux show-environment -t main XDG_RUNTIME_DIR | grep -qx XDG_RUNTIME_DIR=/run/sway'
tmux kill-server
# --- vegas-charge with fake state dir
export VEGAS_ST=$T/cg; mkdir -p $VEGAS_ST
ok "charge band at start" '[ "$(sh $O/usr/local/sbin/vegas-charge status)" = band ]'
sh $O/usr/local/sbin/vegas-charge full >/dev/null
ok "override content" '[ "$(cat $VEGAS_ST/override)" = "$(printf "STOP=100\nRESUME=99")" ]'
ok "pending" '[ "$(sh $O/usr/local/sbin/vegas-charge status)" = "full (pending)" ]'
echo "override: STOP=100 RESUME=99 (from x)" > $VEGAS_ST/override-state
ok "full" '[ "$(sh $O/usr/local/sbin/vegas-charge status)" = full ]'
echo "WARNING: ignoring" > $VEGAS_ST/override-state
ok "ignored" '[ "$(sh $O/usr/local/sbin/vegas-charge status)" = ignored ]'
sh $O/usr/local/sbin/vegas-charge band >/dev/null
ok "band removes" '[ ! -e $VEGAS_ST/override ]'
# real chargeguard parses our file
ok "chargeguard accepts format" 'grep -q "^STOP=100$" <(printf "STOP=100\nRESUME=99\n") && printf "STOP=100\nRESUME=99\n" | sed -n "s/^STOP=\([0-9]\{1,3\}\)[[:space:]]*$/\1/p" | grep -qx 100'
unset VEGAS_ST
# --- PIN logic
export VEGAS_SYSROOT=$T/root VEGAS_UI_LIB=$O/usr/lib/vegas/ui; PY="python3 -m vegasui.pin"; cd $VEGAS_UI_LIB
ok "pin unset" '$PY status | grep -q ^unset'
ok "pin mismatch refused" '! printf "1234\n1235\n" | $PY set 2>/dev/null'
ok "pin too short refused" '! printf "123\n123\n" | $PY set 2>/dev/null'
printf "4321\n4321\n" | $PY set
ok "pin file mode 600" '[ "$(stat -c %a $T/root/etc/vegas/away-pin)" = 600 ]'
ok "right pin" 'echo 4321 | $PY check'
for i in 1 2 3 4; do echo 0000 | $PY check; done
ok "5th wrong locks" 'echo 0000 | $PY check; [ $? = 3 ]'
ok "locked even with right pin" 'echo 4321 | $PY check; [ $? = 3 ]'
echo "fails=5 until=0" > $T/root/var/lib/vegas/away-fails
ok "6th wrong locks 60s" 'echo 0000 | $PY check | grep -q "locked for 60 s"'
# vegas-away status/setpin without iptables
ok "away status off" 'bash $O/usr/local/sbin/vegas-away status | grep -q "^off"'
ok "away on refuses without a pin" '! VEGAS_SYSROOT=$T/nopin bash $O/usr/local/sbin/vegas-away on 2>/dev/null'
ok "away on refused: no away file" '[ ! -e $T/nopin/etc/vegas/away ]'
bash $O/usr/local/sbin/vegas-away on >/dev/null; bash $O/usr/local/sbin/vegas-away on >/dev/null
ok "away on: one INPUT hook" '[ "$(iptables-legacy -S INPUT | grep -c VEGAS-AWAY)" = 1 ]'
ok "away status on" 'bash $O/usr/local/sbin/vegas-away status | grep -q "^on (SSH closed"'
bash $O/usr/local/sbin/vegas-away off >/dev/null
ok "away off clean" '! iptables-legacy -S | grep -q VEGAS; ! ip6tables-legacy -S 2>/dev/null | grep -q VEGAS'
ok "away file gone" '[ ! -e $T/root/etc/vegas/away ]'
# --- pad geometry
ok "pad upright cols" 'python3 -c "
from vegasui import pad
k=pad.layout(20,20); assert [x for _,_,x,_,_,_ in k[:3]]==[0,7,14], k[:3]
assert pad.key_at(0,k[0][3],20,20)==0 and pad.key_at(6,k[0][3],20,20) is None
assert pad.key_at(19,k[11][3]+1,20,20)==11
assert pad.hit(1079, (k[11][3]+1)*119+5, 1080, 2388)==\"ok\"
assert pad.hit(30, 10, 1080, 2388) is None
k=pad.layout(44,9); assert all(x+w<=44 and y+h<=9 for _,_,x,y,w,h in k)
"'
# --- glance render with fake sysroot
R=$T/root; mkdir -p $R/sys/class/power_supply/battery $R/sys/class/power_supply/primary_chg $R/sys/class/thermal/thermal_zone0 $R/run/vegas-chargeguard $R/proc $R/sys/class/net/usb0 $R/run/vegas-ui
echo 78 > $R/sys/class/power_supply/battery/capacity; echo 310 > $R/sys/class/power_supply/battery/temp; echo 0 > $R/sys/class/power_supply/battery/current_now
echo 1 > $R/sys/class/power_supply/primary_chg/online; echo 41000 > $R/sys/class/thermal/thermal_zone0/temp; echo off > $R/run/vegas-chargeguard/want
echo "300000.00 1" > $R/proc/uptime; echo main > $R/etc/vegas/root-role; echo 1 > $R/sys/class/net/usb0/carrier
G=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g')
echo "$G"
ok "glance holding band" 'echo "$G" | grep -q "holding *70-80%"'
ok "glance width<=20" '! echo "$G" | awk "length>20" | grep -q .'
ok "glance main root" 'echo "$G" | grep -q "main root *up 3d"'
echo 39 > $R/sys/class/power_supply/battery/temp; echo on > $R/run/vegas-chargeguard/want
printf 'STOP=100\nRESUME=99\n' > $R/run/vegas-chargeguard/override; echo "override: STOP=100 RESUME=99" > $R/run/vegas-chargeguard/override-state
G=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); ok "glance charging 99-100" 'echo "$G" | grep -q "charging *99-100%"'
echo "n=2 max=6 hl=4 msg=wrong PIN" > $R/run/vegas-ui/pin
P=$(COLS=20 ROWS=20 python3 $O/usr/lib/vegas/vegas-glance --once --mode=pin | sed 's/\x1b\[[0-9;]*m//g'); echo "$P"
ok "pin dots" 'echo "$P" | grep -q "● ● ○ ○ ○ ○"'
ok "pin keys row" 'echo "$P" | grep -q "1 .* 2 .* 3"'
L=$(COLS=44 ROWS=9 python3 $O/usr/lib/vegas/vegas-glance --once | sed 's/\x1b\[[0-9;]*m//g'); echo "$L"
ok "landscape <=44" '! echo "$L" | awk "length>44" | grep -q .'
# --- vegas-menu with a fake bemenu
mkdir -p $T/bin; printf '#!/bin/sh\ncat >%s/rows; head -n %s %s/rows | tail -1\n' $T '${PICK:-1}' $T > $T/bin/bemenu; chmod +x $T/bin/bemenu
ok "menu prints row" '[ "$(PATH=$T/bin:$PATH PICK=3 bash $O/usr/lib/vegas/vegas-menu full upright)" = "Reboot to Android" ]'
ok "menu full has 8 rows" '[ $(wc -l < $T/rows) = 8 ]'
PATH=$T/bin:$PATH PICK=6 bash $O/usr/lib/vegas/vegas-menu full-prog upright >/dev/null; ok "full-prog close program" 'sed -n 6p $T/rows | grep -qx "Close program"'
ok "cancel exits 1" '! PATH=$T/bin:$PATH PICK=4 bash $O/usr/lib/vegas/vegas-menu short upright'
ok "power off confirm -> Power off now" '[ "$(PATH=$T/bin:$PATH PICK=1 bash -c "printf x" ; PATH=$T/bin:$PATH PICK=1 bash $O/usr/lib/vegas/vegas-menu short upright)" = "xScreen off" ]'
cat > $T/bin/bemenu <<'B'
#!/bin/sh
rows=$(cat); case "$rows" in *"Power off now"*) echo "Power off now";; *) echo "Power off";; esac
B
ok "power off two-step" '[ "$(PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright)" = "Power off now" ]'
ok "bad row from typing = cancel" 'printf "#!/bin/sh\ncat >/dev/null; echo rm -rf\n" > $T/bin/bemenu; ! PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright'
# integration: with a charger online the power-off confirm's PROMPT line is the warning (designer ruling 2, 23 Nov:
# "Cable in: charges to full" in place of "Vol keys move · Power picks" on that list); rows stay two
mkdir -p $T/chg/sys/class/power_supply/primary_chg
cat > $T/bin/bemenu <<'B'
#!/bin/sh
rows=$(cat); printf '%s\n' "$rows" > "$ROWS"
p=; while [ $# -gt 0 ]; do [ "$1" = -p ] && { p=$2; shift; }; shift; done; printf '%s\n' "$p" >> "$ROWS.prompts"
case "$rows" in *"Power off now"*) echo "${CONFIRM:-Power off now}";; *) echo "Power off";; esac
B
echo 1 > $T/chg/sys/class/power_supply/primary_chg/online
rm -f $T/crows.prompts
ok "charger: confirm prompt is the cable warning, two rows" 'ROWS=$T/crows VEGAS_SYSROOT=$T/chg PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright >/dev/null; [ "$(tail -1 $T/crows.prompts)" = "Cable in: charges to full" ] && [ "$(cat $T/crows)" = "$(printf "Power off now\nCancel")" ]'
ok "charger: the main list keeps its own prompt" '[ "$(head -1 $T/crows.prompts)" = "Vol keys move · Power picks" ]'
ok "charger: Cancel on the confirm = cancel" '! ROWS=$T/crows CONFIRM="Cancel" VEGAS_SYSROOT=$T/chg PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright'
ok "charger: Power off now still works" '[ "$(ROWS=$T/crows VEGAS_SYSROOT=$T/chg PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright)" = "Power off now" ]'
echo 0 > $T/chg/sys/class/power_supply/primary_chg/online
rm -f $T/crows.prompts
ok "no charger: 2 confirm rows, prompt 'Power off the phone?'" 'ROWS=$T/crows VEGAS_SYSROOT=$T/chg PATH=$T/bin:$PATH bash $O/usr/lib/vegas/vegas-menu full upright >/dev/null; [ $(wc -l < $T/crows) = 2 ] && [ "$(tail -1 $T/crows.prompts)" = "Power off the phone?" ]'
echo "== $pass passed, $fail failed"; rm -rf $T
