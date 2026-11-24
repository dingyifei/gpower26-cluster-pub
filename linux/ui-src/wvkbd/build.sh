#!/usr/bin/env bash
# Build keyboard v2 (design page "Vegas Touch UI" draft 6, Keyboard v2; spec 6.2): wvkbd 0.21 with our layout,
# installed on the phone as /usr/bin/wvkbd-vegas. Runs natively in the arm64 Debian VM, no sudo:
#   orb -m vegas-deb linux/ui-src/wvkbd/build.sh
# Build deps (once, in the VM): sudo apt-get install build-essential pkg-config libwayland-dev libwayland-bin \
#   libxkbcommon-dev libpango1.0-dev libcairo2-dev dpkg-dev
# Source: the vendored tree linux/work/ref/moto-g-power-2025-omarchy/vendor/wvkbd (0.21 + upstream e14b53a, plus an
# opt-in WVKBD_IMMEDIATE_DRAW=1 patch) if present, else the upstream v0.21 tarball pinned by sha256. WVKBD_SRC=<dir>
# overrides. Our files: layout.vegas.h, config.vegas.h, *.patch (here); keymap.vegas.h = upstream keymap.deskintl.h.
# Output (gitignored) in linux/work/wvkbd-vegas/: wvkbd-vegas (binary), wvkbd-vegas_<ver>_arm64.deb,
# wvkbd-vegas-<ver>-source.tar.gz (the exact tree built: GPLv3 corresponding source), BUILD-INFO.
# wvkbd is GPLv3; it stays out of the repo's MIT tree (only our two GPL layout headers live here).
set -Eeuo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../../.." && pwd)
[ -d "$REPO/linux/debian/overlay" ] || { echo "build.sh: cannot find the repo root from $HERE" >&2; exit 1; }
OUT=$REPO/linux/work/wvkbd-vegas
VER=0.21-vegas1
TARBALL_URL=https://github.com/jjsullivan5196/wvkbd/archive/refs/tags/v0.21.tar.gz
TARBALL_SHA=e0a88358cf5a76f812a766f9323a2633da1297bfb11a1e38d420689efdd26f9d
VENDORED=$REPO/linux/work/ref/moto-g-power-2025-omarchy/vendor/wvkbd
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1763856000}   # 2025-11-23 00:00 UTC: fixed mtimes in the .deb/tar
[ "$(uname -m)" = aarch64 ] || { echo "build.sh: run it in the arm64 VM (orb -m vegas-deb ...)" >&2; exit 1; }

mkdir -p "$OUT"; rm -rf "$OUT/src" "$OUT/pkg" "$OUT/pkgwork"
if [ -n "${WVKBD_SRC:-}" ]; then SRC=$WVKBD_SRC; ORIGIN="WVKBD_SRC=$SRC"
elif [ -f "$VENDORED/main.c" ]; then SRC=$VENDORED; ORIGIN="vendored $VENDORED"
else
  tgz=$OUT/dl/wvkbd-0.21.tar.gz; mkdir -p "$OUT/dl"
  [ -s "$tgz" ] || curl -sfL -o "$tgz" "$TARBALL_URL"
  echo "$TARBALL_SHA  $tgz" | sha256sum -c --quiet || { echo "build.sh: tarball checksum mismatch" >&2; exit 1; }
  rm -rf "$OUT/dl/x"; mkdir -p "$OUT/dl/x"; tar xzf "$tgz" -C "$OUT/dl/x"
  SRC=$OUT/dl/x/wvkbd-0.21; ORIGIN="tarball $TARBALL_URL sha256 $TARBALL_SHA"
fi
grep -q '^VERSION = 0.21' "$SRC/config.mk" || { echo "build.sh: $SRC is not wvkbd 0.21" >&2; exit 1; }

# copy the tree (no git metadata, no earlier build products), then add our layout
mkdir -p "$OUT/src"
(cd "$SRC" && tar cf - --exclude=.git --exclude='build-*' --exclude='wvkbd-*' --exclude='*.o' \
   --exclude='proto/*-client-protocol.[ch]' .) | (cd "$OUT/src" && tar xf -)
