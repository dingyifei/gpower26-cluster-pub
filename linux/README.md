# Linux route B on vegas: rebuilt GKI kernel + stock vendor modules

Part 1 takes one expendable phone to "the rebuilt kernel boots Android, and a Linux initramfs gives a USB shell
on it". The research and every rule behind this is `docs/linux-on-vegas.md` (sections 2.4, 3.4, 6 and 7.2). Debian
root, Wi-Fi and dual boot by swapping `init_boot_a` are part 2.

Experiment unit: **phone #5** (listed in `farm-exclude.txt`, so `farm.py` skips it).

## Phase 0: offline

Build VM: an OrbStack **x86_64** Ubuntu 24.04 machine called `vegas-kbuild`. Google's prebuilt clang r450784e is
x86_64-only, so it runs under Rosetta.
- Packages: `repo bc bison flex libssl-dev libelf-dev cpio lz4 zstd dwarves erofs-utils android-sdk-libsparse-utils
  gcc-aarch64-linux-gnu libc6-dev-arm64-cross file`.
- For the arm64 busybox: `dpkg --add-architecture arm64`, mark the existing apt lines `[arch=amd64]`, and add
  `deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports noble main universe`.

Kernel source, in the VM at `~/ack`:
- `repo init -u https://android.googlesource.com/kernel/manifest -b common-android13-5.15-2025-05`, then `repo sync`.
  The `common` project fails because its release branch is gone. That's expected.
- Fetch `common/` by hand at tag `android13-5.15-2025-05_r14`, which is commit 9b2308ac0ad6, the stock kernel's
  commit.

Steps (`repo/` is this checkout, mounted in the VM at the same path):

1. **Stock material** (Mac):
   - Unzip `boot.img`, `init_boot.img`, `vendor_boot.img`, `vbmeta*.img` and `dtbo.img` from the -4-2 zip into
     `linux/work/stock/`.
   - Run `unpack_bootimg --format=mkbootimg` on each of the three boot images.
   - Run `lpunpack -p vendor_dlkm_a -p system_dlkm_a <phone dump>/super.img linux/work/stock/`.
   - Then, in the VM, run `linux/tools/extract_stock.sh`. It writes `config.stock`, the 202 vendor-ramdisk modules,
     the 197 `vendor_dlkm` modules and `modules.list`.
2. **Kernel** (VM):
   - `linux/kernel/build.sh stock` is the control build with `gki_defconfig`. Its `config.diff` against the stock
     embedded config should be empty.
   - `linux/kernel/build.sh b` adds `linux/kernel/fragment.config`.
3. **Gate**, both must pass before any flash:
   - `linux/tools/modcrc.py linux/work/kernel/<variant>/Module.symvers linux/work/stock/vendor_ramdisk linux/work/stock/vendor_dlkm`
     must show 0 mismatch and 0 missing, for `stock` (positive control) and for `b`.
   - `linux/tools/btfdiff.sh linux/work/kernel/stock/vmlinux linux/work/kernel/b/vmlinux` must show no layout
     differences.
4. **Images** (Mac, `linux/tools/mkimg.sh` packs, then runs `checkimg.py`):
   - `boot_4a.img`: the stock kernel re-gzipped at level 6, so the payload differs from stock.
     `gzip -dc linux/work/stock/boot/kernel | gzip -6 -n > linux/work/img/Image.stock.regz.gz`
   - `boot_4b.img`: `linux/tools/mkimg.sh boot linux/work/kernel/b/Image.gz linux/work/img/boot_4b.img`
   - `init_boot_probe.img`: run `linux/initramfs/build.sh` (VM), then
     `linux/tools/mkimg.sh init_boot linux/work/img/probe-initramfs.cpio.gz linux/work/img/init_boot_probe.img`
5. **Unlock lk**: `patch_lk.py` on the zip's `lk.img` (stock `b6e5a74f…`) gives `linux/work/unlock/lk.unlock-serial.img`.
   It is byte-identical to #1's proven `914acfce…`. Only the `oem unlock` key is per-serial.

