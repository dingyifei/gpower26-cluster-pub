#!/bin/bash
# VM only (as the normal user; uses sudo to place /etc/firefox-esr/vegas.js): does Debian's firefox-esr read it?
# Headless screenshots of a page printing window.devicePixelRatio, fresh profiles, without and with the file.
set -u
O=/path/to/repo/linux/debian/overlay
D=$(cd "$(dirname "$0")" && pwd); T=$(mktemp -d); trap 'rm -rf $T; sudo rm -f /etc/firefox-esr/vegas.js' EXIT
page='data:text/html,<div style="font-size:40px">DPR=<script>document.write(window.devicePixelRatio)</script></div>'
shot(){ mkdir -p $T/p$1; HOME=$T timeout 90 firefox-esr --headless --profile $T/p$1 --no-remote --window-size 400,120 --screenshot $T/$1.png "$page" >/dev/null 2>&1; cp $T/$1.png $D/ff-dpr-$1.png; }
sudo rm -f /etc/firefox-esr/vegas.js; shot without
sudo install -m 644 $O/etc/firefox-esr/vegas.js /etc/firefox-esr/vegas.js; shot with
python3 - "$D" <<'PY'
import sys, struct
for n in ("without", "with"):
    f = open(f"{sys.argv[1]}/ff-dpr-{n}.png", "rb").read()
    print(n, "png %dx%d" % struct.unpack(">II", f[16:24]))
PY
