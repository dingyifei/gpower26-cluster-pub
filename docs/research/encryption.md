# Encryption for Debian on phone #5 (research, 2026-11-23)

> Research report from the v1 build sessions, imported as written. `#5` is the maintainer's dual-boot phone.
> Paths starting `<scratch>/` are the session's working folder and are not in this repo. `linux/work/ref/<name>/` are
> local clones of the public sister-port repos; their URLs are in `docs/linux-on-vegas.md` section 8.

Scope: design defaults Q30 (a small encrypted folder for secrets now) and D19 (an encrypted main root later).
Research only: no phone was touched. Tests ran in the `vegas-deb` OrbStack VM (Debian trixie arm64, kernel
7.2.12-orbstack, which is **not** the phone kernel).

Tags: **[verified: source]** = checked in this session against the named file, command output or VM test.
**[unverified]** = reasoning, memory of upstream behaviour, or not testable without the phone.

---

## 1. Short answer

- **Now (Q30): a gocryptfs folder on the main root**, unlocked by hand after boot from a foot/Textual prompt
  (or over SSH), with nothing secret needed for boot inside it. It needs no kernel change, no ext4 feature flag,
  no partition write and no initramfs change, and it can be removed with `rm -r`. It works in the trixie VM
  (gocryptfs 2.5.1, init/mount/write/unmount) **[verified: VM test]**, and the phone kernel has `CONFIG_FUSE_FS=y`
  **[verified: linux/work/kernel/b/.config]**.
- **Second choice for the folder: fscrypt (ext4 `encrypt` feature, policy v2).** It is kernel-native and needs no
  daemon, but the `encrypt` flag must be set while the main root is **unmounted** (from the rescue root). Section 4.1
  explains why.
- **Later (D19): LUKS2 over the vegasdisk map** (`dm-crypt` on top of the `vegas-disk` dm-linear device), unlocked in
  `init.linux` **over USB first**. Running cryptsetup **from the rescue root via chroot** avoids the 8 MiB `init_boot`
  size limit. Do not build an on-screen PIN pad in the initramfs until a test shows a DRM client can exit before
  switch_root without crashing (D10).
- **Encryption covers data at rest only.** #5's bootloader is unlocked and the initramfs and rescue root are
  unsigned plaintext, so anyone who gets the phone and gives it back can plant a passphrase logger. The main root is
  plaintext on flash today **[verified: docs/linux-on-vegas.md §12 "Limits"]**.

---

## 2. Facts that constrain the design

### 2.1 Where the main root lives
- The main root is ext4 `vegas-root2`, built as dm-linear `vegas-disk` over pinned f2fs files inside Android's
  `/data`, mapped through the **raw** `userdata` partition by `vegasdisk map` in `init.linux`.
  **[verified: linux/initramfs/init.linux; linux/tools/vegasdisk.c header]**
- Data written through that map is **stored unencrypted**. Android's FBE and metadata encryption
  (`aes-256-xts ... wrappedkey_v0`, keys unwrapped by the Trustonic TEE) do not cover it, and Linux cannot use those
  keys. **[verified: docs/linux-on-vegas.md §12 "Encryption", "Limits"]**
- The rescue root is ext4 `vegas-root` in super LP partition `linux` (3 GiB). `init.linux` mounts it read-only before
  mapping the main root, to read `/etc/vegas/vegasdisk.conf`. **[verified: init.linux]**
- The boot-failure counter (`/var/lib/vegas/bootfail`) and the one-shot `/rescue` flag live **inside the main root**,
  and `init.linux` reads and writes them before switch_root. **[verified: init.linux]** An encrypted root therefore
  has to be unlocked before those checks can run.

### 2.2 Kernel (the rebuilt "b" kernel and the stock GKI kernel have identical crypto config)
Sources: `linux/work/kernel/b/.config`, `linux/work/kernel/stock/.config`. The fragment
(`linux/kernel/fragment.config`) changes no crypto option. **[verified]**

