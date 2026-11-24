#!/bin/bash
# R6, VM only (vegas-deb): one throwaway headless sway per transform with one output + one bar per scenario (the
# real bar settings), grim each output; the PNGs are measured on the Mac (r6measure.py). Kills only the sway it
# started (never the phone's, never another test's). Usage: r6b.sh <outdir> scenario...  (vm/r6.sh plus VSENV and WAIT knobs; mk_r6.py found via MK_R6)
set -u; VSENV=${VSENV:-}
S=$(cd "$(dirname "$0")" && pwd); D=$1; shift; mkdir -p "$D"
OV=/path/to/repo/linux/debian/overlay
export PYTHONDONTWRITEBYTECODE=1 WLR_BACKENDS=headless WLR_RENDERER=pixman WLR_LIBINPUT_NO_DEVICES=1 LANG=C.UTF-8
export WLR_HEADLESS_OUTPUTS=$#
for tr in normal 90; do
  export XDG_RUNTIME_DIR=$(mktemp -d); C=$XDG_RUNTIME_DIR/sway.conf; : > $C; i=0
  for sc in "$@"; do
    i=$((i+1)); T=$XDG_RUNTIME_DIR/vs-r6-$sc; python3 "${MK_R6:-$(dirname "$0")/../status-tests/vm/mk_r6.py}" "$T" "$sc"
    if [ "$sc" = fallback ]; then     # the real swaystatus with vegas-status missing and sysfs moved into the tree
      sed -e "s#/usr/local/bin/vegas-status#$T/nonexistent/vegas-status#g" -e "s#/sys/#$T/sys/#g" \
        $OV/usr/lib/vegas/swaystatus > $T/swaystatus; chmod +x $T/swaystatus; cmd="$T/swaystatus"
    else
      cmd="env $VSENV VEGAS_SYSROOT=$T VEGAS_SBIN=$T/sbin $OV/usr/local/bin/vegas-status --bar"
    fi
    cat >> $C <<CFG
output HEADLESS-$i mode 1080x2388@60Hz scale 3 position $((i*3000)) 0 subpixel none bg #0b0f14 solid_color transform $tr
bar {
    id b$i
    output HEADLESS-$i
    position top
    height 36
    font monospace 10
    workspace_buttons no
    tray_output none
    status_edge_padding 18
    status_command $cmd 2>>$D/bar.err
    colors {
        background #000000
        statusline #e0e0e0
    }
}
CFG
  done
  unset SWAYSOCK; sway -c $C >"$D/sway-$tr.log" 2>&1 & SP=$!
  sleep ${WAIT:-7}
  export SWAYSOCK=$(ls $XDG_RUNTIME_DIR/sway-ipc.*.sock) WAYLAND_DISPLAY=$(basename $(ls $XDG_RUNTIME_DIR/wayland-* | grep -v lock | head -1))
  swaymsg -t get_outputs | python3 -c 'import json,sys; [print(o["name"], o["rect"]) for o in json.load(sys.stdin)]'
  i=0; for sc in "$@"; do i=$((i+1)); grim -o HEADLESS-$i "$D/$sc-$tr.png"; done
  kill $SP; wait $SP 2>/dev/null
done
