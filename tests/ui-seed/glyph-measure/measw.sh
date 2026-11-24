#!/bin/bash
# VM only: throwaway headless sway, one output+bar per case, grim; kills only the sway it started.
set -u
S=$(cd "$(dirname "$0")" && pwd); D=$1; shift; mkdir -p "$D"
export WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LANG=C.UTF-8 WLR_HEADLESS_OUTPUTS=$#
export XDG_RUNTIME_DIR=$(mktemp -d); C=$XDG_RUNTIME_DIR/sway.conf; : > $C; i=0
for c in "$@"; do i=$((i+1)); cat >> $C <<CFG
output HEADLESS-$i mode 1080x2388@60Hz scale 3 position $((i*3000)) 0 subpixel none bg #0b0f14 solid_color
bar {
    id m$i
    output HEADLESS-$i
    position top
    height 36
    font monospace 10
    workspace_buttons no
    tray_output none
    status_edge_padding 18
    status_command python3 $S/emitw.py $S/blocks.json $c
    colors {
        background #000000
        statusline #e0e0e0
    }
}
CFG
done
unset SWAYSOCK; sway -c $C >"$D/meas-sway.log" 2>&1 & SP=$!
sleep 6
export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock) WAYLAND_DISPLAY=$(basename $(ls $XDG_RUNTIME_DIR/wayland-* | grep -v lock | head -1))
i=0; for c in "$@"; do i=$((i+1)); grim -o HEADLESS-$i "$D/meas-$c.png"; done
kill $SP; wait $SP 2>/dev/null
