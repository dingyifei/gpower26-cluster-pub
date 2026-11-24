#!/bin/bash
# Offline test of vegasdisk on real f2fs in the arm64 VM (needs f2fs-tools, dmsetup):
#   orb -m vegas-deb sudo linux/tools/vegasdisk-test.sh linux/work/vegasdisk
# Stack like the phone: loop (raw "userdata") -> dm-linear offset 0 (stands in for default-key) -> f2fs.
set -Eeuo pipefail
VD=$(realpath "${1:?path to the arm64 vegasdisk}")
W=/var/tmp/vdtest; M=$W/mnt
ok() { echo "  PASS $*"; }
bad() { echo "  FAIL $*"; exit 1; }
must_fail() { local what=$1; shift; if "$@" >/tmp/vd.out 2>&1; then cat /tmp/vd.out; bad "$what was accepted"; else ok "$what refused: $(tail -1 /tmp/vd.out)"; fi; }
cleanup() { set +e; umount "$M" 2>/dev/null; dmsetup remove vt 2>/dev/null; dmsetup remove fakeud 2>/dev/null; [ -n "${LOOP:-}" ] && losetup -d "$LOOP"; }
trap cleanup EXIT
cleanup; rm -rf "$W"; mkdir -p "$M"
truncate -s 3G "$W/raw.img"; LOOP=$(losetup -f --show "$W/raw.img")
dmsetup create fakeud --table "0 $(blockdev --getsz "$LOOP") linear $LOOP 0"
mkfs.f2fs -q /dev/mapper/fakeud; mount -t f2fs /dev/mapper/fakeud "$M"

echo "== create 300 MiB in 100 MiB pieces"
"$VD" --test create "$M/vegas" 300 --piece-mib 100 | tee /tmp/vd.create
read -r ANCHOR UUID < <(sed -n 's/.*anchor=\([0-9]*\) uuid=\([0-9a-f]*\).*/\1 \2/p' /tmp/vd.create | tail -1)
[ -n "$UUID" ] && ok "anchor $ANCHOR uuid $UUID" || bad "no anchor"
"$VD" --test verify "$M/vegas" | grep -q 'verify OK' && ok verify || bad verify

echo "== map with f2fs unmounted (as on the phone: Android is not running), write a pattern"
umount "$M"
"$VD" --test map "$LOOP" "$ANCHOR" "$UUID" vt
SZ=$(blockdev --getsize64 /dev/mapper/vt); echo "  mapped $SZ bytes"
head -c $((16 << 20)) /dev/urandom > "$W/pat"; dd if="$W/pat" of=/dev/mapper/vt bs=1M oflag=direct status=none
dd if=/dev/urandom of=/dev/mapper/vt bs=1M seek=$(( SZ / 1048576 - 1 )) count=1 oflag=direct status=none   # last MiB
dmsetup remove vt
fsck.f2fs -f /dev/mapper/fakeud >/tmp/fsck.out 2>&1 && ok "fsck.f2fs clean after raw writes" || { tail /tmp/fsck.out; bad fsck; }
mount -t f2fs /dev/mapper/fakeud "$M"
"$VD" --test verify "$M/vegas" | grep -q 'verify OK' && ok "verify after raw writes" || bad verify2

echo "== grow to 500 MiB"
"$VD" --test grow "$M/vegas" 500 --piece-mib 100 | tail -2
"$VD" --test verify "$M/vegas" | grep -q 'verify OK' && ok "verify after grow" || bad verify3
umount "$M"
"$VD" --test map --ro "$LOOP" "$ANCHOR" "$UUID" vt
SZ2=$(blockdev --getsize64 /dev/mapper/vt); [ "$SZ2" -gt "$SZ" ] && ok "grew $SZ -> $SZ2" || bad "did not grow"
cmp -n $((16 << 20)) "$W/pat" /dev/mapper/vt && ok "pattern intact after grow" || bad "pattern changed"
dmsetup remove vt

echo "== f2fs GC stress with the pieces pinned"
mount -t f2fs /dev/mapper/fakeud "$M"
for r in 1 2 3; do
  for i in $(seq 1 40); do head -c $((8 << 20)) /dev/urandom > "$M/junk$i"; done; sync
  rm -f "$M"/junk{1..40..2}; sync
  D=$(basename "$(readlink -f /dev/mapper/fakeud)")
  echo 1 > /sys/fs/f2fs/$D/gc_urgent 2>/dev/null || true; sleep 3; echo 0 > /sys/fs/f2fs/$D/gc_urgent 2>/dev/null || true
  rm -f "$M"/junk*; sync
done
"$VD" --test verify "$M/vegas" | grep -q 'verify OK' && ok "verify after GC stress" || bad "moved by GC"
umount "$M"
"$VD" --test map --ro "$LOOP" "$ANCHOR" "$UUID" vt && cmp -n $((16 << 20)) "$W/pat" /dev/mapper/vt && ok "pattern intact after GC" || bad "pattern lost after GC"
dmsetup remove vt

