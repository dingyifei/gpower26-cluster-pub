export XDG_RUNTIME_DIR=$(mktemp -d) WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
OV=/path/to/repo/linux/debian/overlay
printf 'output HEADLESS-1 mode 1080x2388@60Hz scale 3 transform 90\nbar {\n status_command /path/to/scratch/ui/strip-test/barwrap.sh\n}\n' > /tmp/dbg.conf
sway -c /tmp/dbg.conf >/dev/null 2>&1 & sleep 4
export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock)
swaymsg output HEADLESS-1 transform normal >/dev/null; sleep 2
swaymsg exit
cut -c1-120 /tmp/bar2.out | head; grep -o '"min_width": [0-9]*' /tmp/bar2.out; cat /tmp/bar2.err
