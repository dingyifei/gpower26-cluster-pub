#!/usr/bin/env bash
# Build the vegas GKI kernel (ACK android13-5.15 @ 9b2308ac0ad6) in the OrbStack x86_64 VM.
#
#   linux/kernel/build.sh stock   # gki_defconfig only: control build, must reproduce config.stock
#   linux/kernel/build.sh b       # + fragment.config: route B kernel
#
# Expects ~/ack (repo checkout of kernel/manifest common-android13-5.15-2025-05, with common/ at the tag
# android13-5.15-2025-05_r14 and prebuilts/clang/host/linux-x86/clang-r450784e). Build tree stays in the VM
# (~/kout/<variant>); results are copied to linux/work/kernel/<variant>/.
set -Eeuo pipefail
VARIANT=${1:?usage: build.sh stock|b}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
ACK=${ACK:-$HOME/ack}
OUT=$HOME/kout/$VARIANT
DEST=$REPO/linux/work/kernel/$VARIANT
STOCK=$REPO/linux/work/stock/config.stock
EXPECT=9b2308ac0ad616788fb57ba688aa07f0ff221355

[ "$(git -C "$ACK/common" rev-parse HEAD)" = "$EXPECT" ] || { echo "common/ is not at $EXPECT" >&2; exit 1; }
CLANG=$ACK/prebuilts/clang/host/linux-x86/clang-r450784e/bin
export PATH=$CLANG:$ACK/prebuilts/build-tools/linux-x86/bin:$ACK/prebuilts/kernel-build-tools/linux-x86/bin:$PATH
# Match the stock version string: 5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692
MK=(make -C "$ACK/common" O="$OUT" ARCH=arm64 LLVM=1 LLVM_IAS=1 CC=clang
    KBUILD_BUILD_USER=build-user KBUILD_BUILD_HOST=build-host LOCALVERSION=-android13-8 -j"$(nproc)")

mkdir -p "$OUT" "$DEST"
"${MK[@]}" gki_defconfig
if [ "$VARIANT" = b ]; then
  "$ACK/common/scripts/kconfig/merge_config.sh" -m -O "$OUT" "$OUT/.config" "$HERE/fragment.config"
  "${MK[@]}" olddefconfig
  for o in DEVTMPFS FHANDLE AUTOFS_FS; do grep -q "^CONFIG_$o=y" "$OUT/.config" || { echo "CONFIG_$o did not stick" >&2; exit 1; }; done
fi

# Config drift report vs the stock embedded config (ignore toolchain/version lines)
filt() { grep -vE '^(CONFIG_(CC_VERSION_TEXT|CLANG_VERSION|LLD_VERSION|AS_VERSION|LD_VERSION|RUSTC|PAHOLE_VERSION|GCC_VERSION)|#)' "$1" | grep -v '^$' | sort; }
diff <(filt "$STOCK") <(filt "$OUT/.config") > "$DEST/config.diff" || true
echo "config lines differing from stock: $(grep -c '^[<>]' "$DEST/config.diff" || true)  (see $DEST/config.diff)"

"${MK[@]}" Image.gz modules 2>&1 | tail -n 3
cp "$OUT/arch/arm64/boot/Image.gz" "$OUT/arch/arm64/boot/Image" "$OUT/Module.symvers" "$OUT/.config" "$OUT/vmlinux" "$DEST/"
{ strings "$OUT/arch/arm64/boot/Image" | grep "^Linux version 5" | head -1 || true; } | tee "$DEST/version.txt"
