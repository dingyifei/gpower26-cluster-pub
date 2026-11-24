#!/bin/bash
# VM only (vegas-deb, as root): headless sway set up like #5, running the session glue from the repo overlay.
# Checks vegas-term/vegas-session respawn, font size change, Mac attach without resize, glance + PIN pad window,
# bemenu power menu (print only, never --run). Screenshots land next to this script. Never run on the phone.
set -u
D=$(cd "$(dirname "$0")" && pwd)
O=/path/to/repo/linux/debian/overlay
B=$(mktemp -d); pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
# VM test install: overlay glue at the installed paths (the VM is a throwaway test box)
install -D -m755 $O/usr/lib/vegas/vegas-session /usr/lib/vegas/vegas-session
install -D -m755 $O/usr/lib/vegas/vegas-term /usr/lib/vegas/vegas-term
install -D -m644 $O/etc/vegas/tmux-vegas.conf /etc/vegas/tmux-vegas.conf
rm -f /run/vegas-ui/fontsize /run/vegas-ui/term.pid
export TMUX_TMPDIR=$B XDG_RUNTIME_DIR=$B WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
cat > $B/sway.conf <<EOF
output HEADLESS-1 mode 1080x2388 scale 3 position 0 0 subpixel none bg #1d3b53 solid_color
default_border none
gaps left 10
gaps right 10
gaps bottom 16
bar {
  position top
  height 36
  font monospace 10
  workspace_buttons no
  status_command while :; do date +%H:%M; sleep 60; done
}
for_window [app_id="vegas-glance"] floating enable, fullscreen enable, border none
for_window [app_id="^(?!vegas-term\$|vegas-glance\$).*"] move container to workspace number 2, workspace number 2
exec choom -n 0 -- /usr/lib/vegas/vegas-term
EOF
sway -c $B/sway.conf >$D/sway.log 2>&1 & SP=$!
for i in $(seq 50); do ls $B/wayland-? >/dev/null 2>&1 && break; sleep 0.1; done
export WAYLAND_DISPLAY=$(basename $(ls $B/wayland-? | head -1)) SWAYSOCK=$(ls $B/sway-ipc.*.sock)
termpid(){ cat /run/vegas-ui/term.pid 2>/dev/null; }
mapped(){ swaymsg -t get_tree | grep -c "\"app_id\": \"$1\""; }
cw(){ tmux display -p -t main '#{window_width}x#{window_height}'; }   # current window of main
for i in $(seq 60); do [ "$(tmux list-clients -t main 2>/dev/null | wc -l)" = 1 ] && break; sleep 0.25; done
sleep 1
ok "foot attached to main" '[ "$(tmux list-clients -t main | wc -l)" = 1 ]'
ok "term.pid is foot" '[ "$(cat /proc/$(termpid)/comm)" = foot ]'
ok "vegas-term window mapped" '[ "$(mapped vegas-term)" = 1 ]'
ok "choom: foot oom adj 0" '[ "$(cat /proc/$(termpid)/oom_score_adj)" = 0 ]'
echo "size at 7.25: $(cw)"; ok "60 columns at 7.25" '[ "$(cw | cut -dx -f1)" = 60 ]'
grim $D/term.png
# exit the shell window: tmux moves to another window, foot stays; next foot (kill) restores 2:sh
p1=$(termpid); tmux send-keys -t main:2 'exit' Enter; sleep 1
ok "exit in 2:sh keeps foot" '[ "$(termpid)" = $p1 ] && kill -0 $p1'
ok "exit gives a fresh shell in 2:sh" '[ "$(tmux display -p -t main "#{window_index}:#{pane_current_command}")" = 2:bash ]'
kill $p1; for i in $(seq 40); do [ -n "$(termpid)" ] && [ "$(termpid)" != $p1 ] && [ "$(tmux list-clients -t main | wc -l)" = 1 ] && break; sleep 0.25; done
ok "killed foot reopens" '[ "$(termpid)" != $p1 ] && [ "$(tmux list-clients -t main | wc -l)" = 1 ]'
ok "2:sh back" 'tmux list-windows -t main -F "#I:#W" | grep -qx 2:sh'
# tmux detach: foot exits by itself -> reopened
p2=$(termpid); tmux detach-client -s main; for i in $(seq 40); do [ "$(termpid)" != $p2 ] && [ "$(tmux list-clients -t main | wc -l)" = 1 ] && break; sleep 0.25; done
ok "detach reopens foot" '[ "$(termpid)" != $p2 ]'
# text size: 6.25 -> 68 columns (spec 3.2)
echo 6.25 > /run/vegas-ui/fontsize; p3=$(termpid); kill $p3
for i in $(seq 40); do [ "$(termpid)" != $p3 ] && [ "$(tmux list-clients -t main | wc -l)" = 1 ] && break; sleep 0.25; done; sleep 0.7
echo "size at 6.25: $(cw)"; ok "68 columns at 6.25" '[ "$(cw | cut -dx -f1)" = 68 ]'
grim $D/term-6.25.png
echo 7.25 > /run/vegas-ui/fontsize; p4=$(termpid); kill $p4
for i in $(seq 40); do [ "$(termpid)" != $p4 ] && [ "$(tmux list-clients -t main | wc -l)" = 1 ] && break; sleep 0.25; done; sleep 0.7
# Mac attach: a 200x50 client in group session "mac" must not resize the phone's windows
before=$(cw)
script -qfc "stty cols 200 rows 50; tmux new -A -s mac -t main -f ignore-size" /dev/null < <(sleep 30) >/dev/null 2>&1 & MP=$!
for i in $(seq 40); do tmux has-session -t '=mac' 2>/dev/null && [ "$(tmux list-clients -t mac | wc -l)" = 1 ] && break; sleep 0.25; done; sleep 0.5
ok "mac client attached" '[ "$(tmux list-clients -t mac | wc -l)" = 1 ]'
ok "phone size unchanged ($before -> $(cw))" '[ "$(cw)" = "$before" ]'
ok "group attached = 2" '[ "$(tmux display -p -t main "#{session_group_attached}")" = 2 ]'
grim $D/term-mac.png
kill $MP 2>/dev/null; tmux kill-session -t mac 2>/dev/null
# fast-exit backoff: make foot fail instantly 6 times (bad font size is clamped, so use a broken tmux target)
# (skipped: vegas-term has no hook; covered by reading the loop)
# glance window
echo glance > /run/vegas-ui/state; rm -f /run/vegas-ui/pin
VEGAS_UI_LIB=$O/usr/lib/vegas/ui python3 $O/usr/lib/vegas/vegas-glance & GP=$!
for i in $(seq 30); do [ "$(mapped vegas-glance)" = 1 ] && break; sleep 0.1; done
echo "glance mapped after ~$((i*100)) ms"; sleep 1.2
ok "glance mapped" '[ "$(mapped vegas-glance)" = 1 ]'
ok "glance fullscreen" 'swaymsg -t get_tree | python3 -c "import json,sys
def walk(n):
  if n.get(\"app_id\")==\"vegas-glance\": return n
  for c in n.get(\"nodes\",[])+n.get(\"floating_nodes\",[]):
    r=walk(c)
    if r: return r
g=walk(json.load(sys.stdin)); print(g[\"fullscreen_mode\"], g[\"rect\"]); sys.exit(0 if g[\"fullscreen_mode\"]==1 and g[\"rect\"][\"width\"]==360 and g[\"rect\"][\"height\"]==796 else 1)"'
echo "glance geom: $(cat /run/vegas-ui/glance-geom)"
ok "glance 20 columns" '[ "$(cut -d" " -f1 /run/vegas-ui/glance-geom)" = 20 ]'
ok "term still 60 under glance" '[ "$(cw | cut -dx -f1)" = 60 ]'
grim $D/glance.png
echo "n=3 max=6 hl=4 msg=" > /run/vegas-ui/pin; echo pin > /run/vegas-ui/state; sleep 1; grim $D/pin.png
echo glance > /run/vegas-ui/state
# landscape
swaymsg -q 'output HEADLESS-1 transform 90; gaps left all set 32; gaps right all set 16; gaps bottom all set 10'; sleep 1.5
echo "landscape glance geom: $(cat /run/vegas-ui/glance-geom)"; grim $D/glance-land.png
echo pin > /run/vegas-ui/state; sleep 1; grim $D/pin-land.png
kill $GP; wait $GP 2>/dev/null; sleep 0.3
ok "glance gone after kill" '[ "$(mapped vegas-glance)" = 0 ]'
echo "landscape term: $(cw)"; grim $D/term-land.png
wtype -s 60000 -k Shift_L & KB=$!; sleep 0.5
# power menu, landscape then upright; moved by a virtual keyboard like vegas-keys' uinput (print only)
bash $O/usr/lib/vegas/vegas-menu full landscape > $B/m1 & MP=$!; sleep 1.2; grim $D/menu-land.png; wtype -k Escape; wait $MP; r1=$?
ok "menu Esc = cancel (exit 1)" '[ $r1 = 1 ] && [ ! -s $B/m1 ]'
swaymsg -q 'output HEADLESS-1 transform normal; gaps left all set 10; gaps right all set 10; gaps bottom all set 16'; sleep 1
bash $O/usr/lib/vegas/vegas-menu full upright > $B/m2 & MP=$!; sleep 1.2; grim $D/menu.png
wtype -k Down -k Down -k Down -k Down -k Down -k Down; sleep 0.3; grim $D/menu-hl.png; wtype -k Return; wait $MP
ok "menu Down x6 + Enter = Home" '[ "$(cat $B/m2)" = Home ]'
bash $O/usr/lib/vegas/vegas-menu full upright > $B/m3 & MP=$!; sleep 1.2
wtype -k Down -k Down -k Down -k Down -k Return; sleep 1; grim $D/menu-confirm.png; wtype -k Return; wait $MP
ok "Power off -> confirm -> Power off now" '[ "$(cat $B/m3)" = "Power off now" ]'
ok "no window moved to ws 2" '! swaymsg -t get_workspaces | grep -q "\"num\": 2"'
kill $KB 2>/dev/null
# cleanup (headless VM sway only)
pkill -f '^/bin/sh /usr/lib/vegas/vegas-term'; kill $(termpid) 2>/dev/null; tmux kill-server 2>/dev/null
swaymsg exit >/dev/null 2>&1; wait $SP 2>/dev/null
echo "== $pass passed, $fail failed"; rm -rf $B