install -m 644 "$HERE/layout.vegas.h" "$HERE/config.vegas.h" "$OUT/src/"
cp "$OUT/src/keymap.deskintl.h" "$OUT/src/keymap.vegas.h"
for p in "$HERE"/*.patch; do [ -e "$p" ] || continue; patch -s -p1 -d "$OUT/src" --no-backup-if-mismatch < "$p"; done
# GPLv3 corresponding source includes how it is built: record the exact make command in the tree
printf 'wvkbd-vegas %s: build with\n  make LAYOUT=vegas VERSION=%s CC="cc -O2" wvkbd-vegas\n' "$VER" "$VER" \
  > "$OUT/src/BUILD.vegas"
tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner -C "$OUT" \
  -czf "$OUT/wvkbd-vegas-$VER-source.tar.gz" --transform "s,^src,wvkbd-vegas-$VER," src

# build (Makefile target wvkbd-$(LAYOUT)); -O2 through CC because config.mk assigns CFLAGS with '='
make -C "$OUT/src" -j"$(nproc)" LAYOUT=vegas VERSION="$VER" \
  CC="cc -O2 -ffile-prefix-map=$OUT/src=." wvkbd-vegas > "$OUT/build.log" 2>&1 \
  || { tail -40 "$OUT/build.log" >&2; exit 1; }
grep -i 'warning' "$OUT/build.log" >&2 || true
install -m 755 "$OUT/src/wvkbd-vegas" "$OUT/wvkbd-vegas"; strip "$OUT/wvkbd-vegas"

# smoke test without a compositor: the layer list comes from our layout
layers=$("$OUT/wvkbd-vegas" --list-layers 2>&1 | tr '\n' ' ')
[ "$layers" = "letters symbols fn landscape " ] || { echo "build.sh: unexpected layers: $layers" >&2; exit 1; }

# .deb: /usr/bin/wvkbd-vegas + copyright; Depends from dpkg-shlibdeps
P=$OUT/pkg; install -D -m 755 "$OUT/wvkbd-vegas" "$P/usr/bin/wvkbd-vegas"
install -d "$P/usr/share/doc/wvkbd-vegas" "$P/DEBIAN"
{ echo "wvkbd-vegas $VER: wvkbd 0.21 (https://github.com/jjsullivan5196/wvkbd) with the Vegas phone layout."
  echo "Built from: $ORIGIN"
  echo "License: GPL-3.0-or-later. Full text: /usr/share/common-licenses/GPL-3."
  echo "Corresponding source: wvkbd-vegas-$VER-source.tar.gz, kept next to the .deb in the build output."
  echo; cat "$OUT/src/COPYING"; echo; cat "$OUT/src/COPYING_WESTON"; } > "$P/usr/share/doc/wvkbd-vegas/copyright"
mkdir -p "$OUT/pkgwork/debian"; printf 'Source: wvkbd-vegas\n\nPackage: wvkbd-vegas\nArchitecture: arm64\n' \
  > "$OUT/pkgwork/debian/control"
deps=$(cd "$OUT/pkgwork" && dpkg-shlibdeps -O "$P/usr/bin/wvkbd-vegas" 2>/dev/null | sed -n 's/^shlibs:Depends=//p')
[ -n "$deps" ] || { echo "build.sh: dpkg-shlibdeps gave no dependencies" >&2; exit 1; }
cat > "$P/DEBIAN/control" <<EOF
Package: wvkbd-vegas
Version: $VER
Architecture: arm64
Maintainer: vegas farm <root@localhost>
Depends: $deps
Section: x11
Priority: optional
Description: on-screen keyboard for the vegas phone (wvkbd 0.21, Vegas layout)
 Letters, symbols with navigation, F1-F12 and a landscape layer; one-shot
 modifiers; a Hide key (F20) bound in the sway config. Installs as
 wvkbd-vegas next to Debian's wvkbd-mobintl.
EOF
find "$P" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
DEB=$OUT/wvkbd-vegas_${VER}_arm64.deb
dpkg-deb --root-owner-group -Zxz --build "$P" "$DEB" >/dev/null
rm -rf "$OUT/pkgwork"

{ echo "built $(date -u +%FT%TZ) on $(uname -srm)"
  echo "source: $ORIGIN"
  echo "cc: $(cc --version | head -1)"
  (cd "$HERE" && sha256sum layout.vegas.h config.vegas.h ./*.patch)
  (cd "$OUT" && sha256sum wvkbd-vegas "$(basename "$DEB")" "wvkbd-vegas-$VER-source.tar.gz")
  echo "depends: $deps"; } > "$OUT/BUILD-INFO"
cat "$OUT/BUILD-INFO"