## Phases 1 to 5: on the phone

`scripts/linux_b.sh <serial>` runs these stages:
`preflight readonly unlock setup fbcheck root probe-init-boot restore-init-boot boot-4a boot-4b linux-shell restore`

- Use `--from`/`--only` to resume or redo a stage. `--only stock-boot` puts the stock `boot_a` back.
- Each write is behind a typed token: `UNLOCK <serial>` or `FLASH <serial>`.
- Logs: `logs/<serial>/linux_b.log` and `logs/<serial>/linux_b/`.

The probe initramfs (`linux/initramfs/init`):
- Loads the vendor-ramdisk modules in Android's order.
- Brings up an NCM + ACM gadget. The phone is `172.16.42.1` and the Mac gets `.2` by DHCP; the shell is
  `nc 172.16.42.1 23` or `/dev/cu.usbmodem*`.
- **Always ends in lk fastboot**, after 10 minutes or on any setup failure. `touch /stay` cancels the timer.
- Never boots the system or opens `/dev/watchdog`. The stock kernel keeps the MediaTek watchdog fed until userspace
  opens it (`WATCHDOG_HANDLE_BOOT_ENABLED`).

## Findings so far (offline, 2026-11-21)

- **`system_dlkm` on vegas holds no kernel modules**, only `etc/`. The Google-signed module concern of sec. 2.1 does
  not apply, so MODULE_SIG_PROTECT off is harmless.
- The stock kernel (`5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692`, clang r450784e) is byte-reproducible as a
  gzip stream with `gzip -9 -n`. A 4a image must therefore recompress at another level, or it tests nothing.
- Every module that reboot-to-bootloader and USB device mode need is in the vendor ramdisk: `reboot-mode`,
  `syscon-reboot-mode`, `mtu3`, `phy-mtk-tphy`, `extcon-mtk-usb`, `fusb304`, `tcpc_class`. NCM and ACM are built
  into the kernel.
- `misc` boot-control on #5's dump: slot a priority 7, tries 1, successful 1; slot b priority 6, tries 7,
  successful 0; CRC ok; BCB command `bootonce-bootloader`.
- #5's dumped `lk_a` is the route-D lk (`d2660cc…`), not stock. The unlock lk is built from the zip's stock lk instead.
- Fastboot slot variables (`slot-successful:a`, etc.) read `unknown` while the phone is locked.

## Findings on the phone (2026-11-22, #5)

- Unlock from end state D worked (unlock lk `914acfce` + serial key). The retail lk (`lk-moto2026.img`) was then put back
  on the unlocked phone: it stays `flashing_unlocked`, no Tracfone activation, `carrier=retus`.
- Fastboot slot variables read `unknown` even when unlocked; boot-control is read from `misc` instead.
- **The `init_boot` ramdisk must be lz4 legacy.** lk appends it to the lz4-legacy vendor ramdisk; a gzip ramdisk is
  dropped silently and Android boots from the vendor ramdisk's own `/init`. `checkimg.py` now refuses it.
- **`modules.load` is not dependency ordered** (`mtk-spmi-pmic` line 49 needs `regmap-spmi` line 98). Plain insmod in
  list order leaves the PMIC unloaded, so `mtu3` defers on `vusb33` and no UDC appears (pstore showed the probe's
  60 s bail, then `Restarting system with command 'bootloader'`). The probe now loads `modules.dep` deps first.
- The probe's own log lines go to `/dev/kmsg` at `<3>` so they reach pstore `console-ramoops-0`, readable from Android
  after the next boot.
- `/dev/pts` must be mounted for `telnetd`, and on the stock kernel (no DEVTMPFS, no UEVENT_HELPER) `/dev/ttyGS0` only
  appears after another `mdev -s` once the gadget is bound. busybox `telnetd` drops input sent before its shell is
  ready, so `lsh` waits 1.5 s before sending.

### Results, phone #5 (2026-11-22, hands-on)

