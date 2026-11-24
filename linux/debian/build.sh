#!/usr/bin/env bash
# Build the Debian trixie arm64 root for the "linux" LP partition, in the native arm64 OrbStack VM:
#   orb -m vegas-deb sudo VEGAS_SERIAL=<serial> linux/debian/build.sh [PUBKEY]
# Output: linux/work/debian/debian.img (ext4, label vegas-root, exactly LP_BYTES) and debian.simg (sparse, for
# `fastboot flash linux`). Vendor modules go to /lib/modules/<release>/vendor with depmod; nothing loads them
# automatically (see overlay/etc/vegas/modules.list).
# Android vendor daemons (fuelgauged; wmt/wlan for Wi-Fi) run under Android's own linker: linker64 + bionic + VNDK
# from linux/work/android-rt (scripts/linux_b.sh --only android-capture), /linkerconfig/ld.config.txt from the phone,
# /system -> the read-only system_a mount. Per-phone seeds from logs/<serial>/linux_b/p2/capture2: the fuel gauge
# state (nvcfg/fg) and the Wi-Fi NVRAM, as COPIES on Debian's root (the NV partitions are never mounted).
set -Eeuo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); REPO=$(cd "$HERE/../.." && pwd)
PUBKEY=${1:-}; SERIAL=${VEGAS_SERIAL:?set VEGAS_SERIAL to the phone serial (its captures are in logs/<serial>/)}
RT=$REPO/linux/work/android-rt; CAP=$REPO/logs/$SERIAL/linux_b/p2/capture2
[ -x "$RT/apex/com.android.runtime/bin/linker64" ] && [ -s "$RT/ld.config.android.txt" ] \
  || { echo "no Android runtime in $RT (run: scripts/linux_b.sh $SERIAL --only android-capture)" >&2; exit 1; }
[ -s "$CAP/nvcfg_fg/car_tune_value" ] && [ -s "$CAP/nvram/WIFI" ] || { echo "no gauge/NVRAM copies in $CAP" >&2; exit 1; }
SHIM=$REPO/linux/work/propshim/libpropshim.so
[ -s "$SHIM" ] || { echo "no $SHIM (orb -m vegas-kbuild linux/tools/propshim/build.sh $SERIAL)" >&2; exit 1; }
LP_BYTES=3221225472
REL=$(sed -n 's/^Linux version \([^ ]*\).*/\1/p' "$REPO/linux/work/kernel/b/version.txt")
[ -n "$REL" ] || { echo "no kernel release in linux/work/kernel/b/version.txt" >&2; exit 1; }
OUT=$REPO/linux/work/debian; R=/var/tmp/vegas-root   # build on the VM's own disk (ownership, xattrs)
rm -rf "$R"; mkdir -p "$OUT"

PKGS=systemd,systemd-sysv,udev,dbus,openssh-server,systemd-resolved,systemd-timesyncd,iproute2,iw,wpasupplicant
PKGS+=,wireless-regdb,kmod,e2fsprogs,procps,less,ca-certificates,sudo,nano,iputils-ping,busybox,strace,file,psmisc,libdrm-tests
# screen UI (sway on pixman; verified on #5 2026-11-23): see etc/vegas/sway/config, never enable anything but DSI-1
PKGS+=,seatd,sway,swaybg,foot,foot-terminfo,tmux,wvkbd,fonts-jetbrains-mono,fonts-dejavu-core,evtest,libinput-tools,python3,grim,iptables,hostapd
# touch UI (UI spec 0.3): Textual pages vegas-home/vegas-net, vegas-keys (evdev), power menu (bemenu, Wayland backend
# named so apt never picks the curses one), edge swipes (lisgd), hotspot QR, sign-in check (curl) and its w3m window
PKGS+=,python3-textual,python3-evdev,bemenu,libbemenu-wayland,lisgd,qrencode,curl,w3m
# graphical program on workspace 2 (Home > Programs, the sign-in check's "Open in Firefox"; Q37): drawn at
# devPixelsPerPx 2 by overlay/etc/firefox-esr/vegas.js; Wayland only (MOZ_ENABLE_WAYLAND=1 in vegas-sway.service)
PKGS+=,firefox-esr
mmdebstrap --variant=minbase --architectures=arm64 --include="$PKGS" trixie "$R" http://deb.debian.org/debian

cp -a "$HERE/overlay/." "$R/"
find "$R/usr/lib/vegas" "$R/usr/local" -name __pycache__ -prune -exec rm -rf {} +   # test leftovers (gitignored)
chown -R root:root "$R/etc" "$R/usr/lib/vegas" "$R/usr/local"
# keyboard v2 (wvkbd-vegas, GPL, built by linux/ui-src/wvkbd/build.sh into linux/work): installed when built, but it
# runs only when /etc/vegas/kbd-v2 exists (vegas-kbd); the stock wvkbd-mobintl stays the default
KBD_DEB=$(ls "$REPO"/linux/work/wvkbd-vegas/wvkbd-vegas_*_arm64.deb 2>/dev/null | tail -1) || true
if [ -n "$KBD_DEB" ]; then dpkg --root="$R" -i "$KBD_DEB" >/dev/null
else echo "no linux/work/wvkbd-vegas/*.deb: keyboard v1 only (linux/ui-src/wvkbd/build.sh builds v2)" >&2; fi
rm -f "$R"/etc/ssh/ssh_host_*                      # per-device keys on first boot (vegas-ssh-hostkeys.service)
ln -sf /dev/null "$R/etc/systemd/system-generators/systemd-gpt-auto-generator" 2>/dev/null || {
  mkdir -p "$R/etc/systemd/system-generators"; ln -sf /dev/null "$R/etc/systemd/system-generators/systemd-gpt-auto-generator"; }
