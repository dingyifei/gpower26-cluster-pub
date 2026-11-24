#!/usr/bin/env bash
# Struct-layout gate: compare every struct between the control build (stock config) and a variant build.
# Run in the VM:  linux/tools/btfdiff.sh linux/work/kernel/stock/vmlinux linux/work/kernel/b/vmlinux
# 1) sizes of all structs/unions (pahole --sizes); 2) full member layout of the structs vendor modules touch most.
# Any difference in a struct that a stock module uses is a stop: CRCs do not always see layout changes (PR-5).
set -Eeuo pipefail
A=${1:?control vmlinux}; B=${2:?variant vmlinux}
OUT=$(dirname "$B")/btfdiff; mkdir -p "$OUT"
pahole --sizes "$A" 2>/dev/null | sort > "$OUT/sizes.control"
pahole --sizes "$B" 2>/dev/null | sort > "$OUT/sizes.variant"
diff "$OUT/sizes.control" "$OUT/sizes.variant" > "$OUT/sizes.diff" || true
# Added structs (new code) are fine; a struct present in both builds with another size, or one that vanished, is not.
n=$(python3 - "$OUT/sizes.control" "$OUT/sizes.variant" <<'PY'
import sys
def load(f):
    d = {}
    for l in open(f):
        p = l.split()
        if len(p) >= 3: d.setdefault(p[0], set()).add((p[1], p[2]))
    return d
a, b = load(sys.argv[1]), load(sys.argv[2])
bad = [k for k in a if k not in b or a[k] != b[k]]
for k in bad: print("CHANGED/REMOVED", k, sorted(a[k]), sorted(b.get(k, [])), file=sys.stderr)
print(f"added={len([k for k in b if k not in a])}", file=sys.stderr)
print(len(bad))
PY
)
echo "structs changed or removed: $n (see $OUT/sizes.diff)"
rc=0
for s in task_struct mm_struct file inode super_block dentry sk_buff net_device device module cred signal_struct; do
  if ! diff <(pahole -C "$s" "$A" 2>/dev/null) <(pahole -C "$s" "$B" 2>/dev/null) > "$OUT/$s.diff"; then
    echo "LAYOUT DIFF: $s"; rc=1
  fi
done
[ "$n" -eq 0 ] && [ $rc -eq 0 ] && echo "btfdiff: no layout differences" && exit 0
echo "btfdiff: differences found, inspect $OUT before flashing"; exit 1
