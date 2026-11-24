#!/bin/bash
# VM only: orb -m vegas-deb sudo bash kbd-integ.sh
# Keyboard rule end to end (designer ruling 8 + 5): the real tmux-vegas.conf hook, vegas-kbd verbs and loop,
# vegas-gestures' swipe command, the sway Hide binding's command, vegas-rotate's landscape switch. A fake
# wvkbd-mobintl records its argv and the signals it gets. Runs in its own PID + mount namespace with tmpfs over
# /run/vegas-ui and /usr/lib/vegas, so pkill/pgrep and the /run files never reach anything else in the VM.
if [ "${1:-}" != --inside ]; then exec unshare -pfm --mount-proc bash "$0" --inside; fi
set -u
O=/path/to/repo/linux/debian/overlay
export PYTHONDONTWRITEBYTECODE=1
T=$(mktemp -d)
mount -t tmpfs -o mode=700 none /run 2>/dev/null || true; mkdir -p -m 700 /run/vegas-ui
mkdir -p /usr/lib/vegas; mount -t tmpfs none /usr/lib/vegas
cp -a $O/usr/lib/vegas/. /usr/lib/vegas/; find /usr/lib/vegas -name __pycache__ -prune -exec rm -rf {} +
pass=0; fail=0
ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1  [kbd=$(cat /run/vegas-ui/kbd 2>/dev/null) user=$(cat /run/vegas-ui/kbd-user 2>/dev/null) fake=$(cat $T/fake 2>/dev/null)]"; fail=$((fail+1)); fi; }
mkdir -p $T/bin
cat > $T/bin/wvkbd-mobintl <<EOF
#!/usr/bin/python3
import signal, sys, time
open("$T/argv", "a").write(" ".join(sys.argv[1:]) + "\n")
st = "hidden" if "--hidden" in sys.argv else "shown"
def put(s): open("$T/fake", "w").write(s)
put(st)
signal.signal(signal.SIGUSR1, lambda *a: put("hidden"))
signal.signal(signal.SIGUSR2, lambda *a: put("shown"))
while True: time.sleep(1)
EOF
printf '#!/bin/sh\nexit 0\n' > $T/bin/swaymsg
chmod +x $T/bin/*
export PATH=$T/bin:$PATH
wait_for(){ for _ in $(seq 40); do eval "$1" && return 0; sleep 0.1; done; return 1; }
state(){ echo "$(cat /run/vegas-ui/kbd 2>/dev/null)/$(cat $T/fake 2>/dev/null)"; }
is(){ wait_for "[ \"\$(state)\" = $1/$1 ]"; }

# ---- the keyboard loop (stock keyboard, upright)
/usr/lib/vegas/vegas-kbd & KL=$!
wait_for '[ -s $T/argv ]'
ok "loop: stock keyboard upright -H 250, shown" '[ "$(tail -1 $T/argv)" = "-H 250 --fn Sans 10" ] && is shown'

# ---- tmux session like vegas-session, with the real conf (hook)
export TMUX_TMPDIR=$T
tmux -f $O/etc/vegas/tmux-vegas.conf new-session -d -s main -n home -x 60 -y 38 "sleep 600"
for w in "1 net" "2 sh" "3 logs"; do set -- $w; tmux new-window -d -t main:$1 -n $2 "sleep 600"; done
ok "hook installed" 'tmux show-hooks -g session-window-changed | grep -q "vegasui.uictl kbd auto"'
ok "bar right side counts clients (0 attached, not ' attached')" '[ "$(tmux display -p -t main "#{T:status-right}")" = "0 attached" ]'
tmux select-window -t main:2; sleep 0.5
ok "shell window: shown" 'is shown'
tmux select-window -t main:0
ok "Home in front: hidden" 'is hidden'
ok "  choice remembered as shown" '[ "$(cat /run/vegas-ui/kbd-user)" = shown ]'
tmux select-window -t main:1
ok "Network in front: hidden" 'is hidden'
tmux select-window -t main:3
ok "back to a shell window: shown again" 'is shown'
/usr/lib/vegas/vegas-kbd hide            # e.g. the Hide key on a shell window
ok "Hide on a shell: hidden, choice hidden" 'is hidden && [ "$(cat /run/vegas-ui/kbd-user)" = hidden ]'
tmux select-window -t main:0; sleep 0.4; tmux select-window -t main:2
ok "Home and back: stays hidden" 'sleep 0.4; is hidden'
# the bottom-edge swipe: run the exact lisgd command string from vegas-gestures
SWIPE=$(sed -n 's/^KBD_SHOW="\(.*\)"$/\1/p' /usr/lib/vegas/vegas-gestures)
sh -c "$SWIPE"
ok "swipe up: shown, choice shown" 'is shown && wait_for "[ \"\$(cat /run/vegas-ui/kbd-user)\" = shown ]"'
# the Hide key: the command of the sway binding
HIDECMD=$(sed -n 's/^bindsym XF86AudioMicMute exec //p' $O/etc/vegas/sway/config)
sh -c "$HIDECMD"; ok "Hide key binding command hides" 'is hidden'
sh -c "$SWIPE"; is shown
# a text field on Network: field-on from a live process while Network is in front
tmux select-window -t main:1; is hidden
bash -c '/usr/lib/vegas/vegas-kbd field-on net; echo $$ > '$T'/holder; sleep 30' & HOLD=$!
ok "field on Network: shown" 'is shown'
ok "  kbd-field-net holds the field's process" 'wait_for "[ -s $T/holder ]" && [ "$(cat /run/vegas-ui/kbd-field-net)" = "$(cat $T/holder)" ]'
tmux select-window -t main:0; ok "Home (no field): hidden" 'is hidden'
tmux select-window -t main:1; ok "back to Network with the field open: shown" 'is shown'
kill $HOLD; wait $HOLD 2>/dev/null
tmux select-window -t main:0; sleep 0.3; tmux select-window -t main:1
ok "the field's process died: Network keeps it hidden" 'is hidden'
bash -c '/usr/lib/vegas/vegas-kbd field-on net; /usr/lib/vegas/vegas-kbd field-off net'
ok "field-off: hidden, file gone" 'is hidden && [ ! -e /run/vegas-ui/kbd-field-net ]'
# the Mac's grouped session switching windows must not change the phone's rule
tmux new-session -d -s mac -t main; tmux select-window -t mac:2; sleep 0.5
ok "Mac session to a shell window, phone on Network: still hidden" 'is hidden'
sh -c "$SWIPE"; is shown                 # the phone user swipes the keyboard up on Network (no field)
tmux select-window -t mac:3; sleep 0.5; tmux select-window -t mac:0; sleep 0.5
ok "Mac switching its own windows leaves a swiped-up keyboard alone" 'is shown'
/usr/lib/vegas/vegas-kbd hide; is hidden; tmux select-window -t main:2; is hidden   # (choice now hidden)
sh -c "$SWIPE"; is shown; tmux select-window -t main:1
ok "main itself to Network: the rule still applies (hidden)" 'is hidden'
# a window closing while in front (e.g. `exit` in a window from + new)
tmux new-window -t main:4 -n x "sleep 600"; ok "new shell window: shown" 'is shown'
tmux select-window -t main:4; tmux select-window -t main:0; is hidden; tmux select-window -t main:4; is shown
tmux kill-window -t main:4; sleep 0.5
w=$(tmux display -p -t main '#{window_index}'); echo "  after kill main is on window $w"
if [ "$w" -le 1 ]; then ok "closed window -> Home/Network: hidden" 'is hidden'; else ok "closed window -> shell: shown" 'is shown'; fi
ok "bar right side with the Mac grouped" '[ "$(tmux display -p -t main "#{T:status-right}")" = "0 attached" ]'
tmux select-window -t main:2; is shown

# ---- keyboard restart keeps the shown/hidden state; landscape (ruling 5)
mkdir -p $T/sock; python3 -c "import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.listen(); import time; time.sleep(120)" $T/sock/sway-ipc.sock & SK=$!
wait_for '[ -S $T/sock/sway-ipc.sock ]'; export SWAYSOCK=$T/sock/sway-ipc.sock
n0=$(wc -l < $T/argv)
bash $O/usr/local/sbin/vegas-rotate 90
sleep 1.5
ok "rotate 90 without the switch: keyboard not restarted" '[ "$(wc -l < $T/argv)" = $n0 ] && [ "$(cat /run/vegas-ui/rotation)" = 90 ]'
export VEGAS_KBD_LANDSCAPE_RESTART=$T/kbd-landscape-restart; : > $VEGAS_KBD_LANDSCAPE_RESTART
kill $KL; wait $KL 2>/dev/null; /usr/lib/vegas/vegas-kbd & KL=$!     # loop restarted so it sees the switch env
wait_for '[ "$(wc -l < $T/argv)" -gt $n0 ]'; n1=$(wc -l < $T/argv)
ok "switch on, rotation 90: -H 144" '[ "$(tail -1 $T/argv)" = "-H 144 --fn Sans 10" ]'
/usr/lib/vegas/vegas-kbd hide; is hidden
bash $O/usr/local/sbin/vegas-rotate normal
wait_for '[ "$(wc -l < $T/argv)" -gt $n1 ]'
ok "switch on, rotate to upright: restarted with -H 250 --hidden (state kept)" '[ "$(tail -1 $T/argv)" = "-H 250 --fn Sans 10 --hidden" ] && is hidden'
n2=$(wc -l < $T/argv); bash $O/usr/local/sbin/vegas-rotate 270
wait_for '[ "$(wc -l < $T/argv)" -gt $n2 ]'
ok "switch on, rotate 270: restarted with -H 144" '[ "$(tail -1 $T/argv)" = "-H 144 --fn Sans 10 --hidden" ]'
rm -f $VEGAS_KBD_LANDSCAPE_RESTART; n3=$(wc -l < $T/argv); bash $O/usr/local/sbin/vegas-rotate normal; sleep 1.5
ok "switch removed: no restart on rotation" '[ "$(wc -l < $T/argv)" = $n3 ]'

kill $KL $SK 2>/dev/null; pkill -x wvkbd-mobintl; tmux kill-server 2>/dev/null
echo "== $pass passed, $fail failed"
umount /usr/lib/vegas 2>/dev/null; rm -rf $T
[ $fail = 0 ]
