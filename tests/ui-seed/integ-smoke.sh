#!/bin/bash
# Integration smoke test, VM only (vegas-deb, as root; never the phone): headless sway with the FINAL repo config
# (DSI-1 renamed HEADLESS-1, XDG_RUNTIME_DIR=/run/sway like the phone), the overlay installed at its real paths,
# vegas-keys running against a fake sysfs (DRYRUN) whose /run/vegas-ui is the real one. Screenshots -> integ-shots/.
# The headless test sway is ended with `swaymsg exit` at the end: this is the VM's throwaway compositor only.
set -u
D=$(cd "$(dirname "$0")" && pwd); SH=${SHOTS:-$D/integ-shots-v2}; mkdir -p $SH
O=/path/to/repo/linux/debian/overlay
pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
wait_for(){ local i; for i in $(seq ${2:-40}); do eval "$1" && return 0; sleep 0.25; done; return 1; }
pgrep -x sway >/dev/null && { echo "a sway already runs in the VM; stop it first" >&2; exit 2; }
tmux kill-server 2>/dev/null; rm -rf /run/vegas-ui /run/sway; mkdir -p /run/sway; chmod 700 /run/sway

# --- install the overlay (VM test box) -------------------------------------------------------------------------
install -d /usr/lib/vegas /etc/vegas
for f in vegas-session vegas-term vegas-kbd vegas-gestures vegas-menu vegas-glance vegas-keys swaystatus; do
  install -m755 $O/usr/lib/vegas/$f /usr/lib/vegas/$f; done
rm -rf /usr/lib/vegas/ui; cp -r $O/usr/lib/vegas/ui /usr/lib/vegas/ui; find /usr/lib/vegas/ui -name __pycache__ -prune -exec rm -rf {} +
for f in vegas-home vegas-net vegas-status; do install -m755 $O/usr/local/bin/$f /usr/local/bin/$f; done
for f in vegas-charge vegas-away vegas-hotspot vegas-usbshare; do install -m755 $O/usr/local/sbin/$f /usr/local/sbin/$f; done
sed 's/DSI-1/HEADLESS-1/g' $O/usr/local/sbin/vegas-rotate > /usr/local/sbin/vegas-rotate; chmod 755 /usr/local/sbin/vegas-rotate
install -m644 $O/etc/vegas/tmux-vegas.conf /etc/vegas/tmux-vegas.conf
[ -e /etc/tmux.conf.pre-vegas ] || cp /etc/tmux.conf /etc/tmux.conf.pre-vegas 2>/dev/null || touch /etc/tmux.conf.pre-vegas
install -m644 $O/etc/tmux.conf /etc/tmux.conf
rm -f /etc/vegas/kbd-v2 /etc/vegas/away
C=$(mktemp -d); sed 's/DSI-1/HEADLESS-1/g' $O/etc/vegas/sway/config > $C/config
ok "config differs from repo only in the output name" '[ "$(diff $O/etc/vegas/sway/config $C/config | grep -c "^>")" = "$(grep -c DSI-1 $O/etc/vegas/sway/config)" ]'

