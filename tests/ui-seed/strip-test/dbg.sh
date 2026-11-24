export XDG_RUNTIME_DIR=$(mktemp -d) WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1
printf 'output HEADLESS-1 mode 1080x2388@60Hz scale 3 transform 90\nbar {\n status_command sh -c "env | grep -i sway >/tmp/barenv; sleep 100"\n}\n' > /tmp/dbg.conf
sway -c /tmp/dbg.conf >/dev/null 2>&1 & sleep 3
export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock)
cat /tmp/barenv; swaymsg -t get_outputs -r | python3 -c 'import json,sys; print([(o["name"],o["rect"]) for o in json.load(sys.stdin)])'
python3 -c 'import sys; sys.path.insert(0,"/path/to/repo/linux/debian/overlay/usr/lib/vegas/ui"); from vegasui import swayipc; print(swayipc.sock_path(), swayipc.output_width())'
swaymsg exit
