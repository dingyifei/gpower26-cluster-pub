#!/bin/bash
# VM only: headless throwaway sway, render the strip per scenario, grab the top 36 logical px (108 px)
set -u
S=$(cd "$(dirname "$0")" && pwd); D=$S/out; mkdir -p $D; OV=/path/to/repo/linux/debian/overlay
export PYTHONDONTWRITEBYTECODE=1 XDG_RUNTIME_DIR=$(mktemp -d) WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LANG=C.UTF-8
for sc in "$@"; do
  for tr in normal 90; do
    T=/tmp/vs-strip-$sc; python3 "$S/mk.py" "$T" "$sc"
    cat > "$D/sway.conf" <<CFG
output HEADLESS-1 mode 1080x2388@60Hz scale 3 bg #1d3b53 solid_color transform $tr
bar {
    position top
    height 36
    font monospace 10
    workspace_buttons no
    status_edge_padding 20
    status_command env VEGAS_SYSROOT=$T VEGAS_SBIN=$T/sbin $OV/usr/local/bin/vegas-status --bar 2>>$D/bar.err
    colors {
        background #000000
        statusline #e0e0e0
    }
}
CFG
    unset SWAYSOCK; sway -c "$D/sway.conf" >"$D/sway.log" 2>&1 & SP=$!
    sleep 4
    export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock) WAYLAND_DISPLAY=$(basename $(ls $XDG_RUNTIME_DIR/wayland-* | grep -v lock | head -1))
    grim -s 3 -g "0,0 $([ $tr = normal ] && echo 360 || echo 796)x36" "$D/$sc-$tr.png"
    kill $SP; wait $SP 2>/dev/null
  done
done
