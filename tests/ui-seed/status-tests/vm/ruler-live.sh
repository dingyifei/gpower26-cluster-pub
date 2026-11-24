#!/bin/bash
# VM: --ruler on/off signals a real running feed (SigCgt check) and never signals a process without a handler
set -u; export PYTHONDONTWRITEBYTECODE=1 LANG=C.UTF-8
O=/path/to/repo/linux/debian/overlay; VS=$O/usr/local/bin/vegas-status
pass=0; fail=0; ok(){ if eval "$2"; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1"; fail=$((fail+1)); fi; }
T=/tmp/vs-ruler-live; python3 $(dirname $0)/mk.py $T normal
export VEGAS_SYSROOT=$T VEGAS_SBIN=$T/sbin SWAYSOCK=/nonexistent
mkfifo $T/in; sleep 60 > $T/in & HOLD=$!
python3 $VS --bar < $T/in > $T/out 2>$T/err & FP=$!
python3 -c 'import time; time.sleep(60)' vegas-status --bar & OLD=$!     # looks like a feed, no SIGUSR1 handler
sleep 1.5
ok "status lists the feed only" '$VS --ruler status | grep -q "follow it: $FP\$"'
R=$($VS --ruler on); echo "  $R"
ok "on: feed told" 'echo "$R" | grep -q "strip feed $FP told"'
sleep 0.7
ok "feed drew the ruler at once" 'tail -1 $T/out | grep -q "\"name\": \"ruler\""'
ok "handlerless lookalike untouched" 'kill -0 $OLD'
R=$($VS --ruler off); echo "  $R"; sleep 0.7
ok "off: strip back at once" 'tail -1 $T/out | grep -q "\"name\": \"home\""'
ok "feed alive, no traceback" 'kill -0 $FP && ! grep -q Traceback $T/err'
kill $FP $OLD $HOLD 2>/dev/null; wait 2>/dev/null; rm -rf $T
unset VEGAS_SYSROOT VEGAS_SBIN
ok "report on the VM's real tree" 'python3 $VS --report >/dev/null'
ok "glance once on the VM's real tree" 'COLS=20 ROWS=20 VEGAS_UI_LIB=$O/usr/lib/vegas/ui python3 $O/usr/lib/vegas/vegas-glance --once | grep -q "no gauge"'
echo "== $pass passed, $fail failed"