| Stage | Result |
|---|---|
| probe on stock kernel | 186/186 vendor-ramdisk modules, UDC `11201000.usb0`, NCM + DHCP + telnet + ACM serial, `rebootbl` → fastboot in ~6 s. 109 MB RAM used of 7.6 GB. |
| boot-4a (stock kernel recompressed) | Android boots (orange); `misc` slot a still successful. |
| boot-4b (rebuilt GKI + fragment) | Android boots on `5.15.180-android13-8-g9b2308ac0ad6`, 362 modules live, 0 module errors in dmesg, `DEVTMPFS`/`FHANDLE` on. |
| linux-shell (rebuilt kernel + probe) | `/dev` via devtmpfs, 186/186 modules, NCM + telnet, `AUTOFS_FS` on, `rebootbl` works. |

Boot-control in `misc` never changed across all flashes (slot a prio 7 successful, slot b untouched); no failed boots
were counted. Evidence: `logs/<serial>/linux_b/`.

## Part 2 and end state E: runbook (#5, 2026-11-22)

Findings and their verification status are in `docs/linux-on-vegas.md` section 11.

**Builds (VMs, no phone):**
```bash
orb -m vegas-kbuild bash -lc "cd $PWD && linux/initramfs/build_chooser.sh dry|linux|e <serial>"
linux/tools/mkimg.sh init_boot linux/work/img/chooser-<v>.ramdisk linux/work/img/init_boot_chooser_<v>.img
orb -m vegas-deb sudo VEGAS_SERIAL=<serial> bash linux/debian/build.sh "$(cat ~/.ssh/id_ed25519.pub)"   # needs android-capture first
```
- `dry` and `linux` sit on the KernelSU init_boot (rooted Android). `e` sits on the stock init_boot (unrooted).
- The Debian image needs `linux/work/android-rt/` (linker64, bionic, VNDK) and the per-phone copies in
  `logs/<serial>/linux_b/p2/capture2/`. Both come from `--only android-capture`, which needs root.

**Using it:**
- **Boot Debian:** reboot, leave the keys alone during the orange warning, then tap Vol-up for about 5 s. Then run
  `ssh root@172.16.42.1`. If the Mac shows a 169.254.x address on the "vegas Debian" interface (it missed the
  DHCP lease), either run `sudo ipconfig set <enN> DHCP`, or use IPv6 link-local: `ping6 -c2 ff02::1%<enN>`, then
  `ssh root@fe80::…%<enN>` (`linux_b.sh` does this by itself). The serial console on `/dev/cu.usbmodem*` is off by
  default (`systemctl start serial-getty@ttyGS0`): when nothing reads it, its shell blocks shutdown for 30 s.
- **Rescue shell:** if `linux` holds no Debian, the branch serves a rescue shell (telnet `172.16.42.1`, or ACM serial)
  and reboots to Android after 10 min. `touch /stay` keeps it up.
- **Debian units:**
  - `vegas-fuelgauged`: the vendor gauge daemon. SOC is valid only while it runs.
  - `vegas-chargeguard.timer`: the 80/70% band and the temperature limits; thresholds in
    `/etc/vegas/chargeguard.conf`.
  - `vegas-thermal`: caps CPU frequency from the `soc_max` zone every 2 s (down at 80 °C or above, back up at 70 °C
    or below, power off at 100 °C); Android's thermal HAL does this under Android. Thresholds in `/etc/vegas/thermal.conf`.
  - `vegas-wifi`: enabled (proven on #5 2026-11-23). It brings up connsys + `wlan0` after `ssh.service` (sshd never
    waits for it), then starts `wpa_supplicant@wlan0` if a network was written with `linux/tools/wifi-conf.sh <SSID>`
    (rerun it after a `rootfs-flash`). A failed run powers the radio off and stops the vendor daemons.
  - `nvguard`: refuses to start any vendor daemon if an NV path is not on Debian's own root.
- **Read the previous boot's chooser log:** `/sys/fs/pstore/console-ramoops-0`, from Android (root) or Debian;
  `systemd-pstore` is masked.

**Stages** (`scripts/route_e.sh`, which is `scripts/linux_b.sh`):