mkdir -p "$R/vendor" "$R/vendor_dlkm" "$R/android/system" "$R/config"
passwd -R "$R" -l root >/dev/null
if [ -n "$PUBKEY" ]; then install -d -m 700 "$R/root/.ssh"; echo "$PUBKEY" > "$R/root/.ssh/authorized_keys"; chmod 600 "$R/root/.ssh/authorized_keys"; fi
# No getty on ttyGS0 by default: with nothing reading the ACM port on the Mac, the autologin shell blocks in
# set_termios (output never drains), ignores SIGTERM and holds shutdown 2 x 15 s (measured 31 s on #5). Start it
# by hand when needed: systemctl start serial-getty@ttyGS0 (autologin drop-in kept).
systemctl --root="$R" enable systemd-networkd systemd-resolved ssh vegas-modules vegas-ssh-hostkeys \
  vegas-fuelgauged vegas-chargeguard.timer vegas-thermal vegas-diskgrow vegas-wifi vegas-bootok \
  vegas-sway vegas-keys vegas-away >/dev/null   # vegas-sway: reboot with it alive verified on #5 2026-11-23 (power-off not yet)
# vegas-keys (screen UI key daemon) and vegas-away (Away's SSH rules, only while /etc/vegas/away exists) run on the
# main root only / when needed through their Conditions
# networkd-wait-online: no network at boot is normal. systemd-pstore: it would move + unlink /sys/fs/pstore, which
# holds the chooser's log of the previous boot.
systemctl --root="$R" mask systemd-networkd-wait-online systemd-pstore hostapd >/dev/null   # hostapd: only vegas-hotspot runs it

# Android runtime for the vendor daemons (same paths as on Android; /system and /vendor come from the phone)
mkdir -p "$R/apex" "$R/linkerconfig"
cp -a "$RT/apex/." "$R/apex/"; chmod 755 "$R/apex/com.android.runtime/bin/linker64"; chown -R root:root "$R/apex"
install -m 644 "$RT/ld.config.android.txt" "$R/linkerconfig/ld.config.txt"
install -D -m 644 "$SHIM" "$R/odm/lib64/libpropshim.so"   # Android property stand-in (vendor namespace allows /odm)
ln -sfn /android/system/system "$R/system"
# per-phone copies: fuel gauge state + Wi-Fi NVRAM (plain files on this root; nvguard checks it stays that way)
install -d -m 700 "$R/mnt/vendor/nvcfg/fg"; install -m 600 "$CAP"/nvcfg_fg/* "$R/mnt/vendor/nvcfg/fg/"
install -d -m 755 "$R/mnt/vendor/nvdata/APCFG/APRDEB"; install -m 640 "$CAP"/nvram/WIFI* "$R/mnt/vendor/nvdata/APCFG/APRDEB/"
rm -f "$R/mnt/vendor/nvdata/APCFG/APRDEB/SHA256SUMS"

# vendor modules (vendor ramdisk + vendor_dlkm) for modprobe/depmod under the rebuilt kernel's release
M="$R/lib/modules/$REL/vendor"; mkdir -p "$M"
# vendor_dlkm first, then the vendor-ramdisk copies win for duplicates (Android loads those first, the rest get EEXIST)
cp "$REPO"/linux/work/stock/vendor_dlkm/lib/modules/*.ko "$M/"
cp -f "$REPO"/linux/work/stock/vendor_ramdisk/lib/modules/*.ko "$M/"
depmod -b "$R" "$REL"
echo "vegas Debian built $(date -u +%FT%TZ) for $REL, seeds from $SERIAL" > "$R/etc/vegas/build-info"
# main root on the userdata disk (scripts/linux_b.sh datadisk-create): init.linux reads its anchor/uuid only from this
# (rescue) root, so a rebuilt rescue root must carry it; rootfs-flash compares debian.vegasdisk with the phone's copy
VCONF=$REPO/logs/$SERIAL/linux_b/datadisk/vegasdisk.conf
if [ -s "$VCONF" ]; then install -m 644 "$VCONF" "$R/etc/vegas/vegasdisk.conf"; fi

# exact-size ext4, label + marker checked by init.linux
rm -f "$OUT/debian.img"; truncate -s "$LP_BYTES" "$OUT/debian.img"
mkfs.ext4 -q -F -L vegas-root -d "$R" "$OUT/debian.img"
img2simg "$OUT/debian.img" "$OUT/debian.simg"
echo "$SERIAL" > "$OUT/debian.serial"   # rootfs-flash refuses to flash an image built from another phone's seeds
if [ -s "$VCONF" ]; then cat "$VCONF" > "$OUT/debian.vegasdisk"; else echo none > "$OUT/debian.vegasdisk"; fi
du -sh "$R"; ls -l "$OUT"