# --- vegas-keys against a fake sysfs, with the real /run/vegas-ui ---------------------------------------------
# One #5-like fake tree for EVERY reader (vegas-keys, the glance, the strip, Home: VEGAS_SYSROOT is exported into
# sway's environment below), so the screenshots agree (designer's 06-glance question: the glance read this tree
# while Home read the VM's own sysfs). /run/vegas-ui inside it is the real one (symlink).
K=$(mktemp -d)
put(){ mkdir -p "$(dirname "$K$1")"; printf '%b\n' "$2" > "$K$1"; }
put /sys/class/backlight/ktd3136-bl/brightness 889; put /etc/vegas/root-role main; put /etc/hostname vegas5
put /etc/debian_version 13.2; put /proc/uptime "274320.5 1000.0"
B=/sys/class/power_supply/battery
put $B/capacity 78; put $B/status "Not charging"; put $B/temp 312; put $B/current_now 0
put /sys/class/power_supply/primary_chg/online 1
put /sys/class/thermal/thermal_zone0/type soc_max; put /sys/class/thermal/thermal_zone0/temp 41000
for pm in policy0:2000000 policy6:2400000; do
  put /sys/devices/system/cpu/cpufreq/${pm%:*}/cpuinfo_max_freq ${pm#*:}; put /sys/devices/system/cpu/cpufreq/${pm%:*}/scaling_max_freq ${pm#*:}; done
put /sys/class/net/wlan0/operstate up; put /sys/class/net/usb0/carrier 1
put /run/vegas-test/ipv4/wlan0 192.0.2.57; put /run/vegas-test/ipv4/usb0 172.16.42.1
put /run/vegas-test/iw-link "Connected to aa:bb:cc:dd:ee:ff (on wlan0)\n\tSSID: harbour-guest\n\tfreq: 5180.0\n\tsignal: -52 dBm"
put /proc/net/tcp "  sl  local_address rem_address   st\n   0: 012A10AC:0016 022A10AC:C822 01 0"
put /proc/net/tcp6 "  sl  local_address rem_address st"
cp $O/etc/vegas/chargeguard.conf $K/etc/vegas/chargeguard.conf
put /run/vegas-chargeguard/want off; put /run/vegas-chargeguard/control "control: cmd"
put /run/vegas-chargeguard/override-state "override: none"
mkdir -p -m700 /run/vegas-ui; ln -s /run/vegas-ui $K/run/vegas-ui
VEGAS_SYSROOT=$K VEGAS_KEYS_DRYRUN=1 python3 /usr/lib/vegas/vegas-keys 2>$SH/vegas-keys.log & KP=$!
ok "vegas-keys made the ctl FIFO" 'wait_for "[ -p /run/vegas-ui/ctl ]"'

# --- sway, set up like the phone ------------------------------------------------------------------------------
export XDG_RUNTIME_DIR=/run/sway WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LANG=C.UTF-8
export VEGAS_SYSROOT=$K PYTHONDONTWRITEBYTECODE=1
unset WAYLAND_DISPLAY SWAYSOCK TMUX
choom -n -1000 -- bash -c "exec -a @sway sway -c $C/config" > $SH/sway.log 2>&1 & SP=$!
wait_for 'ls /run/sway/sway-ipc.*.sock >/dev/null 2>&1' 60
export SWAYSOCK=$(ls /run/sway/sway-ipc.*.sock | head -1) WAYLAND_DISPLAY=wayland-1
ok "wayland-1 like the phone" '[ -S /run/sway/wayland-1 ]'
ok "config: no errors" '! grep -iE "error|invalid|unknown" $SH/sway.log | grep -viE "xwayland|libinput|drm|seat|backend/|render|EGL|gles|vulkan|session"'
ok "foot (vegas-term) attached to main" 'wait_for "[ \"\$(tmux list-clients -t main 2>/dev/null | wc -l)\" = 1 ]" 80'
ok "keyboard v1 (stock wvkbd-mobintl) is the default" 'wait_for "pgrep -x wvkbd-mobintl >/dev/null" 40 && ! pgrep -x wvkbd-vegas >/dev/null'
sleep 3
TP=$(cat /run/vegas-ui/term.pid)
ok "term.pid is foot" '[ "$(cat /proc/$TP/comm)" = foot ]'
ok "choom: sway -1000, foot 0" '[ "$(cat /proc/$SP/oom_score_adj)" = -1000 ] && [ "$(cat /proc/$TP/oom_score_adj)" = 0 ]'
ok "choom: wvkbd 0" '[ "$(cat /proc/$(pgrep -x wvkbd-mobintl)/oom_score_adj)" = 0 ]'
ok "choom: vegas-gestures loop 0" '[ "$(cat /proc/$(pgrep -f "^/bin/sh /usr/lib/vegas/vegas-gestures" | head -1)/oom_score_adj)" = 0 ]'
ok "strip feed is vegas-status --bar (not the fallback)" 'wait_for "pgrep -f \"vegas-status --bar\$\" >/dev/null" 40'
ok "choom: strip feed 0" '[ "$(cat /proc/$(pgrep -f "vegas-status --bar$" | head -1)/oom_score_adj)" = 0 ]'
ok "strip feed wrote /run/vegas-ui/strip.pid (uictl pokes it on keyboard changes)" 'wait_for "[ -s /run/vegas-ui/strip.pid ]" 20 && tr "\\0" " " < /proc/$(cat /run/vegas-ui/strip.pid)/cmdline | grep -q "vegas-status --bar"'
ok "kbd state shown" '[ "$(cat /run/vegas-ui/kbd)" = shown ]'
ok "/run/vegas-ui is 0700" '[ "$(stat -c %a /run/vegas-ui)" = 700 ]'
W=$(tmux list-windows -t main -F '#I:#W' | tr '\n' ' ')
ok "tmux windows 0 home 1 net 2 sh 3 logs ($W)" '[ "$W" = "0:home 1:net 2:sh 3:logs " ]'
ok "current window 2:sh" '[ "$(tmux display -p -t main "#{window_index}")" = 2 ]'
ok "mouse on" '[ "$(tmux show -gv mouse)" = on ]'
ok "tmux bar on top" '[ "$(tmux show -gv status-position)" = top ]'
SZ=$(tmux display -p -t main '#{window_width}x#{window_height}')
ok "grid 60x37 with the keyboard up ($SZ)" '[ "$SZ" = 60x37 ]'
ok "vegas-term window mapped on ws 1" 'swaymsg -t get_tree | grep -q "\"app_id\": \"vegas-term\""'
grim $SH/01-term.png

# --- Home and Network draw at 60x37 ---------------------------------------------------------------------------
tmux select-window -t main:0; sleep 6
ok "vegas-home running" 'pgrep -f /usr/local/bin/vegas-home >/dev/null'
ok "Home in front: keyboard down (ruling 8), terminal 60x56" '[ "$(cat /run/vegas-ui/kbd)" = hidden ] && [ "$(tmux display -p -t main "#{window_width}x#{window_height}")" = 60x56 ]'
tmux capture-pane -p -t main:0 > $SH/home.txt
ok "Home drew (no traceback)" '! grep -q Traceback $SH/home.txt && [ $(grep -c . $SH/home.txt) -gt 8 ]'
grim $SH/02-home.png
tmux select-window -t main:1; sleep 6
ok "vegas-net running" 'pgrep -f /usr/local/bin/vegas-net >/dev/null'
tmux capture-pane -p -t main:1 > $SH/net.txt
ok "Network drew (no traceback)" '! grep -q Traceback $SH/net.txt && grep -q "IN RANGE" $SH/net.txt && grep -q "Hotspot" $SH/net.txt'
grim $SH/03-net.png
ok "Home/Net width 60" '[ "$(tmux display -p -t main:0 "#{pane_width}")" = 60 ] && [ "$(tmux display -p -t main:1 "#{pane_width}")" = 60 ]'

# --- keyboard: Hide key binding, show by signal, v2 opt-in -----------------------------------------------------
wtype -k XF86AudioMicMute; sleep 1
ok "Hide key (XF86AudioMicMute) -> kbd hidden" '[ "$(cat /run/vegas-ui/kbd)" = hidden ]'
SZ=$(tmux display -p -t main '#{window_width}x#{window_height}'); echo "  keyboard hidden: $SZ"
ok "terminal grows when the keyboard hides" '[ "${SZ#*x}" -gt 37 ]'
grim $SH/04-kbd-hidden.png
VEGAS_SYSROOT= PYTHONPATH=/usr/lib/vegas/ui python3 -c 'from vegasui import uictl, host; uictl.keyboard(host.Runner(), True)'; sleep 1
ok "uictl show -> kbd shown, 60x37 again" '[ "$(cat /run/vegas-ui/kbd)" = shown ] && [ "$(tmux display -p -t main "#{window_height}")" = 37 ]'
touch /etc/vegas/kbd-v2; pkill -x wvkbd-mobintl
ok "kbd-v2 opt-in runs wvkbd-vegas" 'wait_for "pgrep -x wvkbd-vegas >/dev/null" 20'
sleep 1.5; grim $SH/05-kbd-v2.png
rm -f /etc/vegas/kbd-v2; pkill -x wvkbd-vegas
ok "opt-out returns to wvkbd-mobintl" 'wait_for "pgrep -x wvkbd-mobintl >/dev/null" 20 && ! pgrep -x wvkbd-vegas >/dev/null'
sleep 1

# --- graphical program -> workspace 2 (for_window), back to 1 -------------------------------------------------
swaymsg -q exec 'choom -n 0 -- foot -a testprog sleep 30'
ok "program moved to workspace 2" 'wait_for "swaymsg -t get_workspaces | grep -q \"\\\"num\\\": 2\"" 20'
ok "terminal stays on workspace 1" 'swaymsg -t get_tree | python3 -c "import json,sys
def find(n, ws=None):
  if n.get(\"type\")==\"workspace\": ws=n.get(\"num\")
  if n.get(\"app_id\")==\"vegas-term\": print(ws); return True
  return any(find(c, ws) for c in n.get(\"nodes\",[])+n.get(\"floating_nodes\",[]))
find(json.load(sys.stdin))" | grep -qx 1'
# review 2026-11-23: a reopened terminal goes back to 1 even when the program on 2 has focus
term_respawned(){ local p; p=$(cat /run/vegas-ui/term.pid 2>/dev/null); [ -n "$p" ] && [ "$p" != "$TP" ] && kill -0 "$p" 2>/dev/null; }
placement(){ swaymsg -t get_tree | python3 -c 'import json,sys
def walk(n, ws=None):
  if n.get("type")=="workspace": ws=n.get("num")
  if n.get("app_id"): yield n["app_id"], ws
  for c in n.get("nodes",[])+n.get("floating_nodes",[]): yield from walk(c, ws)
d=dict(walk(json.load(sys.stdin))); print("  placement:", d); sys.exit(0 if d.get("vegas-term")==1 and d.get("testprog")==2 else 1)'; }
swaymsg -q 'workspace number 2'; kill "$TP"
ok "reopened terminal maps on ws 1, program stays on 2" 'wait_for term_respawned 40 && sleep 1 && placement'
TP=$(cat /run/vegas-ui/term.pid)
swaymsg -q '[app_id="testprog"] kill'; swaymsg -q 'workspace number 1'; sleep 0.5

# --- vegas-keys over ctl: brightness, screen off (touch mute), glance, menu ------------------------------------
tmux select-window -t main:0; sleep 1
echo 'brightness up' > /run/vegas-ui/ctl; sleep 0.7
ok "ctl brightness up -> vegas-keys wrote the backlight (1200)" '[ "$(cat $K/sys/class/backlight/ktd3136-bl/brightness)" = 1200 ] && [ "$(cat /run/vegas-ui/brightness)" = 1200 ]'
# R7 (24 Nov): a menu opened from "on" cancels back to "on", lit, touch live
echo menu > /run/vegas-ui/ctl
ok "R7: menu from on is up" 'wait_for "pgrep -x bemenu >/dev/null" 20 && [ "$(cat /run/vegas-ui/state)" = menu ]'
sleep 0.5; wtype -k Escape
ok "R7: Esc from a menu opened on 'on' -> state on" 'wait_for "[ \"\$(cat /run/vegas-ui/state)\" = on ]" 20'
ok "R7: touch not muted with the screen on (no sway-mute marker)" 'sleep 0.5; [ ! -e /run/vegas-ui/touch-sway-muted ]'
ok "R7: lit after that menu" '[ "$(cat $K/sys/class/backlight/ktd3136-bl/brightness)" = 1200 ]'
echo 'screen off' > /run/vegas-ui/ctl; sleep 0.7
ok "screen off: backlight 0, state off" '[ "$(cat $K/sys/class/backlight/ktd3136-bl/brightness)" = 0 ] && [ "$(cat /run/vegas-ui/state)" = off ]'
echo glance > /run/vegas-ui/ctl
ok "glance window mapped" 'wait_for "swaymsg -t get_tree | grep -q \"\\\"app_id\\\": \\\"vegas-glance\\\"\"" 20'
sleep 1.2; grim $SH/06-glance.png
ok "glance lit" '[ "$(cat $K/sys/class/backlight/ktd3136-bl/brightness)" = 1200 ] && [ "$(cat /run/vegas-ui/state)" = glance ]'
echo menu > /run/vegas-ui/ctl
ok "power menu (bemenu) up" 'wait_for "pgrep -x bemenu >/dev/null" 20'
sleep 1.2; grim $SH/07-menu.png
ok "menu: glance closed, state menu" '[ "$(cat /run/vegas-ui/state)" = menu ] && ! swaymsg -t get_tree | grep -q "\"app_id\": \"vegas-glance\""'
wtype -k Escape
# R7: a menu opened from the glance cancels back to the glance, touch muted, lit once the glance maps
ok "R7: Esc from a menu opened on the glance -> state glance" 'wait_for "[ \"\$(cat /run/vegas-ui/state)\" = glance ]" 20'
ok "R7: glance window back" 'wait_for "swaymsg -t get_tree | grep -q \"\\\"app_id\\\": \\\"vegas-glance\\\"\"" 20'
ok "R7: touch muted in the glance (sway-mute marker)" 'sleep 0.5; [ -e /run/vegas-ui/touch-sway-muted ]'
ok "R7: glance lit" 'sleep 1.2; [ "$(cat $K/sys/class/backlight/ktd3136-bl/brightness)" = 1200 ]'
ok "R7: glance times out to off (touch stays muted)" 'wait_for "[ \"\$(cat /run/vegas-ui/state)\" = off ]" 60 && [ -e /run/vegas-ui/touch-sway-muted ]'

# --- rotation: vegas-rotate writes the UI state; Home redraws two columns ---------------------------------------
# ruling 5 (23 Nov): the stock keyboard finds its landscape layer by itself on #5, so by default a rotation neither
# kills it nor overrides -H; only /etc/vegas/kbd-landscape-restart brings the restart back, with -H 144.
rm -f /etc/vegas/kbd-landscape-restart
KB0=$(pgrep -x wvkbd-mobintl)
/usr/local/sbin/vegas-rotate 90
ok "vegas-rotate 90 -> rotation 90, rotation-last 90" '[ "$(cat /run/vegas-ui/rotation)" = 90 ] && [ "$(cat /run/vegas-ui/rotation-last)" = 90 ]'
sleep 6; grim $SH/08-home-landscape.png
tmux select-window -t main:1; sleep 3; grim $SH/08n-net-landscape.png; tmux select-window -t main:0; sleep 1
LS=$(tmux display -p -t main '#{window_width}x#{window_height}'); echo "  landscape (Home in front, keyboard down): $LS"
ok "landscape: stock keyboard not restarted, no -H override (pid $KB0), Home in front has >= 20 rows ($LS)" '[ "$(pgrep -x wvkbd-mobintl)" = "$KB0" ] && ! pgrep -af wvkbd-mobintl | grep -q "H 1[45][04]" && [ "${LS#*x}" -ge 20 ]'
ok "landscape: Home drew (no traceback)" 'tmux capture-pane -p -t main:0 > $SH/home-landscape.txt; ! grep -q Traceback $SH/home-landscape.txt'
tmux select-window -t main:2; sleep 2
LK=$(tmux display -p -t main '#{window_width}x#{window_height}'); echo "  landscape (shell, keyboard up): $LK"
ok "landscape shell: keyboard back up (the person's choice)" '[ "$(cat /run/vegas-ui/kbd)" = shown ]'
# VM limit: the VM's wvkbd 0.15 does not re-detect landscape when the headless output's transform changes (it keeps
# the upright 250 px: 132x3 here). On #5 it did (designer, 23 Nov: 13 rows at 132 columns). The switch below is the
# fallback if #5 ever behaves like the VM; its row count is checked there.
echo "  (VM: stock wvkbd keeps its upright height after a live rotation: $LK; #5 measured 13 rows)"
grim $SH/08c-landscape-shell-kbd.png
wtype -k XF86AudioMicMute; sleep 0.5; /usr/local/sbin/vegas-rotate 270; sleep 2
ok "a hidden keyboard stays hidden across a rotation (not restarted)" '[ "$(cat /run/vegas-ui/kbd)" = hidden ] && [ "$(pgrep -x wvkbd-mobintl)" = "$KB0" ]'
ok "rotation-last 270" '[ "$(cat /run/vegas-ui/rotation-last)" = 270 ]'
grim $SH/08b-landscape-270-kbd-hidden.png
# the switch: restart in landscape with -H 144, keeping the hidden state
touch /etc/vegas/kbd-landscape-restart; pkill -x wvkbd-mobintl
ok "switch on, landscape: restarted at -H 144 --hidden" 'wait_for "pgrep -af wvkbd-mobintl | grep -q -- \"-H 144 .*--hidden\"" 40'
sleep 1; /usr/lib/vegas/vegas-kbd show; sleep 1.5
LK2=$(tmux display -p -t main '#{window_width}x#{window_height}')
ok "switch on, landscape shell with the keyboard up: terminal >= 10 rows ($LK2)" '[ "$(cat /run/vegas-ui/kbd)" = shown ] && [ "${LK2#*x}" -ge 10 ]'
grim $SH/08d-landscape-switch-kbd.png
/usr/lib/vegas/vegas-kbd hide; sleep 0.5
/usr/local/sbin/vegas-rotate normal; sleep 2
ok "switch on, upright: restarted at -H 250" 'wait_for "pgrep -af wvkbd-mobintl | grep -q -- \"-H 250\"" 40'
rm -f /etc/vegas/kbd-landscape-restart
pkill -USR2 -x 'wvkbd-(vegas|mobintl)'; echo shown > /run/vegas-ui/kbd; echo shown > /run/vegas-ui/kbd-user
/usr/local/sbin/vegas-rotate normal
ok "vegas-rotate normal -> rotation normal, rotation-last kept" '[ "$(cat /run/vegas-ui/rotation)" = normal ] && [ "$(cat /run/vegas-ui/rotation-last)" = 270 ]'
sleep 4
ok "upright again: keyboard -H 250, grid 60x37" 'pgrep -af wvkbd-mobintl | grep -q "H 250" && [ "$(tmux display -p -t main "#{window_width}x#{window_height}")" = 60x37 ]'

# --- review 2026-11-23: vegas-rotate leaves a keyboard alone when no vegas-kbd loop would restart it (old session) ---
ok "pgrep -x vegas-kbd finds the loop (vegas-rotate's guard)" 'pgrep -x vegas-kbd >/dev/null && pgrep -x vegas-gestures >/dev/null'
pkill -f '^/bin/sh /usr/lib/vegas/vegas-kbd'; pkill -x wvkbd-mobintl; sleep 0.5
swaymsg -q exec 'choom -n 0 -- wvkbd-mobintl -H 250 --fn "Sans 10"'
wait_for "pgrep -x wvkbd-mobintl >/dev/null" 20; OK1=$(pgrep -x wvkbd-mobintl)
/usr/local/sbin/vegas-rotate 90; sleep 1
ok "no vegas-kbd loop: rotation keeps the plain-exec keyboard (pid $OK1)" '[ "$(pgrep -x wvkbd-mobintl)" = "$OK1" ]'
/usr/local/sbin/vegas-rotate normal; sleep 0.5
pkill -x wvkbd-mobintl; swaymsg -q exec 'choom -n 0 -- /usr/lib/vegas/vegas-kbd'
ok "vegas-kbd loop back" 'wait_for "pgrep -x vegas-kbd >/dev/null && pgrep -x wvkbd-mobintl >/dev/null" 20'
sleep 2

# --- rulings of 24 Nov: one background (R1), each text size's grid with Home/Network drawn (R2, R4) ---------------
# (last: the four foot restarts take ~40 s, which would let vegas-keys' idle timers darken the screen before the ctl
# checks above)
px(){ grim -t ppm -g "$1 1x1" - 2>/dev/null | tail -c 3 | od -An -tx1 | tr -d ' \n'; }   # logical x,y -> rrggbb
tmux select-window -t main:0; wait_for '[ "$(cat /run/vegas-ui/kbd)" = hidden ]' 20; sleep 2   # keyboard down: bottom visible
ok "R1: sway output background is 0b0f14 (side gap, $(px 2,400))" '[ "$(px 2,400)" = 0b0f14 ]'
ok "R1: sway output background below the terminal ($(px 180,790))" '[ "$(px 180,790)" = 0b0f14 ]'
ok "R1: foot's own pad under the last row is 0b0f14 ($(px 180,778))" '[ "$(px 180,778)" = 0b0f14 ]'
ok "R1: foot runs with the UI colours" 'tr "\0" " " < /proc/$(cat /run/vegas-ui/term.pid)/cmdline | grep -q "colors.background=0b0f14 -o colors.foreground=d5dbe3"'
for pc in 8.25:51 7.25:60 6.25:68 5.75:72; do
  pt=${pc%:*}; cols=${pc#*:}; old=$(cat /run/vegas-ui/term.pid)
  echo $pt > /run/vegas-ui/fontsize; kill $old
  wait_for "[ -n \"\$(cat /run/vegas-ui/term.pid 2>/dev/null)\" ] && [ \"\$(cat /run/vegas-ui/term.pid)\" != $old ] && [ \"\$(tmux list-clients -t main 2>/dev/null | wc -l)\" = 1 ]" 80
  tmux select-window -t main:0; sleep 4
  G=$(tmux display -p -t main '#{window_width}x#{window_height}'); echo "  text size $pt: Home grid $G"
  ok "text size $pt: $cols columns, keyboard down ($G)" '[ "${G%x*}" = $cols ] && [ "$(cat /run/vegas-ui/kbd)" = hidden ]'
  tmux capture-pane -p -t main:0 > $SH/home-$cols.txt
  ok "text size $pt: Home drew, message line last, buttons at the bottom (Power on the last button row)" '! grep -q Traceback $SH/home-$cols.txt && grep -q "TRAVEL" $SH/home-$cols.txt && [ "$(grep -n "SSH" $SH/home-$cols.txt | head -1 | cut -d: -f1)" -lt "$(( $(grep -n "BRIGHTNESS" $SH/home-$cols.txt | cut -d: -f1) - 2 ))" ]'
  grim $SH/10-home-$cols.png
  tmux select-window -t main:1; sleep 3
  tmux capture-pane -p -t main:1 > $SH/net-$cols.txt
  ok "text size $pt: Network drew, R5 text" '! grep -q Traceback $SH/net-$cols.txt && grep -qE "Not scanned yet|No (other )?networks in range" $SH/net-$cols.txt'
  grim $SH/11-net-$cols.png
done
old=$(cat /run/vegas-ui/term.pid); echo 7.25 > /run/vegas-ui/fontsize; kill $old
wait_for "[ \"\$(cat /run/vegas-ui/term.pid 2>/dev/null)\" != $old ] && [ \"\$(tmux list-clients -t main 2>/dev/null | wc -l)\" = 1 ]" 80; sleep 2
TP=$(cat /run/vegas-ui/term.pid)
tmux select-window -t main:1; sleep 1
ok "back to 60 columns" '[ "$(tmux display -p -t main "#{window_width}")" = 60 ]'

# --- D10 and the end state ---------------------------------------------------------------------------------------
ok "sway alive the whole run" 'kill -0 $SP'
ok "vegas-keys alive, no handler errors" 'kill -0 $KP && ! grep -q "handler error\|timer error" $SH/vegas-keys.log'
ok "Home/Net never crashed" '! tmux capture-pane -p -t main:0 | grep -q Traceback && ! tmux capture-pane -p -t main:1 | grep -q Traceback'
ok "no __pycache__ written into the repo overlay" '[ -z "$(find $O -name __pycache__)" ]'
grim $SH/09-end.png
echo "== $pass passed, $fail failed"

# --- cleanup (VM only) ---------------------------------------------------------------------------------------------
kill $KP 2>/dev/null; wait $KP 2>/dev/null
pkill -f '^/bin/sh /usr/lib/vegas/vegas-(term|kbd|gestures)'; pkill -x wvkbd-mobintl; pkill -x wvkbd-vegas; pkill -x lisgd
tmux kill-server 2>/dev/null
swaymsg exit >/dev/null 2>&1; wait $SP 2>/dev/null
rm -rf $K $C /run/vegas-ui; cp /etc/tmux.conf.pre-vegas /etc/tmux.conf 2>/dev/null
