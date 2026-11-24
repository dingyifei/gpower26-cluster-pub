#!/usr/bin/env bash
# Compress a vegas-freedom partition-dump dir into a gitignored archive under backups/.
# Space-saving reuse: the FIRST phone of a build is archived in full ("_stock_"); later
# same-build phones store only partitions whose SHA-256 differs from that reference
# ("_delta_"), i.e. the device-unique set (nvram/nvdata/persist/protect*/seccfg/cid/...).
# Build-identical images (super/system/md1img/boot/vbmeta/...) are reused from the reference.
#   scripts/archive_backup.sh [vegas-freedom/backups/stock_<ts>]   (default: newest stock_* dir)
set -euo pipefail   # a failed tar must not leave a valid-looking archive behind
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$(ls -dt "$ROOT"/vegas-freedom/backups/stock_* 2>/dev/null | head -1)}"
[ -d "$SRC" ] || { echo "No dump dir found. Pass one explicitly." >&2; exit 1; }
[ -f "$SRC/SHA256SUMS" ] || { echo "Dump has no SHA256SUMS (incomplete?): $SRC" >&2; exit 1; }
command -v zstd >/dev/null || { echo "zstd not installed (brew install zstd)" >&2; exit 1; }
gp() { sed -n "s/^\[$1\]: \[\(.*\)\]/\1/p" "$SRC/getprop.txt" 2>/dev/null; }
SERIAL="$(gp ro.serialno)";        SERIAL="${SERIAL:-unknown}"
BUILD="$(gp ro.build.display.id)"; BUILD="${BUILD:-unknown}"
STAMP="$(basename "$SRC" | sed -e 's/^stock_//' -e "s/_${SERIAL}\$//")"   # phone.sh names dirs stock_<ts>_<serial>
META="SHA256SUMS getprop.txt name_map.txt partitions_by-name.txt proc_partitions.txt backup.log"

# Reference = first FULL (_stock_) archive for this build from a DIFFERENT serial.
REF="$(ls "$ROOT"/backups/*_"${BUILD}"_stock_*.tar.zst 2>/dev/null | grep -v "/${SERIAL}_" | head -1 || true)"

if [ -z "$REF" ]; then
  OUT="$ROOT/backups/${SERIAL}_${BUILD}_stock_${STAMP}.tar.zst"
  echo "Full archive (first phone of build $BUILD) -> $OUT"
  tar -C "$(dirname "$SRC")" -cf - "$(basename "$SRC")" | zstd -T0 -3 -q -f -o "$OUT.part"
else
  echo "Reference for build $BUILD: $(basename "$REF")"
  # macOS tar is bsdtar: patterns match natively (GNU tar would need --wildcards).
  REFSUMS="$(zstd -dc "$REF" | tar -xOf - '*/SHA256SUMS' | awk '{print $1}' | sort -u)"
  [ -n "$REFSUMS" ] || { echo "could not read SHA256SUMS from reference $REF" >&2; exit 1; }
  # Partition .img files whose sha256 is NOT in the reference = device-unique / differing.
  uniq_files=()
  while read -r h f; do
    case "$f" in *.img) ;; *) continue;; esac
    grep -qxF "$h" <<<"$REFSUMS" || uniq_files+=("$f")
  done < "$SRC/SHA256SUMS"
  OUT="$ROOT/backups/${SERIAL}_${BUILD}_delta_${STAMP}.tar.zst"
  echo "Delta archive (reuse build images from reference) -> $OUT"
  echo "  device-unique partitions stored: ${uniq_files[*]:-none}"
  echo "build images reused from: $(basename "$REF")" > "$SRC/REUSES.txt"
  b="$(basename "$SRC")"
  printf '%s\n' ${uniq_files[@]+"${uniq_files[@]}"} $META REUSES.txt | sed "s#^#$b/#" \
    | tar -C "$(dirname "$SRC")" -cf - -T - | zstd -T0 -3 -q -f -o "$OUT.part"
fi
zstd -tq "$OUT.part" && mv "$OUT.part" "$OUT"   # only a complete, verified archive gets the final name
echo "Done: $(du -h "$OUT" | cut -f1)  $OUT"
echo "Contents (head):"; { zstd -dc "$OUT" | tar -tf - | head -8; } || true
