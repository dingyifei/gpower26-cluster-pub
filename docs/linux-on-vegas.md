# Linux on the moto g power 2026 (XT2617V, vegas / vegas26, MT6835)

Research synthesis dated 2026-11-21. The research ran in two passes on that day. Pass 1 combined desk research with static analysis of the stock -4-2 firmware zip and one stock partition backup. Pass 2 re-ran four tracks that had failed in pass 1 (what lk accepts to flash and to boot, rescue paths below fastboot, the partition write-safety map, and coexistence with Android). It added disassembly of the stock -4-2 `lk.img`, a hash comparison of the owner's partition backups and the owner's flashing logs, and it applied the 28 fixes of the pass-1 audit. No adb or fastboot command was run and nothing was flashed for this document. Every direction below is untested on vegas unless a line says otherwise. Where pass-1 text conflicted with a confirmed pass-2 claim, the pass-2 claim is used and the conflict is stated once at that place.

**Tags used**

- `[confirmed]`: all verification passes that checked the claim agreed with it.
- `[contested]`: the passes disagreed, or the original wording was refuted and the verifiers' corrected wording is what appears here.
- `[unverified]`: the claim was not put through verification, rests on one self-reported source, or comes from a source only the critic pass read.
- `(firmware)`: read from the stock -4-2 images. `(notes)`: from the owner's repository notes.
- Evidence links that point at `../logs/`, `../backups/`, `../vegas-freedom/backups/` or `sources/` name the maintainer's local
  files. They hold device-unique data or other people's posts and are not published, so those links lead nowhere in the public repo.
- Source IDs such as VK-3 point to the entry of the same name in section 8. IDs that start with LG (lk gate), RS (rescue), PM (partition map) and CX (coexistence) are pass-2 claims.
- "Static reading" means disassembly or strings of the stock -4-2 firmware. It predicts behaviour and is not a run on a phone.

"By analogy" means the evidence is from another device and has not been shown on vegas.

## 1. Bottom line

Ranked by expected value for the farm, not by nativeness:

1. **Rebuilt GKI kernel with the stock vendor modules and a plain Linux userspace** (section 3.4). This is the best ratio of result to effort. The stock kernel is a public Google commit, a static check found every imported symbol CRC matching, and one author self-reports the same recipe running Arch on a same-platform Motorola tablet (unreplicated). Pass 2 adds two self-reported precedents, by analogy, of a rebuilt android13-5.15 kernel that keeps the stock vendor modules and replaces only `boot`; one is an MT6835 phone on 5.15.180 (CX-5, CX-6). On the phone, a footered repack of `boot_a` with the stock kernel comes before any self-built kernel (section 7.2, step 4a), and the offline module check must also cover the Google-signed modules in `system_dlkm` (section 2.1). Headless with USB networking should come first, then Wi-Fi through two vendor helper binaries.
2. **Halium 13 (Ubuntu Touch)** (section 3.6) if a GPU-accelerated UI, camera or modem matters. Same kernel work, plus an Android HAL container. Telephony on the nearest MT6835 port is still poor. Android apps can come back on top through Waydroid, which has an official image for this vendor level (section 3.12).
3. **Stock kernel with a replaced `init_boot`** (section 3.5). This is the cheapest probe and the only step that reuses a flash already done hands-on on this phone. Static reading of lk offers a likely explanation (contested) for why that image passed the flash gate (section 2.4). The userspace is limited by the stock config.
4. **Android host with a system container on the rebuilt kernel** (section 3.11). This is not Linux-native: Android stays the host. It is listed because it keeps Android and its data, it gives a full distribution userland with its own init at native CPU speed, and it uses the same rebuilt kernel as items 1 and 2. It is close to the arrangement the owner ruled out, so treat it as a stepping stone or a fallback.
5. **Mainline kernel** (section 3.1). The most native route and a months-long project; MT6835 has no upstream SoC support.
6. **UEFI or U-Boot chain-loaded from lk** (section 3.2). It gives a boot menu and adds no drivers.
7. **KVM** (section 3.7). GenieZone most likely holds EL2, so KVM is most likely blocked. Freeing EL2 means patching code that runs before fastboot.

**Dual boot.** Slot B is not usable (section 2.5). The realistic dual boot is switching images inside slot A: one rebuilt kernel in `boot_a` that serves both systems, and a swap of `init_boot_a` between the stock ramdisk and a Linux initramfs, with the Linux root on microSD (section 3.9). No source shows this on vegas.

**What pass 2 changed**

- **Flash gate.** Static reading of the stock -4-2 lk says an unlocked unit accepts a `boot`, `init_boot` or `vendor_boot` image that has no AVB footer, or one that keeps a large enough footer even though its hash no longer matches, and accepts a vbmeta signed with any key without `avb_custom_key` (section 2.4). This was not run on a phone, and the size rule and the vbmeta rule are contested between verifiers. Pass 1 called the gate "not established".
- **No RAM boot.** `fastboot boot` is a stub in this lk (LG-10). Every kernel test is a flash, so every test can cost a retry.
- **No rescue below fastboot.** No download agent for a Motorola MT6835 phone is public, and lk contains code that blows a BROM-disable fuse (section 2.7). Plan any write that stops lk from reaching fastboot as permanent.
- **Slot B.** It is all zeros in every backup examined: phone #1 in pass 1 and four more phones in pass 2.
- **Return to stock.** It is a partition-selective restore from the -4-2 zip, never a full flashfile run (section 6).

**Recommended first experiment.** On a locked, temp-rooted stock phone, do the read-only probe and the full per-phone partition backup before unlocking (section 7.2, step 1). Then unlock one expendable -4-2 unit, block OTAs before it first joins a network, and confirm the key combination into fastboot (step 2). Then replace only `init_boot_a` with a small initramfs that loads the stock vendor modules, exposes a USB network shell and carries a timed reboot to the bootloader (step 3). The proven pattern is a footer-bearing `init_boot` whose footer `vbmeta_offset` is at least 3096576, the stock descriptor size (LG-4 [contested]). The hands-on case was a KernelSU image whose ramdisk grew. A minimal initramfs is smaller than the stock ramdisk, and the usual repacking tools then move the footer below that size, which is the case static reading predicts lk rejects (LG-3 [contested]). So the probe image must be padded explicitly: pad the boot image to at least 3096576 bytes, then re-add the hash footer with avbtool for partition `init_boot` at the 8388608-byte partition size. Verify offline that `vbmeta_offset` is at least 3096576 before flashing (section 7.2, step 0). A padded small image is untested; only the larger KernelSU image is hands-on. Standardise all Linux experiments on build -4-2, because the owner's lk patch, the public kernel commit, the Motorola source tag, the static module check and the lk disassembly all match that build.

**Standing rules.** Do not activate slot B. Make no lk write other than the owner's established unlock patch, and write nothing else in the bootloader chain (preloader, GPT, `tee`, `gz`). Write no NV or identity partition. The unlock step itself may erase `nvdata`: a repository note, from static reading of lk, says the `oem unlock` and `oem lock` paths erase `nvdata` and `md_udc` ([G13-15](../tools/locked/) verifier note, [unverified]). The per-phone backup therefore comes before unlocking. Stop and restore stock after two or three failed boots. Never relock: do not run `oem lock`, `fastboot flashing lock` or `flashing lock_critical` on an experiment unit. Under these rules unlocking is one-way: the unit cannot return to the locked, green end state D of the farm, so choose an expendable unit and remove it from route-D maintenance (`farm.py`).

## 2. What the phone gives us

### 2.1 Kernel and modules