| Option | Value | Meaning |
|---|---|---|
| `DM_CRYPT` | y | LUKS / plain dm-crypt possible |
| `BLK_DEV_DM`, `DM_DEFAULT_KEY`, `DM_VERITY` | y | |
| `DM_INTEGRITY` | not set | no authenticated (AEAD) dm-crypt; XTS only |
| `BLK_DEV_LOOP` | y | LUKS file containers possible |
| `FS_ENCRYPTION`, `FS_ENCRYPTION_INLINE_CRYPT` | y | fscrypt (ext4/f2fs) available, policy v2 (kernel 5.15) |
| `BLK_INLINE_ENCRYPTION` (+ `_FALLBACK`) | y | blk-crypto; the fallback does it in software |
| `CRYPTO_AES_ARM64_CE`, `CRYPTO_AES_ARM64_CE_BLK` | y | AES with ARMv8 Crypto Extensions (xts-aes-ce), if the CPU has them |
| `CRYPTO_XTS`, `CRYPTO_CTS`, `CRYPTO_ESSIV`, `CRYPTO_GCM`, `CRYPTO_CBC` | y | aes-xts-plain64 (dm-crypt), aes-256-cts (fscrypt names) |
| `CRYPTO_ADIANTUM`, `CRYPTO_CHACHA20_NEON` | y | Adiantum available as a fallback |
| `CRYPTO_NHPOLY1305_NEON` | **not set** | Adiantum would use generic C NH: slower than it could be |
| `CRYPTO_HCTR2` | not set | |
| `CRYPTO_USER_API_SKCIPHER/HASH/AEAD` (AF_ALG) | **not set** | userspace cannot use kernel ciphers through AF_ALG |
| `FUSE_FS` | y | gocryptfs possible |
| `KEYS` | y; `ENCRYPTED_KEYS`, `TRUSTED_KEYS` not set | no TPM-style sealed keys (there is no TPM anyway) |
| `VT`, `FB` | not set | no text console on the panel |

### 2.3 CPU crypto extensions (MT6835, Cortex-A76 + A55)
- On Cortex-A76 and A55 the Crypto Extensions are a licensable option, so the core names do not prove AES support.
  **[unverified: general Arm knowledge]**
- Android uses `aes-256-xts` for FBE with `inlinecrypt_optimized` (UFS inline engine; `ufshcd-mtk ... clk
  "aes_ufsfde_ck"` in Debian dmesg) **[verified: docs §12; logs/<serial>/linux_b/p2/debian/dmesg.txt]**. That
  proves the UFS engine does AES; it does **not** prove CPU AES instructions.
- No `/proc/cpuinfo` capture exists in the repo or logs (searched `logs/`, `linux/work`, `docs`). **[verified: grep]**
- How to settle it on the phone, read-only: `grep -m1 Features /proc/cpuinfo` (look for `aes pmull sha2`) and
  `grep -A3 'xts-aes-ce' /proc/crypto` (`selftest: passed`). The CE drivers register only when the CPU advertises
  AES. **[unverified for this kernel; the upstream driver is gated on `cpu_have_named_feature(AES)`]**
- Expected: AES-CE present, which makes **aes-xts-plain64 / fscrypt AES-256-XTS the right mode**, with Adiantum only
  if the check fails. **[unverified]**
- Do not use the UFS inline engine from Linux (fscrypt `inlinecrypt` mount option). Android programs it with
  hardware-wrapped keys through the TEE, and nothing shows whether it takes standard keys from a non-Android kernel.
  The gain on a phone this size is small. **[unverified]**

### 2.4 Userspace tools (trixie)
Installed and run in the VM **[verified: VM]**:
- `cryptsetup-bin 2:2.7.5-2`: links `libcrypto.so.3` (OpenSSL backend). `luksFormat --type luks2 --pbkdf argon2id
  --pbkdf-memory 262144` and `open` worked on a 64 MiB file. (`mkfs` right after `open` raced udev creating the
  node; the node existed a moment later.)
- `gocryptfs 2.5.1` (go1.24.4): `-init` and mount worked, a write produced encrypted names, `fusermount -u` worked.
  `gocryptfs -speed` in the VM gives AES-GCM-256-Go at 6.6 GB/s on the M-series host. **That number does not carry
  over to the phone.**
