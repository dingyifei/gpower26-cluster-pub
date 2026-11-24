#!/usr/bin/env bash
# Route to END STATE E (dual boot) for one phone: Android (unrooted at rest) by default, Debian trixie on a Vol-up tap.
#
#   scripts/route_e.sh <serial> [--from STAGE | --only STAGE] [--list]      (= scripts/linux_b.sh, same stages/logs)
#
# E = BL unlocked (orange) + retail lk (carrier=retus) + rebuilt GKI boot_a + init_boot_a = chooser over the STOCK
#     init_boot ramdisk (no KernelSU) + LP partition "linux" in super holding Debian (SSH over USB 172.16.42.1,
#     fuel gauge + charge/thermal guard, Wi-Fi if proven) + Moto 80% cap in Android + listed in farm-exclude.txt.
# From end state D, in order (each flash/unlock behind a typed token; see linux/README.md):
#   part 1  preflight readonly unlock retail-lk setup fbcheck root probe-init-boot restore-init-boot boot-4a boot-4b
#           linux-shell restore
#   part 2  p2-capture fastbootd-check lp-create chooser-dry chooser-linux
#           android-capture (rooted, read-only: feeds the Debian build)  -> build debian.simg for this serial
#           rootfs-flash (needs root)  debian-boot
#   E       state-e (unrooted chooser; the last write). Updating Debian later: root-on, rootfs-flash, root-off.
# Builds first: linux/initramfs/build_chooser.sh dry|linux|e <serial> (VM) + mkimg.sh; linux/debian/build.sh (VM).
# In E:  --only root-on / root-off   temp root (KernelSU chooser) and back
#        --only state-e-check        Vol-up -> Debian, read-only checks of init_boot_a + misc, reboot -> Android
# Rescue: --only chooser-off (KernelSU init_boot, leaves Android ROOTED), --only lp-delete, --only stock-boot.
# E -> D (documented, never run): lp-delete, stock-boot, flash the stock init_boot, `fastboot flashing lock`
#        (wipes data), then scripts/route_d.sh.
exec "$(cd "$(dirname "$0")" && pwd)/linux_b.sh" "$@"