| Fact | Consequence | Basis |
|---|---|---|
| Kernel is `5.15.180-android13-8-00018-g9b2308ac0ad6-ab14563692`, an unmodified Google GKI binary, 4K pages | The kernel can be rebuilt from public source. | (firmware) |
| Commit 9b2308ac0ad6 is ACK tag `android13-5.15-2025-05_r14`; Google's CI record for build 14563692 names the same commit | The exact source is known. Byte identity of the binary was not checked. | [VK-4](https://android.googlesource.com/kernel/common/+/refs/tags/android13-5.15-2025-05_r14), [X-CI](https://ci.android.com/builds/submitted/14563692/kernel_aarch64/latest/raw/BUILD_INFO) [confirmed] |
| Not set: KEXEC, USER_NS, SYSVIPC, POSIX_MQUEUE, CGROUP_PIDS, CGROUP_DEVICE, FHANDLE, AUTOFS_FS, VT, DEVMEM, SQUASHFS, BTRFS, NFS | No containers, no SysV shared memory, no virtual terminals, no kexec on the stock binary. | (firmware) |
| PID_NS and FHANDLE are not set in the config embedded in the stock -4-2 kernel, as in upstream `gki_defconfig` at 9b2308ac0ad6. USER_NS is not set either, and with SYSVIPC and POSIX_MQUEUE off there is no IPC namespace. PID_NS is a built-in-only option | The stock kernel cannot create a PID namespace, and neither root nor a loadable module such as the KernelSU LKM can add one. A container with its own PID 1 needs a rebuilt kernel. Pass 1 listed the vegas value as unknown; CX-3 settles it from the firmware. | [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) [confirmed]; [HA-7](https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.15/arch/arm64/configs/gki_defconfig) [confirmed] for upstream |
| Set in the same config: CGROUP_BPF, ASHMEM, MEMFD_ASHMEM_SHIM, binder and binderfs | The binder and ashmem pieces that Waydroid probes for are present. They are not sufficient: Waydroid's container also needs PID and IPC namespaces. | [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) [confirmed] |
| DEVTMPFS and BT_HCIVHCI on vegas | DEVTMPFS is not set in the config embedded in the stock -4-2 kernel (CX-3 verifier note [confirmed source]). BT_HCIVHCI reads not set in the same extracted config (re-read in section 7.2, step 0). An initramfs must populate `/dev` itself, and the Bluetooth bridge of section 3.4 needs `hci_vhci` built. | [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) verifier note; BT_HCIVHCI [unverified] |
| Set: MODULE_SIG, MODULE_SIG_PROTECT, MODVERSIONS, TRIM_UNUSED_KSYMS. Not set: MODULE_SIG_FORCE | Unsigned modules load but, with MODULE_SIG_PROTECT, cannot use protected GKI symbols. A rebuilt kernel needs no signing key for the vendor modules but must keep symbol CRCs and struct layouts. | (firmware); [VK-6](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/init/Kconfig) [confirmed] |
| `system_dlkm` is a logical partition in `super` (firmware). It holds GKI modules signed with Google's build key | A self-built kernel cannot verify those signatures, so with MODULE_SIG_PROTECT kept on they count as unsigned and are restricted. Android on a rebuilt kernel (section 7.2, step 4) needs them. Either turn MODULE_SIG_PROTECT off, as the tablet fragment does (VK-9), or rebuild and ship `system_dlkm` from the same tree. Include the `system_dlkm` modules in the step-0 CRC and symbol check. No track listed or checked these modules, and a pass-2 verifier flags their loading on a self-built kernel as untested. | (firmware) for the partition; [CX-5](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/community-supported-devices.md) verifier note, [unverified] |
| 202 modules in the `vendor_boot` ramdisk plus 197 in `vendor_dlkm` (inside `super`), 376 distinct, all with vermagic `5.15.180-android13-8-g72da1abbd4bf`. None of the 202 `vendor_boot` modules is signed (the 197 in `vendor_dlkm` were not checked) | "202 modules" is not the full set. Drivers that live only in `vendor_dlkm` need `super` mapped before they can load. The signature scan of `vendor_dlkm` is an offline check (section 7.2, step 0). | [G13-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/android/abi_gki_aarch64.xml) [confirmed] |
| `vendor_dlkm` holds the connectivity stack: `wmt_drv.ko`, `wmt_chrdev_wifi.ko`, `wlan_drv_gen4m_6835.ko`, `bt_drv_connac1x.ko` | Wi-Fi and Bluetooth cannot come up from an `init_boot`-only probe that does not map `super`. | [G23-7](../tools/locked/) [confirmed] |
| Which of display (`mediatek-drm`), Mali, panel, touch and `mtk-mmc` sit in `vendor_boot` versus `vendor_dlkm` | Not listed by any track. This is an offline check on the unpacked firmware. | unknown |
| Vendor partition is API 33: `ro.vndk.version=33`, `ro.board.api_level=33`, MediaTek branch `alps-mp-t0.mp1.tc2sp2`. Only `ro.product.first_api_level` is 36 | Android 16 system on a vendor frozen at Android 13. This selects Halium 13. | [G13-12](../tools/locked/), [HA-1](https://github.com/qfertig/vegas26-gsi) [confirmed] |

### 2.2 Kernel source

- Motorola's `kernel-mtk` tag `MMI-W1WN36.18-114` is Linux 5.15.180. Its tip commit message reads "Merge source code with GKI android13-5.15-2025-05_r14 for Kansas NA/Vegas/Nevada NA/Orlando", and its merge list starts at 9b2308a. [VK-3](https://github.com/MotorolaMobilityLLC/kernel-mtk/commit/0fa176ca7f56c349b51acd83684284c02ced5854) [confirmed]
- The three dates quoted for that tag are all correct and refer to different things: author date 2026-01-29, commit date 2026-04-27, tag date 2026-06-25. The tag annotation is "Nevada push for Android 16", so it is a Nevada release that carries the vegas files. [VK-3](https://github.com/MotorolaMobilityLLC/kernel-mtk/commit/0fa176ca7f56c349b51acd83684284c02ced5854) [confirmed]
- The tree contains `mt6835-orlando-evb-overlay.dts` (model "vegas", hab_product "orlando", board-id `0x241 0xA100`) and a vegas config fragment. The third overlay in the stock -4-2 `dtbo.img` carries the same model, product and board-id. [VK-5](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/boot/dts/mediatek/mt6835-orlando-evb-overlay.dts) [confirmed]
- No Motorola repository has a tag for any W1WE build, which is the build prefix of this phone. [VK-1](https://github.com/jimmielin/android_device_motorola_vegas26-kernels) [confirmed]
- Source requests for builds -4-7 and -4-9 were open without a Motorola reply on 2026-11-21. [VK-2](https://github.com/MotorolaMobilityLLC/kernel-mtk/issues/312) [unverified]
- The same tag exists in the Motorola module, GPU and connectivity repositories. It is absent from the mtkcam, met_drv_v3 and kernel-build-kernel repositories. [VK-7](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/configs/mgk_64_k515_defconfig) [unverified]
- Whether the published module sources reproduce the shipped -4-2 modules is untested.

This settles a disagreement between the research tracks. Statements that "Motorola has not published vegas kernel source" are true only in the narrow sense that no W1WE tag exists.

**Naming.** Community trees call the XT2617V "vegas26". Motorola's kernel source calls the 2026-only parts "orlando". The bootloader reports "vegas", which is also the codename of the 2025 moto g power (XT2515V). [VK-5](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/boot/dts/mediatek/mt6835-orlando-evb-overlay.dts) [confirmed] Which of the three dtbo overlays a given unit selects has not been read from a live phone.

### 2.3 Boot chain

- `boot` holds only the kernel (header v4, gzip, empty cmdline). `init_boot` holds the generic ramdisk. `vendor_boot` holds the DTB, the vendor cmdline, the vendor ramdisk and recovery. There is no recovery partition. Kernel load address is 0x40000000. (firmware)
- The `vendor_boot` header also gives `ramdisk_addr` 0x66F00000 and `tags_addr` 0x47C80000. All three addresses equal those recorded for the Lenovo TB365FC, another MT6835 device. [UE-3](https://github.com/LittleStar-OuO/uefi-tb365fc/blob/HEAD/Resources/Configs/tb365fc.toml) [contested]
- AOSP documents that the generic ramdisk is concatenated after the vendor ramdisk and that its `/init` wins. [NP-5](https://source.android.com/docs/core/architecture/partitions/generic-boot) [confirmed] The owner's earlier KernelSU `init_boot` on an unlocked unit (notes) is consistent with this, because KernelSU's LKM mode replaces `/init` in that ramdisk. [X-KSU](https://kernelsu.org/guide/installation.html) [unverified] Pass 2 disassembled lk's flash gate and command table (section 2.4). The ramdisk concatenation order inside lk was still not traced.
- `lk.img` is a container of sub-images (`lk`, `bl2_ext`, `aee`, `lk_main_dtb`, `lk_dtbo`), each with its own certificates. [UE-14](../tools/locked/) [unverified]
- lk has no RAM boot. In the stock -4-2 lk, the fastboot `boot` command points to a stub that only prints "command is not implemented!". No hook overrides it and no `oem` subcommand offers a RAM boot. The same stub is in the base-build lk and in the patched lk images the owner's phones run; the -4-3 lk was not checked. After the stub returns, the command loop appears to answer OKAY, so the host tool may report success although nothing boots. This is static reading, not a test on vegas. The identical message is reported hands-on on an unlocked Motorola Edge 60 Fusion, and a near-identical one on a Moto G54 5G whose lock state is not stated (both by analogy). [LG-10](../tools/locked/) [confirmed] Pass 1 said RAM boot was "not settled by its strings" (UE-14); LG-10 settles it. Consequence: there is no zero-write test of a kernel or payload. Every test image has to be flashed.
- At boot, lk's kernel decompressor recognises only gzip and lz4-legacy images and calls its panic routine for anything else. Package a self-built kernel or payload as gzip, like stock. Static reading; whether a raw image can skip that routine was not fully traced. [LG-11](../tools/locked/) [unverified]
- At boot, lk runs the AVB slot verification with the allow-verification-error flag whenever the unit is unlocked, ignores the result in that case and skips the stored rollback-index update. By static reading an unlocked unit tolerates hash, key and rollback-index errors at boot. Only `init_boot` has exercised this on a phone. [LG-12](../tools/locked/) [unverified]
- The stock -4-2 `vbmeta` (rollback index 5, flags 0) holds hash descriptors for `boot` (21549056 bytes), `dtbo` (377808), `init_boot` (3096576) and `vendor_boot` (30642176). The footer vbmeta embedded in each of those stock images is unsigned. [LG-16](../tools/locked/) [unverified]
- The owner's unlock lk differs from stock -4-2 at four short ranges and the route-D lk at two. None of them is in the flash validator, the hash-check code or the boot AVB path, so the gate analysis of section 2.4 should apply to the owner's unlocked configuration. [LG-15](../vegas-freedom/) [unverified]
- Stock lk on other MediaTek phones refuses or crashes on a device tree that lacks vendor nodes. This is documented for Samsung's MT6833 LK ([ML-7](https://gitlab.com/pessdres/a22x-mainline/-/blob/main/docs/BUILDING.md) [confirmed]) and stated by two upstream series ([ML-4](https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116576.html), [ML-5](https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116317.html) [confirmed]). On the MT6895 xaga, replacing the `vendor_boot` DTB is reported to crash LK. [NP-12](https://wiki.nura.eco/wiki/Xiaomi_Redmi_Note_11T_Pro_%28%2B%29_/_POCO_X4_GT_/_Redmi_K50i_%28xiaomi-xaga%29) [unverified] All of this is by analogy. The pass-2 disassembly did not trace how lk parses the DTB at boot. Treat a custom DTB in `vendor_boot` as unsafe until that code is read or Motorola's lk is tested.

### 2.4 The flashing and boot gate on an unlocked unit

Pass 1 had four hands-on observations and no rule, and called the gate "not established". Pass 2 disassembled the `lk` sub-image of the stock -4-2 `lk.img` and compared the code with the hands-on sources. The static statements below hold for that build only, were not run on a phone, and assume that the lock-state word the code tests is the unlocked state (inferred from the code, not read live).

**What static reading of the -4-2 lk says**

- The message "Preflash validation failed" has exactly one code reference. It sits in a validator that lk registers to run before the fastboot `flash` command. The validator calls a dispatcher that routes by partition name and fails the flash when the dispatcher returns false. The base-build lk has the same code; the -4-3 lk was not checked. [LG-1](../tools/locked/) [confirmed]
- The dispatcher sends `boot`, `init_boot` and `vendor_boot` (slot suffix stripped) to an AVB hash check. In the unlocked state that check passes an image with no AVB footer ("Cannot find footer, ignored.") and an image whose hash does not match the vbmeta descriptor (the mismatch is logged and the flash continues). Other failures still reject in the unlocked state: an invalid footer vbmeta size or offset, no hash descriptor for that partition, a descriptor `image_size` larger than the new image's footer `vbmeta_offset`, or a bad salt, digest length or hash algorithm. So this is not "any boot image passes when unlocked". [LG-2](../tools/locked/) [confirmed]
- The size rule in detail. The verifier who re-disassembled the function for this claim found all the checks in the binary, but read the size comparison as a consistency check inside the image being flashed and found the cited instruction offsets mis-transcribed. The verifiers who disassembled the same function for LG-2 and LG-7 read it as the descriptor in the active slot's vbmeta against the new image's footer. The other two lenses on this claim held it without re-deriving the branch logic. Either reading gives the same practical rule for an image repacked from stock: keep the footer and do not let the image end below the stock descriptor size, or remove the footer entirely. A patched image that shrinks but keeps a footer is predicted to be rejected; that was not demonstrated. [LG-3](../tools/locked/) [contested]
- Flashing `vbmeta` or `vbmeta_system`. In the unlocked state a failed signature check, an untrusted public key and a rollback index below the stored one are logged and accepted, and the function then returns success without parsing the descriptors. The rejects that remain are allocation errors, an error reading the stored rollback index, and an error from the public-key step, which occurs if the custom-key slot (the last 4096 bytes of the `sp` partition) cannot be read. Static reading therefore says a vbmeta signed with any key passes on an unlocked -4-2 unit with no `avb_custom_key` installed. [LG-5](../tools/locked/) [contested] (the dissenting verifier corrected one sentence of the original wording; the corrected wording is used here)
- The vbmeta flags for disabled verification (2 or 3) do not bypass the per-image check. The hash check never reads the on-device vbmeta flags. [LG-8](../tools/locked/) [unverified]
- `dtbo` is not checked by AVB at flash time. It is in lk's MediaTek certificate table together with `tee`, `md1img`, `lk`, `gz`, `logo` and others, and the stock `dtbo.img` carries a MediaTek certificate. An image that fails that check passes only if it starts with the Android sparse magic, and then only its size is checked. So an unsigned raw custom dtbo is predicted to be rejected. [LG-9](../tools/locked/) [unverified] The dtbo that was accepted in the -4-3 log (LG-6) carried the stock payload, so it does not test this prediction, and the two are not reconciled. The sparse path covers `lk` and `tee` as well and must not be used as a trick.
- Flashing or erasing `avb_custom_key` is allowed when unlocked and refused when locked. [LG-14](../tools/locked/) [unverified]

**Hands-on observations and how they fit**

| Observation | Build | How it fits | Status |
|---|---|---|---|
| The owner flashed a KernelSU-patched `init_boot_a` through bootloader fastboot in the unlocked state, and the phone booted with root on every boot | -4-2, running the patched unlock lk, not stock lk | The image kept its AVB footer at 3592192 bytes, above the stock descriptor size of 3096576, and its hash does not match the stock descriptor. The notes record no vbmeta flash and no step that installs `avb_custom_key`; neither was read back. This fits the static reading. It shows nothing for a smaller or footerless image, a custom kernel in `boot`, a `vendor_boot` or DTB change, or dtbo. | [LG-4](../backups/) [contested]: the verifiers agree on the image facts and on the boot. One rejects "a hash mismatch is tolerated when unlocked" as a general rule because of the next row. One objects that the lk in use was the patched unlock lk and that "stock vbmeta, no custom key" is inferred, not recorded |
| One root guide saw a Magisk 31.1 `init_boot_a` rejected with "Preflash validation failed" despite the unlocked state. fastbootd reported "unlocked: yes" and could not open `init_boot_a`. The author then wrote the image with dd from temp-rooted Android and it booted. The guide does not identify the cause | -4-2, one unit | Not explained. A candidate is one of the rejects that survive the unlocked state, for example a footer that ends below the stock descriptor size. It also shows that the flash-time check and the boot-time check differ. | [PM-7](https://github.com/parsimo2010/moto-g-power-2026-straight-talk-wifi-root-guide/blob/main/GUIDE.md) [contested] (the original wording "unlocking does not lift image validation" was refuted; this is the corrected wording) |
| A second guide names an lk address as the gate, calls it AVB verification that runs even when unlocked, and passes it by installing `avb_custom_key` plus a self-signed vbmeta | -4-2, one author | In the -4-2 lk that address is MediaTek image authentication. It is reached only for the firmware partitions in the certificate table and for the efuse image, never for `boot`, `init_boot` or `vendor_boot`. The attribution does not match the code. The guide's result with a custom key stands as a report. | [LG-7](https://github.com/jesussaves-dev/moto-g-power-2026-root/blob/daf8192a7f/README.md) [contested] |
| The author of the unofficial LineageOS tree instructs: lk "validates each image against the vbmeta currently on the device", so vbmeta goes first | -4-3 | Consistent with the size and descriptor rejects; it is an instruction, not a demonstrated rule. | [VK-14](https://github.com/jimmielin/android_device_motorola_vegas26) [contested] |
| An install log records a self-built LineageOS 23.2 userdebug build signed with test keys flashed to slot A in this order: `vbmeta_a`, `vbmeta_system_a`, `boot_a`, `init_boot_a`, `vendor_boot_a`, `dtbo_a`. All six were accepted, read back identical, and the phone booted in orange state. The bootloader check listed `avb_custom_key: not found` | -4-3, one unit, unlocked with a different lk patch | A vbmeta signed with the public AOSP test key was accepted with no custom key recorded, as the static reading predicts for -4-2. Acceptance was conditional: an earlier `boot_a` flash of a stale -4-2 image was rejected, and a Magisk `init_boot` had to be written with dd. The boot image carried the byte-identical stock kernel, the stock DTB and a stock dtbo payload, so this shows nothing for a rebuilt kernel or a changed DTB. | [LG-6](https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/5b14ca912a/ACTIONS-LOG.md) [contested] (the original wording said "release-key" and "all were accepted" without conditions and was refuted; this is the corrected wording) |
| A GSI guide flashes the stock vbmeta images with the disable flags from the bootloader, then flashes `system` in fastbootd, and says fastbootd cannot see vbmeta | -4-3, one author | Single unreproduced report on the fastbootd point. | [PM-6](https://github.com/qfertig/vegas26-gsi) [contested] |

**Still unexplained**

- Why the Magisk image failed on -4-2 while the KernelSU image passed. An offline check can test the size explanation: read the AVB footer of a Magisk-patched -4-2 `init_boot` and compare its `vbmeta_offset` with 3096576.
- Whether a rollback index below the stored one blocks boot on an unlocked unit. Static reading says no (LG-12). The -4-3 log attributes a slot-A boot failure to rollback index 5 against a device at 7, but that slot also mixed -4-2 images with -4-3 firmware. [LG-13](https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/5b14ca912a/ACTIONS-LOG.md) [unverified]

**Conflict with pass 1, stated once.** Pass 1 refuted the claim "lk validates every image against the on-device vbmeta, so a self-made vbmeta must always be flashed first", because the owner's own flash contradicts it. That refutation of "always" stands. Pass 1's conclusion that the gate is not established is superseded for the flash path: lk does check boot-chain images against vbmeta descriptors at flash time, a hash mismatch is tolerated when unlocked, and a new vbmeta is needed first only when the image would otherwise fail the size or descriptor checks. Confirmation on a phone is still outstanding.

**Working rules for experiments** (derived from the above; only the first has run on a phone)

1. Proven pattern: a footer-bearing image whose footer `vbmeta_offset` is at least the stock descriptor size. This is how the owner's `init_boot` passed, under the patched unlock lk, and that image had grown. An image that would end up smaller than stock (a minimal initramfs, for example) must be padded to at least the stock descriptor size and have its hash footer re-added at the partition size. A padded small image is untested.
2. A footerless `boot`, `init_boot` or `vendor_boot` image is predicted to pass the flash gate and to boot with a tolerated hash mismatch. Untested, and the boot-time tolerance rests on LG-12 [unverified]. Try it only after the footered stock-kernel repack of section 7.2, step 4a, has shown the boot-time behaviour.
3. A self-signed vbmeta flashed first, then images that match it. Hands-on on -4-3 only. Back up `vbmeta_a` first, and keep the rollback index and security patch level at or above the rollback index stored on that device, as a precaution. The stock vbmeta carries index 5 on -4-2 and 7 on -4-3, and a stored index does not decrease. On phones that ever ran -4-3 (#7 and #8), assume 7. The stored value has not been read on any phone. Those two phones are recorded as booting locked and green on the stock -4-2 vbmeta after the downgrade (PM-4 verifier note), which suggests index 5 was not blocked there; do not rely on that.
4. The `avb_custom_key` route is not needed by static reading, and the track notes that its author warns stock images then no longer flash as they are (track note, [unverified]). Do not use it.
5. Do not wrap images as sparse to get past the certificate check.

No source shows a self-built kernel in `boot` on vegas. Every reported `boot` image carried the stock kernel binary.

### 2.5 Slots

- In the owner's stock -4-2 backup of phone #1 (2026-11-18), every slot-B GPT partition is all zeros, including `lk_b`, `tee_b`, `gz_b`, `boot_b`, `vendor_boot_b` and `vbmeta_b`. The misc boot-control block still marks slot B bootable (priority 6, 7 tries). Slot A shows priority 7, successful 1. [G12-1](../backups/) [confirmed]
- Four more backups, taken on 2026-11-20 from bootloader-locked phones on -4-2 with slot A active, show the same. All 23 slot-B GPT partitions are zero. Only `preloader_b` on UFS boot LU B holds data. `connsys_wifi` and `connsys_gnss` are empty on both slots. [PM-13](../vegas-freedom/backups/) [unverified]; the verifiers of PM-4 and PM-8 recounted the same zeros
- `misc` is byte-identical on those four phones. It holds a well-formed AOSP-format boot-control structure that starts at offset 2048 (four zero bytes, then the magic at offset 2052) with a valid CRC. Slot A: priority 7, tries 1, successful 1. Slot B: priority 6, tries 7, successful 0. By its metadata slot B still counts as bootable, and its values match untouched defaults, not a slot that was ever validated. Whether the boot chain would really fall back to it is untested: the stock preloader and lk both contain their own slot-image validity checks (strings such as "slot b LK image is invalid, rollback_slot BOOTCTRL_SUFFIX_A"). The same `misc` image also carries a `bootonce-bootloader` command at offset 0. The state of `misc` after a bootloader unlock has not been observed. [PM-8](../vegas-freedom/backups/) [contested] (the original wording called slot B "a valid fallback target" and was refuted; this is the corrected wording)
- An all-zero slot B is the state of every backup examined (five of the eight phones), including two phones that came from -4-3 through the downgrade route. It is not guaranteed for every unit. A phone that took an OTA may have a populated slot B: the owner's archived forum threads contain one such report ([G12-16](sources/uscardforum-moto-g-power-2026-threads.md) [unverified]), and one -4-3 install log records lk falling back from slot A to slot B after a failed boot, which the author attributes to a vbmeta rollback index of 5 against a device at 7, on a slot that mixed -4-2 and -4-3 images ([LG-13](https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/5b14ca912a/ACTIONS-LOG.md) [unverified]). Read each phone live. A phone that was downgraded from -4-3 needs a live read of every slot-B partition and of both preloader LUs before it is chosen as the experiment unit.
- The flashfile writes `gz` only to `gz_a`; the fact sheet line "gz_a/gz_b" is imprecise. [PR-8](https://github.com/jimmielin/android_device_motorola_vegas26) [confirmed] Every slotted write in the stock -4-2 flashfile targets slot A, and there is no step for `tzapp`, `connsys_wifi` or `connsys_gnss`. [PM-1](../tools/locked/) [confirmed]
- UFS boot LU B holds an older preloader (build 20250918) than LU A (20260406). The community slot-copy script deliberately does not copy the preloader. Whether a slot switch also flips the UFS boot LU on vegas is unknown. [G12-2](https://github.com/jimmielin/android_device_motorola_mt6835-common/blob/lineage-23.2/tools/copy-firmware-to-other-slot.sh) [contested]
- The preloader on LU A is not the same on every phone. Across the hash lists of all eight archives, `preloader_a` comes in two builds, six phones against two (PM-4 verifier note [contested]); the two are the phones that came from -4-3. In the four full backups that were byte-compared, the builds are stamped 20260406 and 20260521. The newer one sits on the two phones that went -4-3, base, -4-2: the downgrade and upgrade scripts skip the preloader and the GPT, so those phones kept the newer preloader. `preloader_b` is the same older build on the four phones compared; the other four were not reported. "Same Android build" therefore does not mean "same preloader", and one preloader image must never be assumed to fit all eight phones. [PM-4](../vegas-freedom/backups/) [contested] (the original wording said every slot-A image was identical and was refuted; this is the corrected wording)
- The preloader contains strings for a slot-validity check with rollback to A. This is string evidence only. [G12-3](../backups/) [confirmed]
- Stock lk warns when the target slot's bootloader images are invalid and lets a repeat of the same command within 30 seconds force the switch. It does not decrement the retry counter for a slot whose successful flag is set. Both come from disassembly, not from a run. [G12-4](../tools/locked/) [confirmed] The matching strings ("There is risk of bricking HW", "Unable to find any bootable slot", "When power up reason is HW_RESET AND the other slot is unbootable, we do not decrease retry counter") are in the -4-2 lk. [PM-9](../tools/locked/) [unverified]
- A Motorola Dimensity 7300 owner who overrode that same warning ended with a phone that showed nothing on USB. A service centre said the only fix was a programmer soldered to the flash chip. [G12-5](https://web.archive.org/web/20261007214046/https://xdaforums.com/t/motorola-g100-pro-motorola-g86-5g-soft-brick-after-switching-to-empty-slot-b-need-test-point-location.4803154/) [contested], by analogy
- `super` is one partition but its metadata has groups `main_a` and `main_b`. All `_b` logical partitions are zero-size except `system_b` (528.7 MiB), and about 4358 MiB is unallocated. [G12-11](../backups/) [unverified] This refines the fact sheet's "single, not A/B".

Tracks that proposed "Android on one slot, Linux on the other" assumed a usable slot B. On every phone whose backup was examined, that assumption is false. Two ways to neutralise the empty-slot fallback were proposed and neither is tested: copying the slot-A firmware to slot B with the community script (it writes a second lk, and no slot-B boot after it has been reported), or setting slot B's priority to 0 in `misc` (what lk does with no bootable slot is unknown). Neither is part of the plan in section 7.

### 2.6 Hypervisor

- `gz.img` is MediaTek GenieZone ("GZ_hypervisor: 3.2.0.013.T0MP1, Built ... Feb 1 2023"). Its strings show it booting Linux as a guest with stage-2 translation. [G15-1](../tools/locked/) [confirmed] as static evidence
- The GenieZone loader sits in the `bl2_ext` sub-image of `lk.img`, not in the preloader. [G15-2](../tools/locked/) [confirmed]
- The kernel is therefore most likely entered at EL1. On MediaTek phones that load GenieZone, lk and the kernel are documented hands-on as running at EL1 for one MT6833 phone. [G15-3](https://raw.githubusercontent.com/BreezeExceed/camellian-linux/master/docs/KERNEL_EL2.md) [contested], by analogy (one MT6833 phone) In that case KVM returns `-ENODEV` and `/dev/kvm` never appears, whatever the config says. [G15-4](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/kvm/arm.c) [confirmed] for the code path; the entry level on vegas is not a runtime observation
- Android's virtualization framework is not functional on stock -4-2. The `com.android.virt` APEX is the disabled stub, and no hypervisor property is set. [G15-8](../tools/locked/) [confirmed]
- Any kernel or UEFI payload started by stock lk will probably also run at EL1 under GenieZone. GenieZone contains a string about forbidden SMC calls. Whether a non-vendor kernel runs cleanly there is unknown.

### 2.7 Unlock, firmware baseline and rescue

**Unlock and baseline**

- All eight phones are locked. Unlock needs a patched lk and wipes data. (notes) A repository note, from static reading of lk, says the `oem unlock` and `oem lock` paths themselves erase `nvdata` and `md_udc`, and that the modem normally rebuilds `nvdata` from `nvram`. [G13-15](../tools/locked/) verifier note, [unverified] So the unlock step may touch NV, and the per-phone backup of section 6 belongs before it.
- Under the rules of this report unlocking is one-way. Relocking (`oem lock`, `fastboot flashing lock`, `flashing lock_critical`) with custom images on the slot or with the patched lk in place is the classic hard-brick path, and relocking is the only way back to the farm's locked, green end state D. An unlocked experiment unit therefore leaves the D fleet for good: choose an expendable unit and remove it from route-D maintenance (`farm.py`).
- The unlock window is stated two ways. The notes say security patch <= 2026-09. One guide says the hole is reported patched in builds from September 2026 onward, with August untested. [X-JES](https://github.com/jesussaves-dev/moto-g-power-2026-root) [unverified]; this sentence of the guide is not a ledger claim. Builds -4-7 and -4-9 exist and no source says which side of the fix they are on. Keep experiment phones on -4-2 and block OTAs before the unlocked unit first joins a network (method and timing in section 7.2, step 2; reasons in section 6.4).
- Build pairing: -4-2 is 5.15.180 at 9b2308ac0ad6 and matches the Motorola tag. The LineageOS tree needs -4-3 (5.15.189) and aborts on anything else. [PR-7](https://github.com/jimmielin/android_device_motorola_vegas26) [contested] The UBports Halium kernel base is 5.15.178. [HA-6](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/tree/android13-5.15-halium) [confirmed]
- The stock lk enforces anti-rollback on bootloader images. The owner's downgrade from -4-3 to base worked only after a community "rollback" lk was flashed first. [PM-12](../tools/locked/) [unverified]

**Rescue below fastboot: none found**

- The vegas26 tree author states "no known BROM rescue path: a damaged bootloader chain is a permanent brick". [PR-8](https://github.com/jimmielin/android_device_motorola_vegas26) [confirmed] as the author's statement. The same author says only `boot`, `init_boot`, `vendor_boot`, `dtbo`, the vbmeta partitions and the logical partitions in `super` should ever be flashed. [PM-11](https://github.com/jimmielin/android_device_motorola_vegas26) [unverified]
- mtkclient has a chip entry for hardware code 0x1209 (MT6835) with the XML download-agent mode. The BROM payload address, the loader and the exploit fields of that entry are commented out, and the payload directory has no MT6835 payload. So mtkclient ships no BootROM exploit for this SoC. The vegas hardware code has not been read; 0x1209 is assumed from the SoC. [RS-1](https://raw.githubusercontent.com/bkerler/mtkclient/main/mtkclient/config/brom_config.py) [confirmed]
- None of the download agents bundled with mtkclient 2.1.4 covers 0x1209, and that was still true on its main branch on 2026-11-20. This is about the bundled agents only. It was reported on a Vivo phone and reproduced by the verifiers from the files. [RS-2](https://github.com/bkerler/mtkclient/issues/435) [confirmed], by analogy
- On a Motorola XT2513-1 (MT6835), mtkclient reached the preloader, which reported secure boot on, SLA off and DAA on. No download agent was available and nothing was uploaded. No one offered a Motorola MT6835 agent, and the issue closed without a fix. This shows that no public agent is known. It does not show that a correctly Motorola-signed agent would be rejected, and it says nothing about BootROM mode. [RS-3](https://github.com/bkerler/mtkclient/issues/182) [confirmed], by analogy
- A Motorola XT2515-2 owner reported "da signature fail" and a moto g 2025 owner reported the same, with no logs. Thin evidence. [RS-4](https://github.com/bkerler/mtkclient/issues/201) [contested], by analogy
- For another MT6835 phone with DAA on, the mtkclient maintainer answered "Authentication needed or you downgrade the preloader to engineering preloader." [RS-5](https://github.com/bkerler/mtkclient/issues/217) [unverified], by analogy. A forum report on a Samsung MT6835 phone says BROM needs a test point and a paid tool. [PM-15](https://www.hovatek.com/forum/post-245958.html) [unverified], by analogy
- A community summary of Motorola bootloader policy says Motorola disables BROM USB download by e-fuse on newer MediaTek devices and that the stock download agents only flash the bootloader. Hands-on reports confirm a BROM block on some Motorola MediaTek models and not on others, and none is about MT6835 or vegas. [RS-6](https://github.com/zenfyrdev/bootloader-unlock-wall-of-shame/blob/main/brands/motorola/README.md) [contested], by analogy
- The stock -4-2 lk contains Motorola code that checks the BROM-mode status and re-blows the BROM-disable fuse if BROM mode is not disabled. It also has an `oem ssm_test` option labelled "Blow BROM DIS fuse and disable blankflash". The owner's patched lk images keep this code. This is static evidence. When the re-blow path runs, whether the test command is reachable on a production unit, and whether the fuse is blown on the owner's phones were not determined. [RS-7](../tools/locked/) [confirmed]; the partition-map track found the same strings ([PM-10](../tools/locked/) [unverified]). Never run `oem ssm_test` with any argument: some of its options blow fuses.
- The preloader does open a USB tool-handshake window. On one stock, locked unit the `expdb` log shows it on normal boots with a cable attached (about 3 seconds on the newest boots) and shows it skipped on a boot with volume-down held. The preloader contains download-agent signature-check code and also a branch that disables the check. On these fused units the check is expected to be active; that is unverified, because no agent has ever been sent to a vegas preloader. Treat preloader download mode as present and unusable without a Motorola-signed agent. [RS-8](../backups/) [contested] (the original wording said "on every boot" and "verifies any DA" and was narrowed)
- The owner's -4-2 firmware zip is driven only by fastboot steps and contains no download agent, auth file or scatter file. Its flashfile writes `efuse.img` to `efuseBackup`, not to `efuse`. Motorola's generic rescue-tool help page describes no download-mode procedure. That silence proves little: for another Motorola MediaTek phone (moto g23, MT6768) the rescue tool was found to download a separate flash tool that contains a download agent. Whether it serves one for vegas is unknown. [RS-9](https://help.motorola.com/hc/apps/service/rsa/58/en-us/CGT1908243440.html) [contested] (the original wording "describes only fastboot identification" was refuted; this is the corrected wording)
- The same-platform Moto Pad 2026 project does have a BROM path: mtkclient with a factory download agent and auth file. [PR-16](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/53-wsl-write-boot-a.sh) [unverified] Those files come from a Lenovo ZUI ROM that the rescue tool downloaded for that tablet, and the project states its use for recovery was never exercised. [RS-10](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/52-wsl-printgpt.sh) [unverified] Nothing ties those keys to Motorola phones, and no such files are known for vegas.
- A 2026 MediaTek tablet (Helio G99) fails download-agent authentication under mtkclient. [NP-13](https://wiki.nura.eco/wiki/Onn_11_Core_Tablet_%28onn-t405a%29) [unverified], by analogy
- In the one vegas26 incident where a phone "dropped off USB entirely", the phone was not below fastboot. It came back after a replug and was repaired with fastboot writes. [RS-11](https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/HEAD/ACTIONS-LOG.md) [unverified]
- Conclusion: lk fastboot is the only way back that anyone has shown. Any write that stops lk from reaching fastboot should be planned as permanent. The only thing below that is a chip-level UFS programmer at a service centre, known from one by-analogy report (G12-5).

**Ways to observe a failed boot**

These matter because there is no RAM boot and a hung test image costs a boot attempt.

- The stock kernel has RAM pstore with console and pmsg and reboots at once on panic. The stock DTB has no ramoops node; lk reserves a pstore region and passes `ramoops.*` arguments on the kernel command line. Capturing a failed Linux boot this way has not been tested, and it needs a warm reset, not a power-off. [RS-12](../tools/locked/) [unverified]
- On a stock phone the `expdb` partition already holds readable preloader and lk boot logs, including the A/B retry state. The `pstore` partition was all zeros in the same backup. [RS-13](../backups/) [unverified]
- lk has debug knobs: `oem config` entries that can add to the kernel command line and enable a kernel console (off by default), a uart8250 earlycon template, a command that dumps the preloader and lk log, and a boot-menu item for bootloader logs. Which of them work on an unlocked unit is untested. [RS-14](../tools/locked/) [unverified] By the same lk strings, `oem config set` and `oem config unset` write Motorola's `utags` partition (RS-14 [unverified]), which section 6.1 puts in class A. Do not probe which keys are writable on a unit that matters. Back up `utags` first, and prefer a command line built into the initramfs or the kernel. The rescue track rates the read-type items (the log dump and the boot-menu logs) as low risk (track note, [unverified]).
- Two MT6835 Linux ports use an initramfs USB console with a boot-loop breaker. On the moto g power 2025 (XT2515-1, same SoC, stock 5.15.180 kernel), an initramfs gave a root shell over a USB serial gadget, `fastboot boot` did not boot from RAM there either, and rebooting into fastboot from Linux needed `reboot-mode.ko` and `syscon-reboot-mode.ko` loaded first. [RS-15](https://github.com/zoan37/moto-g-power-2025-omarchy/blob/HEAD/notes/linux-bringup-20261006.md) [unverified], by analogy. The Moto Pad port holds at a USB network console if the previous boot did not finish and saves the pstore files of that boot. [RS-16](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/archinit) [unverified], by analogy
- A preloader handshake that asks lk to start in fastboot without any download agent is used on the Moto Pad. It is untested on vegas and works only while lk is intact (track note, [unverified]). It talks to the same preloader tool window that carries the download-agent path, so it is an optional check, not a required one: run only the documented META-to-FASTBOOT request, never a download-agent upload or any write command (section 7.2, step 2).
- No UART pad map for this phone is public.

## 3. Directions, most native first

Common to every direction: an unlocked unit on -4-2, the per-phone backup of section 6 taken before unlocking, slot A only, no lk write other than the owner's established unlock patch, and nothing else in the bootloader chain written.

Every brick-risk rating below carries the same conditions, stated once here. lk has no RAM boot (LG-10), so every test is a flash and a hung image costs a boot attempt. A rating of "low" holds provided that the slot-A successful flag survives the flash or the boot-control state is checked after each failed boot, that stock images are restored after at most two or three failed boots, and that lk still reaches fastboot. Whether flashing `boot_a` or `init_boot_a` clears the successful flag is unknown. If it does, repeated hung boots can end in a fallback to the all-zero slot B (G12-1, G12-4, PM-8), and there is no rescue below fastboot (section 2.7).

For `boot_a` the rating has two cases. It is low for a footered `boot_a` that carries the stock kernel binary (section 7.2, step 4a). It is medium for a footerless image or any self-built kernel or payload until step 4a has shown the boot-time behaviour, because the boot-time tolerance of a hash mismatch (LG-12) is [unverified] and the effect of a flash on the successful flag is unknown. The lk-gate track itself rates the footerless option medium. Step 4a is therefore mandatory before any footerless or self-built image goes into `boot_a`.

Sections 3.1 to 3.8 are ordered from most to least native. Sections 3.9 to 3.12 are cross-cutting or coexistence arrangements.

### 3.1 Mainline kernel for MT6835

**How it works.** Write MT6835 support against current mainline, boot it from stock lk, and run an ordinary distribution.

**What must be built or ported**

- Upstream has no MT6835 SoC support. At v7.4-rc3 the string "mt6835" appears only as a UART DMA compatible. [ML-1](https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/drivers/dma/mediatek/mtk-uart-apdma.c) [confirmed] On linux-mediatek in the last 13 months it is the only patch whose subject names this SoC; a few others touch the same UART-DMA compatible without naming it in the subject. Its commit message names the SoC "Dimensity 6300 MT6835". [ML-2](https://lists.infradead.org/pipermail/linux-mediatek/2025-November/101140.html) [confirmed] No MT6835 base series exists on the list. Posting one, in the shape of the MT6833 and MT6895 series now under review, is the upstream-first variant of this direction (track option, [unverified]).
- GPL downstream drivers for the missing pieces are public in a OnePlus tree: `clk-mt6835*.c`, `pinctrl-mt6835.c`, `mtk-scpsys-mt6835.c`, `mt6835.dts`. The pinctrl driver uses the "paris" framework that mainline also uses. The clock and power-domain drivers sit on downstream frameworks and need real porting. [ML-11](https://github.com/OnePlusOSS/android_kernel_oneplus_mt6835/blob/20ad6b319f91a8fd036077ee7aa27683469b8292/drivers/pinctrl/mediatek/pinctrl-mt6835.c) [confirmed] The Motorola tag in section 2.2 has the vegas and orlando board files.
- The stock vegas DTB already uses compatibles that mainline drivers match for UART, mtu3, T-PHY v2, the UFS host and the watchdog. [ML-10](../tools/locked/) [unverified]
- Mainline has no driver for the PMIC interface (`mt6835-spmi`), MT6377, MT6375, the CCCI modem or the phone connsys Wi-Fi. [ML-16](https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/drivers/spmi/spmi-mtk-pmif.c) [unverified] There is no CCCI modem driver in `drivers/net/wwan`. [HW-4](https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wwan/Kconfig) [confirmed]
- Boot method: keep `vendor_boot`, `init_boot` and `dtbo` stock so lk's fixups succeed. Put a small shim in `boot` that copies memory and reserved-memory from lk's FDT into an embedded mainline DTB and jumps to an embedded kernel. This shim is an inference from the sibling ports and is untested. The alternative, a mainline DTB that keeps the whole stock tree disabled and is built with symbols, is what a22x does on Samsung's LK. [ML-7](https://gitlab.com/pessdres/a22x-mainline/-/blob/main/docs/BUILDING.md) [confirmed] On vegas that would mean a custom `vendor_boot`, which is the risky variant (section 2.3).
- Boot-image variants that carry their own DTB are a further candidate, because they avoid a custom `vendor_boot`: a header v2 or v0 image with the DTB inside `boot` (what a22x uses on Samsung's LK, and what Nura's wiki says usually makes GKI bootloaders ignore `vendor_boot` and `init_boot`), or a DTB linked into the kernel. [NP-4](https://gitlab.nura.eco/nura/boot-deploy/-/merge_requests/83) verifier note, [unverified], by analogy. This is untested on Motorola's lk and must never be combined with erasing or changing `vendor_boot`.
- Whatever goes into `boot` must be gzip or lz4-legacy compressed, or lk is expected to panic (LG-11, section 2.3).
- Hand-off hazard, by analogy: the Nura port for the MT6878 CMF Phone 1 boots through a patched U-Boot because that board needs a secure-monitor call on each jump to the kernel. [ML-13](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/master/device/testing/device-nothing-tetris/deviceinfo) [unverified] Whether MT6835 needs the same call, or a secure-world watchdog fires without it, is unknown. It applies to the shim here and to UEFI or U-Boot in section 3.2.

**What works on comparable devices**

- Base series for MT6833 and MT6895 are under review upstream and reach an initramfs. The MT6833 one uses a framebuffer console and was tested with the kaeru LK payload. The MT6895 one uses serial and a non-public modified LK. [ML-4](https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116576.html), [ML-5](https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116317.html) [confirmed] kaeru targets ARMv7 LK only. [ML-15](https://github.com/R0rt1z2/kaeru/blob/HEAD/README.md) [unverified] The vegas `lk` sub-image is AArch64 (G12-4 and LG-1 disassembly), so kaeru does not apply, and patching lk is excluded by section 6.
- a22x-mainline (Galaxy A22 5G, MT6833, Linux 7.2, 143 patches, one developer, self-reported) boots from stock Samsung LK by flashing only `boot`. Its root filesystem replaces Android's `userdata`. [ML-6](https://gitlab.com/pessdres/a22x-mainline/-/blob/main/README.md) [contested] It has no cellular modem and no camera. Wi-Fi is the vendor gen4m driver ported out of tree. [ML-8](https://gitlab.com/pessdres/a22x-mainline/-/blob/main/README.md) [confirmed]
- The claim that the Nothing CMF Phone 1 (MT6878) is the most advanced mainline Dimensity port, with no touch, Wi-Fi or modem, was refuted: its wiki table is stale. [HW-2](https://wiki.nura.eco/wiki/Nothing_CMF_Phone_1_%28nothing-tetris%29) [contested] The MT6895 xaga page lists display, touch, GPU, audio, Wi-Fi, Bluetooth and battery as working, with calls and data not working. [X-XAGA](https://wiki.nura.eco/wiki/Xiaomi_Redmi_Note_11T_Pro_%28%2B%29_/_POCO_X4_GT_/_Redmi_K50i_%28xiaomi-xaga%29) [unverified] This is one verifier's reading of the page; another track could not confirm the Wi-Fi and Bluetooth status for MT6895.
- A Volla Plinius (MT6878) fork self-reports Wi-Fi, Bluetooth, SMS, LTE data and calls on a mainline-based kernel. Its modem driver is not in upstream Linux, and the report is a single author's. [G23-14](https://github.com/karagos01/plinius-mainline) [contested]
- So "modem is out of reach on mainline MediaTek" is too strong as a general statement. It remains true that nothing exists for MT6835.

**Expected hardware coverage on vegas**

| Item | Expectation |
|---|---|
| Display / UI | lk's framebuffer through simple-framebuffer at first. Native DSI needs MT6835 mmsys and DSI work. |
| GPU | The Mali node has a JOB interrupt, so Panfrost is the candidate. The GPU ID and the gpueb power path are unknown. [ML-9](https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/Documentation/devicetree/bindings/gpu/arm,mali-bifrost.yaml) [unverified] |
| USB networking | After clock, pinctrl and power-domain ports. |
| Wi-Fi | Only by porting the vendor connsys stack out of tree, as a22x did. |
| Modem | Assume absent. |
| Camera | Assume absent. libcamera has no MediaTek pipeline handler. [HW-11](https://raw.githubusercontent.com/libcamera-org/libcamera/master/meson_options.txt) [unverified] |
| Charge limit | The vendor proc node will not exist. Charging control needs a new charger driver. |

**Android coexistence and overhead.** No runtime overhead. Android survives only if the root filesystem goes on microSD or a `super` logical partition (section 3.9) and stock `boot` is reflashed to return.

**Effort.** Days to about two weeks for a first console. Three to eight weeks for a headless USB and storage node. Months for a phone with UI.

**Brick risk.** Medium until section 7.2, step 4a, has shown how lk boots a changed `boot_a`; after that, low while only `boot_a` is written, under the conditions at the top of section 3. A kernel that hangs early cannot mark the boot successful and cannot reboot itself to fastboot, so the stop rule matters most here. There is no thermal or charger driver in early stages, so sessions must be short and supervised.

**First experiment.** Offline: decompile the stock DTB and write the minimal `mt6835.dtsi`. On a phone: only after the lk-accepts-foreign-payload question is answered by the cheaper test in section 3.2.

**Nura packaging.** No MT6835 device package was found in Nura's package tree or package index (verifier side-checks; [ML-12](https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/master/device/testing/linux-postmarketos-mediatek-mt6878/APKBUILD), [PR-11](http://mirror.nura.eco/postmarketos/main/aarch64/APKINDEX.tar.gz) [unverified]). No wiki page for vegas or any MT6835 device was found ([NP-9](https://wiki.nura.eco/wiki/Samsung_Galaxy_A15_5G_(samsung-a15x)) [unverified]; the wiki search was reported as unreliable). Its "testing" category requires a close-to-mainline kernel; vendor-kernel ports go in "downstream" and are described only as a step toward mainline. [NP-1](https://docs.nura.eco/pmaports/main/packaging/device-categorization.html) [confirmed] A mainline vegas port is the only kind Nura would carry long term.

### 3.2 UEFI or U-Boot chain-loaded from stock lk (the UniXNU pattern)

**How it works.** Pack a UEFI firmware image as the gzip "kernel" of a boot v4 image in `boot_a`. Stock lk decompresses it to 0x40000000 and jumps in. The firmware reuses lk's framebuffer and then loads an OS.

**Evidence**

- On the Lenovo TB365FC (MT6835), a Mu-Silicium-derived UEFI boots this way and reaches a menu. This is one author's self-report on one unit and is not replicated. [UE-1](https://github.com/LittleStar-OuO/uefi-tb365fc) [confirmed] as a report
- The earlier assessment "stops at a menu, no storage, no OS booted" was refuted as stale. The maintainer's newer branches (2026-11-04 to 2026-11-21) report XNU booting to the iPadOS home screen, with a 58 MiB payload in the `vendor_boot_a` ramdisk and a UFS driver on the XNU side. The UEFI firmware itself still has no UFS, USB or SD driver. [X-TB](https://raw.githubusercontent.com/LittleStar-OuO/UniXNU-tb365fc/docs/readme-zh-en-20261121/README.en.md) [contested], unmerged and self-reported
- That repository is internally inconsistent: `PORTING.md` still says nothing has been read from the tablet. [UE-1](https://github.com/LittleStar-OuO/uefi-tb365fc) [confirmed]
- In that firmware, the GPIO and MSDC tables for MT6835 are byte-identical copies of the MT6833 ones. [UE-2](https://github.com/LittleStar-OuO/uefi-tb365fc/blob/HEAD/PORTING.md) [contested]
- None of this involves Linux. No Linux boot through a MediaTek UEFI was found. Upstream Mu-Silicium lists three MediaTek devices, all inactive, none with working Linux boot, and has no MT6835 package. [UE-7](https://github.com/Project-Silicium/Mu-Silicium/blob/main/Status.md) [confirmed]
- Mu-Silicium's shortcut of reusing UEFI driver binaries from the phone's own firmware is Qualcomm-only. MediaTek phones ship LK, so there is nothing to extract. [UE-8](https://github.com/Project-Silicium/Guides/blob/main/Silicium/Porting/Snapdragon/Device/README.md) [confirmed]
- The vegas `vendor_boot` addresses match the TB365FC ones (section 2.3). The claim that this means "no address shim is needed on vegas" was refuted as worded. It is a reasonable first hypothesis that depends on Motorola's lk behaving like Lenovo's. [UE-3](https://github.com/LittleStar-OuO/uefi-tb365fc/blob/HEAD/Resources/Configs/tb365fc.toml) [contested]
- A foreign kernel has also been reported booting directly from stock MediaTek LK through an Android boot image, with no UEFI in between. One such project reports XNU reaching the home screen on a Motorola moto g54 5G (MT6855). This is the closest evidence that a Motorola MediaTek lk jumps to a non-Linux payload. [UE-5](https://raw.githubusercontent.com/LittleStar-OuO/UniXNU-tb365fc/docs/readme-zh-en-20261121/README.en.md) verifier note, [unverified], by analogy, single source
- On vegas, static reading of the flash gate predicts that a footerless image in `boot_a` is accepted on an unlocked unit, and that lk panics unless the payload is gzip or lz4-legacy compressed (sections 2.3 and 2.4). Neither was run.

**What it does and does not buy.** A boot menu and a standard loader. It does not add drivers. On arm64, Linux under UEFI still needs a full device tree. [UE-16](https://docs.kernel.org/arch/arm/uefi.html) [unverified] The kernel it starts is either a mainline kernel (section 3.1) or the GKI kernel through its EFI stub. Nobody has reported the vendor modules working after an EFI-stub entry.

**U-Boot variant.** Upstream U-Boot has no MT6xxx phone target. It carries a MediaTek UFS driver matching `mediatek,mt8183-ufshci`, the compatible in the vegas DTB, and the mtu3 USB driver. Neither is tested on MT6835 and there is no MT6835 clock driver. [UE-11](https://raw.githubusercontent.com/u-boot/u-boot/c1958b5f6cce03956d309ce422b5d9f819955d4a/arch/arm/mach-mediatek/Kconfig) [contested] The tracks disagree on precedent: the UEFI track found only U-Boot ports that replace lk (see section 5), while one verifier reports the MT6878 Volla Plinius fork chain-loading a ported U-Boot from stock LK (G23-14 verifier note, [unverified]). No MT6835 U-Boot exists either way.

**Hardware coverage.** Whatever the loaded kernel provides.

**Android coexistence.** With a UEFI image in `boot_a`, Android boots only by reflashing stock `boot` or by teaching the firmware to start the GKI kernel. No recipe exists for the second.

**Effort.** One to three weeks to a menu, if Motorola's lk accepts the payload.

**Brick risk.** Two ratings, both under the conditions at the top of section 3.
- Menu test: `boot_a` only, low to moderate, and only after step 4a (a non-Linux payload is a self-built image in the sense of the top of section 3). A payload cannot mark the boot successful, so each run may cost a boot attempt.
- Loading an OS: higher. The firmware has no UFS, USB or SD driver, and the only reported OS boot carries its payload in the `vendor_boot_a` ramdisk. On vegas that means either a payload embedded in the 64 MiB `boot_a`, or a repacked `vendor_boot_a` that keeps the stock DTB bytes. The second is the variant section 2.3 treats as risky.
- The secure-monitor hand-off hazard of section 3.1 applies to any loader that jumps to a kernel itself (by analogy, [unverified]).

**First experiment.** A minimal gzip-compressed payload in `boot_a` that only proves lk jumps to non-Linux code (for example, one that fills the lk framebuffer). It answers the gating question for sections 3.1 and 3.2 at once. It comes after the stock-kernel repack test of section 7.2, step 4, so that the flash gate and the boot-control behaviour are already known.

### 3.3 Source-built Motorola 5.15 kernel with own-built modules

**How it works.** Build `kernel-mtk` at `MMI-W1WN36.18-114` with the vegas fragment, the orlando overlay and the external module repositories at the same tag. Because kernel and modules are built together, the KMI no longer binds for the modules rebuilt from source: VT with a panel console, KEXEC, SYSVIPC, namespaces, CGROUP_PIDS and BTRFS all become possible. Any stock module that is reused brings the CRC and layout constraint back, and the camera-stack sources lack the tag. This needs a custom `vendor_boot` and `vendor_dlkm`. The custom `vendor_boot` must carry the stock DTB bytes, and the stock `dtbo` must stay untouched, until Motorola's lk device-tree handling is known. Only the modules and the ramdisk change.

**Status**

- The source exists and names vegas (section 2.2). No evidence was found that anyone has built or booted it for vegas26.
- The orlando overlay includes a generated `cust.dtsi` that is not in `kernel-mtk`, so the dtbo cannot be rebuilt from that repository alone. [VK-5](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/boot/dts/mediatek/mt6835-orlando-evb-overlay.dts) [confirmed]
- The camera-stack module repository lacks the tag. [VK-7](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/configs/mgk_64_k515_defconfig) [unverified]
- A panel text console needs this route, or at least a rebuilt `mediatek-drm.ko`. The vendor driver compiles its fbdev code only under `DRM_FBDEV_EMULATION`, which no defconfig sets. [VK-12](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/drivers/gpu/drm/mediatek/mediatek_v2/Makefile) [unverified]
- Nura would place this in "downstream". Its kernel-config lint requires VT, SYSVIPC, USER_NS and PID_NS, which this route can satisfy. [NP-3](https://gitlab.nura.eco/nura/pmaports/-/raw/main/kconfigcheck.toml) [confirmed]
- Nura's tooling generates `boot` and `vendor_boot` for header v4 and never touches `init_boot`, so `init_boot` must be handled by hand. [NP-4](https://gitlab.nura.eco/nura/boot-deploy/-/merge_requests/83) [contested]
- Nura dropped libhybris, so a Nura install gets no Mali, camera or RIL blobs. [NP-14](https://wiki.nura.eco/wiki/Hybris) [unverified]
- An older fallback, rebuilding the MT6835 modules from the public BraX3 kernel tree (5.15.148), was proposed by one track on the premise that Motorola had published no vegas source. The Motorola tag supersedes it. (track option, [unverified])
- Flash gate for `vendor_boot_a`: it goes through the same AVB hash check as `boot` and `init_boot` (LG-2), and the stock descriptor size is 30642176 bytes (LG-16). No custom `vendor_boot` has been flashed on -4-2 by anyone; the -4-3 log flashed one that carried the stock DTB (LG-6).

**Hardware coverage.** As section 3.4 in principle, minus anything whose module source is missing.

**Effort.** Several weeks, dominated by reconstructing MediaTek's build flow.

**Brick risk.** Moderate to high, and higher than section 3.4. A custom `vendor_boot` replaces the recovery ramdisk and fastbootd, changes what lk parses, and can break display and USB together. If a changed DTB stops lk before fastboot, there is nothing below to restore from (section 2.7). Keeping the stock DTB bytes is what holds this at moderate.

**First experiment.** Offline only: build the tree and diff the resulting module list, vermagic and CRCs against the 376 stock modules. That also answers whether the published source matches the shipped binaries.

### 3.4 Rebuilt GKI kernel, stock vendor modules, plain Linux userspace

This is the recommended main path.

**How it works**

1. Build AOSP `kernel/common` at 9b2308ac0ad6 with the stock config plus a small fragment, and pack it as a gzip kernel in a header v4 image like stock.
2. Flash it to `boot_a`. Make the image footered so that its footer does not sit below the stock `boot` descriptor size of 21549056 bytes (section 2.4); a footerless image is the second choice. Either comes only after the stock-kernel repack of section 7.2, step 4a. Leave vbmeta stock at first.
3. Leave `vendor_boot`, `init_boot`, `dtbo` and the vendor partitions stock. The 376 stock vendor modules are expected to load by the static check; confirm with the offline CRC gate before any flash. The GKI modules in `system_dlkm` are a separate matter (section 2.1): they are signed with Google's key, so either MODULE_SIG_PROTECT goes off or `system_dlkm` is rebuilt from the same tree.
4. Start Linux without ever running Android's `/init`. If stock `init_boot` stays in place, the generic ramdisk's `/init` wins (NP-5) and Android's init takes PID 1, which is how the Pixel 7a attempt failed (NP-7). The tablet recipe avoids this by embedding the initramfs in the kernel and starting it under its own name with `rdinit=` in CONFIG_CMDLINE. The alternative is to replace `init_boot_a` as in section 3.5.
5. That initramfs loads the modules, brings up a USB NCM gadget, and switches to an ordinary root filesystem.

A lower-risk first boot of the rebuilt kernel is with Android: the same kernel without the `rdinit=` line and with stock `init_boot`. If Android comes up, the flash gate, the boot path and the module loading are proven with adb available, and the kernel is known to serve both systems. Both pass-2 precedents below boot Android this way. Nobody has shown it on vegas.

**What must be built**

- **Kernel base.** The fragment used on the tablet enables DEVTMPFS, FHANDLE, AUTOFS_FS, TMPFS_POSIX_ACL and VT, and disables TRIM_UNUSED_KSYMS and MODULE_SIG_PROTECT. Its author found that turning DEBUG_INFO off changed CRCs. The per-option probe compared only three symbols against one module; the repository also has a script that checks every module. The stated reason for keeping LOCALVERSION_AUTO does not match Google's source; keeping it on is harmless. [VK-9](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/HEAD/kernel/arch-fragment.config) [contested]
- **Config match.** The tablet's stock config differs from the vegas config in one line. [VK-9](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/HEAD/kernel/arch-fragment.config) [contested]
- **Offline gate before any flash.** Compare every stock module's imported CRCs against the built `Module.symvers`. That means the 376 vendor modules and also the `system_dlkm` modules, which no track has listed or checked yet. For anything that touches struct layout, add a BTF member comparison against the stock kernel. A passed vendor-module check alone can still end in a boot loop under Android if the `system_dlkm` modules are refused.
- **Static result already in hand.** All 2348 kernel symbols imported by the 376 stock modules are present with identical CRCs in the ACK ABI definition at 9b2308ac0ad6, and also at the UBports base b9c7089e (5.15.178). The version part of vermagic is ignored when modules carry CRCs. This is a check against Google's ABI file, not against a built kernel. [G13-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/android/abi_gki_aarch64.xml) [confirmed]
- **Initramfs.** Either embedded in the kernel, as on the tablet, or in `init_boot`.
- **Pass-2 precedents on the same kernel generation** (both self-reported, both by analogy, both with Android as the userspace):
  - A recipe for the REDMAGIC 8S Pro+ (Qualcomm SM8550, ACK android13-5.15 at 5.15.167) builds from the phone's own `/proc/config.gz`, turns TRIM_UNUSED_KSYMS off, keeps the stock version string, and adds namespace options with a kABI patch. Its offline script reports 0 missing symbols and 0 CRC mismatches across 374 vendor modules, including those in the `vendor_boot` ramdisk. Only the kernel inside `boot` was replaced, and the KernelSU LKM in `init_boot` was left alone. Single commit, described by its author as fully AI-built, no independent replication. The same offline script approach can be reused for the vegas modules. [CX-6](https://github.com/fkun1754/redmagic-nx729j-droidspaces-kernel) [confirmed] as a report
  - A Samsung Galaxy A25 5G (SM-A253Z, MT6835, kernel 5.15.180, Android 16) runs a rebuilt kernel that replaces only `boot.img` and keeps the stock vendor modules; its maintainer lists it as working. That kernel is built from Samsung's source drop, not from Google's tree. [CX-5](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/community-supported-devices.md) [confirmed] as a report
  - `include/linux/sched.h` at the vegas commit is byte-identical to the one at the REDMAGIC commit (CX-6 verifier check), so patches against that header apply at source level.

**Adding namespaces and SYSVIPC (feature-kernel variant)**

The tracks disagreed on how dangerous these options are. Resolved:

| Option | Layout effect | Evidence |
|---|---|---|
| SYSVIPC | Adds two members to `task_struct`. Cannot be switched on naively. | [VK-11](https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/configs/gki_defconfig) [unverified]; agreed by every lens that read `sched.h` |
| USER_NS, PID_NS, POSIX_MQUEUE | Gate only functions and macros in the headers examined, not struct members. The tablet author left them off as a precaution, without testing. | [G13-10](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/cred.h) [unverified], [PR-4](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/kernel/arch-fragment.config) [confirmed] |
| CGROUP_DEVICE | Breaks the KMI when plainly enabled. UBports leaves it off with "FIXME: breaks GKI ABI somehow". | [HW-7](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/raw/android13-5.15-halium/arch/arm64/configs/halium.config) [confirmed] |
| CGROUP_PIDS, CFS_BANDWIDTH | Break the KMI with no patch available on 5.15. CGROUP_PIDS adds a cgroup subsystem and so resizes arrays inside `struct cgroup` and `struct css_set` in the tree at the vegas commit. Off in every tree examined. Per-container process and CPU limits are therefore unavailable while stock modules are kept. | [CX-2](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md) [confirmed] |
| Device control on cgroup v2 | The cgroup device BPF program type is compiled under CGROUP_BPF, which stock vegas has, so cgroup-v2 device control does not need CGROUP_DEVICE. | [CX-4](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/bpf_types.h) [unverified] |

- Modules compiled without USER_NS still inline init-namespace assumptions. That is a semantic risk, not a layout one. [G13-10](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/cred.h) [unverified]
- Ready-made SYSVIPC patch: UBports keeps the SysV state past the end of an over-allocated `task_struct` slab slot. [HA-6](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/tree/android13-5.15-halium) [confirmed] Its 18 Halium commits replay onto 9b2308ac0ad6 without textual conflict. The result was not compiled, and the scratch tree was not kept in the repository. [G13-2](https://github.com/MotorolaMobilityLLC/kernel-mtk/tree/MMI-W1WN36.18-114) [confirmed]
- The realme 12x 5G (MT6835) precedent was refuted as worded. It does not show that these options can simply be enabled. That kernel needed SysV state confined to KABI reserve slots 1-3 because an Oplus module writes slots 4-8, and its own README says "CRCs cannot see these changes". One earlier build passed the CRC check and was still wrong. [PR-5](https://github.com/ivangotoy/rmx3997-kernel) [contested]
- Motorola's published modules use only `android_oem_data1` and `android_vendor_data1` for per-task state. A disassembly scan of the stock scheduler-class modules found no access in the reserve range. That scan is a heuristic. [G13-11](https://github.com/MotorolaMobilityLLC/motorola-kernel-modules/blob/MMI-W1WN36.18-114/drivers/moto_sched/msched_common.h) [unverified]
- A realme-style patch that gives the devices cgroup an id after the counted subsystems exists only for 5.15.225. [G13-9](https://github.com/ivangotoy/rmx3997-kernel/blob/2963eddf9f7b259bbc626348d4f97f3087b187b9/include/linux/cgroup_subsys.h) [unverified]
- A third SYSVIPC approach: the Droidspaces project moves the two SysV members into reserved padding slots of `task_struct`. It ships three alternative patches for kernels 5.4 to 6.6 that use slots 6-8 (the default), 3-5 or 1-3, and its documentation says to try the alternatives "if the device bootloops". On 5.15 the patches change only the SYSVIPC fields. One verifier found all eight reserve slots unused in Google's tree at the vegas commit; another found slot 1 in use at the current android13-5.15 branch head, where the 1-3 variant would not fit. Slots 6 to 8 are free in both. The Samsung MT6835 kernel above uses slots 6-8; the realme MT6835 kernel needed 1-3 because an OEM module writes 4-8. Which slots Motorola's modules touch is known only from the heuristic scan in G13-11, so a build that passes the CRC check is not proof. [CX-1](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md) [contested] (the original wording said one patch covers 5.4 to 6.6 and was refuted; this is the corrected wording)
- AOSP's kernel config requirements for Android 13 on 5.15 require SYSVIPC to be unset. The maintainer of the Samsung MT6835 kernel removed Android's boot-time "internal problem with your device" warning by making `/proc/config.gz` report the stock config. A feature kernel that also boots Android on vegas will probably need the same workaround. [CX-7](https://android.googlesource.com/kernel/configs/+/refs/heads/main/t/android-5.15/android-base.config) [unverified], by analogy

**systemd.** The conclusion "OpenRC only on the vendor kernel" rested on a Moto G50 report whose reading was refuted. The freeze there most likely comes from the G50's 5.4 kernel being below what current systemd requires, and Debian's systemd 257 is reported to boot on that same kernel. This is one verifier's reading of the source; the wiki page itself names missing FHANDLE plus statx as the likely cause, and a second verifier rated the reading medium confidence without reproducing it. [NP-6](https://wiki.nura.eco/wiki/Motorola_Moto_G50_%28motorola-ibiza%29) [contested] For vegas on 5.15: systemd's README lists FHANDLE as required. [X-SD](https://raw.githubusercontent.com/systemd/systemd/main/README) [unverified] UBports' Halium kernel config reportedly leaves FHANDLE off (HW-7 verifier note), and the REDMAGIC recipe above does not add FHANDLE yet reports systemd running in its container ([CX-8](https://raw.githubusercontent.com/systemd/systemd/main/README) [unverified]), so the requirement may depend on the systemd version and on what the instance does. The tablet runs Arch with FHANDLE added and USER_NS and PID_NS still off. [PR-4](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/kernel/arch-fragment.config) [confirmed] Whether systemd runs on the unmodified vegas kernel is open. On the rebuilt kernel with FHANDLE it is expected to.

**What works on the comparable device**

The Moto Pad 2026 (XT2575-4) is described by its README as MT6835 and by Motorola's tablet issue tracker as MT8755 on the MT6835 platform. Its stock kernel is GKI 5.15.185. One author self-reports Arch Linux with XFCE running from `userdata` on a rebuilt kernel in `boot_a`, with 300+ stock modules loading. [PR-1](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/README.md), [PR-2](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/README.md) [confirmed] as a report; [VK-8](https://github.com/Mattcabrices/moto-pad-2026-arch-linux) [contested] on wording and independence

- Working there: display, touch, Wi-Fi, Bluetooth, audio, USB network gadget, GPU through libhybris, hardware video decode.
- Not working there: camera and modem. The tablet is Wi-Fi only, and the author did not attempt either. [PR-3](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/README.md) [confirmed]
- No System V shared memory, so PostgreSQL cannot run there. [PR-4](https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/kernel/arch-fragment.config) [confirmed]
- Differences that matter for vegas: the tablet writes `boot_a` through BROM with a factory download agent, has a Lenovo-style lk, and its commit log records an unexplained boot hold after lk tried slot B. [VK-8](https://github.com/Mattcabrices/moto-pad-2026-arch-linux) [contested]

**Expected hardware coverage on vegas**

*USB networking.* Expected first. The kernel has the configfs NCM function built in; the device controller (`mtu3.ko`) is a vendor module the initramfs must load. [NP-15](https://docs.nura.eco/pmaports/main/packaging/device-packages/deviceinfo-reference.html) [unverified] A Pixel 7a attempt on a prebuilt GKI kernel never enumerated its gadget. [NP-7](https://wiki.nura.eco/wiki/Google_Pixel_7a_%28google-lynx%29) [unverified], by analogy On the moto g power 2025 (XT2515-1, MT6835, stock 5.15.180 kernel) a native initramfs is reported to give a root shell over a USB serial gadget, which is the nearest evidence that the MediaTek USB controller enters device mode without Android. [RS-15](https://github.com/zoan37/moto-g-power-2025-omarchy/blob/HEAD/notes/linux-bringup-20261006.md) [unverified], by analogy Whether mtu3 does so on vegas is still the first unknown.

*Wi-Fi.*
- On the tablet, Wi-Fi needs exactly two Android executables, `wmt_loader` (one-shot) and `wmt_launcher` (daemon). They run under the bionic linker in a small chroot with a property shim. There is no binder, no service manager and no HAL. [G23-1](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/README.md), [G23-2](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/pad-wifi-start) [confirmed]
- Loading `wlan_drv_gen4m_6835` pulls in the modem modules `ccci_md_all` and `mddp` (G23-1 verifier note). The tablet is Wi-Fi only; on a phone with a live 5G modem this is untested. Keep the NV partitions unmounted and confirm that no modem boot is triggered.
- The stock vegas vendor image has the same module names and starts `wmt_launcher` with the same command line. [G23-7](../tools/locked/) [confirmed]
- This is a Linux host with two closed helper binaries in a chroot. It is the reverse of a Linux chroot on Android, and it is still a chroot.
- An open replacement for both helpers exists for MT6833 (about 80 lines of Python). [G23-9](https://gitlab.com/pessdres/a22x-mainline/-/raw/main/conn/A22X-CHANGES.md) [confirmed] for MT6833 Motorola's source defines the same ioctl numbers and handles chip 0x6835 in the same case list. [G23-10](https://github.com/MotorolaMobilityLLC/vendor-mediatek-kernel_modules-connectivity-common/blob/MMI-W1WN36.18-114/common_main/linux/wmt_dev.c) [unverified]
- vegas keeps connsys firmware in raw `connsys_*` partitions and has no ROM-patch files in `/vendor/firmware`, so the replies a native launcher must give have to be captured from the stock launcher first. [G23-8](../tools/locked/) [unverified]
- Stock vegas also runs `wlan_assistant` to push NVRAM calibration and the MAC address; the tablet skips that step. For eight racked phones a default or duplicate MAC matters. The write is a plain prefixed write to `/dev/wmtWifi` and has been done without Android on MT6878. [G23-11](https://github.com/rajmahavir/cmf-mainline/blob/faea34bd8aa6fb396a9730aeffd3542d9561b3d7/tools/run-radio-test.sh) [unverified]

*Bluetooth.* On the tablet, no Android piece is needed once WMT is up: a 55-line bridge between the vendor driver's `/dev/stpbt` and `/dev/vhci`. It needs `hci_vhci` built for the rebuilt kernel, as a module or built in, because BT_HCIVHCI is off in the stock vegas config (section 2.1). [G23-4](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/pad-bt-bridge.py) [unverified]

*Display and UI without GPU.*
- Plain KMS clients run on the tablet's vendor `mediatek-drm` only on the legacy subset: SETCRTC, ADDFB, PAGE_FLIP, dumb buffers. [G23-5](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/wlroots-pad/include/backend/pad.h) [unverified]
- On the tablet, plane enumeration, hardware cursor, gamma, property writes and CRTC disable oops the kernel. [G23-6](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/src/noplanes.c) [unverified]
- A single-purpose KMS client or Xorg with a shadow framebuffer is a realistic "optional custom UI".
- VT gives virtual terminals but no text on the panel.
- vegas's 120 Hz video-mode panels are untested.

*GPU.* Only through libhybris with the service managers and the MediaTek allocator running. That is Halium in everything but name. [G23-3](https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/config/android-units/pad-android.target) [unverified]

*Modem.*
- No project runs a MediaTek modem from plain Linux on a vendor 5.15 kernel. [G23-16](https://gitlab.com/pessdres/a22x-mainline/-/raw/main/docs/MODEM-VALIDATION-20261103.md) [unverified]
- Templates exist: an open re-implementation of `ccci_mdinit` against vendor-style eccci nodes for MT6895, which calls itself not validated. [G23-15](https://github.com/MT6895-Mainline/mtk-ccci-userspace/blob/f6147b10cf7ef95932674506fbdfb7f3d67a1067/README.md) [unverified] And the Plinius daemon and ModemManager plugin. [G23-14](https://github.com/karagos01/plinius-mainline) [contested]
- Weeks of work with no promise. The modem writes NVRAM through its file-system channel, so any such server must run on a copy, never on the real partitions.

*Camera.* Not available.

*Audio.* ALSA mixer on the tablet. vegas's aw883xx smart amplifier is untested.

*Charge limit.* The vendor proc node is expected to exist once the stock charger modules load (unverified without Android; section 3.10).

**Android coexistence and overhead.** No runtime overhead. Android is gone if the root filesystem takes `userdata`. With the root filesystem on microSD or a `super` logical partition, Android returns by reflashing stock `boot`, or by the slot-A image switching of section 3.9 if the same kernel also boots Android. Nobody has shown the rebuilt kernel booting Android on vegas; both pass-2 precedents do exactly that on their devices (CX-5, CX-6). The same kernel with the namespace options is also the base for the Android-host container of section 3.11.

**Effort.** Days to a first USB shell. Weeks for display, Wi-Fi and audio. One to three more weeks for the feature-kernel variant.

**Brick risk.** Low for a footered `boot_a` carrying the stock kernel (section 7.2, step 4a). Medium for a footerless or self-built kernel image until step 4a shows the boot-time behaviour, because boot-time tolerance (LG-12) is [unverified] and the effect of a flash on the successful flag is unknown. After that, low while only `boot_a` is written, under the conditions at the top of section 3. By static reading no vbmeta step is needed for a footerless or correctly footered `boot_a` (section 2.4). If a vbmeta is written anyway, back up `vbmeta_a` first and keep its rollback index and patch level at or above the rollback index stored on that device; on phones that ever ran -4-3 (#7 and #8), assume 7 (section 2.4, rule 3). A layout mismatch in the feature-kernel variant causes memory corruption, not a clean load failure.

**First experiment.** Offline: build at 9b2308ac0ad6 with the minimal fragment and run the full CRC check against the 376 stock modules. On a phone: section 7.2, steps 4 and 5.

### 3.5 Stock GKI binary with a replaced `init_boot`

**How it works.** Keep stock `boot`, `vendor_boot` and `dtbo`. Replace the generic ramdisk in `init_boot_a` with a Linux initramfs whose `/init` loads the stock vendor modules from the vendor ramdisk, brings up USB networking, and either stops at a rescue shell or switches to a root filesystem.

**Why it is first.** It is the only custom image already flashed hands-on on an unlocked vegas (notes), it is one 8 MiB partition, and it answers the boot-chain questions before any kernel work. Static reading offers a likely reason that flash worked: the image kept its AVB footer above the stock descriptor size, and lk logs but tolerates a hash mismatch when unlocked (LG-2 [confirmed]; the size rule LG-3 and its application to this image LG-4 are [contested]; that the patched unlock lk has the same gate rests on LG-15 [unverified]). The probe image is not the same kind of image. The KernelSU ramdisk grew, so its footer sat at 3592192. A minimal initramfs is smaller than the stock generic ramdisk, and magiskboot-style repacking moves the footer to the new 4096-aligned end of the image (lk-gate track lead, [unverified]), which would put it below 3096576, the case LG-3 predicts is rejected. So pad the boot image explicitly to at least 3096576 bytes and re-add the hash footer with avbtool for partition `init_boot` at the 8388608-byte partition size, then verify offline that `vbmeta_offset` is at least 3096576 (section 7.2, step 0). A padded small image is untested; only the larger KernelSU image is hands-on. A moto g power 2025 project on the same SoC and kernel version reports a native initramfs with a USB shell on the stock kernel (RS-15, [unverified], by analogy).

**Limits**

- The stock kernel has no VT, USER_NS or SYSVIPC, so the userspace is constrained (see the systemd discussion in section 3.4).
- The stock config fails Nura's default kernel-config lint. That is a packaging check, not a boot gate. [NP-3](https://gitlab.nura.eco/nura/pmaports/-/raw/main/kconfigcheck.toml) [confirmed]
- A port on a prebuilt kernel will not be accepted into Nura's package tree, so this stays local. [NP-2](https://wiki.nura.eco/wiki/Porting_to_a_new_device/Kernel_package/Downstream) [contested]
- DEVTMPFS is off, so the initramfs must populate `/dev` itself.
- The initramfs must fit 8 MiB and should be lz4 like the vendor ramdisk. One Droidian port calls 8 MiB too small for a Halium initramfs. [X-TAP](https://github.com/Sype0/linux-android-xiaomi-tapas) [unverified] The UBports ports in section 3.6 do fit theirs in `init_boot`.
- Assume that stock recovery and fastbootd need the stock `init_boot`. The ledger lists this as an open question, not a finding, so observe it in section 7.2, step 3. Until then, do anything that needs fastbootd before the swap.
- The stock kernel has no PID namespace (CX-3), so no container with its own init can run on this route.
- To return to fastboot from the initramfs, `reboot-mode.ko` and `syscon-reboot-mode.ko` must be loaded first; on the 2025 sibling the first-stage module list omits them (RS-15, [unverified], by analogy). Every experiment initramfs in this report, not only this probe, must load both modules and carry a timed reboot to the bootloader.

**Evidence by analogy.** A Moto G50 (Qualcomm, vendor 5.4 kernel, stock `vendor_boot`) boots a console-only Nura root filesystem with SSH over USB, started by RAM boot only. [NP-6](https://wiki.nura.eco/wiki/Motorola_Moto_G50_%28motorola-ibiza%29) [contested] A Pixel 7a attempt that left Android's `init_boot` in place failed because Android's init took PID 1. [NP-7](https://wiki.nura.eco/wiki/Google_Pixel_7a_%28google-lynx%29) [unverified]

**Hardware coverage.** USB and UFS if the modules load. Display only for a KMS client and only if the display modules are in the vendor ramdisk. Wi-Fi needs `super` mapped for `vendor_dlkm` and for the helper binaries. Nura's unlock UI can render through DRM without VT, if the vendor driver tolerates it. [NP-16](https://gitlab.nura.eco/nura/buffybox/-/raw/main/unl0kr/README.md) [unverified] Modem and camera: no. Charge limit: the proc node is expected to exist once the stock charger modules load (unverified without Android).

**Android coexistence.** Best of all routes when combined with the `init_boot_a` switching in section 3.9, because the kernel and every other partition stay stock.

**Effort.** About a day for the probe.

**Brick risk.** Very low, and the only rating backed by a hands-on flash of the same partition on this phone. The hands-on image had grown; the padded small probe image is a different, untested image. If lk refuses it, nothing is written by static reading, because the validator runs before the flash command (LG-1 [confirmed]). The conditions at the top of section 3 still apply: watch the boot-control state (section 6), and build a timed reboot-to-bootloader into the initramfs.

**First experiment.** This is the recommended first flash (section 7.2, step 3).

### 3.6 Halium 13: Linux host with Android HALs in a container

**How it works.** A rebuilt GKI kernel in `boot`, the Halium initramfs in `init_boot`, the distribution image on the logical `system` partition, and stock `vendor_boot`, `vendor` and `vendor_dlkm`. Linux is the host. Android's HAL services run in an LXC container and are reached through libhybris and binder. That gives the Mali blob, hwcomposer, the camera HAL, the audio HAL and the RIL.

**Which generation.** Halium 13. The vendor is API 33 (section 2.1), and every API 33 vendor port examined uses Halium 13. The tracks that recommended Halium 16 did so on the premise of an Android 16 vendor, which the firmware contradicts. [HW-8](https://raw.githubusercontent.com/Halium/android/halium-16.0/default.xml) [contested] Halium 16 exists (LineageOS 23.2 base, last commit 2026-08-28) and is a fallback only. No port pairing a Halium 16 image with an API 33 vendor was found. No Halium 13 port of a device that launched on Android 15 or 16 was found either. [G13-13](https://gitlab.com/ubports/porting/community-ports/halium-generic-adaptation-build-tools/-/blob/main/prepare-fake-ota.sh) [unverified]

**Which kernel.** The UBports generic branch `android13-5.15-halium`: `gki_defconfig` plus `halium.config`, which turns on SYSVIPC, USER_NS, VT, AppArmor, squashfs and POSIX_MQUEUE and turns off MODULE_SIG_PROTECT. It also carries the out-of-struct SYSVIPC patch. [HA-6](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/tree/android13-5.15-halium), [HW-7](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/raw/android13-5.15-halium/arch/arm64/configs/halium.config) [confirmed] Both bases, the branch as it is (5.15.178) and 9b2308ac0ad6, carry identical CRCs for every symbol the stock vendor modules import. Rebasing is cleaner, not required. [G13-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/android/abi_gki_aarch64.xml) [confirmed] That static check covers the stock ABI only. It compared module imports with Google's ABI file for the stock config, not with a `halium.config` build, which turns on SYSVIPC and the other options above and turns off MODULE_SIG_PROTECT. A `halium.config` build must itself pass the step-0 CRC plus BTF layout check before flashing. The out-of-struct SYSVIPC patch is meant to keep the layout, but that is unproven on vegas (G13-2: replayed, not compiled), and a CRC-clean build can still bootloop (CX-1, PR-5). `vendor_boot` stays stock.

**Precedents**

| Device | What it shows | Status |
|---|---|---|
| Motorola Edge 50 Pro (Qualcomm, vendor API 33 on Android 14 to 16 firmware) | Halium 13 on the generic kernel with stock modules. The README gives no working-feature status. | [HA-2](https://gitlab.com/ubports/porting/community-ports/android13/motorola-edge-50-pro/motorola-eqe), [G13-6](https://gitlab.com/ubports/porting/community-ports/android13/motorola-edge-50-pro/motorola-eqe/-/blob/master/README.md) [confirmed] |
| Nothing Phone 2a (MediaTek MT6886, vndk 33) | Same recipe on MediaTek. README lists recovery, modem and USB gadget as "not wired up yet"; later commits add a USB gadget config, so that item may be stale. It never states that the port boots. | [HA-3](https://gitlab.com/ubports/porting/community-ports/android13/nothing-phone-2a/nothing-pacman) [contested] |
| BraX3 (MT6835) | Halium 13, Ubuntu Touch 24.04, header v4 with `init_boot`. | [HA-4](https://gitlab.com/ubports/porting/community-ports/android13/brax3/brax-prithvi) [confirmed] |
| Volla Phone Plinius (MT6878, Halium 14, kernel 6.1) | The upper bound: camera, calls, SMS, data, Wi-Fi, Bluetooth, GPS, audio and hardware video marked working. VoLTE is experimental. One display module there was rebuilt from vendor source. | [HW-5](https://gitlab.com/ubports/infrastructure/devices.ubuntu-touch.io/-/raw/main/data/devices/ansuz/releases/noble.md), [HW-6](https://gitlab.com/ubports/porting/reference-device-ports/halium-14/volla-phone-plinius/volla-ansuz/-/raw/master/deviceinfo) [confirmed] |

Correction on BraX3: it does not use the generic kernel. It builds `kernel-brax-mt6835`, a MediaTek vendor fork at 5.15.148 with the older SYSVIPC patch in KABI slots 6-8. Its maintainer's commit message says it loads the prebuilt stock vendor modules. [HA-5](https://gitlab.com/ubports/porting/community-ports/android13/brax3/kernel-brax-mt6835/-/commit/c8ab389745cc024877adc2a22ff28874077cfcc7) [contested] The port repository's functional commits date from 2026-09-20 to 2026-09-24. No hands-on status after them was found, so the "September 2026 rework" is confirmed as commits and unconfirmed as an improvement.

BraX3 hardware status, corrected from a refuted summary:
- 2026-01-02: UI works, no carrier attach, camera app dies.
- March to April 2026 on the 0.9 beta: SMS, MMS and data after manual APN changes; no voice.
- June to October 2026: users still report no calls and SIM often not recognised.
[HA-13](https://community.braxtech.net/t/flashing-ubuntu-touch-megathread/3677), [G13-14](https://forums.ubports.com/topic/12368) [contested]

**vegas-specific items**

- MediaTek lk on the BraX3 and Phone 2a drops the first 20 characters of the `boot.img` cmdline. Stock vegas has an empty one. Whether Motorola's lk behaves the same is unknown. [HA-3](https://gitlab.com/ubports/porting/community-ports/android13/nothing-phone-2a/nothing-pacman) [contested]
- The UBports PID-namespace workaround for Mali matches a module named `mali_kbase`. The vegas module is `mali_kbase_mt6835` and imports the affected symbol, so the workaround would not apply as written. [G13-16](https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/commit/a7589e4c1b3a0ec4ff3372ca5596e57a360e306e) [unverified]
- The vendor declares AIDL radio HALs and MediaTek `mtkradioex` HALs. The BraX3 port drives the same interface family with ofono's binder plugin. [G13-12](../tools/locked/) [confirmed] An ofono extension provides VoLTE and SMS over IMS on devices with `mtkradioex` 3.0. [HW-9](https://raw.githubusercontent.com/FuriLabs/ofono-binder-plugin-ext-mtk/forky/README) [unverified] The version on vegas is unknown. US carriers need VoLTE for calls.
- Wi-Fi under Halium waits for the vendor nvram service, loads the gen4m module from `vendor_dlkm` and writes to `/dev/wmtWifi`. [HW-10](https://gitlab.com/ubports/porting/reference-device-ports/halium-14/volla-phone-plinius/volla-ansuz/-/raw/master/overlay/system/usr/libexec/lxc-android-config/device-hacks) [unverified]

**Userspace choices**

- Ubuntu Touch (Lomiri) is the path with build tooling.
- Droidian publishes generic images only up to API 33 and has no port that reuses stock modules on android13-5.15. [HA-11](https://github.com/droidian-images/droidian/releases/expanded_assets/droidian%2F101.20261023) [unverified]
- FuriOS runs a 4.19 kernel and is a source of components, not an image. [HA-12](https://github.com/FuriLabs/linux-furiphone-krypton/blob/forky/debian/kernel-info.mk) [unverified]
- A custom UI can be a small wlroots compositor on the Droidian or FuriLabs fork that adds a hwcomposer backend. [HW-15](https://raw.githubusercontent.com/droidian/wlroots/HEAD/backend/meson.build) [unverified] A kiosk built that way is an inference, not a reported setup.

**Expected hardware coverage.** GPU-accelerated display, touch, Wi-Fi, Bluetooth and audio are plausible. Modem and camera are possible in principle and unproven on MT6835. Charge limit through the vendor proc node, which is expected to exist once the stock charger modules load (unverified without Android).

**Install order.** `system` is a logical partition and is flashed in fastbootd, and fastbootd is assumed to need the stock `init_boot` (section 3.5). So: flash vbmeta from the bootloader if a vbmeta step is used, flash `system` in stock fastbootd while stock `init_boot_a` is still in place, and only then flash `boot_a` and the Halium `init_boot_a`. On -4-3, two install flows flash vbmeta from the bootloader first and logical partitions in fastbootd afterwards. [PM-6](https://github.com/qfertig/vegas26-gsi) [contested] The Halium initramfs takes its data partition from the partition named `userdata` unless `datapart=` overrides it, and mounts it before it parses `super`. [CX-16](https://github.com/halium/initramfs-tools-halium/blob/dynparts-lvm/scripts/halium) [unverified]

**Android coexistence and overhead.** The Android `system` image is replaced and `userdata` is reformatted, so stock Android does not coexist. Runtime overhead is the HAL container. Android apps can run again inside Waydroid on top of the Halium host (section 3.12). Returning to stock needs a factory reset from stock recovery to recreate the hardware-wrapped data key. [VK-15](https://github.com/qfertig/vegas26-gsi) [unverified]

**Effort.** Days to a first USB shell. Weeks for display, Wi-Fi and audio. Telephony is open-ended.

**Brick risk.** Low to moderate, under the conditions at the top of section 3: `boot_a`, `init_boot_a`, vbmeta, `system` and `userdata` are written. All of them are expected to be rewritable from the stock zip through bootloader fastboot while lk is intact (section 6); for a bad vbmeta that expectation rests on the flash path only (section 6.2). Any vbmeta written must keep the rollback index and patch level at or above the rollback index stored on that device (assume 7 on phones that ever ran -4-3, #7 and #8), with `vbmeta_a` backed up first. The Halium kernel is a self-built image, so the `boot_a` rating at the top of section 3 applies: medium until step 4a has run. The Android container must not be started before the fstab rule in section 6 is in place.

**IMEI.** One BraX3 user lost both IMEIs each time he returned from Ubuntu Touch to Android. The tool named in most of those losses is SP Flash Tool; one loss was "just using fastboot" with no commands given. A second user lost IMEIs with SP Flash with no Ubuntu Touch involved. The cause is undetermined. The Ubuntu Touch fastboot install itself touches no NV partition. [G13-15](https://community.braxtech.net/t/i-got-ut-installed-a-third-time-now-can-i-flash-back-to-android-without-losing-imeis/4444) [contested] On vegas the stock flashfile contains an `erase nvdata` step, and the stock fstab marks `nvdata`, `nvcfg`, `protect1`, `protect2` and `persist` as formattable. [G13-15](../tools/locked/) [contested] The repository's `downgrade.sh` already skips the nvdata erase (project notes). The Halium Android container processes that fstab, and whether a Halium boot reformats an NV partition when a mount fails is an open question. Section 6 therefore requires the overlay to override those fstab entries before the first container start.

**First experiment.** After section 3.4 produces a booting rebuilt kernel: the Halium initramfs in `init_boot_a` with no root filesystem, which should fall back to its USB debug shell. Then restore stock `init_boot_a` and follow the install order above.

### 3.7 KVM, pKVM and GenieZone

Not native by the owner's definition, but the unknown here affects sections 3.1 and 3.2.

- Stock state: section 2.6. KVM is most likely unusable because GenieZone owns EL2.
- The GenieZone guest-VM route (`/dev/gzvm`) is very likely closed on this kernel. There is no gzvm driver for this KMI and neither module set ships one, and the shipped GenieZone build predates the first upstream gzvm patch. [G15-5](../tools/locked/), [G15-6](https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.15/drivers/virt/) [unverified] It can be falsified with the read-only probe in section 7.2, step 1. The theoretical path is a backport of the driver from android14-6.1 as a module; no evidence says it can work with this GenieZone.
- Linux as host with Android or other systems as KVM guests would fit the owner's preference for Linux-as-host. The 5.15 kernel has KVM, vhost-vsock and TUN built in. It is speculative: it depends entirely on EL2 being freed on MT6835, which nobody has shown, and it inherits the brick risk of that step. (gap1-5 track option, [unverified])
- Without KVM, a VM on this phone means QEMU in pure emulation, which is the highest-overhead arrangement in this report.
- Freeing EL2 has been done on other MediaTek SoCs. A GPT method is marked verified by its author on MT6833 and MT6893. [G15-11](https://raw.githubusercontent.com/jsbsbxjxh66/mtk-soc-disable-geniezone/main/README.md) [unverified] An ATF patch gives a working `/dev/kvm` on an MT6833 phone. [G15-13](https://raw.githubusercontent.com/BreezeExceed/camellian-linux/master/docs/KERNEL_EL2.md) [unverified] No MT6835 attempt was found.
- On platforms where `bl2_ext` loads GenieZone, as on vegas, the tool's author documents boot failures after removing it, and co-processor watchdog crashes on MT6895. [G15-12](https://raw.githubusercontent.com/jsbsbxjxh66/mtk-soc-disable-geniezone/main/README.md) [unverified] vegas ships the affected co-processor modules.
- `bl2_ext` runs before lk's fastboot. A patched image that hangs there leaves no way back. Erasing `gz` is equally unsafe until the failure path is disassembled: the image creates an lk guest, and `bl2_ext` contains an assertion on hypervisor load.

**Brick risk.** None for the read-only probe. High for any step that changes `gz` or `bl2_ext`: that code runs before fastboot, and no rescue below fastboot was found (section 2.7).

**Effort.** Minutes for the read-only probe. Weeks and an expendable phone for anything else.

**First experiment.** The read-only EL probe in section 7.2, step 1. Everything beyond that is deferred.

### 3.8 Android stepping stones

These are not Linux targets. They prove the custom boot chain and give a debuggable host.

**LineageOS 23.2 device tree for vegas26**
- Unofficial, single author, four commits on 2026-11-16, no releases.
- Requires stock -4-3 on slot A and aborts on anything else. No stock -4-3 package was found online (PR-7 verifier note), so -4-3 is reachable only by OTA and has no matching rescue image. On a -4-2 unit the tree is unusable as published; it would need its blobs and prebuilts re-extracted from -4-2 (untested).
- Its kernel, DTB and dtbo are unmodified stock prebuilts, so it shows re-signed repacked images being accepted, not a custom kernel. A second person's install log of a self-built test-keys build from this tree confirms that: stock kernel, stock DTB, stock dtbo payload (LG-6, section 2.4).
- Its vbmeta is signed with the public AOSP test key with rollback index 7 (LG-6 verifier note).
- The author self-reports display, touch, three cameras, fingerprint, audio, Wi-Fi, Bluetooth, GPS, NFC, mobile data, calls and SMS working. VoLTE is not verified.
- [PR-7](https://github.com/jimmielin/android_device_motorola_vegas26) [contested]; [VK-13](https://github.com/jimmielin/android_device_motorola_vegas26) [unverified]
- Its recovery, with root adb, would be a useful rescue environment, but it lives in a custom `vendor_boot`.

**LineageOS GSI on the stock vendor**
- Reported running on one XT2617V on -4-3, with vbmeta verification disabled and `system` flashed in fastbootd. [HA-1](https://github.com/qfertig/vegas26-gsi) [confirmed] as a single-author report
- The same guide found that the fastboot wipe leaves `/data` unformatted and bootloops on second boot unless data is wiped from stock recovery. [VK-15](https://github.com/qfertig/vegas26-gsi) [unverified]
- Value for the Linux work: it shows the `system` partition can be replaced on this vendor, which is the Halium install path.
- The GSI result is on -4-3 only. On -4-2 it is untested.

**Brick risk of these stepping stones.** Low to moderate on -4-3 as reported. The LineageOS route writes a custom `vendor_boot_a`, which section 6.1 defers on -4-2 (class D). The GSI route writes vbmeta and `system` only.

Neither stepping stone justifies moving an experiment unit to -4-3. The rule of section 2.7 stands: stay on -4-2 and block OTAs.

**Feature kernel under Android with a Linux container.** Technically the same kernel as the section 3.4 variant. Pass 2 found documentation and two precedents for it, so it now has its own section (3.11).

### 3.9 Cross-cutting: boot selection and root filesystem placement

**Boot selection**

| Method | How | Status and risk |
|---|---|---|
| Slot-A image switching | Keep one kernel in `boot_a` that both systems accept, and keep two ramdisk images: the stock generic ramdisk (or a KernelSU-patched one) and a Linux or Halium initramfs. A small tool in each system writes the other system's image to `init_boot_a` and reboots. The Linux root and data sit on microSD or another partition, never on Android's encrypted `userdata`. Slot B is never used. | Concept only for vegas. The nearest working precedent is FuriOS bootman on the FuriPhone FLX1 (MediaTek MT6877, 4.19 kernel, boot header v2): when the chosen entry differs from the last boot it writes that system's `boot.img` and `dtbo.img` onto `boot_a` and `dtbo_a` and reboots. It switches only between Halium-based Linux systems, has no Android entry, never touches slot B, and keeps its state in `vendor_boot_a`, reformatted as ext4, which suggests that phone does not boot from `vendor_boot` (inference). On vegas (header v4) the swap set is `init_boot_a` only if both systems share the stock kernel and `vendor_boot`; otherwise `init_boot_a` and/or `vendor_boot_a` would have to be swapped too (CX-13 vegas verifier). The state must live elsewhere, because `vendor_boot_a` is a live boot-chain partition on vegas. [CX-13](https://github.com/FuriLabs/bootman/blob/HEAD/main.c) [contested] (two verifiers hold it as a precedent for the idea; one rejects it as a recipe for vegas) It runs only on unencrypted installs. [CX-14](https://github.com/FuriLabs/initramfs-tools-halium/blob/forky/scripts/halium) [unverified] Low to moderate risk: only `init_boot_a` is written, but a write from a running system bypasses lk's flash gate, so a bad image is found only at the next boot and then needs fastboot. With the stock kernel this pairs with section 3.5. With the rebuilt kernel it needs that kernel shown to boot Android first. |
| Single-slot chooser | A small static `/init` in `init_boot_a` decides at boot by a volume key or the presence of a labelled SD card. It then either execs the renamed Android init untouched or switches to the Linux root. Slot B is never used. Do not use a flag file on `metadata` written from Linux: `metadata` holds the key state for Android's metadata-encrypted `userdata`. If `metadata` is used at all, mount it read-only and create the flag from Android. | No existing implementation for GKI `init_boot` devices was found. The nearest precedent is a wrapper that unmounts everything and execs the renamed Android init. [G12-15](https://github.com/Android-Boot-Manager/ABM-init/blob/HEAD/main.c) [unverified] The Halium initramfs cannot serve as the chooser: on Android 8 and later it deliberately reboots instead of starting Android. [CX-15](https://github.com/FuriLabs/initramfs-tools-halium/blob/forky/scripts/halium) [unverified] Low to moderate risk; new code. Works only while the same kernel serves both systems, so it applies to the stock-kernel route (section 3.5) until the rebuilt kernel is shown to boot Android. |
| Tethered RAM boot | Boot a Linux boot image from the host each time; nothing is written. | Ruled out. lk's `boot` command is a stub (LG-10, section 2.3). |
| Slot B | Populate slot B, put the Linux chain there, switch slots. | Not to be attempted (section 5). |

**Root filesystem placement**

| Place | Keeps Android data | Notes |
|---|---|---|
| `userdata` reformatted | No | What the tablet, a22x and Halium do. Metadata-encrypted `userdata` cannot be *mounted* by a non-Android system; it can still hold a Linux disk as pinned files reached through the raw partition (section 12). |
| New logical partition in `super` | Yes | About 4.3 GiB is free. AOSP fastbootd can create a partition on an unlocked device, and AOSP's updater removes only groups carrying the target slot suffix. [G12-12](https://android.googlesource.com/platform/system/update_engine/+/refs/heads/main/aosp/dynamic_partition_utils.cc) [unverified] Whether Motorola's builds behave the same is unknown. A flashfile reflash rewrites `super` and erases `userdata`, so the partition does not survive `downgrade.sh` or `upgrade.sh`. [G12-13](../tools/locked/) [unverified] The initramfs needs dm-linear and a dynamic-partition parser. |
| microSD | Yes | Supported by design in comparable projects; pass 1 found no SD-root report on MT6835. [G12-14](https://github.com/Dodaskot/a22x-mainline/blob/HEAD/docs/BUILDING.md) [unverified] Pass 2 found one lead, a moto g power 2025 project that keeps its root on microSD with the stock kernel (rescue track lead, https://github.com/zoan37/moto-g-power-2025-omarchy, same project as RS-15, not yet read in full, [unverified]). Needs `mtk-mmc.ko` and its dependencies from the initramfs. Slower and less durable than UFS. |

For a Halium-style initramfs, the data partition defaults to `userdata` and is mounted before `super` is parsed. To coexist with Android's encrypted `userdata`, the Linux data must therefore come from a `datapart=` override that points at microSD or a raw partition; the system image can still sit in a `super` logical partition. [CX-16](https://github.com/halium/initramfs-tools-halium/blob/dynparts-lvm/scripts/halium) [unverified] The stock `boot.img` command line is empty and MediaTek lk may drop its first 20 characters (HA-3), so how such a parameter reaches the kernel on vegas is open. Build it into the initramfs or the kernel. The lk `oem config` command-line route writes `utags`, a class A partition (sections 2.7 and 6.1), and is not used.

**Retry counter.** Boot-control state on vegas is an AOSP-style structure in `misc` that starts at offset 2048, with the magic at offset 2052, a CRC, and 7 retries by default. [G12-1](../backups/) [confirmed]; layout detail from [PM-8](../vegas-freedom/backups/) [contested] A Linux that boots from a slot whose successful flag is clear burns one retry per boot and may then fall back to slot B. On a MediaTek tablet running a GSI, the count fell on every boot, and switching slots cleared a manually set mark. [G12-10](https://github.com/sethforprivacy/dc1-lineage-gsi/issues/10) [unverified], by analogy Whether flashing `boot_a` or `init_boot_a` clears the flag on vegas is unknown. A Linux-side writer for that block is a prerequisite for any unattended Linux boot. It writes only the boot-control structure, after a backup of `misc`, with the CRC recomputed and the result read back. It is itself untested on vegas. lk has fastboot variables for slot state (the strings `slot-successful`, `slot-unbootable` and `slot-retry-count` are in the -4-2 lk, PM-8 verifier note), which is the likely way to read that state without Android; this is to be confirmed in section 7.2, step 2. The Nura slot tool is built on Qualcomm GPT flags and does not apply. [G12-9](https://github.com/Gigaset-dev/lk2/blob/ab107ff351cb5550ee2aa92b0b7bc6ac0089befc/platform/mediatek/common/bootctrl/3/bootctrl_api.c) [unverified]

### 3.10 Cross-cutting: charge limit

- Moto's 80% cap is an Android feature and disappears without Android userspace (track summary, not separately verified).
- The claim that writing to `/proc/mtk_battery_cmd/current_cmd` "held 57-60%" on a rooted vegas was refuted. What was observed on phone #1: writing "0 1" switched charging off while the phone ran from USB, and the battery read 97-99% for the roughly 11 hours the module ran. The 57-60% band was a configured threshold and was never observed. Throttling input current to its floor did not stop charging. [HW-12](../ksu-modules/README.md) [contested]
- In MediaTek's 5.15 vendor charger source (not the vegas build), that node's second field disables or re-enables the charger in the kernel. [HW-13](https://nest-open-source.googlesource.com/manifest_repos/kernel_device_modules-5.15/+/refs/heads/main/drivers/power/supply/mtk_charger.c) [unverified]
- Consequence: on every vendor-kernel route (sections 3.3 to 3.6) the node is expected to exist once the stock charger modules load, and a small daemon could then drive it. This is unverified without Android: the node was seen on vegas only under stock Android, and its kernel-side origin is known only from a non-vegas source tree. The mainline route has no such node. On the Android-host route (section 3.11) Android's own 80% cap keeps working. Whether the fuel gauge and thermal limits work fully in-kernel without Android is unknown and must be checked before leaving a non-Android phone on charge unattended.

### 3.11 Coexistence: Android host with a system container on the rebuilt kernel

This is not a Linux-native arrangement. Android stays the host and owns the hardware. It is here because the owner allows Android to stay, because the overhead is far below a VM, and because it is built from the kernel of section 3.4. It differs from the chroot or proot the owner ruled out in one respect: the distribution runs its own init as PID 1 in its own PID, IPC, UTS and mount namespaces.

**How it works.** Rebuild the GKI kernel at 9b2308ac0ad6 from the phone's own config with the namespace options added and a kABI patch for SYSVIPC. Replace only the kernel in `boot_a`. Keep a KernelSU-patched `init_boot_a` for root. A container runtime on Android (Droidspaces is the documented one) then boots a Debian, Ubuntu or Alpine root filesystem with systemd or OpenRC as PID 1, with an optional network namespace and cgroup v2 memory limits.

**Why the stock kernel cannot do it.** PID_NS is not set in the stock vegas kernel and cannot be added by root or by a module. [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) [confirmed]

**What must be built**

- The kernel options: SYSVIPC, POSIX_MQUEUE, IPC_NS, PID_NS and DEVTMPFS, optionally USER_NS and MACVLAN. SYSVIPC needs one of the padding-slot patches described in section 3.4. The project's documentation says a GKI phone bootloops without the patch because the vendor modules refuse to load, and that a patched kernel can still bootloop if the wrong slots are used. [CX-1](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md) [contested]
- Leave CGROUP_PIDS and CFS_BANDWIDTH off. They break the KMI and no patch covers them, so per-container process and CPU limits are not available. [CX-2](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md) [confirmed]
- CGROUP_DEVICE is not needed on cgroup v2, where device control comes from CGROUP_BPF. [CX-4](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/bpf_types.h) [unverified]
- Probably a patch that makes `/proc/config.gz` report the stock config, to avoid Android's "internal problem" dialog. [CX-7](https://android.googlesource.com/kernel/configs/+/refs/heads/main/t/android-5.15/android-base.config) [unverified], by analogy
- The offline CRC gate of section 3.4 against all stock modules, plus the layout comparison, before any flash. "All stock modules" includes the Google-signed GKI modules in `system_dlkm` (section 2.1). This recipe starts from the stock config, which keeps MODULE_SIG_PROTECT on, so either that option goes off or `system_dlkm` is rebuilt from the same tree. Neither precedent states how it handled this ([unverified]).

**Evidence.** Two self-reported precedents on the same kernel generation, both by analogy: the Samsung Galaxy A25 5G (MT6835, 5.15.180, SYSVIPC in slots 6-8, status "Working", GPU acceleration "none") and the REDMAGIC 8S Pro+ (SM8550, 5.15.167, 0 CRC mismatches across 374 modules, Debian 13 with systemd running, GPU not working). [CX-5](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/community-supported-devices.md), [CX-6](https://github.com/fkun1754/redmagic-nx729j-droidspaces-kernel) [confirmed] as reports. Nothing has been tried on vegas or on any Motorola MediaTek phone. The partitions involved match what is already known on vegas: `boot_a` only, with the KernelSU `init_boot_a` that the owner has flashed before.

**Hardware coverage.** Whatever Android provides, reached through Android. The container has real init, services and network stack. It has no direct display. On Mali phones GL in the container comes only through a software bridge to an Android-side display app, and the MT6835 precedent lists GPU acceleration as none (track summary and CX-5). Modem, camera and the charge cap stay with Android.

**Android coexistence and overhead.** Full coexistence: Android and its data are untouched. Overhead is one shared kernel and the container's own processes.

**Effort.** One to three days to build the kernel and verify CRCs. Minutes to set up the container afterwards.

**Brick risk.** As section 3.4: medium for a self-built kernel image until section 7.2, step 4a, has shown the boot-time behaviour, then low under the conditions at the top of section 3. Only `boot_a` changes, and stock `boot_a` is expected to restore it. The main failure is a black screen or a boot loop when a vendor module rejects the kernel, which the offline check is meant to catch and which the stop rule bounds.

**First experiment.** The same as section 3.4: the rebuilt kernel with the minimal fragment booting Android. The namespace options and the SYSVIPC patch are a second build on top of that.

### 3.12 Coexistence: Linux host with Waydroid for Android apps

**How it works.** Waydroid runs an Android system image in an LXC container on a Linux host. It needs binderfs, ashmem or memfd, and PID and IPC namespaces. The first two are in the stock kernel; the namespaces need the rebuilt kernel. [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) [confirmed]; memfd fallback [CX-12](https://github.com/waydroid/waydroid/blob/main/tools/helpers/lxc.py) [unverified]

**Two variants**

- **On the Halium 13 host of section 3.6.** Waydroid maps the host's `ro.vndk.version` to a vendor type; 33 gives HALIUM_13. In that mode it binds the host's `/vendor` and hwbinder into the container and uses the host's gralloc when it finds one, so on a Halium 13 vegas host Android apps would be expected to use the vendor Mali driver (inferred from Waydroid's code and the vegas vendor; no Waydroid run on vegas or MT6835). The stock vegas vendor reports version 33 and ships a gralloc HAL. [CX-9](https://github.com/waydroid/waydroid/blob/main/tools/helpers/lxc.py) [contested] (the code facts hold; one verifier rejects the "direct" label because the vegas outcome is inferred from code and firmware, not run)
- **On the plain Linux of section 3.4, without Halium.** There is no Android property service on the host, so Waydroid treats the host as mainline. With no host gralloc and no DRM render node it falls back to software rendering. The vendor display driver exposes no render node by static inspection, and Mali's vendor driver is not a DRM driver. Android apps would render on the CPU. This is inferred from Waydroid's source and the firmware; no one has run it. [CX-9](https://github.com/waydroid/waydroid/blob/main/tools/helpers/lxc.py) [contested]

**Images.** The official Waydroid image server serves a HALIUM_13 arm64 vendor image based on LineageOS 20, newest build dated 2026-10-22, and returns nothing for HALIUM_14, 15 or 16. That is the channel Waydroid would select for a vendor at version 33. It is a version match only. [CX-10](https://ota.waydro.id/vendor/waydroid_arm64/HALIUM_13.json) [contested] (the server facts hold; one verifier rejects the "direct" label because nothing in the source is about vegas)

**Evidence on MediaTek.** Ubuntu Touch device pages mark Waydroid as working on a Volla phone with MT6769 (Halium 11), partly working on one with MT6789 (Halium 12, with unofficial Android 13 images), and not working on the MT6878 Plinius (Halium 14, for lack of Android 14 images). No Waydroid report for MT6835 or vegas was found. [CX-11](https://gitlab.com/ubports/infrastructure/devices.ubuntu-touch.io/-/raw/main/data/devices/ansuz/releases/noble.md) [unverified], by analogy

**Android coexistence and overhead.** Stock Android and its data do not survive the Halium install. What comes back is an Android userspace for apps, running in a container at native CPU speed. On the Halium variant there are then two Android userspaces on top of Linux: the HAL container and Waydroid. No RAM measurement for Waydroid on a Halium host was found; the vegas RAM size is not in the fact sheet (read it in section 7.2, step 1).

**Effort.** Weeks, because the Halium bring-up comes first. Waydroid itself is then a package install plus debugging. Days after section 3.4 boots for the software-rendered variant.

**Brick risk.** As the host route (section 3.4 or 3.6). Waydroid adds no flashing.

**First experiment.** None until the host route boots.

## 4. Comparison

| Direction | Nativeness | Effort | Brick risk | UI | Modem | Camera | Android coexistence | Evidence strength |
|---|---|---|---|---|---|---|---|---|
| 3.1 Mainline | Own mainline kernel, no blobs | Months | Medium until step 4a, then low (`boot_a` only); a hung kernel cannot mark the boot good | Framebuffer first; GPU uncertain | Assume none | None | SD or `super` root, reflash `boot` | Sibling SoCs only; nothing on MT6835 |
| 3.2 UEFI / U-Boot from lk | Own firmware layer plus a kernel from 3.1 or 3.4 | Weeks to a menu | Menu test: low to moderate. Loading an OS: higher | Menu on lk framebuffer | As loaded kernel | As loaded kernel | Reflash `boot` | One self-reported MT6835 tablet, XNU not Linux |
| 3.3 Motorola source kernel + own modules | Own vendor-fork kernel and modules | Several weeks | Moderate with the stock DTB bytes kept; high with a changed DTB or dtbo | KMS and fbcon possible | Unproven | Sources missing | Poor | Source exists; never built for vegas |
| 3.4 Rebuilt GKI + stock modules + plain Linux | Own-built GKI, vendor blobs as modules | Days to shell, weeks to Wi-Fi and UI | Low for a footered `boot_a` carrying the stock kernel (step 4a). Medium for a footerless or self-built kernel image until step 4a shows boot-time behaviour | CPU-rendered KMS; GPU only via libhybris | Unproven, templates exist | None | SD or `super` root; reflash `boot` or switch `init_boot_a` | One same-platform tablet and two same-KMI phones (all self-reported), plus static CRC check on vegas modules |
| 3.5 Stock GKI + replaced `init_boot` | Stock kernel, Linux userspace | About a day | Very low | KMS client at most | None | None | Best, with `init_boot_a` switching | `init_boot` flash hands-on verified for an image that grew, with a likely (contested) static explanation; the padded probe image is untested; rest by analogy |
| 3.6 Halium 13 | Rebuilt GKI, Linux host, Android HAL container | Days to shell, weeks to usable | Low to moderate | Lomiri or wlroots on hwcomposer, GPU | Possible, poor on nearest port | Possible, unproven | None (`system` and `userdata` replaced); Android apps via 3.12 | Three ports on same KMI or SoC; none on vegas |
| 3.7 KVM after freeing EL2 | VM | Weeks | High (code before fastboot) | n/a | n/a | n/a | n/a | Other SoCs only |
| 3.8 LineageOS / GSI | Android | Afternoon to days | Low to moderate | Android | Reported working | Reported working | It is Android | Hands-on on vegas on -4-3 only, single authors; not reproduced on -4-2 |
| 3.9 Slot-A image switching | Native when booted; one system at a time | One to two weeks after 3.4 or 3.5 boots | Low to moderate (`init_boot_a` written from a running system) | As the booted system | As the booted system | As the booted system | Yes, exclusive dual boot | Concept for vegas; one MediaTek precedent that switches Linux systems only |
| 3.11 Android host + system container | Android host; distro with its own init in namespaces | One to three days | As 3.4: medium for the self-built kernel until step 4a, then low (`boot_a` only) | None direct; via Android | Android's | Android's | Full; Android and data untouched | Two self-reported same-KMI precedents, one on MT6835; none on vegas |
| 3.12 Linux host + Waydroid | Linux host; Android apps in a container | Weeks (after 3.6), or days after 3.4 with software rendering | As the host route | GPU expected on a Halium host (inferred, not run); CPU rendering on plain Linux | As the host route | As the host route | Android apps only; stock Android data not kept | Official image for the vendor level exists; no MT6835 report |

Every "low" in the brick-risk column assumes the conditions at the top of section 3. The ratings changed in pass 2 for three reasons: there is no RAM boot, so every test costs a possible boot attempt; no rescue below fastboot was found; and the flash gate now has a likely static explanation (partly contested, not run on a phone), which removes the vbmeta step from the first experiments. "Step 4a" is the footered stock-kernel repack of section 7.2, step 4; it is mandatory before any footerless or self-built image goes into `boot_a`. Unlocking is one-way under the rules of section 6, so every route costs the farm one end-state-D unit.

## 5. Ruled out or unlikely

- **Slot-B dual boot.** Slot B is all zeros in every backup examined: phone #1 ([G12-1](../backups/) [confirmed]) and four more phones ([PM-13](../vegas-freedom/backups/) [unverified], recounted by the PM-4 and PM-8 verifiers). lk's own guard warns of bricking ([G12-4](../tools/locked/) [confirmed]). The preloader on boot LU B is an older build. [G12-2](https://github.com/jimmielin/android_device_motorola_mt6835-common/blob/lineage-23.2/tools/copy-firmware-to-other-slot.sh) [contested] There is one by-analogy forum report of a Dimensity 7300 Motorola going dark after its owner forced a switch to an empty slot. [G12-5](https://web.archive.org/web/20261007214046/https://xdaforums.com/t/motorola-g100-pro-motorola-g86-5g-soft-brick-after-switching-to-empty-slot-b-need-test-point-location.4803154/) [contested] The tree author's own README says never to switch slots. [PR-8](https://github.com/jimmielin/android_device_motorola_vegas26) [confirmed] Not to be attempted. Reconsider only if (a) the preloader slot check and lk's handling of the UFS boot LU are disassembled, (b) every slot-B partition and both boot LUs are read live on that unit, and (c) the unit is expendable.
- **RAM boot (`fastboot boot`) as a zero-write test.** Ruled out. The command is a stub in the stock -4-2 lk, the base-build lk and the owner's patched lk images. [LG-10](../tools/locked/) [confirmed]
- **A rescue through BROM or a download agent.** Do not plan on it. No Motorola-signed MT6835 download agent is public, mtkclient ships neither an exploit nor an agent for this SoC, and lk contains code that blows a BROM-disable fuse (section 2.7). [RS-1](https://raw.githubusercontent.com/bkerler/mtkclient/main/mtkclient/config/brom_config.py), [RS-2](https://github.com/bkerler/mtkclient/issues/435), [RS-3](https://github.com/bkerler/mtkclient/issues/182), [RS-7](../tools/locked/) [confirmed]
- **A full flashfile run as the way back to stock.** It rewrites the GPT, the preloader and lk and erases `nvdata` (section 6). [PM-1](../tools/locked/) [confirmed]
- **Relocking an experiment unit.** `oem lock`, `fastboot flashing lock` and `flashing lock_critical` are never run (section 6.1). Unlocking is one-way under these rules.
- **`oem config` as the way to pass a kernel command line.** It writes `utags`, a class A partition (sections 2.7 and 6.1).
- **Installing `avb_custom_key`.** Not needed by static reading of the flash gate, and it changes what stock images the phone then accepts (section 2.4).
- **Wrapping an image as sparse to pass the certificate check.** The same code path covers `lk` and `tee` (section 2.4, LG-9).
- **U-Boot written over lk.** This is how the MT6878 and MT6789 mainline ports boot, including a Motorola. It is possible only where the preloader does not verify the lk payload. [UE-12](https://wiki.nura.eco/wiki/MediaTek_Dimensity_7300_%28MT6878%29) [unverified] On the Moto G72, Motorola disabled USB boot and recovery depends on a leaked download agent. [UE-13](https://wiki.nura.eco/wiki/Motorola_Moto_G72_%28motorola-vicky%29) [unverified] No MT6835 U-Boot exists and vegas has no rescue path.
- **Erasing `gz` or patching `bl2_ext` to free EL2.** Section 3.7.
- **Stock AVF / Android Linux Terminal.** The APEX is the disabled stub and no hypervisor is advertised. [G15-8](../tools/locked/) [confirmed]
- **GenieZone guest VMs (`/dev/gzvm`).** Unlikely, not ruled out. No driver for this KMI, and the shipped GenieZone predates the first upstream gzvm patch. [G15-6](https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.15/drivers/virt/) [unverified] The read-only probe in section 7.2, step 1 can falsify it.
- **A VM under Android.** With KVM most likely blocked and no gzvm driver, what remains is QEMU in pure emulation. It works anywhere and is the slowest arrangement; no measurement on vegas exists.
- **A container with its own init on the stock kernel.** PID_NS is off and cannot be added without rebuilding the kernel. [CX-3](https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig) [confirmed]
- **CGROUP_PIDS or CFS_BANDWIDTH on a kernel that keeps the stock modules.** They break the KMI and no patch covers them on 5.15. [CX-2](https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md) [confirmed]
- **The Halium initramfs as an Android-or-Linux chooser.** It reboots instead of starting Android 8 or later. [CX-15](https://github.com/FuriLabs/initramfs-tools-halium/blob/forky/scripts/halium) [unverified]
- **kexec from Android into another kernel.** KEXEC is not set (firmware). A hot-jump kernel module exists only as reference code for MT6833 on a 4.14 kernel.
- **Halium or libhybris inside Nura.** Dropped by the project. [NP-14](https://wiki.nura.eco/wiki/Hybris) [unverified]
- **Reusing vendor UEFI drivers.** There is no vendor UEFI on MediaTek phones. [UE-8](https://github.com/Project-Silicium/Guides/blob/main/Silicium/Porting/Snapdragon/Device/README.md) [confirmed]
- **A custom DTB in `vendor_boot` as a first step.** Section 2.3.
- **Halium 16 as the first Halium attempt.** Wrong generation for an API 33 vendor (section 3.6).
- **A generic arm64 distro kernel through UEFI.** It would see CPUs and a framebuffer and nothing else. [ML-1](https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/drivers/dma/mediatek/mtk-uart-apdma.c) [confirmed]

## 6. Safety

The premise of this section: lk fastboot on slot A is the only way back that anyone has shown, there is no RAM boot, and no rescue below fastboot was found (sections 2.3 and 2.7). A write that stops lk from reaching fastboot is to be planned as permanent.

### 6.1 Partition write-safety table

The table was built in pass 2 from the stock -4-2 flashfile and servicefile, the GPT, a hash comparison of the owner's partition backups, the owner's flashing logs and strings in the stock lk. The class assignment is the track's judgement; the facts under it carry their own tags. "Stock zip" means the hash-verified -4-2 firmware zip. Partition names without a suffix that exist in two slots mean slot A.

| Class | Partitions | Rule | Where a good copy comes from | Basis |
|---|---|---|---|---|
| A. Never write | `preloader` on both UFS boot LUs; the GPT | Never. The stock flashfile and servicefile both write them, which is one reason neither is ever run whole. The owner's downgrade and upgrade scripts skip both. The preloader on LU A exists in two builds across the owner's phones, so there is no single known-good image | The same phone's own backup, and nothing can write it once lk is gone | [PM-1](../tools/locked/), [PM-2](../tools/locked/) [confirmed]; [PM-4](../vegas-freedom/backups/) [contested] |
| A. Never write | `lk_a` beyond the owner's established unlock patch, including the `bl2_ext` sub-image inside `lk.img`; `lk_b` | One write, made by the unlock step. No experiment patches lk. Do not run `oem lock`, `fastboot flashing lock` or `flashing lock_critical`. lk enforces anti-rollback on bootloader images | That unit's own serial-bound unlock lk, archived from the unit after the unlock (section 6.5). The pre-unlock backups hold the route-D lk, which is a different image | notes; LG-4 verifier note; [PM-12](../tools/locked/) [unverified] |
| A. Never write | `tee`, `gz` | No experiment writes them. They are in the stock zip, but they run before fastboot is reachable, so a bad image may leave nothing to restore from | Stock zip. Neither return-to-stock level of section 6.3 writes them | [PM-1](../tools/locked/) [confirmed]; [PM-11](https://github.com/jimmielin/android_device_motorola_vegas26) [unverified] |
| A. Never write | NV, calibration, identity and security data: `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`, `prodpersist`, `proinfo`, `seccfg`, `efuse`, `efuseBackup`, `otp`, `sec1`, `cid`, `utags`, `utagsBackup`, `hw`, `sp`, `dram_para`, `boot_para`, `frp`, `flashinfo`, `para` | Never write, never copy from one phone to another, and keep unmounted or read-only under Linux. None is restored by the stock zip: the flashfile only erases `nvdata` and writes `efuse.img` to `efuseBackup`. `sp` also holds the custom AVB key slot, so do not install `avb_custom_key`. `oem config set` and `unset` write `utags`, so they are not run outside a deliberate, backed-up test. Never restore `seccfg` from a backup: its validity is anchored outside the backup (section 6.5) | The same phone's own backup only. Whether a raw restore is sufficient is unproven | [PM-1](../tools/locked/) [confirmed]; [PM-4](../vegas-freedom/backups/) [contested]; LG-5 [contested]; RS-14 [unverified] |
| A. Never write | `tzapp_a`, `tzapp_b` | Leave alone. No stock zip contains a `tzapp` image and no flashfile step touches it. It is not device-unique: in the backups of all eight phones it holds the same 34 trustlet files, identical to a directory in the stock vendor image, and stock Android has a script that fills it after boot. Only filesystem metadata differs per phone. Erasing or rebuilding it has not been tried on vegas | The phone's own backup first; the files are also in the stock vendor image | [PM-3](https://github.com/jimmielin/android_device_motorola_mt6835-common/blob/lineage-23.2/tools/copy-firmware-to-other-slot.sh) [contested] (the original wording called it device-unique and unrestorable and was refuted; this is the corrected wording) |
| A. Never write | Every slot-B partition; the active-slot setting | Never write, never switch | n/a | G12-1, G12-4 [confirmed]; PM-8 [contested] |
| B. Stock copy only | Co-processor, radio and splash firmware: `sspm`, `mcupm`, `spmfw`, `dpm`, `scp`, `vcp`, `pi_img`, `md1img`, `connsys_bt`, `logo`, `mcf_ota` | No Linux experiment writes them. The only acceptable content is the -4-2 stock copy, written from bootloader fastboot, and only for an image whose hash, read from the rooted phone, differs from the stock zip (section 6.3, level 2). Several are co-processor images loaded early and go through lk's MediaTek certificate path (LG-9 [unverified]). The owner's established SIM-unlock modem image for `md1img` is the one existing exception; writing the stock `md1img` removes it | Stock zip | [PM-1](../tools/locked/) [confirmed]; [PM-11](https://github.com/jimmielin/android_device_motorola_vegas26) [unverified] |
| B. Stock copy only | `connsys_wifi`, `connsys_gnss` | Empty on both slots in the backups and absent from the flashfile. Do not write | n/a | [PM-13](../vegas-freedom/backups/) [unverified]; [PM-1](../tools/locked/) [confirmed] |
| B. Stock copy only | `super` as a whole | Only the 26 stock sparse chunks, from bootloader fastboot. Flash the stock `vbmeta_a` and `vbmeta_system_a` in the same bootloader session before the `super` chunks. The -4-2 lk contains the warning that both are required before `super` (lk-gate track lead, string evidence, [unverified]). On two locked units running the community rollback lk, bootloader fastboot returned OKAY for every chunk (PM-5 [contested]); behaviour under stock or the unlock lk was not logged. AOSP says a bootloader must refuse to flash dynamic partitions; Motorola's lk departs from that for the whole-`super` container ([PM-16](https://source.android.com/docs/core/architecture/bootloader/fastbootd) [unverified]) | Stock zip | [PM-1](../tools/locked/) [confirmed]; [PM-5](../logs/) [contested] |
| C. Experiment partitions | `boot_a`, `init_boot_a` | Open for experiments under the image rules of section 2.4: a footer whose `vbmeta_offset` is not below the stock descriptor size, with explicit padding where the image would be smaller; no footer only after step 4a of section 7.2; gzip kernel. Only `init_boot_a` has been exercised hands-on, with an image that grew. For `boot_a`: low risk for a footered image with the stock kernel, medium for a footerless or self-built image until step 4a has run. Expected, not shown, to be recoverable from fastboot after a bad `boot_a` | Stock zip and the phone's own backup | LG-2 [confirmed]; LG-4 [contested] |
| C. Experiment partitions | `vbmeta_a`, `vbmeta_system_a` | Write only when a step needs it. Back up `vbmeta_a` first. Keep the rollback index and patch level at or above the rollback index stored on that device; on phones that ever ran -4-3 (#7 and #8), assume 7, so any self-made vbmeta written there must carry index 7 or higher. Prefer a unit that never ran -4-3. Flash from the bootloader, not fastbootd. A bad vbmeta is expected to be recoverable by flashing the stock vbmeta from bootloader fastboot (flash path only, section 6.2) | Stock zip | LG-5 [contested]; LG-13 [unverified]; [PM-6](https://github.com/qfertig/vegas26-gsi) [contested] |
| C. Experiment partitions | Logical partitions inside `super` (`system` and the others, or a new one) | Through fastbootd, with stock `init_boot_a` and `vendor_boot_a` in place. Bootloader fastboot is expected to rewrite `super` whole, with the two stock vbmeta images flashed first in the same session (row above). A stock reflash of `super` destroys any added partition | Stock zip | [PM-6](https://github.com/qfertig/vegas26-gsi) [contested]; G12-12, G12-13 [unverified] |
| C. Experiment partitions | `userdata`, `metadata` | Erase or reformat only, and that destroys Android's data. Never write files into `metadata` from Linux: it holds the key state for Android's encrypted data. After a non-stock system has used `userdata`, wipe from stock recovery, because the fastboot erase leaves `/data` unformatted | Recreated by stock recovery | [PM-14](https://github.com/qfertig/vegas26-gsi) [unverified]; VK-15 [unverified] |
| D. Only after lk's behaviour is characterised | `vendor_boot_a` with changed modules or ramdisk and the stock DTB bytes; any DTB change in `vendor_boot_a`; `dtbo_a` | Deferred. `vendor_boot_a` carries recovery and fastbootd. lk's DTB parsing at boot was not traced, and on other MediaTek phones a changed DTB stops lk. `dtbo` goes through lk's MediaTek certificate check, not AVB, and an unsigned raw dtbo is predicted to be rejected. Writing back the stock copy of either is always allowed | Stock zip | NP-12 [unverified], by analogy; LG-9 [unverified]; LG-6 [contested] |
| D. Only after lk's behaviour is characterised | `misc` | The boot-control structure only, after a backup, with the CRC recomputed and a read-back | The phone's own backup | PM-8 [contested] |
| E. Read only | `expdb`, `pstore`, `logs`, `logks` | No reason to write. The preloader, lk and the kernel write them. Read them for diagnosis | n/a | [RS-13](../backups/) [unverified] |

What the flashfile and servicefile do, for reference. The stock -4-2 flashfile writes the GPT and the preloader, `lk_a` and the slot-A firmware, `efuse.img` to `efuseBackup`, `init_boot_a`, `boot_a`, `vendor_boot_a` and 26 `super` chunks, and erases `nvdata`, `userdata`, `metadata` and `debug_token`. [PM-1](../tools/locked/) [confirmed] The servicefile is the same list without the `efuseBackup` write and without the `userdata` and `metadata` erases. It still writes the GPT, the preloader and lk and still erases `nvdata`, so by itself it is not a safe data-keeping restore. [PM-2](../tools/locked/) [confirmed] On two locked units running the community rollback lk, lk answered the `efuseBackup` write with "Blowing efuseBackup is not allowed, skipping!"; the partition was not read back. [PM-5](../logs/) [contested] (the original wording called the phones "cid-50" and omitted which lk was running; this is the corrected wording)

**Never run**

- The stock flashfile or servicefile as written.
- The `erase nvdata` step, on any path.
- `oem lock`, `fastboot flashing lock` or `flashing lock_critical`. Relocking with custom images on the slot, or with the patched lk in place, is the classic hard-brick path.
- A slot switch, or `oem ab_reset`.
- `oem ssm_test` with any argument, `oem blankflash`, or `oem ramdump`. These are test-command families in the same lk `oem` table (lk-gate track lead, string evidence, [unverified]); what `blankflash` does on this platform is unknown.
- `oem config set` or `oem config unset`, outside a deliberate test with `utags` backed up first. They write `utags` (class A).
- `oem fb_mode_set`, until it is characterised. `oem partition` and its siblings likewise.
- The `oem` steps of the flashfile (`fb_mode_set`, `fb_mode_clear`, `config unset console`, `config unset cmdl`). The owner's downgrade and upgrade scripts drop them, together with the flashfile's `getvar` step, so the hands-on precedent never ran them.
- A modem file-system server pointed at the real NV partitions.
- An immature UFS driver against mounted NV partitions. Keep them unmounted or read-only.
- The Halium Android container before its fstab overlay removes `formattable` from `nvdata`, `nvcfg`, `protect1`, `protect2` and `persist` (or makes those entries read-only or absent), and before the per-phone backup exists. Whether a Halium boot reformats an NV partition when a mount fails is an open question (section 3.6).

### 6.2 Recovery paths, in order of what exists

1. lk fastboot on slot A, with images from the hash-verified stock -4-2 zip or from the phone's own backup, used selectively as described in section 6.3. This is the only path to rely on. It is expected, not shown, to survive a bad `boot_a`, `init_boot_a`, `system` or `userdata`; only `init_boot_a` has been exercised hands-on. A bad vbmeta is expected to be recoverable by flashing the stock vbmeta first (LG-5 [contested], flash path only; that lk does not use vbmeta to reach fastboot is not verified), so vbmeta stays in class C. The path does not cover `dtbo_a` or a changed DTB in `vendor_boot_a` until lk's handling of them is known (class D above).
2. Stock recovery and fastbootd. Assume they are available only while stock `vendor_boot_a` and stock `init_boot_a` are in place.
3. Preloader download mode and BROM: assume unavailable (section 2.7).

Getting back into fastboot after a hung boot is itself unproven for a non-Android image. The candidates are the key combination the owner uses on stock (not yet tried from a hung non-Android boot), a timed reboot-to-bootloader inside the initramfs (needs `reboot-mode.ko` and `syscon-reboot-mode.ko` loaded, RS-15), and the preloader handshake that asks lk to start in fastboot ([unverified] on vegas, optional). The flashfile's `oem fb_mode_set` is uncharacterised and is not run. Confirming the key combination from power-off is the required check in section 7.2, step 2, before any experiment image is flashed. The timed reboot-to-bootloader, with both modules loaded, is required in every experiment initramfs.

### 6.3 Return to stock, in words

No part of this has been run on an unlocked vegas. Close subsets ran on two locked units: `downgrade.sh` (base zip, skipping lk, the GPT, the preloader and the `nvdata` erase, under the community rollback lk) and `upgrade.sh` (-4-2 zip, which skipped only the GPT and the preloader and so also wrote stock `lk_a`). Both dropped every `oem` and `getvar` step, used stock Motorola-signed images, and saw every step return OKAY. Neither is exactly level 2, and neither ran on an unlocked unit or under the unlock lk. [PM-5](../logs/) [contested]

**Level 1: selective restore after an experiment.** This is the normal way back.

- Start in bootloader fastboot (not fastbootd) with slot A active.
- Write back only the slot-A images the experiment changed, taken from the stock -4-2 zip or from that phone's backup: `boot_a` and `init_boot_a`, and `vendor_boot_a`, `dtbo_a`, `vbmeta_a` and `vbmeta_system_a` only if they were touched.
- If a vbmeta was changed, write the stock vbmeta images first and the boot-chain images after them.
- Rewrite `super` from the stock chunks only if a logical partition was changed. This removes any logical partition that was added. Flash the stock `vbmeta_a` and `vbmeta_system_a` in the same bootloader session before the `super` chunks, even if vbmeta was never touched. The -4-2 lk contains the warning that both are required before `super` (lk-gate track lead, string evidence, [unverified]); a `super` write with no vbmeta step in that session may be refused.
- If `avb_custom_key` was ever installed, erase it (allowed when unlocked by static reading, LG-14 [unverified]).
- Nothing else is written. The patched lk stays, so the phone is expected to stay unlocked and to boot stock Android in orange state.

**Level 2: reduced stock reflash.** For a unit whose Android no longer boots after level 1.

- Start in bootloader fastboot with slot A active.
- Do not walk the flashfile as written. Take its flash and erase steps through a copy of the parser in `downgrade.sh` and `upgrade.sh`, with the flash skip list set to lk (all names), the GPT, the preloader, `efuseBackup`, `tee` and `gz`, and the erase skip list set to `nvdata`.
- Drop every `oem` and `getvar` step of the flashfile, as `downgrade.sh` and `upgrade.sh` do. `oem config` writes `utags` (class A) and `oem fb_mode_set` is uncharacterised.
- Restrict the writes to the partitions an experiment can change, from the -4-2 zip: `vbmeta_a` and `vbmeta_system_a` first, then `boot_a`, `init_boot_a`, `vendor_boot_a` and `dtbo_a`, then all 26 `super` chunks in the same bootloader session, then the erases of `userdata`, `metadata` and `debug_token`.
- Leave the class-B firmware alone (`sspm`, `mcupm`, `spmfw`, `dpm`, `scp`, `vcp`, `pi_img`, `md1img`, `connsys_bt`, `logo`, `mcf_ota`). No experiment in this report writes it. Several of these are co-processor images loaded early, and rewriting them adds risk before fastboot with no benefit. Write one only if its hash, read from the phone or taken from the unit's last archive (section 6.5), differs from the stock zip.
- Writing the stock `md1img` removes the owner's SIM-unlock modem. If it has to be written, the SIM-unlock image can be written again afterwards.
- To keep Android's data when `userdata` was never touched, leave out the `userdata` and `metadata` erases, as the servicefile does. Unmodified, the servicefile is not safe (section 6.1).
- Use -4-2 images only. Firmware from another build next to the kept lk is the residual risk of this level.
- `tzapp_a` and `misc` are not restored by this. Restore them from the phone's own backup only if they were damaged.
- On a unit that ever ran -4-3 (#7 or #8), the stock -4-2 vbmeta carries rollback index 5 and the stored index may be 7. Those units booted locked and green on it after the downgrade, but the stored value is unread; this is one more reason to choose a unit that never ran -4-3 (section 6.4).

**After either level**, if a non-stock system has used `userdata`: boot stock recovery and do the factory reset there, so that `/data` is formatted and the hardware-wrapped data key is recreated. The fastboot erase alone is reported to bootloop a GSI on its second boot (PM-14, VK-15, [unverified]).

**Never the rescue:** the full flashfile or servicefile, relocking, or a slot switch.

### 6.4 Things that can turn a soft failure into a hard one

- The boot-control state. lk does not decrement the retry counter for a slot whose successful flag is set (G12-4), but whether flashing `boot_a` or `init_boot_a` clears that flag is unknown. If it does, a series of hung boots can end in a fallback to slot B, which is all zeros in every backup examined. The preloader has a slot validity check that may roll back to A (strings only), so the outcome is untested, not known to be fatal. Read the boot-control state after each failed boot, and restore stock images after two or three failed boots. Never continue toward the end of the retry count.
- A `vendor_boot_a` or `dtbo_a` that stops lk before fastboot. This is by analogy, but the consequence is the worst case.
- An image in `boot_a` that is not gzip or lz4-legacy compressed. lk is expected to panic on it (LG-11); what lk does after that panic is unknown.
- A vbmeta with a rollback index or patch level below the rollback index stored on that device. By AVB's design the stored index follows the highest build the phone has booted, not the build it runs now, and it does not decrease; the stored value has not been read on any vegas unit. On phones that ever ran -4-3 (#7 and #8), assume 7. Static reading says an unlocked unit tolerates a lower index; one -4-3 log blames a failed boot on exactly 5 against 7 (LG-12, LG-13, both [unverified]). Prefer an experiment unit that has never run -4-3; for a unit that has, any vbmeta written must carry index 7 or higher.
- OTAs. They can move a phone past the unlock window. An A/B OTA writes the slot-B images, including a stock `lk_b` without the unlock patch, and switches the active slot to B on the next reboot; the effect on an unlocked unit is unknown. That breaks the "slot A only" premise of this report. Block OTAs on experiment phones before the unlocked unit first joins a network (section 7.2, step 2), and after every boot confirm that the current slot is still A and that slot B is unchanged.
- Relocking. `oem lock`, `fastboot flashing lock` or `flashing lock_critical` with custom images on the slot or with the patched lk in place.
- A phone that came from another build. The downgrade and upgrade scripts skip the preloader, so such a phone carries a different preloader from its siblings (PM-4). Read it live before choosing it.

### 6.5 Back up before unlocking, per phone

The backup comes before the unlock step, because the unlock path may itself erase `nvdata` (section 2.7), and it is taken on the locked phone with temp root.

- The owner's existing full-partition backup reads every named partition, both preloader LUs and the head and tail of the GPT, with hashes computed on the device. Archives exist for all eight phones (PM-3 and PM-4 verifier notes); the pass-2 verifiers re-hashed all 90 images per phone on four of them and every hash matched. It skips `userdata`. This answers the pass-1 question of whether the backup covers every NV partition.
- Keep this per-phone set and off the machine: `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`, `prodpersist`, `proinfo`, `seccfg`, `cid`, `utags`, `hw`, `sp`, `dram_para`, `para`, `frp`, `efuse`, `tzapp_a`, `misc`, and the preloader of both LUs. Of these, only `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`, `prodpersist`, `seccfg`, `cid`, `utags`, `hw`, `sp`, `dram_para` and `efuse` were found to differ per phone (`efuse` in two variants). `tzapp_a`, `misc`, `proinfo`, `frp` and `preloader_b` were identical across the phones compared, or differed only in filesystem metadata, and are kept as a precaution. `preloader_a` comes in two builds, and `para` differs but may be run-time state. (PM-3, PM-4, PM-8 [contested]) Record both IMEIs. `nvcfg` is live and its hash changes between reads (track note).
- Slot-A boot chain as flashed on that unit: `boot_a`, `init_boot_a`, `vendor_boot_a`, `dtbo_a`, `vbmeta_a`, `vbmeta_system_a`, `lk_a`.
- These backups are of locked phones in route-D state, so their `lk_a` is the route-D lk. `seccfg`, `misc` and `metadata` change at unlock, so read those again once the unit is unlocked and rooted.
- After the unlock, also archive that unit's `lk_a` (the serial-bound unlock lk, which is the only good copy for the class A `lk_a` row), the hashes of its post-unlock `boot_a`, `init_boot_a` and `vbmeta_a`, and the KernelSU `init_boot` image used to root it. Keep that image before step 3 of section 7.2 overwrites `init_boot_a`.
- Never restore `seccfg` from a backup. Its validity is anchored outside the backup: a community summary says Motorola checks the unlock state in `seccfg` against a value stored in RPMB (RS-6 source, [contested], by analogy), and RPMB state cannot be restored from any backup.
- `expdb` (preloader and lk logs) and the `super` metadata.
- A raw `nvdata` restore has not been proven sufficient on vegas. Rehearse the return path on the least valuable unit.

**Operational**

- Without Android, nothing enforces a charge cap or runs the vendor thermal stack. Supervise early sessions.
- Unlocking wipes `userdata`. Every route that replaces `userdata` or `system` loses Android data again.

## 7. Open questions and proposed first experiments

### 7.1 Open questions that only a hands-on test or a missing source can answer

**Answered in pass 2, and by what**

- "What is the flashing gate on an unlocked -4-2 unit?" Answered for the flash path by static reading of lk, not on a phone, and with the size rule and the vbmeta rule contested between verifiers: per-image checks against vbmeta descriptors that tolerate a hash mismatch and a missing footer when unlocked, and a vbmeta check that tolerates any key (LG-1, LG-2 [confirmed]; LG-3, LG-5 [contested]). A custom AVB key is not required. What remains is confirmation on a phone and the unexplained Magisk rejection, both listed below.
- "Does lk implement RAM boot?" No (LG-10 [confirmed]).
- "What does PID_NS read on vegas?" Not set, read from the config embedded in the stock kernel (CX-3 [confirmed]). DEVTMPFS is not set in the same config (CX-3 verifier note), and BT_HCIVHCI reads not set there too (re-read in step 0).
- "Does the owner's backup cover every NV partition?" Yes, it reads every named partition (section 6.5).
- "Is preloader B the same older build on all eight phones?" Preloader A: two builds, 6 vs 2, across all eight archives. Preloader B: the same build on the four phones compared, the other four not reported (PM-4 [contested], corrected wording and verifier note).
- "What does `img_auth_required` read in `expdb`?" On the one phone whose `expdb` was read, the later boots log secure boot enabled and `img_auth_required = 1` (RS-8 verifier note, [unverified]).
- "Is there any factory download agent for vegas?" None was found in the firmware zip, in mtkclient or in public reports (RS-1, RS-2, RS-3 [confirmed]; RS-9 [contested]). Whether Motorola's rescue tool would download one for vegas is still unknown.
- "Is `tzapp` device-unique?" No (PM-3 [contested], corrected wording).

**Boot chain**
- Does the static reading of the flash gate hold on a phone: is a footerless `boot_a`, or one with a correct-size footer and a wrong hash, accepted with stock vbmeta on an unlocked -4-2 unit?
- Why was a Magisk-patched `init_boot_a` rejected on -4-2 when the KernelSU one passed? (Offline: compare the footer of a Magisk-patched image with the stock descriptor size.)
- Is the lock-state mapping inferred from the code right? (`getvar` of the secure state and warranty flag on an unlocked unit would support it.)
- Does lk boot a self-built gzip kernel in `boot_a` to orange state? The boot-path tolerance has been exercised only for `init_boot`. Does lk accept a non-Linux payload there?
- Does the kernel decompressor run on every boot, or can a raw image skip it? What does lk do after its panic routine?
- Does a rollback index below the stored one block boot on an unlocked unit?
- Which vbmeta does the gate compare against when the non-active slot is flashed? (Not needed while slot B is never written.)
- Which partitions does lk's "is not allowed to be flashed" message refuse, locked and unlocked? (Disassembly.)
- Does lk treat `unlock_critical` as a separate state, and does the owner's unlock give it?
- Does lk keep the vendor-then-generic ramdisk order for a non-Android `init_boot`, and does it need lz4?
- Does lk drop the first 20 cmdline characters, and does it pass the slot suffix? Which `oem config` keys are writable on an unlocked unit, and does a command-line addition reach a non-Android kernel? `oem config set` and `unset` write `utags` (class A). Do not probe this on a unit that matters. Back up `utags` first and prefer a command line built into the initramfs or the kernel; disassembly can answer the first half without a write.
- Does lk refuse a `super` write unless `vbmeta_a` and `vbmeta_system_a` were flashed earlier in the same session? The -4-2 lk contains the warning that both are required before `super` (lk-gate track lead, string evidence, [unverified]). Until this is known, every restore that writes `super` flashes the two stock vbmeta images first (section 6.3).
- What rollback index is stored on each phone, in particular on the two that ran -4-3? Is there a fastboot variable or an lk log line that shows it?
- Do the Google-signed `system_dlkm` modules load on a self-built kernel with MODULE_SIG_PROTECT on, and does Android boot without them?
- Which DT nodes does lk require, and does it refuse or skip when they are missing? Does replacing the DTB inside `vendor_boot` crash this lk? (Disassembly first.)
- Does flashing `boot_a`, `init_boot_a` or `vendor_boot_a` clear the successful-boot flag or change the retry count? What does lk do if slot A fails with slot B marked unbootable?
- Does fastbootd work with a non-stock `init_boot_a`?
- How is fastboot re-entered from a hung non-Android boot: key combination, the preloader handshake, or only a working initramfs?
- Does lk pass the `ramoops.*` arguments to every boot image, and does pstore content survive the reset after a panic?

**Exception level**
- At what level is the kernel entered, and are `/dev/kvm` and the hypervisor properties absent as predicted?
- Does a kernel without the GenieZone client drivers run cleanly as the GenieZone guest, and do PSCI and SiP calls pass?
- Does the `bl2_ext` failure path continue to lk and fastboot? (Disassembly, not a flash.)

**Modules and kernel**
- Which drivers live only in `vendor_dlkm`: display, Mali, panels, touch, `mtk-mmc`? (Offline.)
- Does a kernel actually built at 9b2308ac0ad6 with each fragment produce CRCs matching all 2348 imported symbols?
- Do the stock modules match what the Motorola tag builds?
- Is the out-of-struct SYSVIPC patch safe for the statically allocated init task? Which `task_struct` reserve slots do Motorola's modules touch, which decides whether a padding-slot SYSVIPC patch is safe?
- Does the Mali module need the PID-namespace quirk? Does PID_NS on the host change anything for it while Android stays in the initial namespace?
- Does one kernel boot both stock Android and Linux or Halium? Does Android 16 on vegas boot cleanly with SYSVIPC, PID_NS and IPC_NS enabled, or does a config check fail harder than a dialog?
- Is a systemd userland fully functional without FHANDLE on this kernel?

**Hardware without Android**
- Does mtu3 enter device mode and enumerate NCM from an initramfs?
- Does `mediatek-drm` light the vegas panels for a legacy KMS client, and does the panel stay lit after lk?
- Where does `wmt_drv` get the ROM patch on vegas, and what MAC does the driver use without NVRAM?
- Does the aw883xx amplifier work from ALSA alone?
- Do charging, the fuel gauge and thermal protection work fully in-kernel, and does the proc node behave the same?
- Is there a reachable UART? No pad map is public; a service manual for the 2025 model has a test-points page behind a login that was not read. Where does lk leave the framebuffer?
- Does loading the Wi-Fi driver, which pulls in the modem modules, start anything on a phone with a live modem?
- Does Waydroid's HALIUM_13 image work with the MT6835 vendor graphics stack on a Halium host, and what does it cost in RAM?

**Radio**
- Does the vendor expose `mtkradioex` 3.0?
- Does ofono's binder plugin work with Motorola's RIL?
- Is the IMEI regenerated after an nvdata erase on vegas, and from where?
- Does a Halium boot ever reformat an NV partition when a mount fails?

**Slots and rescue**
- Which `preloader_b` build is on the four phones not yet compared?
- What does a staged A/B OTA do to an unlocked unit: does it write a stock `lk_b` and switch the active slot, and what does stock lk then do with an unlocked `seccfg`? (Do not test; block OTAs.)
- Does a slot switch flip the UFS boot LU?
- Does the preloader's slot check really refuse an all-zero lk?
- Is the BROM-disable fuse blown on the owner's units? lk has a test option that prints it, but the same command has fuse-blowing options, so it must not be run until disassembly shows the read option is read-only.
- Does the vegas preloader accept the handshake that starts lk in fastboot without a download agent?
- Does Motorola's rescue tool download a flash tool with a download agent for vegas?
- What does the lk `blankflash` command do on this platform? (Disassembly.)
- Does `tzapp_a` get refilled by a stock boot after an erase, and does the phone boot normally while it is empty? (Do not test on a phone that matters.)
- Has a reduced stock reflash ever been run on an unlocked vegas, and does stock Android then boot cleanly in orange state?
- What is in `misc` after a bootloader unlock?

**Sources not reached, or to read in full**
- Current BraX3 status after the September 2026 commits.
- The UBports android16 group listing.
- Several Nura wiki pages in their current revision (bot protection).
- Which side of the unlock fix builds -4-7 and -4-9 are on. The statement that the unlock is patched from September 2026 comes from one guide and is not a ledger claim.
- The MT6878 Plinius fork's boot chain, to settle whether it chain-loads U-Boot from stock LK (section 3.2).
- The moto g power 2025 Linux project on the same SoC (microSD root, stock kernel, USB shell). It is cited here only through RS-15 and is worth a full read as the closest Motorola precedent.
- The -4-3 install log's passages on slot use. The pass-1 critic reading said the log shows a unit running stock -4-3 from slot B and switching slots in both directions. No pass-2 claim or verifier covers that, so it is not used as fact here; LG-13 supports only the fallback from A to B.
- The XDA threads for vegas26 and its siblings, which blocked the fetcher, for brick and recovery reports.
- The Samsung MT6835 kernel repository of CX-5, to compare its config and module handling with vegas.
- The Droidspaces documents not read in full (compositor path, cgroup handling, troubleshooting).
- Nura's contribution policy: one track reported a ban on AI-assisted contributions; this was not verified and no source was recorded, so decide separately whether upstreaming is a goal.

### 7.2 Proposed first experiments, least to most risky

The order changed in pass 2 for three reasons. There is no RAM boot, so the old "test with no writes" step is gone and its place is taken by checks that make a failed flash recoverable. The flash gate now has a likely static explanation (partly contested, not run on a phone), so the first images are built to the rules of section 2.4 and no vbmeta step is planned. And the rebuilt kernel is booted with Android first, which tests the kernel with adb available and establishes whether one kernel serves both systems.

One rule applies to every step that flashes: after a failed boot, read the boot-control state; after two or three failed boots, restore stock (section 6.3, level 1) and stop.

**Step 0. No phone needed**
- List which modules are in the vendor ramdisk versus `vendor_dlkm`. Scan the `vendor_dlkm` modules for signatures. List the `system_dlkm` modules, their signatures and their imported symbols.
- Re-read DEVTMPFS and BT_HCIVHCI in the config already extracted from the stock kernel. Both read not set; this is a confirmation, not an open question.
- Build the kernel at 9b2308ac0ad6 with the minimal fragment and run the full CRC and symbol check against all 376 stock vendor modules and against the `system_dlkm` modules; the offline checker of the REDMAGIC recipe (CX-6) is a ready model. Decide here how `system_dlkm` is handled: MODULE_SIG_PROTECT off, or `system_dlkm` rebuilt from the same tree (section 2.1). Repeat with the Halium config and with the namespace options plus a SYSVIPC patch. Each of those builds must pass the CRC check and a BTF layout comparison on its own; the static result G13-3 covers the stock ABI only.
- Prepare the test images and check them against section 2.4 before they go near a phone: footer present with `vbmeta_offset` not below the stock descriptor size (3096576 for `init_boot`, 21549056 for `boot`), or no footer; gzip kernel; header v4. The stage-0 `init_boot` probe is a padded image: pad the boot image to at least 3096576 bytes, re-add the hash footer with avbtool for partition `init_boot` at the 8388608-byte partition size, and read the footer back to confirm `vbmeta_offset` is at least 3096576. Check that any self-made vbmeta carries a rollback index at or above the one assumed for the chosen unit (section 6.4).
- Read the footer of a Magisk-patched -4-2 `init_boot` and compare it with the stock descriptor size, to test the explanation of the one rejection on record.
- Continue the lk disassembly where pass 2 stopped: the boot path (verification tolerance, the decompressor, DTB parsing for `vendor_boot`), whether a flash touches the boot-control block, the list behind "is not allowed to be flashed", the `ssm_test` and `blankflash` handlers, and the conditions under which the BROM-disable fuse is blown. Then the preloader slot check and download-agent verification, and the `bl2_ext` GenieZone failure path.
- Decompile the stock DTB as the reference for sections 3.1 and 3.2.

**Step 1. Locked stock phone with temp root, read-only**
- The full per-phone backup of section 6.5, before anything else and before unlocking.
- Early dmesg lines for the CPU start level and KVM; presence of `/dev/kvm` and `/dev/gzvm`; hypervisor properties.
- Live vendor API properties, the RAM size, and the board ID that selects the dtbo overlay.
- `expdb` for the preloader and lk logs, the secure-boot lines and the A/B retry state; the lk framebuffer address and geometry. `pstore`, to see whether anything is recorded.
- The `misc` boot-control structure.
- The preloader build on both boot LUs and every slot-B partition, on every phone that is a candidate unit.
- A trace of the stock `wmt_launcher` replies.

**Step 2. Unlock one unit on -4-2, then check before any experiment write.** There is no RAM boot, so nothing can be tested without a flash (LG-10). Use this step to make later failures recoverable. Choice of unit, before the unlock: unlocking is one-way under the rules of section 6, so the unit leaves the end-state-D fleet. Pick an expendable one and remove it from route-D maintenance (`farm.py`). Prefer a unit that has never run -4-3; for a unit that has (#7, #8), any vbmeta written must carry rollback index 7 or higher.
- First, before the unlocked unit joins any network: disable OTA. The unlock wipes data, and the first boot of a networked phone can fetch and stage an A/B OTA. Either disable the Motorola update app and the update engine from adb or root, or keep Wi-Fi and the SIM off (the method is a suggestion and was not tested for this document). After every boot, confirm that the current slot is still A and that slot B is unchanged.
- After the unlock: confirm both IMEIs and the modem still register, because the unlock path may erase `nvdata`.
- In fastboot: read the secure state, the warranty flag, whether a custom AVB key is reported, the current slot, and the slot variables for successful, unbootable and retry count. This establishes how the boot-control state can be read without Android and checks the lock-state mapping behind section 2.4.
- Confirm that slot A is active with its successful flag set.
- Required: confirm the key combination from power-off as a way into fastboot that does not depend on a working system. Do not run `oem fb_mode_set`; it is uncharacterised.
  - Optional sub-step, [unverified] on vegas: the preloader handshake that asks lk to start in fastboot. It talks to the same preloader tool window that carries the download-agent path, and sending tool commands to a fused production preloader is untested here. Run only the documented META-to-FASTBOOT request of mtkclient, never a download-agent upload or any write command.
- Do not probe `oem config` keys on this unit unless `utags` is backed up and the test is deliberate (section 2.7).
- Root the unlocked unit the established way and re-read `seccfg`, `misc` and `metadata`. Archive that unit's `lk_a` (the serial-bound unlock lk), the hashes of its `boot_a`, `init_boot_a` and `vbmeta_a`, and the KernelSU `init_boot` image used to root it, before step 3 overwrites `init_boot_a` (section 6.5).

**Step 3. Stage 0 probe.** Replace only `init_boot_a` with a minimal initramfs in a footer-bearing image whose `vbmeta_offset` is at least 3096576. A minimal initramfs is smaller than the stock ramdisk, so the image is padded and its hash footer re-added as prepared and verified in step 0. This padded image is untested; the hands-on case was the larger KernelSU image. If lk refuses the flash, stop and compare the refusal with section 2.4; by static reading the validator runs before the write, so nothing has been written (LG-1). The initramfs carries a USB console, a boot-loop breaker and a timed reboot to the bootloader, with `reboot-mode.ko` and `syscon-reboot-mode.ko` loaded (RS-15); the same three pieces are required in every later experiment initramfs. Check: the flash is accepted with stock vbmeta, `/init` runs as PID 1, the vendor ramdisk modules are present and load, the USB gadget enumerates on the Mac, the reboot to fastboot works, the boot-control state is unchanged after reboot, and whether fastbootd still starts. Restore stock `init_boot_a`.

**Step 4. Confirm the flash gate and boot path for `boot_a`, with harmless images first.**
- Step 4a, mandatory before any footerless or self-built image: a repacked `boot_a` that carries the stock kernel binary in a footered image (footer `vbmeta_offset` at least 21549056), with stock vbmeta. Confirm offline that its hash differs from the stock descriptor (recompressing the same kernel is enough); a byte-identical repack would test nothing about mismatch tolerance. Android should boot. Note whether the flash is accepted, whether the phone boots to orange state, and what happens to the boot-control state, in particular whether the flash cleared the successful flag. This is the low-risk case. Until it has run, every other `boot_a` image is rated medium, because the boot-time tolerance of a hash mismatch (LG-12) is [unverified].
- Step 4b: then the rebuilt kernel with the minimal fragment, in a footered image first, still with stock `init_boot_a`, so that Android boots on it. Check that all stock modules load, including the `system_dlkm` ones (section 2.1), and that Android runs normally. This is the first self-built kernel on vegas by any source. A footerless variant comes only after this, if it is needed at all.
- If either flash is refused, stop and compare the refusal with section 2.4 before trying a vbmeta step. Do not install `avb_custom_key`.

**Step 5. Linux on the rebuilt kernel.** USB shell from an embedded initramfs started by its own name, or from a replaced `init_boot_a`; then `super` mapping and the Wi-Fi helper pair, with the NV partitions unmounted and a check that no modem boot is triggered; then a legacy KMS test pattern. The USB console, the boot-loop breaker and the reboot-to-bootloader helper are already working from step 3.

**Step 6. Root filesystem placement that keeps Android, and switching.** microSD first, then a `super` logical partition. Add the boot-control writer (class D rules in section 6.1). Add slot-A image switching: with the stock kernel between the stock ramdisk and the Linux initramfs, and with the rebuilt kernel only after step 4 showed that it boots Android. A boot-time chooser, if one is written, takes its signal from a volume key or a labelled SD card, never from a file written to `metadata` from Linux.

**Step 6b. Optional: Android host with a system container** (section 3.11). A second kernel build with the namespace options and a SYSVIPC patch, checked offline, then flashed to `boot_a` under Android. It shares everything with step 4 except the config.

**Step 7. Halium 13.** The `halium.config` kernel must itself have passed the step-0 CRC and BTF layout check; the static result for the stock ABI does not cover it. The Halium `init_boot` image follows the same footer and padding rule as step 3 and carries the timed reboot to the bootloader. First the debug-shell probe: the Halium initramfs in `init_boot_a` with no root filesystem. Then restore stock `init_boot_a`, flash `system` in stock fastbootd, and only then flash `boot_a` and the Halium `init_boot_a`. Put the fstab overlay of section 6.1 in place before the Android container starts for the first time. Waydroid (section 3.12) comes after the host works.

**Step 8. Foreign payload in `boot_a`.** A minimal gzip-compressed non-Linux payload, then the UEFI port or the mainline shim. A payload cannot mark the boot successful or reboot itself to fastboot unless it is written to do so, which makes the two-or-three-boots rule strict here.

**Step 9. Deferred until the analysis in step 0 says otherwise.** Anything involving slot B, `gz`, `bl2_ext`, `dtbo_a`, a changed DTB in `vendor_boot_a`, a custom `vendor_boot_a` of any kind, `avb_custom_key`, or U-Boot as lk.

## 8. Sources

Each entry gives the claim in short form, its verdict, the source link and the source date. Entries whose original wording was refuted give the corrected wording and are tagged [contested]. Claims that were not put through verification are tagged [unverified]. Pass-1 entries come first, by topic. Pass-2 entries (LG, RS, PM, CX) follow in four groups at the end. Local sources are relative to the repository. Backups, logs and archives are cited by directory only, so that no serial number appears here. Session scratch data (unpacked `super`, the rebased kernel tree, analysis scripts) was not kept in the repository and must be regenerated.

### Device ground truth and vendor kernel (2.x, 3.3, 3.4)

- **VK-1** No tag for any W1WE build exists in Motorola's kernel, module, devicetree or GPU repositories. [confirmed] https://github.com/jimmielin/android_device_motorola_vegas26-kernels (2026-11-15)
- **VK-2** A source request for build -4-7 was open without a Motorola reply; a second for -4-9 followed. [unverified] https://github.com/MotorolaMobilityLLC/kernel-mtk/issues/312 (2026-11-15)
- **VK-3** `kernel-mtk` tag MMI-W1WN36.18-114 (5.15.180) is declared by its commit message to cover Vegas and Orlando on GKI android13-5.15-2025-05_r14. [confirmed] https://github.com/MotorolaMobilityLLC/kernel-mtk/commit/0fa176ca7f56c349b51acd83684284c02ced5854 (author 2026-01-29, commit 2026-04-27, tag 2026-06-25)
- **VK-4** ACK tag android13-5.15-2025-05_r14 peels to 9b2308ac0ad6, the hash in the stock kernel string. [confirmed] https://android.googlesource.com/kernel/common/+/refs/tags/android13-5.15-2025-05_r14 (2025-11-30)
- **X-CI** Google CI build 14563692 is `kernel_aarch64` at that commit. [confirmed] https://ci.android.com/builds/submitted/14563692/kernel_aarch64/latest/raw/BUILD_INFO (read 2026-11-21)
- **VK-5** The tag contains the orlando overlay and a vegas config fragment; the stock dtbo carries a matching overlay; the overlay includes a `cust.dtsi` not in the repository. [confirmed] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/boot/dts/mediatek/mt6835-orlando-evb-overlay.dts (2026-01-29)
- **VK-6** MODULE_SIG_PROTECT lets unsigned vendor modules load; a rebuilt kernel needs no signing key. [confirmed] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/init/Kconfig (2026-01-29)
- **VK-7** The tag exists in the module, GPU and connectivity repositories and is absent from mtkcam, met_drv_v3 and kernel-build-kernel. [unverified] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/configs/mgk_64_k515_defconfig (2026-01-29)
- **VK-8** Moto Pad 2026: Arch Linux on a CRC-preserving rebuilt GKI 5.15.185 with stock modules; display, touch, Wi-Fi, Bluetooth, audio, USB and GPU working, camera and modem not; single-author self-report; flashed through BROM. [contested] https://github.com/Mattcabrices/moto-pad-2026-arch-linux (2026-11-10)
- **VK-9** The tablet's config fragment and its constraints; per-option probe covered three symbols in one module; the LOCALVERSION_AUTO reason is not borne out; stock configs of tablet and vegas differ in one line. [contested] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/HEAD/kernel/arch-fragment.config (2026-11-09)
- **VK-11** Motorola's `gki_defconfig` leaves PID_NS, FHANDLE and VT unset; SYSVIPC adds two `task_struct` members. [unverified] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/configs/gki_defconfig (2026-01-29)
- **VK-12** The vendor DRM driver builds fbdev code only under DRM_FBDEV_EMULATION, which no defconfig sets. [unverified] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/drivers/gpu/drm/mediatek/mediatek_v2/Makefile (2026-01-29)
- **VK-13 / PR-7** LineageOS 23.2 tree for vegas26: prebuilt stock kernel, requires -4-3, self-reported working list, no releases. [contested] https://github.com/jimmielin/android_device_motorola_vegas26 (2026-11-16)
- **VK-14** Original "lk validates each image against vbmeta, so vbmeta must go first" refuted as a general rule. Corrected: it is the tree author's instruction for -4-3; the exact check is not established. [contested] https://github.com/jimmielin/android_device_motorola_vegas26 (2026-11-16)
- **X-JES** A guide says the unlock is reported patched in builds from September 2026 onward, with August untested. This sentence is not a ledger claim. The guide's statements about the flash gate were verified in pass 2 as LG-7. [unverified] https://github.com/jesussaves-dev/moto-g-power-2026-root (commit of 2026-11-13, read 2026-11-21)
- **VK-15** A LineageOS GSI ran on -4-3; the fastboot wipe leaves `/data` unformatted, and stock recovery must format it. [unverified] https://github.com/qfertig/vegas26-gsi (2026-11-19)
- **PR-1, PR-2** Moto Pad port boots Arch from `boot_a` with the root on `userdata`, keeping CRCs so 300+ stock modules load. [confirmed] https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/README.md (2026-11)
- **PR-3** On that port camera and modem do not work; Wi-Fi and Bluetooth work through Android helpers in a chroot. [confirmed] same URL (2026-11)
- **PR-4** That kernel leaves SYSVIPC, USER_NS and PID_NS off as an untested precaution; no SysV shared memory. [confirmed] https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/kernel/arch-fragment.config (2026-11)
- **PR-5** Original "realme kernel shows these options can be added without breaking modules" refuted. Corrected: it needed SysV state in KABI slots 1-3 and a BTF layout gate; CRCs alone missed a bad build. [contested] https://github.com/ivangotoy/rmx3997-kernel (2026-11-19)
- **PR-8** Tree author: no known BROM rescue path; stock ships with slot B empty; never switch slots. [confirmed] https://github.com/jimmielin/android_device_motorola_vegas26 (2026-11-16)
- **PR-16** The tablet project writes `boot_a` in BROM mode with a factory download agent and auth file. [unverified] https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/53-wsl-write-boot-a.sh (2026-11)
- **X-SD** systemd's README lists CONFIG_FHANDLE as required and kernels below 5.10 as unsupported. [unverified] https://raw.githubusercontent.com/systemd/systemd/main/README (read 2026-11-21)

### Mainline (3.1)

- **ML-1 / HW-1** Mainline v7.4-rc3 and linux-next 20261120 contain "mt6835" only as a UART DMA compatible. [confirmed] https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/drivers/dma/mediatek/mtk-uart-apdma.c (2026-11-20)
- **ML-2** The only patch on linux-mediatek in 13 months whose subject names MT6835 is that one; it names the SoC Dimensity 6300. A few other patches touch the same compatible without naming it in the subject. [confirmed] https://lists.infradead.org/pipermail/linux-mediatek/2025-November/101140.html (2025-11-13)
- **ML-4** MT6833 base series v2 reaches an initramfs; stock LK cannot boot a mainline DT; tested with kaeru. Not merged. [confirmed] https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116576.html (2026-11-17)
- **ML-5** MT6895 base series v2 reaches an initramfs only with a non-public modified LK. [confirmed] https://lists.infradead.org/pipermail/linux-mediatek/2026-November/116317.html (2026-11-13)
- **ML-6** a22x-mainline (MT6833, Linux 7.2) boots from stock Samsung LK by flashing only `boot`; the image is purpose-built and the root replaces `userdata`. [contested] https://gitlab.com/pessdres/a22x-mainline/-/blob/main/README.md (2026-11-14)
- **ML-7** a22x keeps the stock device tree, disabled, in its DTB because Samsung's LK refuses to boot otherwise. [confirmed] https://gitlab.com/pessdres/a22x-mainline/-/blob/main/docs/BUILDING.md (2026-11-14)
- **ML-8** a22x has no modem and no camera; Wi-Fi is the vendor gen4m driver ported out of tree. [confirmed] https://gitlab.com/pessdres/a22x-mainline/-/blob/main/README.md (2026-11-14)
- **ML-9** Panfrost supports Job Manager Valhall GPUs generically; the MT6835 GPU ID is unknown. [unverified] https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/Documentation/devicetree/bindings/gpu/arm,mali-bifrost.yaml (2026-11-20)
- **ML-10** The stock vegas DTB uses mainline-matching compatibles for UART, mtu3, T-PHY, UFS and watchdog. [unverified] `../tools/locked/` (stock -4-2 zip, `vendor_boot.img`; read 2026-11-21)
- **ML-11** GPL MT6835 clock, pinctrl, power-domain and DTS sources are public in a OnePlus tree; only pinctrl shares a mainline framework. [confirmed] https://github.com/OnePlusOSS/android_kernel_oneplus_mt6835/blob/20ad6b319f91a8fd036077ee7aa27683469b8292/drivers/pinctrl/mediatek/pinctrl-mt6835.c (2026-10-28)
- **ML-12** Nura's package tree at its 2026-11-21 commit contains no occurrence of "mt6835". [unverified] https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/master/device/testing/linux-postmarketos-mediatek-mt6878/APKBUILD (2026-11-21)
- **ML-13** Nura's MT6878 CMF Phone 1 port boots through a patched U-Boot because that board needs a secure-monitor call on each jump to the kernel. [unverified] https://gitlab.postmarketos.org/postmarketOS/pmaports/-/blob/master/device/testing/device-nothing-tetris/deviceinfo (2026-11-21)
- **ML-15** kaeru targets ARMv7 LK only. The vegas `lk` sub-image is AArch64 by disassembly. [unverified] https://github.com/R0rt1z2/kaeru/blob/HEAD/README.md (read 2026-11-21)
- **ML-16** Mainline lacks the vegas PMIC interface, MT6377, MT6375, CCCI and connsys drivers. [unverified] https://github.com/torvalds/linux/blob/c44104f3642da720164042623e4832836aefdd8e/drivers/spmi/spmi-mtk-pmif.c (2026-11-20)
- **HW-4** Mainline has no CCCI driver; the only MediaTek WWAN entry is the PCIe T7xx. [confirmed] https://raw.githubusercontent.com/torvalds/linux/master/drivers/net/wwan/Kconfig (2026-11-21)
- **HW-2** Original "CMF Phone 1 is the most advanced mainline Dimensity port" refuted; its table is stale. [contested] https://wiki.nura.eco/wiki/Nothing_CMF_Phone_1_%28nothing-tetris%29 (2026-10-15)
- **X-XAGA** The MT6895 xaga page lists display, touch, GPU, audio, Wi-Fi, Bluetooth and battery working, with calls and data not. One verifier's reading; another track could not confirm the Wi-Fi and Bluetooth status. [unverified] https://wiki.nura.eco/wiki/Xiaomi_Redmi_Note_11T_Pro_%28%2B%29_/_POCO_X4_GT_/_Redmi_K50i_%28xiaomi-xaga%29 (2026-10-05)
- **HW-11** libcamera has no MediaTek pipeline handler. [unverified] https://raw.githubusercontent.com/libcamera-org/libcamera/master/meson_options.txt (2026-11-21)

### Nura / stock-kernel userspace (3.3, 3.5)

- **NP-1** Nura keeps a "downstream" category as a step toward mainline; "testing" needs a close-to-mainline kernel. [confirmed] https://docs.nura.eco/pmaports/main/packaging/device-categorization.html (read 2026-11-21)
- **NP-2** A port on a prebuilt extracted kernel will not be accepted into the package tree. [contested] https://wiki.nura.eco/wiki/Porting_to_a_new_device/Kernel_package/Downstream (2026-09-27)
- **NP-3** The stock vegas config fails Nura's default kernel-config lint, which requires VT, SYSVIPC, USER_NS and PID_NS. [confirmed] https://gitlab.nura.eco/nura/pmaports/-/raw/main/kconfigcheck.toml (2026-11-21)
- **NP-9** The Nura wiki has no page for vegas or any device listed with MT6835; the wiki search was reported as unreliable. [unverified] https://wiki.nura.eco/wiki/Samsung_Galaxy_A15_5G_(samsung-a15x) (2026-09-27)
- **PR-11** Nura's main aarch64 package index of 2026-11-20 has no package that mentions MT6835 or vegas. [unverified] http://mirror.nura.eco/postmarketos/main/aarch64/APKINDEX.tar.gz (2026-11-20)
- **NP-4** boot-deploy writes kernel to `boot` and initramfs plus DTB to a generated `vendor_boot` for header v4 and never touches `init_boot`. [contested] https://gitlab.nura.eco/nura/boot-deploy/-/merge_requests/83 (2025-08-09)
- **NP-5** AOSP: the generic ramdisk is concatenated after the vendor ramdisk and its `/init` wins. [confirmed] https://source.android.com/docs/core/architecture/partitions/generic-boot (2026-10-09)
- **X-KSU** KernelSU's LKM mode patches the image holding the generic ramdisk and replaces `/init`. [unverified] https://kernelsu.org/guide/installation.html (read 2026-11-21)
- **NP-6** Original "systemd freezes for lack of namespaces and FHANDLE" refuted. Corrected: a Moto G50 boots console-only Nura by RAM boot; the systemd freeze is tied to its 5.4 kernel; Debian's systemd 257 boots on it. [contested] https://wiki.nura.eco/wiki/Motorola_Moto_G50_%28motorola-ibiza%29 (2026-10-14)
- **NP-7** Pixel 7a: Android init from the untouched `init_boot` took PID 1; the NCM gadget never enumerated. [unverified] https://wiki.nura.eco/wiki/Google_Pixel_7a_%28google-lynx%29 (2026-09-27)
- **NP-12** On MT6895 xaga, replacing the `vendor_boot` DTB crashes MediaTek LK. [unverified] xaga wiki page, as X-XAGA (2026-10-05)
- **NP-13** A 2026 Helio G99 tablet fails download-agent authentication under mtkclient. [unverified] https://wiki.nura.eco/wiki/Onn_11_Core_Tablet_%28onn-t405a%29 (2026-11-07)
- **NP-14 / HW-14** libhybris has been dropped from Nura. [unverified] https://wiki.nura.eco/wiki/Hybris (2026-10-22)
- **NP-15** Nura's initramfs uses a configfs gadget with NCM by default. [unverified] https://docs.nura.eco/pmaports/main/packaging/device-packages/deviceinfo-reference.html (read 2026-11-21)
- **NP-16** Nura's unlock UI can render through DRM. [unverified] https://gitlab.nura.eco/nura/buffybox/-/raw/main/unl0kr/README.md (read 2026-11-21)
- **X-TAP** A Droidian port calls an 8 MiB `init_boot` too small for a Halium initramfs. [unverified] https://github.com/Sype0/linux-android-xiaomi-tapas (date not retrieved)

### Halium (3.6)

- **HA-1** On an unlocked XT2617V on -4-3: vendor at VNDK 33, first API level 36, LineageOS GSI running from `system`. [confirmed] https://github.com/qfertig/vegas26-gsi (2026-11-19)
- **G13-12** The vendor `build.prop` in `super` (-4-2) says vndk 33 and board API 33; the manifest declares AIDL radio and `mtkradioex` HALs. [confirmed] `../tools/locked/` (stock -4-2 zip, `super`; built 2026-04-06)
- **HA-2 / G13-6** Motorola Edge 50 Pro port: Halium 13, generic UBports kernel, stock vendor modules, vendor API 33 across Android 14 to 16. [confirmed] https://gitlab.com/ubports/porting/community-ports/android13/motorola-edge-50-pro/motorola-eqe (2026-10-19)
- **HA-3** Nothing Phone 2a (MT6886) port: same recipe; status list may be stale; no boot report. [contested] https://gitlab.com/ubports/porting/community-ports/android13/nothing-phone-2a/nothing-pacman (2026-09-26)
- **HA-4** BraX3 (MT6835) Ubuntu Touch 24.04 port exists on Halium 13 with header v4 and `init_boot`. [confirmed] https://gitlab.com/ubports/porting/community-ports/android13/brax3/brax-prithvi (2026-10-19)
- **HA-5** BraX3 uses a 5.15.148 MediaTek vendor-fork kernel; its commit message says it loads prebuilt stock modules; CGROUP_DEVICE removed as KMI-breaking. [contested] https://gitlab.com/ubports/porting/community-ports/android13/brax3/kernel-brax-mt6835/-/commit/c8ab389745cc024877adc2a22ff28874077cfcc7 (2026-09-24)
- **HA-6** UBports branch `android13-5.15-halium` (5.15.178) keeps SYSVIPC state outside `task_struct` and disables protected-module enforcement. [confirmed] https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/tree/android13-5.15-halium (2026-10-14)
- **HW-7** Its `halium.config` enables SYSVIPC, USER_NS, VT, AppArmor, squashfs and POSIX_MQUEUE and leaves CGROUP_DEVICE off as ABI-breaking. [confirmed] https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/raw/android13-5.15-halium/arch/arm64/configs/halium.config (2026-10-14)
- **HA-7** Upstream android13-5.15 `gki_defconfig` leaves PID_NS, FHANDLE and VT unset. [confirmed] https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.15/arch/arm64/configs/gki_defconfig (read 2026-11-21)
- **G13-2** The 18 Halium commits replay onto 9b2308ac0ad6 without textual conflict; not compiled. [confirmed] https://github.com/MotorolaMobilityLLC/kernel-mtk/tree/MMI-W1WN36.18-114 (test run 2026-11-21)
- **G13-3** All 2348 symbols imported by the 376 stock modules have identical CRCs in the ACK ABI file at both bases. [confirmed] https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/android/abi_gki_aarch64.xml (checked 2026-11-21)
- **G13-9** Plain CGROUP_DEVICE breaks the KMI; a realme patch gives it an id after the counted subsystems. [unverified] https://github.com/ivangotoy/rmx3997-kernel/blob/2963eddf9f7b259bbc626348d4f97f3087b187b9/include/linux/cgroup_subsys.h (2026-11-19)
- **G13-10** USER_NS, PID_NS and POSIX_MQUEUE gate no struct members in the headers examined. [unverified] https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/cred.h (commit dated 2025-11-30)
- **G13-11** Motorola's modules use only `android_oem_data1` and `android_vendor_data1` for per-task state. [unverified] https://github.com/MotorolaMobilityLLC/motorola-kernel-modules/blob/MMI-W1WN36.18-114/drivers/moto_sched/msched_common.h (2026-01-29)
- **G13-13** Build tools map Halium version 13 to a halium-13.0 image and 15 or 16 to halium-16.0; no Halium 13 port of an Android 15/16-launched device was found. [unverified] https://gitlab.com/ubports/porting/community-ports/halium-generic-adaptation-build-tools/-/blob/main/prepare-fake-ota.sh (2026-11-09)
- **G13-14** BraX3 on the 0.9 beta: SIM mostly not recognised, no calls in the USA, camera and fingerprint not working. [unverified] https://forums.ubports.com/topic/12368 (2026-06-12)
- **HA-13** Original January 2026 summary refuted on date and on the "rework fixed it is unknown" framing. Corrected: no carrier and dying camera on 2026-01-02; later reports show partial data and SMS, no voice, through 2026-10. [contested] https://community.braxtech.net/t/flashing-ubuntu-touch-megathread/3677 (2026-01-02 to 2026-03-17)
- **G13-15** BraX3 IMEI losses are tied to SP Flash Tool flashing, cause undetermined; the Ubuntu Touch fastboot install touches no NV partition; vegas flashfile contains `erase nvdata` and the fstab marks NV partitions formattable. [contested] https://community.braxtech.net/t/i-got-ut-installed-a-third-time-now-can-i-flash-back-to-android-without-losing-imeis/4444 (2026-04-14) and `../tools/locked/` (stock -4-2 zip)
- **G13-16** The UBports Mali PID-namespace quirk matches `mali_kbase`; the vegas module is `mali_kbase_mt6835`. [unverified] https://gitlab.com/ubports/porting/community-ports/android12/generic/kernel-android-common/-/commit/a7589e4c1b3a0ec4ff3372ca5596e57a360e306e (2026-07-06)
- **HW-5** Volla Phone Plinius (MT6878, Halium 14, kernel 6.1): nearly all hardware marked working. [confirmed] https://gitlab.com/ubports/infrastructure/devices.ubuntu-touch.io/-/raw/main/data/devices/ansuz/releases/noble.md (2026-10-02)
- **HW-6** That port builds the generic GKI kernel and ships prebuilt vendor modules on a boot layout matching vegas. [confirmed] https://gitlab.com/ubports/porting/reference-device-ports/halium-14/volla-phone-plinius/volla-ansuz/-/raw/master/deviceinfo (2026-11-19)
- **HW-8** Halium has 13, 14 and 16 branches and no 15; original inference "vegas needs Halium 16" refuted by the vendor API level. [contested] https://raw.githubusercontent.com/Halium/android/halium-16.0/default.xml (2026-08-28)
- **HW-9** An ofono binder extension provides VoLTE and SMS over IMS on `mtkradioex` 3.0. [unverified] https://raw.githubusercontent.com/FuriLabs/ofono-binder-plugin-ext-mtk/forky/README (2026-11-14)
- **HW-10** Under Halium, MediaTek Wi-Fi is started after the vendor nvram service by loading gen4m and writing to `/dev/wmtWifi`. [unverified] https://gitlab.com/ubports/porting/reference-device-ports/halium-14/volla-phone-plinius/volla-ansuz/-/raw/master/overlay/system/usr/libexec/lxc-android-config/device-hacks (2026-11-20)
- **HW-15** Droidian's wlroots fork adds a hwcomposer backend. [unverified] https://raw.githubusercontent.com/droidian/wlroots/HEAD/backend/meson.build (date unknown)
- **HA-11** Droidian's latest release ships generic rootfs images for API 28 to 33 only. [unverified] https://github.com/droidian-images/droidian/releases/expanded_assets/droidian%2F101.20261023 (2026-10-23)
- **HA-12** FuriOS on the FLX1 runs a 4.19 non-GKI kernel. [unverified] https://github.com/FuriLabs/linux-furiphone-krypton/blob/forky/debian/kernel-info.mk (2026-11-18)

### UEFI / U-Boot (3.2, 5)

- **UE-1** TB365FC (MT6835): a Mu-Silicium-derived UEFI packed as a boot v4 kernel is loaded by stock LK from `boot_a`; single-author self-report; the repository's `PORTING.md` contradicts its README. [confirmed] https://github.com/LittleStar-OuO/uefi-tb365fc (last commit 2026-11-02)
- **UE-2** That firmware has no UFS, USB or MSDC driver in its volume; GPIO and MSDC tables are MT6833 copies. [contested] https://github.com/LittleStar-OuO/uefi-tb365fc/blob/HEAD/PORTING.md (2026-11-02)
- **UE-3** Original "no address shim needed on either device" refuted. Corrected: all three `vendor_boot` addresses match between the tablet and vegas; no-shim on vegas is plausible and untested. [contested] https://github.com/LittleStar-OuO/uefi-tb365fc/blob/HEAD/Resources/Configs/tb365fc.toml (2026-11-02)
- **UE-5 / PR-6 / X-TB** Original "no XNU image built or booted; stops at the menu" refuted as stale. Corrected: newer unmerged branches report XNU reaching the iPadOS home screen, payload in `vendor_boot_a`, UFS driver on the XNU side. [contested] https://raw.githubusercontent.com/LittleStar-OuO/UniXNU-tb365fc/docs/readme-zh-en-20261121/README.en.md (2026-11-21)
- **UE-7** Upstream Mu-Silicium lists three MediaTek devices, all inactive, none booting Linux, no MT6835 package. [confirmed] https://github.com/Project-Silicium/Mu-Silicium/blob/main/Status.md (2026-11-21)
- **UE-8** Mu-Silicium's binary-reuse porting method is Snapdragon-only. [confirmed] https://github.com/Project-Silicium/Guides/blob/main/Silicium/Porting/Snapdragon/Device/README.md (2025-06-14)
- **UE-11** Original target list refuted on branch and count. Corrected: U-Boot `main` at c1958b5 has 16 MediaTek targets, none MT6xxx; it carries UFS and mtu3 drivers untested on MT6835. [contested] https://raw.githubusercontent.com/u-boot/u-boot/c1958b5f6cce03956d309ce422b5d9f819955d4a/arch/arm/mach-mediatek/Kconfig (2026-11-19)
- **UE-12** On MT6878, U-Boot in the lk partition is possible only when the preloader does not verify the lk payload. [unverified] https://wiki.nura.eco/wiki/MediaTek_Dimensity_7300_%28MT6878%29 (2026-09-27)
- **UE-13** On the Moto G72, U-Boot replaces LK; Motorola disabled USB boot there. [unverified] https://wiki.nura.eco/wiki/Motorola_Moto_G72_%28motorola-vicky%29 (2026-09-28)
- **UE-14** Stock vegas `lk.img` is a container of certified sub-images; no UEFI code. Its statement that RAM-boot support is not settled by strings is superseded by LG-10. [unverified] `../tools/locked/` (stock -4-2 zip, `lk.img`; image dated 2026-04-16)
- **UE-16** arm64 Linux under UEFI boots through the EFI stub and uses device tree by default. [unverified] https://docs.kernel.org/arch/arm/uefi.html (read 2026-11-21)

### Dual boot, slots and placement (2.5, 3.9)

- **G12-1** Phone #1 stock -4-2 backup: every slot-B GPT partition is all zeros; `misc` marks slot B bootable (priority 6, 7 tries). Extended to four more phones by PM-8 and PM-13. [confirmed] `../backups/` (phone #1 stock archive, 2026-11-18)
- **G12-2** Boot LU B holds an older preloader; the copy script skips the preloader; whether a slot switch flips the boot LU is unknown. [contested] https://github.com/jimmielin/android_device_motorola_mt6835-common/blob/lineage-23.2/tools/copy-firmware-to-other-slot.sh (2026-11-16)
- **G12-3** The preloader has strings for a slot lk-validity check with rollback; not disassembled. [confirmed] `../backups/` (same archive)
- **G12-4** Stock lk has a slot-switch guard that can be forced within 30 s, and skips the retry decrement for a slot that has booted successfully. [confirmed] `../tools/locked/` (stock -4-2 zip, `lk.img`)
- **G12-5** A Motorola Dimensity 7300 phone went dark after its owner overrode that warning; a service centre named a soldered programmer as the only fix. [contested] https://web.archive.org/web/20261007214046/https://xdaforums.com/t/motorola-g100-pro-motorola-g86-5g-soft-brick-after-switching-to-empty-slot-b-need-test-point-location.4803154/ (2026-10-02)
- **G12-9** MediaTek lk2 keeps A/B state in `misc` at offset 2048 with 7 retries; Qualcomm-based slot tools do not apply. [unverified] https://github.com/Gigaset-dev/lk2/blob/ab107ff351cb5550ee2aa92b0b7bc6ac0089befc/platform/mediatek/common/bootctrl/3/bootctrl_api.c (date unknown)
- **G12-10** On a MediaTek tablet with a GSI, the retry count fell on every boot and switching slots cleared a manual success mark. [unverified] https://github.com/sethforprivacy/dc1-lineage-gsi/issues/10 (2026-09-27)
- **G12-11** `super` holds groups `main_a` and `main_b`; `_b` partitions are zero-size except `system_b`; about 4358 MiB unallocated. [unverified] `../backups/` (same archive)
- **G12-12** AOSP fastbootd creates logical partitions on unlocked devices; AOSP's updater removes only groups with the target slot suffix. [unverified] https://android.googlesource.com/platform/system/update_engine/+/refs/heads/main/aosp/dynamic_partition_utils.cc (read 2026-11-21)
- **G12-13** The -4-2 flashfile writes all `super` chunks, targets slot A only, and erases `userdata` and `metadata`. [unverified] `../tools/locked/` (stock -4-2 zip, `flashfile.xml`)
- **G12-14** Comparable projects support a microSD root by design; no MT6835 SD-root report found. [unverified] https://github.com/Dodaskot/a22x-mainline/blob/HEAD/docs/BUILDING.md (2026-11-04)
- **G12-15** No `init_boot`-level chooser exists for GKI devices; the nearest precedent execs the renamed Android init after unmounting. [unverified] https://github.com/Android-Boot-Manager/ABM-init/blob/HEAD/main.c (2023-12)
- **G12-16** The owner's archived forum threads contain one report of an OTA staging -4-3 into slot B. [unverified] `sources/uscardforum-moto-g-power-2026-threads.md` (2026-11-15)

### KVM and GenieZone (2.6, 3.7)

- **G15-1** `gz.img` is a GenieZone EL2 hypervisor that launches Linux as a guest; static strings only. [confirmed] `../tools/locked/` (stock -4-2 zip, `gz.img`)
- **G15-2** The GenieZone loader is in the `bl2_ext` sub-image of `lk.img`, not in the preloader. [confirmed] `../tools/locked/` (stock -4-2 zip, `lk.img`)
- **G15-3** On MediaTek phones that load GenieZone, lk and the kernel run at EL1 and KVM cannot initialise; documented hands-on for one MT6833 phone. [contested] https://raw.githubusercontent.com/BreezeExceed/camellian-linux/master/docs/KERNEL_EL2.md (2026-08-30)
- **G15-4** KVM init returns `-ENODEV` when the kernel was not entered at EL2. [confirmed] https://github.com/MotorolaMobilityLLC/kernel-mtk/blob/MMI-W1WN36.18-114/arch/arm64/kvm/arm.c (tag source)
- **G15-5** No gzvm module in either vegas module set; only Trusty/MTEE client modules. [unverified] `../tools/locked/` (stock -4-2 zip)
- **G15-6** android13-5.15 has no GenieZone guest driver; it first appears in android14-6.1. [unverified] https://android.googlesource.com/kernel/common/+/refs/heads/android13-5.15/drivers/virt/ (read 2026-11-21)
- **G15-8** AVF is not functional on stock -4-2: disabled-variant APEX, no hypervisor properties. [confirmed] `../tools/locked/` (stock -4-2 zip, `super`)
- **G15-11** A GenieZone-disable tool is marked verified only for the GPT method on MT6833 and MT6893; MT6835 not listed. [unverified] https://raw.githubusercontent.com/jsbsbxjxh66/mtk-soc-disable-geniezone/main/README.md (2026-08-12)
- **G15-12** The same tool documents boot failures and co-processor watchdog crashes after removing GenieZone on `bl2_ext` platforms. [unverified] same URL (2026-08-12)
- **G15-13** On an MT6833 phone, a patched and re-signed `tee.img` boots the kernel at EL2 and `/dev/kvm` appears. [unverified] https://raw.githubusercontent.com/BreezeExceed/camellian-linux/master/docs/KERNEL_EL2.md (2026-11-05)

### Plain Linux on the vendor kernel: connectivity, display, modem, charging (3.4, 3.10)

- **G23-1** Moto Pad port: Wi-Fi and Bluetooth working through MediaTek's Android helpers in a chroot with a property shim. [confirmed] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/README.md (2026-11-10)
- **G23-2** Its Wi-Fi script runs exactly two Android executables and starts no binder service manager. [confirmed] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/pad-wifi-start (2026-11-10)
- **G23-3** The service managers and allocator HAL there are for the GPU path only. [unverified] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/config/android-units/pad-android.target (2026-11-10)
- **G23-4** Bluetooth there is a bridge between `/dev/stpbt` and `/dev/vhci`. [unverified] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/pad-bt-bridge.py (2026-11-10)
- **G23-5** The vendor `mediatek-drm` works for plain KMS clients only on the legacy ioctl subset. [unverified] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/wlroots-pad/include/backend/pad.h (2026-11-10)
- **G23-6** Plane, cursor, gamma, property and CRTC-disable requests oops the driver; an Xorg shim hides them. [unverified] https://github.com/Mattcabrices/moto-pad-2026-arch-linux/blob/a3d672c5967cbf39690bd77207ddb9896116e626/tools/src/noplanes.c (2026-11-10)
- **G23-7** Stock vegas has the same connectivity modules and the same `wmt_launcher` command line. [confirmed] `../tools/locked/` (stock -4-2 zip, vendor and `vendor_dlkm`; read 2026-11-21)
- **G23-8** vegas lists `connsys_wifi` and `connsys_bt` as raw partitions and has no ROM-patch files in `/vendor/firmware`. [unverified] `../tools/locked/` (stock -4-2 zip)
- **G23-9** a22x (MT6833) runs vendor WMT and gen4m with Python replacements for both helpers and its own Bluetooth driver. [confirmed] https://gitlab.com/pessdres/a22x-mainline/-/raw/main/conn/A22X-CHANGES.md (2026-10-12)
- **G23-10** Motorola's connectivity source defines the same launcher ioctls and handles 0x6835 with 0x6833. [unverified] https://github.com/MotorolaMobilityLLC/vendor-mediatek-kernel_modules-connectivity-common/blob/MMI-W1WN36.18-114/common_main/linux/wmt_dev.c (2025-01-18)
- **G23-11** Wi-Fi NVRAM reaches gen4m through a prefixed write to `/dev/wmtWifi`, done without Android on MT6878. [unverified] https://github.com/rajmahavir/cmf-mainline/blob/faea34bd8aa6fb396a9730aeffd3542d9561b3d7/tools/run-radio-test.sh (2026-11-17)
- **G23-14** Volla Plinius (MT6878) fork self-reports Wi-Fi, data, SMS, Bluetooth and calls with an out-of-tree CCCI driver and its own modem daemon; single author. [contested] https://github.com/karagos01/plinius-mainline (2026-11-20)
- **G23-15** An MT6895 project re-implements the modem owner against vendor-style eccci nodes and calls itself not validated. [unverified] https://github.com/MT6895-Mainline/mtk-ccci-userspace/blob/f6147b10cf7ef95932674506fbdfb7f3d67a1067/README.md (2026-10-02)
- **G23-16** No project runs a MediaTek modem from plain Linux on a vendor 5.15 kernel; a22x has no registration. [unverified] https://gitlab.com/pessdres/a22x-mainline/-/raw/main/docs/MODEM-VALIDATION-20261103.md (2026-11-03)
- **HW-12** Original "held 57-60%" refuted. Corrected: writing "0 1" switched charging off; the battery read 97-99% for about 11 hours; the 57-60% band was never observed; input throttling did not stop charging. [contested] `../ksu-modules/README.md` (2026-11-18)
- **HW-13** In MediaTek's 5.15 vendor charger source, the proc node's second field disables or enables the charger in the kernel. [unverified] https://nest-open-source.googlesource.com/manifest_repos/kernel_device_modules-5.15/+/refs/heads/main/drivers/power/supply/mtk_charger.c (date unknown)

### Pass 2: what lk accepts to flash and to boot (2.3, 2.4)

All LG claims that cite `lk.img` are static reading of the `lk` sub-image of the stock -4-2 `lk.img`, disassembled on 2026-11-21. None was run on a phone.

- **LG-1** "Preflash validation failed" has exactly one code reference, in a validator that lk registers before the fastboot `flash` command and that calls a partition-name dispatcher. The base-build lk has the same code; the -4-3 lk was not checked. [confirmed] `../tools/locked/` (stock -4-2 zip, `lk.img`; image dated 2026-04-16)
- **LG-2** The dispatcher sends only `boot`, `vendor_boot` and `init_boot` to an AVB hash check. In the unlocked state that check passes an image with no AVB footer and an image whose hash does not match the vbmeta descriptor. Other footer-present failures still reject. [confirmed] `../tools/locked/` (same image)
- **LG-3** Even when unlocked, the hash check rejects a malformed or oversized footer, a missing hash descriptor for the partition, and a descriptor `image_size` larger than the new image's footer `vbmeta_offset`. Verifiers agree the checks exist; they disagree on whether the size comparison uses the on-device vbmeta or the image's own, and one found the cited offsets mis-transcribed. [contested] `../tools/locked/` (same image)
- **LG-4** The owner's KernelSU `init_boot` for phone #1 keeps an AVB footer at 3592192 bytes, above the stock descriptor size of 3096576; its hash does not match; it was flashed through bootloader fastboot in the unlocked state under the patched unlock lk and booted. "Stock vbmeta, no custom key" is inferred from the notes, not read back. One verifier rejects "a hash mismatch is tolerated when unlocked" as a general rule; one objects to the unstated lk variant and the inferred vbmeta state. [contested] `../backups/` (phone #1 KernelSU `init_boot` image, 2026-11-18) and owner notes
- **LG-5** Flashing vbmeta in the unlocked state: a failed signature check, an untrusted key and a lower rollback index are logged and accepted, and the function returns without parsing descriptors. A vbmeta signed with any key is predicted to pass on an unlocked -4-2 unit with no `avb_custom_key`, provided the `sp` partition is readable. The original sentence "rejects only an image whose descriptors cannot be parsed" was corrected by one verifier. [contested] `../tools/locked/` (same image)
- **LG-6** Original "release-key vbmeta and images all accepted with no custom key" refuted. Corrected: on one unlocked XT2617V on -4-3, a self-built LineageOS 23.2 userdebug test-keys build (vbmeta signed with the public AOSP test key, rollback index 7) was accepted in the order vbmeta, vbmeta_system, boot, init_boot, vendor_boot, dtbo, and booted in orange state, with `avb_custom_key: not found` listed. Acceptance was conditional (a stale `boot_a` was rejected earlier; a Magisk `init_boot` was written with dd), and kernel, DTB and dtbo payload were stock. Supersedes X-FERG, the pass-1 critic reading of the same log, together with LG-13 and RS-11. [contested] https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/5b14ca912a/ACTIONS-LOG.md (2026-11-20, events of 2026-11-18)
- **LG-7** A guide for -4-2 names an lk address as an AVB gate that runs even when unlocked and passes it with `avb_custom_key`. In the -4-2 lk that address is MediaTek image authentication, called only for the firmware partitions in the certificate table and for the efuse image, never for `boot`, `init_boot` or `vendor_boot`. The guide's Magisk rejection is not explained by static reading. [contested] https://github.com/jesussaves-dev/moto-g-power-2026-root/blob/daf8192a7f/README.md (2026-11-13)
- **LG-8** The vbmeta flags for disabled verification do not bypass the per-image flash check. [unverified] `../tools/locked/` (same image)
- **LG-9** `dtbo` is checked against lk's MediaTek certificate table, not by AVB; an image that fails passes only if it is an Android sparse image; an unsigned raw dtbo is predicted to be rejected. [unverified] `../tools/locked/` (same image)
- **LG-10** `fastboot boot` is not implemented: the command-table entry points to a stub that prints "command is not implemented!". No hook or `oem` subcommand provides a RAM boot. The same stub is in the base-build lk and in the owner's patched lk images. The identical message is reported hands-on on an unlocked Motorola Edge 60 Fusion (2025-09), and a near-identical one on a Moto G54 5G (2025-11), both by analogy. [confirmed] `../tools/locked/` (same image, plus the patched lk images in the same directory)
- **LG-11** lk's kernel decompressor recognises only gzip and lz4-legacy and panics otherwise. [unverified] `../tools/locked/` (same image)
- **LG-12** At boot, lk verifies the slot with the allow-verification-error flag when unlocked, ignores the result and skips the rollback-index update. [unverified] `../tools/locked/` (same image)
- **LG-13** The -4-3 install log attributes a slot-A boot failure, with fallback to slot B after about 200 seconds, to vbmeta rollback index 5 against a device at 7; that slot also mixed -4-2 and -4-3 images. The same author's "Preflash validation failed" on `boot_a` came from flashing a stale -4-2 boot image against -4-3 descriptors. [unverified] https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/5b14ca912a/ACTIONS-LOG.md (2026-11-20)
- **LG-14** Flashing or erasing `avb_custom_key` is allowed when unlocked and refused when locked. [unverified] `../tools/locked/` (same image)
- **LG-15** The owner's unlock lk and route-D lk differ from stock -4-2 only at a few short ranges outside the validator, the hash-check code and the boot AVB path. [unverified] `../vegas-freedom/` and `../tools/locked/` (compared 2026-11-21)
- **LG-16** Stock -4-2 vbmeta: rollback index 5, flags 0, hash descriptors for `boot` (21549056 bytes), `dtbo` (377808), `init_boot` (3096576) and `vendor_boot` (30642176); the footer vbmeta in each of those images is unsigned. [unverified] `../tools/locked/` (stock -4-2 zip, `vbmeta.img`)

### Pass 2: rescue and debug channels (2.7)

- **RS-1** mtkclient's chip table has an entry for hardware code 0x1209 (MT6835) with XML download-agent mode and no BROM payload, loader or exploit fields; no MT6835 payload file exists. The vegas hardware code has not been read. [confirmed] https://raw.githubusercontent.com/bkerler/mtkclient/main/mtkclient/config/brom_config.py (file last changed 2026-08-15, fetched 2026-11-21)
- **RS-2** None of the download agents bundled with mtkclient 2.1.4 covers 0x1209; unchanged on main on 2026-11-20. Reported on a Vivo phone; bundled agents only. [confirmed] https://github.com/bkerler/mtkclient/issues/435 (2026-11-03)
- **RS-3** On a Motorola XT2513-1 (MT6835), mtkclient reached the preloader (secure boot on, SLA off, DAA on), had no download agent and uploaded nothing; no Motorola MT6835 agent was offered; closed as stale. [confirmed] https://github.com/bkerler/mtkclient/issues/182 (2026-04-08)
- **RS-4** A Motorola XT2515-2 owner and a moto g 2025 owner reported "da signature fail", with no logs; closed as stale. [contested] https://github.com/bkerler/mtkclient/issues/201 (2026-04-28)
- **RS-5** For an MT6835 phone with DAA on, the mtkclient maintainer says authentication or an engineering preloader is needed. [unverified] https://github.com/bkerler/mtkclient/issues/217 (2026-06-09)
- **RS-6** A community summary says Motorola disables BROM USB download by e-fuse on newer MediaTek devices and that the stock agents only flash the bootloader. Hands-on reports show the block on some Motorola models and not on others; none is MT6835. The same page says Motorola validates the unlock state in `seccfg` against a value stored in RPMB (quoted by the source verifier; not separately verified). [contested] https://github.com/zenfyrdev/bootloader-unlock-wall-of-shame/blob/main/brands/motorola/README.md (file last changed 2026-10-31)
- **RS-7** The stock -4-2 lk contains Motorola code that checks and re-blows a BROM-disable fuse, and an `oem ssm_test` option that blows it and disables blankflash. The owner's patched lk images keep it. Whether the fuse is blown on the owner's phones was not observed. [confirmed] `../tools/locked/` (stock -4-2 zip, `lk.img`; firmware dated 2026-04-16, read 2026-11-21)
- **RS-8** Original "opens a tool window on every boot and verifies any DA" narrowed. Corrected: on one stock locked unit the preloader opened a USB tool-handshake window on normal boots with a cable and skipped it with volume-down held; it contains download-agent signature-check code and a branch that disables it; enforcement on these units is expected and unverified. [contested] `../backups/` (phone #1 stock archive, `expdb` and preloader, 2026-11-18)
- **RS-9** Original "the rescue-tool page describes only fastboot identification" refuted. Corrected: the -4-2 zip is fastboot-only with no download agent, auth or scatter file and writes `efuse.img` to `efuseBackup`; Motorola's generic help page describes no download-mode procedure; for the moto g23 the rescue tool was found to download a separate flash tool with a download agent; unknown for vegas. [contested] https://help.motorola.com/hc/apps/service/rsa/58/en-us/CGT1908243440.html (undated, read 2026-11-21) and `../tools/locked/` (stock -4-2 zip, 2026-04-16)
- **RS-10** The Moto Pad 2026 BROM path uses a download agent and auth file from a Lenovo ZUI ROM that the rescue tool downloaded for that tablet; the project states its recovery use was never exercised. [unverified] https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/52-wsl-printgpt.sh (2026-11)
- **RS-11** In the vegas26 incident where a phone "dropped off USB entirely", the phone reappeared after a replug and was repaired with fastboot writes. [unverified] https://github.com/fergatronanator/vegas26-lineageos-handoff/blob/HEAD/ACTIONS-LOG.md (2026-11-18)
- **RS-12** The stock kernel has RAM pstore with console and pmsg and reboots at once on panic; the DTB has no ramoops node; lk reserves a pstore region and passes `ramoops.*` arguments. [unverified] `../tools/locked/` (stock -4-2 zip, `boot.img` config and `lk.img` strings; read 2026-11-21)
- **RS-13** On a stock phone `expdb` holds readable preloader and lk logs including the A/B retry state; `pstore` was all zeros in the same backup. [unverified] `../backups/` (phone #1 stock archive, 2026-11-18)
- **RS-14** Stock lk has `oem config` entries, kept in the `utags` partition by its strings, for a kernel console and command-line additions, an earlycon template, a log-dump command and a bootloader-logs menu item; untested on an unlocked unit. [unverified] `../tools/locked/` (stock -4-2 zip, `lk.img` strings and `flashfile.xml`; read 2026-11-21)
- **RS-15** On the moto g power 2025 (XT2515-1, MT6835, stock 5.15.180 kernel), `fastboot boot` did not boot from RAM, a native initramfs gave a root shell over a USB serial gadget, and returning to fastboot needed `reboot-mode.ko` and `syscon-reboot-mode.ko` loaded. [unverified] https://github.com/zoan37/moto-g-power-2025-omarchy/blob/HEAD/notes/linux-bringup-20261006.md (2026-10-06)
- **RS-16** The Moto Pad Arch port's initramfs holds at a USB network console when the previous boot did not finish, and saves the pstore files of that boot. [unverified] https://raw.githubusercontent.com/Mattcabrices/moto-pad-2026-arch-linux/main/scripts/archinit (2026-11)

### Pass 2: partition map and fastboot behaviour (2.5, 6)

- **PM-1** The stock -4-2 flashfile writes the GPT and preloader, `lk_a` and the slot-A firmware, `efuse.img` to `efuseBackup`, `init_boot_a`, `boot_a`, `vendor_boot_a` and 26 `super` chunks; it erases `nvdata`, `userdata`, `metadata` and `debug_token`; every slotted write targets slot A; there is no step for `tzapp`, `connsys_wifi` or `connsys_gnss`. [confirmed] `../tools/locked/` (stock -4-2 zip, `flashfile.xml`; read 2026-11-21)
- **PM-2** The servicefile equals the flashfile minus the `efuseBackup` write and the `userdata` and `metadata` erases; it still writes the GPT, preloader and lk and erases `nvdata`. [confirmed] `../tools/locked/` (stock -4-2 zip, `servicefile.xml`; read 2026-11-21)
- **PM-3** Original "`tzapp_a` is device-unique and can be restored only from the phone's own backup" refuted. Corrected: no stock zip contains a `tzapp` image; in the backups of all eight phones `tzapp_a` holds the same 34 trustlet files, identical to a directory in the stock vendor image, and differs only in filesystem metadata; stock Android fills it after boot; `tzapp_b` is zero; rebuild and re-population are untested. [contested] https://github.com/jimmielin/android_device_motorola_mt6835-common/blob/lineage-23.2/tools/copy-firmware-to-other-slot.sh (2026-11-16) and `../backups/`, `../tools/locked/` (2026-11-18 to 2026-11-20)
- **PM-4** Original "every slot-A firmware image is identical on all four phones" refuted. Corrected: the identity, calibration and security partitions differ on every phone; `preloader_a`, `efuse`, `efuseBackup` and the GPT partition GUIDs come in two variants that follow each phone's firmware history; every other slot-A image is identical; several "identical" partitions are simply all zeros; hash differences alone do not prove device-unique content for `super`, `metadata`, `para` and the log partitions. Verifier note: across the hash lists of all eight archives `preloader_a` splits six phones against two; `preloader_b` is the same build on the four phones compared; `misc`, `frp` and `proinfo` are identical on the four (`proinfo` is all zeros). [contested] `../vegas-freedom/backups/` (four backups, 2026-11-20) and `../backups/` (hash lists of all eight archives)
- **PM-5** Original "locked cid-50 phones accepted the stock flash" corrected on scope. Corrected: on two bootloader-locked units reporting cid 0x0033, running the community rollback lk, bootloader fastboot returned OKAY for all 26 stock `super` chunks and for the erases of `userdata`, `metadata` and `debug_token` in four runs; lk printed that it skips the `efuseBackup` write; nothing was read back; says nothing about unsigned images or an unlocked unit. [contested] `../logs/` (downgrade and upgrade logs, 2026-11-20)
- **PM-6** On unlocked -4-3 units, two install flows flash vbmeta from bootloader fastboot first and individual logical partitions in fastbootd; "fastbootd cannot see vbmeta" is one author's unreproduced report; the stock flashfile writes `super` whole from the bootloader. [contested] https://github.com/qfertig/vegas26-gsi (2026-11-19)
- **PM-7** Original "being unlocked does not lift image validation in bootloader fastboot" refuted. Corrected: on one unlocked -4-2 unit a Magisk 31.1 `init_boot_a` was rejected with "Preflash validation failed", fastbootd could not open `init_boot_a`, and dd from temp-rooted Android then worked; the cause was not established; the owner's KernelSU image was accepted on the same build. Supersedes X-PARS, the pass-1 entry for the same source. [contested] https://github.com/parsimo2010/moto-g-power-2026-straight-talk-wifi-root-guide/blob/main/GUIDE.md (2026-11-14)
- **PM-8** Original "slot B is still a valid fallback target" refuted. Corrected: `misc` is byte-identical on four backups and holds a CRC-valid boot-control structure starting at offset 2048 (magic at 2052); slot A priority 7, tries 1, successful 1; slot B priority 6, tries 7, successful 0; slot B is bootable by metadata only; preloader and lk contain their own slot-image validity checks; fallback behaviour is untested. [contested] `../vegas-freedom/backups/` (2026-11-20)
- **PM-9** The stock -4-2 lk contains A/B strings for a set-active guard, retry counting, a mode exemption and a no-bootable-slot error. String evidence only. [unverified] `../tools/locked/` (stock -4-2 zip, `lk.img`; read 2026-11-21)
- **PM-10** The stock lk contains Motorola code for disabling BROM download mode by e-fuse; the fuse state on the owner's units is unknown. Same finding as RS-7. [unverified] `../tools/locked/` (same image)
- **PM-11** The vegas26 tree author says only `boot`, `init_boot`, `vendor_boot`, `dtbo`, the vbmeta partitions and the logical partitions in `super` should ever be flashed, and never preloader, lk, tee, gz or md1img. [unverified] https://github.com/jimmielin/android_device_motorola_vegas26 (2026-11, read 2026-11-21)
- **PM-12** The stock lk enforces anti-rollback on bootloader images; the owner's downgrade from -4-3 worked only after a community rollback lk was flashed. [unverified] `../tools/locked/` (stock -4-2 zip, signing info; read 2026-11-21)
- **PM-13** On four backups every slot-B GPT partition is all zeros; `connsys_wifi` and `connsys_gnss` are empty on both slots; `preloader_b` is populated and differs from LU A. [unverified] `../vegas-freedom/backups/` (2026-11-20)
- **PM-14** Erasing `userdata` and `metadata` in fastboot and then booting stock Android works on vegas; a GSI author reports the same erase bootloops a GSI on its second boot unless data is wiped from stock recovery. [unverified] https://github.com/qfertig/vegas26-gsi (2026-11-19)
- **PM-15** For a Samsung MT6835 phone, forum moderators report MT6835 unsupported by mtkclient and SP Flash Tool, with BROM needing a test point and a paid tool. [unverified] https://www.hovatek.com/forum/post-245958.html (2025-01-16)
- **PM-16** AOSP requires the bootloader to refuse flashing dynamic partitions; Motorola's lk accepts a whole-`super` flash. [unverified] https://source.android.com/docs/core/architecture/bootloader/fastbootd (read 2026-11-21)

### Pass 2: coexistence with Android (3.9, 3.11, 3.12)

- **CX-1** Original "one kABI patch covers kernels 5.4 to 6.6" refuted. Corrected: Droidspaces documents that SYSVIPC, IPC_NS and POSIX_MQUEUE shift the GKI ABI and bootloop the phone without its patches; for 5.4 to 6.6 it ships three alternative SYSVIPC patches using different `task_struct` padding slots and says to try the alternatives if the device bootloops; on 5.15 only the SYSVIPC fields are moved. Not tested on vegas. The only MediaTek 5.15 report is the maintainer-reported Galaxy A25 row (CX-5), which uses slots 6-8; the project does not guarantee that a patched kernel boots. [contested] https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/Kernel-Configuration.md (2026-11-07)
- **CX-2** CFS_BANDWIDTH and CGROUP_PIDS break the KMI on GKI kernels up to android15-6.6 and no patch covers them; in the tree at the vegas commit CGROUP_PIDS adds a cgroup subsystem and resizes arrays in `struct cgroup` and `struct css_set`. [confirmed] same URL (2026-11-07)
- **CX-3** In the config embedded in the stock -4-2 kernel, as in upstream `gki_defconfig` at 9b2308ac0ad6, PID_NS and FHANDLE are not set (USER_NS also not set), while CGROUP_BPF, ASHMEM, MEMFD_ASHMEM_SHIM, binder and binderfs are set. PID_NS is built-in only, so root or a module cannot add it. [confirmed] https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/arch/arm64/configs/gki_defconfig (commit dated 2025-11-30) and `../tools/locked/` (stock -4-2 zip, `boot.img`)
- **CX-4** The cgroup device BPF program type is compiled under CGROUP_BPF, so cgroup-v2 device control does not need CGROUP_DEVICE. [unverified] https://android.googlesource.com/kernel/common/+/9b2308ac0ad616788fb57ba688aa07f0ff221355/include/linux/bpf_types.h (commit dated 2025-11-30)
- **CX-5** The Droidspaces device list has a maintainer-reported row for the Galaxy A25 5G SM-A253Z (MT6835, kernel 5.15.180, Android 16): status Working, GPU acceleration none; its kernel replaces only `boot.img` and puts SYSVIPC state in padding slots 6-8. [confirmed] https://raw.githubusercontent.com/ravindu644/Droidspaces-OSS/master/Documentation/community-supported-devices.md (2026-11-07; row added 2026-05-12)
- **CX-6** A recipe for the REDMAGIC 8S Pro+ (SM8550, android13-5.15) builds from the phone's own config plus the kABI patch, reports 0 CRC mismatches across 374 vendor modules, replaces only the kernel in `boot`, keeps the KernelSU LKM in `init_boot`, and reports Debian 13 with systemd running. Single commit, self-reported, described by its author as fully AI-built. [confirmed] https://github.com/fkun1754/redmagic-nx729j-droidspaces-kernel (2026-10-14)
- **CX-7** AOSP's base config for Android 13 on 5.15 requires SYSVIPC unset; the Samsung MT6835 kernel maintainer removed Android's "internal problem" dialog by making `/proc/config.gz` report the stock config. [unverified] https://android.googlesource.com/kernel/configs/+/refs/heads/main/t/android-5.15/android-base.config (2026-04-20)
- **CX-8** systemd's README lists FHANDLE as required; the REDMAGIC recipe does not add it and reports systemd running, so it is probably not blocking in a container. [unverified] https://raw.githubusercontent.com/systemd/systemd/main/README (read 2026-11-21)
- **CX-9** Waydroid maps host `ro.vndk.version` 33 to HALIUM_13, binds the host vendor and hwbinder in that mode and uses the host gralloc if found; with no host gralloc and no DRM render node it falls back to software rendering. For a non-Halium vendor-kernel vegas, software rendering is inferred from code and firmware, on a rebuilt kernel only. [contested] https://github.com/waydroid/waydroid/blob/main/tools/helpers/lxc.py (2026-11-15)
- **CX-10** The official Waydroid image server serves a HALIUM_13 arm64 vendor image on LineageOS 20, newest build 2026-10-22; HALIUM_14, 15 and 16 return 404. A version match for a vendor at 33, not a vegas result. [contested] https://ota.waydro.id/vendor/waydroid_arm64/HALIUM_13.json (2026-10-22)
- **CX-11** Waydroid on MediaTek Ubuntu Touch ports: working on MT6769 (Halium 11), partly on MT6789 (Halium 12), not working on MT6878 (Halium 14); no MT6835 report. [unverified] https://gitlab.com/ubports/infrastructure/devices.ubuntu-touch.io/-/raw/main/data/devices/ansuz/releases/noble.md (2026-06-24)
- **CX-12** Waydroid allocates its binder nodes through binderfs and falls back to memfd when ashmem is absent. [unverified] https://github.com/waydroid/waydroid/blob/main/tools/helpers/lxc.py (2026-11-15)
- **CX-13** FuriOS bootman on the FuriPhone FLX1 (MT6877, kernel 4.19, boot header v2) switches between Halium-based Linux systems by writing the chosen system's `boot.img` and `dtbo.img` onto `boot_a` and `dtbo_a` and rebooting; no slot B, no Android entry; state kept in `vendor_boot_a`, reformatted as ext4, which suggests that phone does not boot from `vendor_boot` (inference, not verified). On vegas (header v4) the swap set would have to include `init_boot_a` and/or `vendor_boot_a`, or all entries must share them. A precedent for the idea on vegas, not for the recipe. [contested] https://github.com/FuriLabs/bootman/blob/HEAD/main.c (2025-08-23)
- **CX-14** The FuriLabs Halium initramfs runs bootman only on unencrypted installs and keeps its state in `vendor_boot_a` on the FLX1. [unverified] https://github.com/FuriLabs/initramfs-tools-halium/blob/forky/scripts/halium (2026-11-17)
- **CX-15** The Halium initramfs avoids its "android" boot mode on Android 8 and later and reboots instead, so it cannot act as an Android-or-Linux chooser. [unverified] same URL (2026-11-17)
- **CX-16** In the Halium initramfs the data partition defaults to `userdata`, can be overridden with `datapart=`, and is mounted before `super` is parsed. [unverified] https://github.com/halium/initramfs-tools-halium/blob/dynparts-lvm/scripts/halium (2026-07-13)
## 9. Results: route B, offline (2026-11-21)

Tooling and procedure: `linux/README.md`, `scripts/linux_b.sh`. Experiment unit: phone #5. Nothing below ran on a phone.

- `system_dlkm` on -4-2 contains no kernel modules (only `etc/`). The Google-signed-module concern of section 2.1 does not apply to vegas. [hands-on, firmware]
- Kernel source: ACK `common` at tag `android13-5.15-2025-05_r14` = 9b2308ac0ad6, built with the prebuilt clang r450784e (the stock kernel's toolchain), full LTO (needs about 20+ GB RAM to link).
- Control build (`gki_defconfig`): the config equals the stock embedded config except for TRIM_UNUSED_KSYMS and its symbol list. Module CRC gate: 399 stock vendor modules (202 vendor-ramdisk + 197 `vendor_dlkm`), 18,683 kernel imports, **0 mismatch, 0 missing**. [hands-on, offline; closes the open question in 7.1 "Does a kernel actually built at 9b2308ac0ad6 produce CRCs matching all imported symbols?"]
- Route-B build (+ DEVTMPFS, DEVTMPFS_MOUNT, FHANDLE, AUTOFS_FS, TMPFS_POSIX_ACL; - TRIM_UNUSED_KSYMS, - MODULE_SIG_PROTECT): same CRC result, 0/0. pahole over BTF against the control build: 0 structs changed or removed, 25 added; `task_struct`, `file`, `inode`, `super_block`, `sk_buff`, `net_device`, `device`, `module`, `cred` identical.
- The stock kernel's gzip stream is byte-reproducible with `gzip -9 -n`; the step-4a image therefore recompresses at level 6 so its hash really differs.
- Images built to section 2.4: `boot_4a` (stock kernel, footer at 21,557,248), `boot_4b` (rebuilt kernel, footer at 21,942,272), probe `init_boot` (padded, footer at 3,096,576). The unlock lk regenerated from the zip's stock lk is byte-identical to #1's `914acfce…`.

## 10. Results: route B, hands-on on #5 (2026-11-22)

Verified on the phone, see `linux/README.md` for the table and `logs/<serial>/linux_b/` for the evidence.
- Unlock from end state D works (unlock lk + serial key). Putting the retail lk back on the unlocked phone keeps
  `flashing_unlocked` and removes Tracfone activation (community "Variant 2", now confirmed on our hardware).
- A Linux initramfs in `init_boot_a` boots on the stock and the rebuilt kernel: all 186 vendor-ramdisk modules load,
  USB NCM/ACM gadget, shell, and reboot-to-bootloader from Linux. Requirements found: ramdisk **lz4 legacy**, modules
  loaded in `modules.dep` order, devpts mounted, an extra `mdev -s` on the stock kernel.
- The rebuilt GKI (stock config + DEVTMPFS/FHANDLE/AUTOFS, no ksym trimming) boots stock Android with all 362
  modules and no module errors. The offline CRC + BTF gate predicted this correctly.
- `misc` boot-control never changed and no boot failed; slot B stayed untouched.

## 11. Results: part 2 and end state E on #5 (2026-11-22)

Evidence in `logs/<serial>/linux_b/p2/`. Runbook in `linux/README.md`. Each claim is marked.

**Boot chooser** (`linux/initramfs/chooser.c`, the `/init` of `init_boot_a`, layered over the base ramdisk):
- [verified] With no key the phone boots Android with KernelSU. A Vol-up **tap** after lk's orange screen (a 4 s
  window from about 0.33 s of kernel time) runs the Linux branch. Holding Vol-up through lk's screens enters lk
  fastboot, and a key held from before the keypad probe is never reported, so it has to be a tap.
- [verified] `mtk-kpd` must stay loaded: `rmmod` after the key window panicked with a CFI failure in the IRQ handler.
- [verified] Recovery and fastbootd boots have no `force_normal_boot`, and the chooser passes them straight to
  Android.
- [verified] The base ramdisk is kept byte-for-byte and the overlay is appended as a second lz4 cpio. The kernel
  unpacks both; cpio tools stop at the first TRAILER, so the build checks the two parts separately.
- [built, unverified on phone] The state-E variant puts the overlay on the **stock** init_boot ramdisk and execs
  stock first-stage init as `/init.next`. ksuinit already runs stock init from a renamed path, which suggests this
  works.

**Linux branch** (`init.linux`):
- [verified] 186/186 vendor-ramdisk modules load.
- [verified] `lpmap` builds dm-linear maps from super's LP metadata (the `linux` partition has 7 extents, matching
  `lptool.py`). `vendor_a`, `vendor_dlkm_a` and `system_a` are mapped read-only, and their erofs magic is correct.
- [verified] With an empty partition the branch falls back to a rescue telnet/ACM shell, which reboots to Android
  after 10 min unless `/stay` exists.
- [verified] Busybox here has no `blkid`, so the ext4 label is read from the superblock.

**Debian** (trixie arm64, a 3 GiB LP partition `linux` flashed from fastbootd as a sparse image):
- [verified] systemd reaches `running` with 0 failed units. SSH works over USB NCM (172.16.42.1), and no
  NV/userdata partition is mounted.
- [verified] `systemctl reboot` returns to Android.
- [verified] Shutdown stall: `serial-getty@ttyGS0`. Its autologin root shell blocks in `set_termios` because nothing
  on the Mac reads the ACM port (output never drains); it ignores SIGTERM and the tty close waits again, so 2 × the
  stop timeout (about 90 s at the default, 31 s at `DefaultTimeoutStopSec=15s`). Fix: the getty is no longer enabled
  (start it by hand when needed). With it disabled, Debian was off the network 12 s after `systemctl reboot` and
  Android `boot_completed` came 48 s after (2026-11-22, live change; image rebuild pending).
- [verified] The Mac can miss the DHCP lease when the USB link drops once at boot (it falls back to 169.254.x).
  IPv6 link-local still reaches the phone: `ping6 ff02::1%<if>`, then `ssh root@fe80::…%<if>`.
- [verified] `misc` boot-control is unchanged through every chooser, Linux and fastbootd boot. Only the BCB command
  string changed: fastbootd cleared a stale `bootonce-bootloader`.

**Battery and charging under Linux:**
- [verified] `battery/capacity` reads -1 in Linux. The gauge runs in **daemon mode** (`is_daemon_support = 1`): the
  SOC comes from the vendor userspace `fuelgauged`, which dlopens `libfgauge_gm30.so` and talks to the gauge driver
  over netlink protocol 26.
- [verified] The library keeps state in `/mnt/vendor/nvcfg/fg/{car_tune_value,old_fg_data}`.
  `fuelgauged_nvram` writes nvcfg and nvdata and is never run.
- [verified on #5] Vendor binaries run on Debian with Android's own linker: linker64,
  bionic and VNDK v33 (14 files copied from the running Android), plus the phone's `/linkerconfig/ld.config.txt`.
  Without that config, `liblog` binds the wrong `libc++` and linking fails. In the VM, `fuelgauged` reaches its
  netlink socket, and `wlan_assistant`/`wmt_loader` wait for their device nodes, not for Android properties.
- [verified] Moto's 80% cap acts through the `qpnp_adaptive_charge` module (`upper_limit`/`lower_limit`), which
  Android loads from vendor_dlkm. `/proc/mtk_battery_cmd/current_cmd` exists in Android; on #1, `"0 1"` stopped
  charging.
- [verified on #5, 2026-11-22] `vegas-fuelgauged` gives a real SOC: `capacity` 100 at 4458 mV (CV 4496 mV), the
  phone having sat at 100% in Android. [unverified] Tracking against Android over a discharge interval.
- [verified on #5] Charge control `/proc/mtk_battery_cmd/current_cmd`: `"0 0"` → Charging, about 270 mA at 100%;
  `"0 1"` → Not charging, 0 mA. `qpnp_adaptive_charge` is not needed and not loaded.
- [verified on #5] `vegas-fuelgauged` + `vegas-chargeguard` (the guard held charging off at 100% from boot):
  - 80/70% band; stop charging at 42 °C; power off at 55 °C, or at ≤5% while not charging
  - no valid SOC → charging off
  - the gauge state is seeded from a copy
  - `nvguard` refuses to start if any NV path is not on Debian's root

**Thermal:** [verified] The SoC/board/PMIC temperature modules load only from vendor_dlkm in Android.
`md_cooling_all` pulls in the modem stack and is excluded. [verified on #5] 48 thermal zones are live in Debian
without them (SoC/CPU about 28 °C, NTCs about 25 °C, battery 23 °C); `pmic_temp`, `board_temp`,
`thermal_generic_adc`, `charger_cooling`, `backlight_cooling`, `soc_temp_lvts` load cleanly (51 zones) and are in
`modules.list`. `vtskin_temp` zones read -274 °C (filled by Android's thermal HAL). **Gap:** the only kernel trip
is `soc_max` critical at 113.5 °C; throttling below that is Android userspace. A SoC-temperature CPU cap is to do.

**Display:** [verified on #5, 2026-11-22] `mediatek_drm` (loaded by the Linux branch) gives `/dev/dri/card0`,
connector `DSI-1` connected, 1080×2388 at 120/90/60/30 Hz, CRTC 60; backlight `/sys/class/leds/lcd-backlight`
(0–2047). `modetest -M mediatek -s 32@60:#2` showed colour bars on the panel. No fbdev/fbcon (GKI config), and no
GPU loaded in Debian yet (the Mali modules load only under Android today; the 2025 port loaded them from Linux,
see below), so a screen UI needs a KMS userspace drawn in software for now. [verified on #5, 2026-11-23] A Weston
pixman desktop on the DRM backend oopsed the kernel on its first atomic commit; see the next subsection.

**GPU and display UI options (researched 2026-11-23)**

Research and verify agents, plus a hands-on test on #5. No partition was written. The two reference ports in
`linux/work/ref/` are other people's reports on other devices: they are not verified on #5.

*Weston crash on #5:*
- [verified on #5, 2026-11-23] Weston 14.0.2 `--backend=drm --renderer=pixman`, desktop shell, scale 3, 60 Hz,
  started through seatd with `SEATD_VTBOUND=0` (needed because `CONFIG_VT` is unset). The kernel oopsed on Weston's
  first atomic commit at `mtk_drm_crtc_atomic_begin+0xb58`, and the phone rebooted to Android.
- [inference, from disassembly + Motorola source MMI-W1WN36.18-114 `mtk_drm_crtc.c` ~11974] The faulting code is
  the `need_recover` OVL-reset block. It walks the dual-pipe component array, which on MT6835 is `ZERO_SIZE_PTR`
  (0x10) because `dual_path_len` is 0. Two things must both hold: `priv->need_recover` is set (an OVL/DSI underrun
  IRQ sets it, a completed frame on CRTC 0 clears it), and an active CRTC has `is_dual_pipe`. The oops registers
  give CRTC index 1 (id 95), which goes dual pipe at 120 Hz / pixel clock above 241.5 MHz.
- Open: why CRTC 95 was active at all. [inference] One candidate is a phantom connector: the 2025 port saw a
  phantom connected `DP-1` with 4096x2160 modes that caused RDMA underflows until it was turned off
  (`linux/work/ref/moto-g-power-2025-omarchy/notes/direct-drm-latency-20261007.md`). Not checked on #5.
- Next test: boot with `drm.debug=0x14`, dump `/sys/kernel/debug/dri/0/state`, then Weston with the 2025 port's
  config: `--shell=kiosk`, `DSI-1` at 1080x2388@60, scale 1, `DP-1` off
  (`.../port/vegas/root/etc/xdg/weston/vegas.ini`, `.../port/vegas/root/usr/local/bin/vegas-desktop`).
- `WESTON_DISABLE_ATOMIC=1` alone is risky: Weston's legacy path does SETCRTC with fb=0 on unused CRTCs, and the
  Moto Pad shim says that request oopses mediatek-drm (`linux/work/ref/moto-pad-2026-arch-linux/tools/src/noplanes.c`).
- Fallback: patch the branch at module offset 0x762e4 to skip the block. [unverified] Whether a modified `.ko`
  loads on this kernel (module signing, see section 2).
- Sync before every display test: on the 2025 port, killing the DRM master (Weston) rebooted the phone within
  about 2 s and lost unsynced writes (same notes file).

*Touch:* [verified on #5, 2026-11-23] `modprobe ilitek_v3_mmi` (deps `mtk_disp_notify`, `spi_slave`,
`mediatek-drm`, `sensors_class`) registers `ILITEK_TDDI` (`ID_INPUT_TOUCHSCREEN`) and a "double-tap" input device.
The driver loads its firmware into the IC's RAM; it does not write the touch IC's flash.

*CPU rendering (pixman / llvmpipe):*
- [confirmed, report from the 2025 port] Weston 15.0.1 with pixman drove the real DSI output at 1080x2388 / 60 Hz
  (`.../moto-g-power-2025-omarchy/notes/native-omarchy-20261006.md`). No fps or latency was measured for it.
- [confirmed, report from the 2025 port] Hyprland on llvmpipe, direct DRM: about 105-130 ms per frame, about 95% of
  perf samples in llvmpipe JIT, unchanged by damage tracking, scale, `LP_PERF` or core pinning
  (`notes/direct-drm-latency-20261007.md`). CPU peaked near 380% (`notes/gpu-bringup-20261007.md`).
- [confirmed, report from the 2025 port] Foot commit to frame callback through nested Weston on llvmpipe: 114 ms
  at 30 Hz, 116 ms at 60 Hz, 68 ms at a 720x1592 target (`notes/phone-polish-20261007.md`).
- [confirmed, report from the 2025 port] DRM dumb buffers: write 6.7 GB/s, read 0.85 GB/s (2.5 GB/s cached)
  (`notes/direct-drm-latency-20261007.md`). [inference] A full 1080x2388 frame read back from scanout costs about
  12 ms, so a pixman compositor should draw into a cached shadow buffer and copy out.
- [confirmed, report from the 2025 port] Chrome on software: X.com scroll 29 fps with nearly all frames late,
  Wikipedia 71 fps; 2D canvas was faster on software than on any GPU path (`notes/chrome-scrolling-20261010.md`,
  `notes/gpu-bringup-20261007.md`).
- [confirmed] wlroots has a pixman renderer (`WLR_RENDERER=pixman`), and phoc passes it through
  (wlroots `docs/env_vars.md`). A phoc pixman crash (phoc issue 290) is closed and old.
- [confirmed] GTK 4.18 removed the old GL renderer. `GSK_RENDERER=cairo` remains with missing features, and
  llvmpipe is the other option (discourse.gnome.org t/28295). [inference] GTK3, Qt Widgets and foot need no GL;
  Qt Quick needs `QT_QUICK_BACKEND=software`.
- [confirmed] Chrome's automatic SwiftShader WebGL fallback is deprecated from Chrome 130;
  `--enable-unsafe-swiftshader` keeps it (blink-dev thread yhFguWS_3pM). Chrome's own software compositing is a
  separate path.
- [confirmed] Other software-fallback data points, none on MT6835: Weston pixman on i.MX8MP at 24-28% CPU vs 4-6%
  on GL (Toradex forum); plasma-systemmonitor about 70% CPU on llvmpipe (KDE bug 478974); Plasma Mobile "terribly
  slow" on software in 2018 (pmaports MR 79). [unverified] No public fps or power figures were found for software
  compositors on PinePhone Pro, Librem 5 or postmarketOS phones.
- [inference] Battery current from `vegas-fuelgauged` should let us measure the power cost; discharge accuracy is
  itself still [unverified] (Battery section above).

*Mali through patched Mesa + vendor kbase (the 2025 route):*
- [confirmed] Our kbase is Mali DDK r38p1 Valhall in Job Manager mode, vermagic `5.15.180-android13-8-g72da1abbd4bf`,
  sha256 `acc8b80d…e61e`, depends on ged, mtk_gpufreq_wrapper, sspm_v3, mtk_gpu_qos, trusted_mem, mtk_sec_heap,
  mtk_gpu_hal, irq-dbg, mrdump, aee_aed (`linux/work/stock/vendor_dlkm/lib/modules/mali_kbase_mt6835.ko`).
- [confirmed] On #5 these modules loaded only under Android at capture time: ged, gpueb, mali_kbase_mt6835,
  mtk_gpu_hal, mtk_gpu_qos, mtk_gpufreq_mt6835, mtk_gpufreq_wrapper
  (`logs/<serial>/linux_b/p2/capture2/android_only_mods.lst`). trusted_mem and mtk_sec_heap are shared with
  GenieZone's `gz_main_mod`.
- [confirmed, report from the 2025 port] On the moto g power 2025 (XT2515-1, also `vegas`, MT6835, stock r38p1
  kbase), loading a 62-module closure including `mcupm` and `fhctl` let Mali bind and create `/dev/mali0`
  (API 11.38, product 0x9093, 2 cores, 1.1 GHz). Hyprland then drove card0 DSI-1 at 1080x2388@120 through GBM
  scanout buffers (`notes/gpu-bringup-20261007.md`).
- [confirmed, report from the 2025 port] The Mesa is the RandomCoderOrg/mesa-gfxstream `tensor-g1` panfork
  (commit 4a03b179, Mesa 23.0.0-devel) plus local patches: JM deferred BO free (fixes DATA_INVALID/TILE_RANGE
  faults), native fence FDs, glibc `call_once`, an init double-free and a loader fd fix
  (`.../port/vegas/patches/`).
- [confirmed, report from the 2025 port] GPU direct KMS at 120 Hz: foot commit to frame callback 13-16 ms; Hyprland
  about 9% CPU. vendor mediatek-drm ignores `IN_FENCE_FD`, so the port waits on the CPU for the render fence before
  each commit (`AQ_KMS_CPU_FENCE_WAIT=1`, `notes/kms-fence-sync-20261011.md`).
- [confirmed, report from the 2025 port] ARM's glibc libmali r48 (personal PPA) ran off-screen on r38p1 kbase after
  a product-check binary patch, a 64→72-byte JM atom stride shim and `/dev/dma_heap/system` permissions. Experimental.
- [inference] It should transfer to vegas 2026, but not byte for byte: the 2025 kernel is `-00021-g46a5565a0982`
  with module vermagic `gd63125a6a58d`, ours `-00018-g9b2308ac0ad6` / `g72da1abbd4bf`. The JM uAPI and atom
  layout must be re-checked on #5.
- [confirmed] Upstream Mesa has no kbase backend (only panfrost, panthor and virtio kmod). The kbase-capable forks
  (panfork, panfork_offscreen_rootless) are frozen on old Mesa. [confirmed, author's report] apexspan-svg/mesa-panvk-mali-g57
  reports PanVK + Zink GL 3.2 on Dimensity 6300 (MT6835) over kbase, but for Android/Termux X11, not glibc.

*libhybris with the vendor Mali blob (the Moto Pad route):*
- [confirmed] Our vendor_a (-4-2) has `lib64/egl/mt6835/libGLES_mali.so` r38p1-01eac0 (sha256 `db3e8e80…aaa4`);
  it needs libged, libgpud, libgpu_aux, libladder, MTK gralloc libraries, mapper@4.0 and VNDK libraries.
  `build.prop` sets `ro.hardware.egl=meow` (MediaTek's MEOW wrapper), so libhybris must load the Mali blob directly
  or a property shim must answer `mali`. No GPU daemon exists in `/vendor/bin`; libged talks to `/proc/ged`.
  `ueventd.rc` sets `/dev/mali0` 0666.
- [confirmed] The vendor has `allocator@4.0-service-mediatek.mt6835`, mapper 4.0 and composer services.
- [confirmed] The Moto Pad 2026 port runs servicemanager, hwservicemanager, vndservicemanager and that allocator in a
  chroot under systemd, with an `LD_PRELOAD` property shim and a fake logd; no SurfaceFlinger or composer
  (`linux/work/ref/moto-pad-2026-arch-linux/config/android-units/`).
- [confirmed, report from the Moto Pad port] labwc on a patched wlroots 0.20 with a hybris renderer, Firefox and
  Chromium GPU-accelerated. Its libhybris needed an AHardwareBuffer gralloc backend, property hooks, a bionic TLS
  preload and EGL fixes for Android 16. [unverified] Those patches may not fit vegas unchanged: our vendor is API 33
  and ships a gralloc0 module.
- [confirmed, report from the Moto Pad port] mediatek-drm oopses there on plane enumeration, cursor, gamma, SETCRTC
  with no fb and property writes (DPMS on DSI); `noplanes.c` hides them. [unverified] on vegas; the 2025 vegas port's
  Hyprland atomic path did not hit these.
- [inference] Unverified estimate 2-5 weeks. The same property shim is the candidate Wi-Fi fix above.
- [confirmed] Droidian's wlroots fork has a hwcomposer backend; FuriLabs FLX1/FLX1s (Dimensity 900) use Halium +
  libhybris (press source). [unverified] Whether Droidian's phoc uses that backend.

*Panfrost kernel driver:*
- [confirmed] Stock config: `# CONFIG_DRM_PANFROST is not set`, no `CONFIG_DRM_SCHED`, `MODULE_SIG_PROTECT=y`
  (`linux/work/stock/config.stock`).
- [confirmed] Panfrost's Valhall-JM (G57) support landed in Linux 6.0 / Mesa 22.2, so 5.15 would need a backport.
  Mainline matches mt8183/8183b/8186/8188/8192/8370 and generic `arm,mali-valhall-jm`, nothing for mt6835.
  Panthor is for CSF GPUs only; the G57 is JM.
- [confirmed] Our DT Mali node `/soc/mali@13000000` (`mediatek,mali`, `arm,mali-valhall`) has no clocks,
  power-domains or mali-supply; those sit on the vendor `/soc/gpufreq` node (pd_mfg0..3, five clocks);
  `gpueb-support = 0` (`linux/work/stock/vendor_boot/dtb`, first DT only).
- [inference] So Panfrost here means out-of-tree `gpu-sched.ko` + `panfrost.ko` within the KMI's unprotected
  symbols, a DT node or shim (dtbo/vendor_boot are boot-chain partitions, section 6), and doing without mtk_gpufreq
  DVFS and thermal hooks. Weeks to months, and nobody has done it on MT6835.

Refuted during research: "software 30 vs GPU 9 fps canvas, 13-16 vs 114 ms on the same path" (canvas was 27 vs 9 in
that run, and 114 ms was nested Weston, not direct KMS); "libmali r48 needed only two changes" (three: product
patch, stride shim, dma_heap permissions); "PinePhone camera viewfinder is slow on GTK 4.18 software" (Megapixels
fails outright).

| Option | Needs | Effort | Risk | Expected result |
| --- | --- | --- | --- | --- |
| CPU rendering (pixman; llvmpipe only where GL is unavoidable), now | A KMS commit that does not oops (crash above); Weston kiosk or wlroots pixman; touch (works) | Days once the commit is safe | Kernel oops/reboot from mediatek-drm; heat and battery under CPU load; userspace only | 60 Hz for small updates [inference]; GL apps ~100 ms per frame; browsers usable but slow |
| Patched Mesa + kbase (2025 route) | GPU module closure loading in Debian; cross-built panfork Mesa + 2025 patches; JM uAPI re-check on #5 | About 2-5 days [inference] | GPU faults/hard resets; no GPU thermal cap; frozen Mesa 23.0 fork; single-author evidence | 120 Hz Hyprland, ~13-16 ms frames, low CPU (as on the 2025 phone) |
| libhybris + vendor blob (Moto Pad route) | Same GPU modules; Android system/vendor chroot with 4 daemons, property shim, fake logd; patched libhybris + wlroots | About 2-5 weeks [inference] | Bionic TLS vs glibc; blob changes with firmware updates; same mediatek-drm oopses | Vendor-driver GL/Vulkan, GPU browsers |
| Panfrost kernel driver | Valhall-JM backport to 5.15, out-of-tree modules within KMI, DT node, MFG power without mtk_gpufreq | Weeks to months | Boot-chain partition writes for a DT overlay; GPU power/voltage mistakes; no reference | Upstream-style Mesa, but not on this kernel in practice |

Recommendation: get a CPU-rendered UI first. The display path has to work anyway, and today's crash shows the
blocker is mediatek-drm's commit path, not rendering speed: find a KMS commit that leaves CRTC 95 alone (debug state
dump, then the 2025 kiosk config) and put Weston pixman or a wlroots pixman compositor on it. Then make GPU
acceleration the next project through the 2025 Mesa + kbase route. It writes no partition, it ran on the same SoC
and kbase version, and it is days of work rather than weeks. Keep libhybris as the fallback if kbase or that Mesa
fork does not work on #5, and leave Panfrost aside on this kernel.

**Wi-Fi:**
- [verified] `wmt_drv` and the Wi-Fi driver need ccci/ccmni symbols. [verified on #5] Loading them does not boot
  the modem: `ccmni0-20` appear but stay DOWN, ccci reports `md_state = 0`.
- [verified on #5] Up to the handshake it works: connadp/connfem/btif_drv/wmt_drv load, `wmt_loader` detects the
  A-die (MT6631) and creates `/dev/stpwmt`, `wmt_chrdev_wifi` + `wlan_drv_gen4m_6835` register, `wlan_assistant`
  pushes the NVRAM copy.
- [verified on #5] **Blocker:** `wmt_launcher` polls the Android property `vendor.connsys.driver.ready` every
  300 ms (set by `wmt_loader` through the property service on Android). Without its handshake, `echo 1 >
  /dev/wmtWifi` fails with `wmt_core_stp_init: no hif info!` and connsys loops on whole-chip reset (stopped with
  `echo 0`). Candidate fix, not tried: an `LD_PRELOAD` shim answering `property_get` for `vendor.connsys.*`.
  Wi-Fi is deferred; E is USB-only for now.
- [verified] `wlan_assistant` pushes `APCFG/APRDEB/WIFI` (plus `WIFI_CUSTOM`) to `/dev/wmtWifi`.
- [verified] The MAC comes from bootconfig `androidboot.wifimacaddr`.
- [verified 2026-11-23] `vegas-wifi` + `wpa_supplicant@wlan0` on #5: `wlan0` with the bootconfig MAC, 73 networks scanned, WPA2 + DHCP, ping 1.1.1.1 ~12 ms, apt 3.7 MB/s; all `ccmni` stayed down. `wmt_loader` exits 255 without effect. Enabled at boot (started by hand that day; the boot start is [unverified] until the next boot).

**End state E** (unrooted Android + Debian): defined in the README.
- [verified] `scripts/linux_b.sh` stages `android-capture` (run on 2026-11-22), `state-e`, `state-e-check`,
  `root-on`/`root-off`.
- [unverified] On the phone.

## 12. Linux main root inside `userdata` (design 2026-11-22; offline-tested, not yet on the phone)

**Why.** `super` has about 1.3 GB free after `linux` (3 GiB), and microSD is slow for small synced writes (the 2025 port moved off it for Chrome, `linux/work/ref/moto-g-power-2025-omarchy/notes/internal-storage-20261010.md`). `/data` has 103 GB free on #5. [verified]

**Encryption.** `/data` is f2fs with FBE v2 and metadata encryption using hardware-wrapped keys (`fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0`, `metadata_encryption=aes-256-xts:wrappedkey_v0`, `/vendor/etc/fstab.mt6835`). Linux cannot decrypt it: the keys are unwrapped by the Trustonic TEE through Android's KeyMint/vold every boot. [verified]

**Mechanism (Android's own DSU/libfiemap).** [verified in AOSP source, `fs_mgr/libfiemap/{fiemap_writer,image_manager}.cpp`]
- A file on f2fs is pinned (`F2FS_IOC_SET_PIN_FILE`) and then `fallocate`d; its extents come from FIEMAP.
- The block device is found by walking dm layers down through `default-key`/`bow`/`crypt` and offset-0 `linear` (`DeviceMapperStackPop`, `ValidateDmTarget`).
- The image is mapped with dm-linear over the RAW partition. Data written there is stored unencrypted (`ZeroFillNewImage`: zeroes written through the file were encrypted, so they are rewritten through the mapping). f2fs never reads the contents.
- Risk named by the source: f2fs unpins a file after `gc_pin_file_thresh` failed GC attempts (2048 on #5) and may then move it. Callers re-check `HasPinnedExtents`.

**vegasdisk** (`linux/tools/vegasdisk.c`, one static binary for Android, the initramfs and Debian):
- `create`/`grow` (Android, root): pieces `/data/vegas/disk.NNNN` (1 GiB), pinned + `fallocate` + FIEMAP; rejects unwritten/shared/unaligned extents, holes, a raw device that is not PARTNAME `userdata`, and any dm layer that is not 1:1.
- Layout: piece 0 starts with a 1 MiB table (magic, version 2, uuid, fsid, extent table, CRC32s) that must be one physical extent; every piece has a tail canary and pieces after 0 a head canary (uuid, piece, own offset, CRC). The table is written last. Piece sizes are whole 2 MiB f2fs sections. A failed `create`/`grow` removes the pieces it made before the table was written.
- **fsid** = raw bytes [1024, 1152) of `userdata`: the start of the f2fs superblock (magic, layout, block count, f2fs uuid), stored as AES-XTS ciphertext by `default-key`. XTS encrypts each 16-byte chunk on its own, so unchanged fields give unchanged ciphertext. Measured on #5 over two reboots: the hash of raw block 0 changes every boot, but only the 16-byte chunk at 3776 (and its backup at 7872) differs. [verified 2026-11-22] A format or factory reset (new f2fs uuid, new metadata key) changes the fsid, so `map` and `verify` refuse a table left over from an earlier `/data`.
- `verify` (Android): FIEMAP, pin flags, fsid, the raw table and all canaries must agree, and f2fs's pin GC-failure count must be 0.
- `map` (initramfs/Debian): from an anchor (piece 0's raw offset) and uuid kept on the rescue root; checks magic, CRCs, uuid, fsid, bounds, overlaps and every canary before building dm-linear over the data ranges; refuses otherwise. A failure after the dm device was created removes it again.
- `delete` (Android): zeroes the table, then every canary, through the raw device, and only then unlinks the pieces, so a stale `vegasdisk.conf` can never map freed blocks.
- Offline test (`linux/tools/vegasdisk-test.sh`, real f2fs on a loop + offset-0 dm-linear standing in for default-key, arm64 VM): create/verify, raw writes leave `fsck.f2fs` clean, grow keeps data, verify after f2fs GC stress, and refusals (wrong uuid/anchor, non-userdata device, corrupted canary, corrupted table, a table from before a reformat, a piece size that is not whole sections, map after delete, delete with a wrong uuid); a create that hits ENOSPC leaves no pieces. [verified offline 2026-11-22] On the phone: [unverified] (stage `datadisk-poc`).

**Two roots.** `init.linux` mounts the rescue root (`linux` in super) read-only to read `/etc/vegas/vegasdisk.conf`, maps the userdata disk, checks the ext4 label `vegas-root2`, the Debian marker and the completion marker `/etc/vegas/root-role` = `main`, and switches to it. Any failure, a one-shot `/rescue` file in the main root, or **Vol-up held down for 2 s once it registered** (the chooser leaves `/force_rescue` and the main root is not mapped at all; repeated taps, the usual way to hit the window, always release sooner and boot the main root; on #5 Vol-down is on `mtk-pmic-keys`, which is not loaded that early, so Vol-up is the only key the chooser sees) boots the rescue root. `init.linux` logs the reason in `/var/log/vegas/init.log`. The conf lives only on the rescue root; the Mac copy is written only after the main root is complete, so `linux/debian/build.sh` bakes `logs/<serial>/linux_b/datadisk/vegasdisk.conf` into `debian.simg`, and `rootfs-flash` refuses an image whose conf differs from the phone's. A rerun of `datadisk-create` keeps an existing `vegas-root2` only if it carries the completion marker `/etc/vegas/root-role` = `main` (written last), and then only rewrites the conf; without the marker it refuses. `create` zeroes the first MiB of data, so a stale ext4 superblock from earlier blocks cannot be mistaken for a finished root. Debian grows the ext4 online after `datadisk-grow` (`vegas-diskgrow.service`). Resizing needs root in Android: in state E, `root-on` → `datadisk-grow` → `root-off`.

**Limits.** Not encrypted (plaintext on flash). A factory reset or `/data` format deletes the main root; Linux then refuses the old table (fsid) and boots the rescue root. Android cannot see inside the files.

**Residual risk: an f2fs move.** Linux cannot see f2fs metadata (it is encrypted), and canaries catch overwrites, not moves: after a move the old copy stays valid on disk until f2fs reuses it. f2fs only moves a pinned file after `gc_pin_file_thresh` (2048) failed GC attempts on it. GC only picks partly valid sections as victims, and the pieces are whole sections that are never written through f2fs, so their sections stay fully valid and should never be picked. That is the same assumption DSU makes. [reasoned from the f2fs source, not measured on the phone] Checks: `verify` fails on any GC-failure count above 0; `datadisk-poc` runs idle maintenance and verifies; `datadisk-check` runs `verify` when rooted and warns loudly in state E, where Android is unrooted. Run `root-on` → `datadisk-check` → `root-off` now and then.

**Wi-Fi property shim.** `wmt_launcher` polls `vendor.connsys.driver.ready`. `linux/tools/propshim/` (adapted, MIT, from `Mattcabrices/moto-pad-2026-arch-linux`) is a `-nostdlib` `LD_PRELOAD` library answering `__system_property_*` from the captured getprop; it lives in `/odm/lib64` because the vendor linker namespace allows `/odm`. In the arm64 VM the launcher logs "get property(vendor.connsys.driver.ready) is yes" and proceeds to `/dev/stpwmt`. [verified in VM; phone unverified] `Muzuwi/wmt-pyloader` targets MT6765 with patch files in `/lib/firmware`; #5 has no Wi-Fi patch files in `/vendor/firmware`, and the 2025 port's MT6835 adapter is unpublished, so the shim route comes first.