- `fscrypt 0.3.5`, `e2fsprogs 1.47.2`.
- Available in trixie: `unl0kr 2.0.3` (postmarketOS on-screen unlock UI; depends on `cryptsetup-initramfs`,
  libinput, libudev), `dropbear-initramfs 2025.89`, `cryptsetup-initramfs`, `osk-sdl 0.67.1`. **[verified:
  apt-cache in VM]**

What the missing AF_ALG means for cryptsetup:
- Because cryptsetup uses OpenSSL, LUKS2 keyslot decryption should run in userspace without AF_ALG; the data path is
  dm-crypt in the kernel. **[unverified on the phone; it is the first thing the safe first step tests]**
- `cryptsetup benchmark` probably fails without AF_ALG. **[unverified]**
- Do not add AF_ALG to the kernel just for this. The fragment's rule that nothing may change a struct layout or an
  exported symbol CRC makes every kernel change gated work.

### 2.5 Initramfs and early-boot I/O
- `init_boot` is 8 388 608 bytes. The current state-E chooser ramdisk (`linux/work/img/chooser-e.ramdisk`) is
  7 555 366 bytes, leaving about 0.8 MB, less the boot header and AVB footer. **[verified: ls]** cryptsetup with its
  libraries (libcryptsetup, libcrypto ~4–5 MB, libargon2, libdevmapper, libjson-c, libblkid, libuuid, libpopt) does not
  fit. **[size of libcrypto: unverified estimate]**
- **Way around it:** `init.linux` already mounts the rescue root read-only before mapping the main root. It can bind
  `/dev`, `/proc` and `/sys` into it and run `chroot /newroot cryptsetup open ...` from the rescue root's own Debian
  install. **[design; unverified]**
- Keys and display in the initramfs: `vendor_ramdisk/lib/modules/modules.load` contains `mtk-kpd.ko`,
  `mtk-pmic-keys.ko`, `mediatek-drm.ko` and `ktd3136_bl.ko`, so Vol-up, Vol-down, Power, DRM and backlight exist in
  `init.linux` once modules have loaded. **[verified: modules.load]** At the earlier chooser stage only Vol-up is seen
  (docs §12).
- The touch driver `ilitek_v3_mmi.ko` and `sensors_class.ko` are only in `vendor_dlkm` **[verified: find]**, which
  `init.linux` maps read-only (`vendor_dlkm_a`). Touch in the initramfs would need that erofs mounted and the module
  inserted with its dependencies. **[unverified that it works pre-switch_root]**
- There is no fbdev or fbcon (`FB`, `VT` not set; docs line ~1238). An on-screen PIN pad needs a KMS client: unl0kr's
  DRM backend or a custom dumb-buffer program. **[verified config; unl0kr DRM-backend support in 2.0.3 unverified]**
- **D10 conflict:** a compositor or DRM-master exit oopses `mediatek_drm` and panics the phone (task facts; the 2025
  port saw a reboot about 2 s after killing the DRM master, docs §GPU). A PIN UI in the initramfs must release DRM
  before `switch_root`, which is exactly that event. Whether a plain dumb-buffer client (modetest-style, one CRTC,
  60 Hz) can exit safely on #5 is **unverified**: docs record that modetest showed colour bars, not what happened
  when it exited.
- USB: `init.linux` already builds the NCM+ACM gadget that survives switch_root, and the rescue path already runs
  `udhcpd` and `telnetd` on 172.16.42.1. **[verified: init.linux]** An unlock over USB reuses tested code.

---

## 3. The options compared