echo "== refusals"
must_fail "wrong uuid" "$VD" --test map -n "$LOOP" "$ANCHOR" 00000000000000000000000000000000 vt
must_fail "wrong anchor" "$VD" --test map -n "$LOOP" $(( ANCHOR + 4096 )) "$UUID" vt
must_fail "non-userdata device without --test" "$VD" map -n "$LOOP" "$ANCHOR" "$UUID" vt
# corrupt the tail canary of the last piece: find it from the dry-run table (last target end + 0)
cp "$W/raw.img" "$W/raw.bak"
TAILOFF=$("$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt | awk '$3=="linear"{e=($5+$2)*512} END{print e}')
printf 'X' | dd of="$LOOP" bs=1 seek=$(( TAILOFF + 10 )) conv=notrunc status=none; sync
must_fail "corrupted canary" "$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt
cp "$W/raw.bak" "$W/raw.img"; blockdev --flushbufs "$LOOP"; echo 3 > /proc/sys/vm/drop_caches
printf 'X' | dd of="$LOOP" bs=1 seek=$(( ANCHOR + 4096 + 8 )) conv=notrunc status=none; sync
must_fail "corrupted extent table" "$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt
cp "$W/raw.bak" "$W/raw.img"; blockdev --flushbufs "$LOOP"; echo 3 > /proc/sys/vm/drop_caches
"$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt >/dev/null && ok "restored image maps again" || bad restore
# /data reformatted (factory reset): the old table + canaries are still on disk, the f2fs superblock is new
mkfs.f2fs -q -f -t 0 /dev/mapper/fakeud
must_fail "table from before a reformat" "$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt
grep -q 'formatted or reset' /tmp/vd.out && ok "  (refused for the superblock, not by chance)" || bad "refused for another reason"
cp "$W/raw.bak" "$W/raw.img"; blockdev --flushbufs "$LOOP"; echo 3 > /proc/sys/vm/drop_caches
"$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt >/dev/null && ok "restored image maps again" || bad restore2

echo "== map failure after DM_DEV_CREATE leaves no device (name taken by a foreign device -> refused before)"
dmsetup create vt --table "0 8 linear $LOOP 0"
must_fail "map onto an existing dm name" "$VD" --test map "$LOOP" "$ANCHOR" "$UUID" vt
dmsetup table vt | grep -q '^0 8 linear' && ok "foreign device untouched" || bad "foreign device changed"
dmsetup remove vt

echo "== failed create removes its own pieces"
mount -t f2fs /dev/mapper/fakeud "$M"
must_fail "piece size not a whole 2 MiB section" "$VD" --test create "$M/odd" 10 --piece-mib 3
grep -q 'multiple of 2 MiB' /tmp/vd.out || bad "refused for another reason"
must_fail "create larger than the free space" "$VD" --test create "$M/huge" 8192 --piece-mib 1024
grep -q 'fallocate' /tmp/vd.out && grep -q 'removed .*disk.0000' /tmp/vd.out || { cat /tmp/vd.out; bad "not an ENOSPC + undo"; }
[ ! -e "$M/huge" ] && ok "no orphan pieces left ($(grep -c removed /tmp/vd.out) removed)" || { ls -l "$M/huge"; bad "orphans left"; }
umount "$M"

echo "== delete"
mount -t f2fs /dev/mapper/fakeud "$M"
must_fail "delete with wrong uuid" "$VD" --test delete "$M/vegas" 00000000000000000000000000000000
"$VD" --test delete "$M/vegas" "$UUID" && [ ! -e "$M/vegas" ] && ok deleted || bad delete
umount "$M"
must_fail "map after delete (table scrubbed)" "$VD" --test map -n "$LOOP" "$ANCHOR" "$UUID" vt
echo "== re-create over the freed blocks (they still hold the old random pattern): data start must read as zeros"
mount -t f2fs /dev/mapper/fakeud "$M"
head -c $((1800 << 20)) /dev/urandom > "$M/junk" 2>/dev/null || true; sync; rm -f "$M/junk"; sync   # stale data in free blocks
"$VD" --test create "$M/vegas" 300 --piece-mib 100 > /tmp/vd.create2
read -r A2 U2 < <(sed -n 's/.*anchor=\([0-9]*\) uuid=\([0-9a-f]*\).*/\1 \2/p' /tmp/vd.create2 | tail -1)
umount "$M"
echo "  anchor $ANCHOR -> $A2"
"$VD" --test map --ro "$LOOP" "$A2" "$U2" vt >/dev/null
cmp -n $((1 << 20)) /dev/mapper/vt /dev/zero && ok "first MiB of the new disk is zero" || bad "stale data at the start of a new disk"
cmp -s -i $((1 << 20)):0 -n $((1 << 20)) /dev/mapper/vt /dev/zero && echo "  (note: 2nd MiB is zero too, the stale-data case was not exercised)" || ok "  (2nd MiB holds stale data, so the zeroing did the work)"
dmsetup remove vt
echo "ALL PASS"