| Stage | What it does | Token |
|---|---|---|
| `android-capture` | (runs before `rootfs-flash`) rooted, read-only: modules, vendor daemons, the runtime closure, copies of the gauge state and the Wi-Fi NVRAM | none |
| `rootfs-flash` | fastbootd: flash `linux` with `debian.simg` (needs root to verify); refuses an image without this phone's `vegasdisk.conf` | FLASH |
| `debian-boot` | Vol-up → Debian checks over SSH, then reboot → Android (timed) | none |
| `state-e` | flash the unrooted chooser (the last write), then check: no root, the Moto cap, `state-e-check` | FLASH |
| `state-e-check` | Vol-up → Debian; from Debian, read-only: `init_boot_a` hash, misc boot-control, init log; reboot | none |
| `root-on` / `root-off` | temp root (KernelSU chooser), then back to unrooted | FLASH |
| `datadisk-poc` | rooted: 256 MiB pinned test disk in `/data/vegas-poc`; Android writes, Debian reads + writes, Android reads; idle-maintenance GC; delete | FLASH |
| `datadisk-create` | rooted: `VEGAS_DISK_MIB` (32768) pinned disk in `/data/vegas`; in the rescue Debian: ext4 `vegas-root2` + copy of the rescue root (a rerun keeps an existing main root that has its completion marker); then rebuild + flash the chooser (`chooser-linux`) so `init.linux` boots it, and rebuild `debian.simg` (it now carries the conf) | FLASH |
| `datadisk-check` | Android `verify` (when rooted; a loud warning in E); Debian reports the booted root | none |
| `datadisk-grow` | rooted (`root-on` in E): grow to `VEGAS_DISK_MIB`; Debian runs `resize2fs` at the next boot | FLASH |
| `deb-update` | copy `linux/debian/overlay` + the property shim into the running Debian (not `/etc/fstab`); `daemon-reload`; on the main root it records that `vegas-bootok` is enabled (`state-e`/`root-on`/`root-off` refuse a counter chooser without that) | none |

**On the phone (root, `/usr/local/sbin`, verified on #5 2026-11-23):**
- `reboot-rescue [-n]`: one-shot reboot into the rescue root (`-n`: set the flag only).
- `vegas-rotate normal|90|270`: rotate the panel; moves the camera-cutout margin (left at 90, right at 270).
- `vegas-usbshare on|off|status`: share Wi-Fi with the computer on the USB cable until reboot (iptables-legacy NAT:
  this kernel has no nf_tables, so networkd's `IPMasquerade=` fails). The computer must renew its DHCP lease.
- `vegas-hotspot on [min]|off|status|show`: Wi-Fi hotspot on the driver's `ap0` beside `wlan0` (same channel),
  hostapd WPA2, off after 60 min by default; name/passphrase in `/etc/vegas/hotspot.conf`.

**Rescue:**
- **Debian rescue root** (the `linux` partition in super) instead of the main root on the userdata disk:
  the normal way is **`reboot-rescue`** in the main root (writes the one-shot `/rescue`, reboots; tap Vol-up as usual).
  Automatic: any failure to map or mount the main root, and the **boot-failure counter** (init.linux adds 1 before
  each main-root boot, `vegas-bootok.service` clears it at multi-user.target; 2 uncleared attempts in a row -> one
  rescue-root boot, then the counter restarts). Two quick reboots by hand before Debian finishes starting count too.
  Scripted reboots in `linux_b.sh` wait for the counter to clear. Last resort: a fresh Vol-up press held 2 s right
  after the orange screen (the chooser only sees presses, not a key already down; it missed twice on #5, 2026-11-23).
  The reason is in `/var/log/vegas/init.log`.
- `chooser-off` restores the KernelSU init_boot, which leaves Android **rooted**.
- `lp-delete` removes the `linux` partition.
- `stock-boot` puts the stock kernel back.
- **E → D:** `lp-delete`, `stock-boot`, the stock init_boot, `fastboot flashing lock` (wipes data), then
  `route_d.sh`. This path is unverified.