| | gocryptfs dir | fscrypt dir (ext4 `encrypt`) | LUKS file container | LUKS main root (unlock in `init.linux`) |
|---|---|---|---|---|
| Kernel needs | FUSE (y) | FS_ENCRYPTION (y) | loop + dm-crypt (y) | dm-crypt (y) |
| Filesystem change | none | `tune2fs -O encrypt` on the main root, **offline only** (§4.1); clearing it later is doubtful **[unverified]** | none | reformat or in-place reencrypt of the whole 32 GiB root |
| Boot path change | none | none | none | `init.linux`, chooser image rebuild + `init_boot` flash |
| Unlock point | after boot (foot/Textual/SSH) | after boot | after boot | before switch_root (USB, keys, or screen) |
| What leaks | file count, sizes, tree shape | file count, sizes, tree shape, xattrs/perm metadata | only container size | nothing in the root (rescue root stays plaintext) |
| Speed | FUSE overhead; fine for secrets | native, AES-CE through the kernel | native dm-crypt plus loop and double journaling | native dm-crypt |
| Backup | ciphertext dir can be rsync'd to the Mac without the key | ciphertext is unreadable outside the fs (needs the policy metadata) | one big file | whole-disk backup only |
| Undo | `rm -r` | delete the dir; the flag stays | `rm` file | re-format/restore |
| Risk to boot | none | low (an offline `tune2fs` on the main root from the rescue root) | none | **high**: a mistake, a wrong PIN or a hung UI means no main root; a D10 crash if on-screen |
| Tested | VM works | VM kernel lacks FS_ENCRYPTION, so not tested end-to-end (§4.1) | VM luksFormat/open works | design only |

---

## 4. Notes on each option

### 4.1 fscrypt: setting the flag on a mounted filesystem does not stick
VM test (`tune2fs -O encrypt e.img` while it was loop-mounted):
- `dumpe2fs` showed `encrypt` straight away.
- After `umount` and a remount the feature was **gone**: the kernel wrote its in-memory superblock back at unmount.
  **[verified: VM, kernel 7.2]**
- The VM kernel has no `FS_ENCRYPTION` (`/sys/fs/ext4/features/` lacks `encryption`), so fscrypt could not be tested
  end-to-end there.
- **Consequence:** on the phone, set the flag on the main root **from the rescue root** with the main root mapped but
  not mounted (`vegasdisk map` → `tune2fs -O encrypt /dev/mapper/vegas-disk` → `vegasdisk unmap`), or from the
  initramfs shell. Whether the 5.15 phone kernel behaves like the VM is **[unverified]**; the safe assumption is that
  it does.
- Other points **[unverified, from upstream docs]**:
  - `fscrypt setup` creates `/.fscrypt` metadata on the root fs.
  - Use a `custom_passphrase` protector, because everything runs as root and login/PAM protectors do not fit.
  - v2 policies put keys in the filesystem keyring, so locking needs `fscrypt lock`, which also evicts caches.
  - A non-empty directory cannot be encrypted in place.

### 4.2 gocryptfs
- It is the least invasive option. The ciphertext dir (e.g. `/var/lib/vegas/vault.enc`) lives on the main root and
  the plaintext mount is `/root/vault`.
- Mount it with a passphrase prompt in foot (`gocryptfs /var/lib/vegas/vault.enc /root/vault`); unmount with
  `fusermount -u`.
- A Textual "Vault" button can run the same command with the `Input` widget in password mode. Pass the passphrase on
  stdin with `-passfile /dev/stdin` or `-extpass`; never put it on argv. **[design; Textual Input password mode
  unverified on the phone]**
- Throughput on the phone **[unverified]**: expected tens to low hundreds of MB/s with AES-CE, which is plenty for
  secrets.

### 4.3 LUKS file container
- It hides more than gocryptfs does (everything inside one opaque file), but it is fixed-size and has loop and
  double-journal overhead.
- It gives practice with exactly the cryptsetup, argon2id and dm-crypt path a LUKS root will need: a useful
  rehearsal for D19, but heavier than Q30 asks for.

### 4.4 LUKS main root (D19)
Proposed shape **[design; unverified]**:
1. Layout: `vegas-disk` (dm-linear, unchanged) → LUKS2 (aes-xts-plain64, 512-bit key, argon2id, memory around
   256 MiB, sized so unlock takes about 1–2 s on the A76) → ext4 `vegas-root2`. `vegasdisk.c` needs no change: it
   maps raw ranges and does not care what is in them.
2. `init.linux`, after `vegasdisk map`:
   - If the map starts with the LUKS magic (`LUKS\xba\xbe` at offset 0), start the gadget, `udhcpd` and a listener on
     usb0, then wait N minutes for a passphrase.
   - Unlock with `chroot <rescue root> cryptsetup open --key-file=- /dev/mapper/vegas-disk vegas-root`.
   - Then run the existing label/marker/bootfail checks on `/dev/mapper/vegas-root`.
   - On a timeout or 3 wrong tries, boot the rescue root, as every other failure already does.
   - `sblabel` stays as it is; it just runs on the opened device.
3. Unlock input, in order of safety:
   - **(a) USB.** `telnet 172.16.42.1` / ttyGS0 from the Mac, or better dropbear with a pinned `authorized_keys`
     placed on the rescue root. It reuses tested gadget code.
   - **(b) Volume-key PIN.** Vol-up/Vol-down/Power in the initramfs (modules verified present) with backlight blinks as
     feedback. The PIN has low entropy, which only argon2id slows down, so use it as a convenience slot with a long
     passphrase slot kept beside it.
   - **(c) On-screen PIN pad** (unl0kr or custom KMS plus touch from `vendor_dlkm`). This is blocked on a D10 test:
     can a DRM client exit, or hand over, before switch_root without the `mediatek_drm` oops?
4. Migration: back up the main root to the Mac over usb0 first, then either
   - offline in-place `cryptsetup reencrypt --encrypt --reduce-device-size 32M` from the rescue root after shrinking
     ext4, or
   - format a LUKS volume on the same map and restore from the backup.
   Both are big writes on the only main root. The backup must come first. **[unverified procedure on this phone]**
5. Side effects:
   - `vegas-bootok` and `datadisk-grow`/`vegas-diskgrow` need `cryptsetup resize` added.
   - `rootfs-flash` and the conf checks are unaffected (the conf stays on the rescue root).
   - Scripted reboots from the Mac (which wait for the bootfail clear) would need an unlock step, which complicates
     unattended reboots and `--auto` routes.

---

## 5. What not to encrypt in phase 1
These must stay readable at boot, so they stay outside the folder (plaintext):
- `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf` (Wi-Fi PSKs; Wi-Fi comes up before any unlock)
- SSH host keys (the usb0 lifeline)
- the hotspot config
- `/etc/vegas/*`

The folder is for user secrets: SSH client keys, API tokens, a password store, personal files.

Moving an existing secret into the folder leaves the old plaintext in freed ext4 blocks on flash. Replace such
secrets (new keys or tokens) rather than move them. Do not run `fstrim` on the main root as a cleanup step until
discard through dm-linear into pinned f2fs files has been analysed. **[unverified risk]**

---

## 6. First safe step (no partition, boot-chain or filesystem-feature change)
All on #5's main root as ordinary files, read-only checks first:
1. Read-only:
   - `grep -m1 Features /proc/cpuinfo`
   - `grep -B1 -A4 'name *: xts(aes)' /proc/crypto | grep -E 'driver|selftest'` (AES-CE present?)
   - `ls /dev/fuse`
2. `apt-get install gocryptfs` (and `cryptsetup-bin` for the rehearsal).
3. `mkdir -p /var/lib/vegas/vault.enc /root/vault && gocryptfs -init /var/lib/vegas/vault.enc`
   - The passphrase is typed in foot with wvkbd, or over SSH.
   - Keep the printed master key **off the phone** (paper or a password manager).
4. Mount, write a test file, `fusermount -u`, remount, read it back. Then run `gocryptfs -speed` and note the numbers.
5. Optional rehearsal for D19: a 64 MiB LUKS2 file container on the main root
   (`cryptsetup luksFormat --type luks2 --pbkdf argon2id`, `open`, `mkfs.ext4`, mount, close).
   - This proves cryptsetup works on the phone kernel without AF_ALG, and times argon2id on the A76.
   - Delete it afterwards.

None of this touches `init.linux`, `init_boot`, super, NV, `/metadata`, sway or the modem. Undo is `rm -r` of the two
directories and the container file.

## 7. Open questions
- Does the CPU have AES-CE (step 1)?
- Does cryptsetup open LUKS2 on the phone kernel without AF_ALG (step 5)?
- Can the 5.15 phone kernel set the ext4 `encrypt` flag on a mounted fs, or does it drop it as the VM did? This only
  matters if fscrypt is chosen.
- D10 for early boot: does a DRM client that exits before switch_root crash `mediatek_drm`? This blocks any on-screen
  initramfs unlock.
- Is a TRIM through `vegas-disk` safe for the pinned f2fs pieces?
