# LineageOS (vegas26 tree) on phone #5: replace stock Android, or use it as reference only?

> Research report from the v1 build sessions, imported as written. `#5` is the maintainer's dual-boot phone.
> Paths starting `<scratch>/` are the session's working folder and are not in this repo. `linux/work/ref/<name>/` are
> local clones of the public sister-port repos; their URLs are in `docs/linux-on-vegas.md` section 8.

Date: 2026-11-23. No phone was touched. Sources: GitHub API reads of the repos (files saved under
`<scratch>/ui/lg/`), the repo docs, two web searches.

Labels: **[verified: source]** = read directly from the named source today (for a third-party claim, it means the
source says it, not that we reproduced it). **[unverified]** = inference or a claim nobody here has checked.

## TL;DR

**Recommendation: don't replace stock Android on #5. Keep the vegas26 tree as reference material.** Reconsider
only if one of three things happens: the tree gets a release, the tree gets a -4-2 build, or a separate expendable
unlocked unit becomes available.

The main reasons:
1. **Wrong firmware base.** The tree runs only on firmware `-4-3`. #5 runs `-4-2`.
2. **No microG.** The tree is LineageOS with MindTheGapps, not microG.
3. **Its install flow deletes everything end state E is built on:**
   - `wipe-super` deletes the `linux` partition, which holds the rescue root.
   - `fastboot -w` deletes the 32 GiB pinned-file main root.
   - It overwrites `init_boot_a`, where the chooser lives.
   - It writes a custom `vendor_boot_a`, which our rules defer on -4-2.
4. **The kernels don't match.** The tree uses the stock 5.15.189 kernel. Our Debian and chooser depend on the
   rebuilt 5.15.180 GKI, which matches the -4-2 module CRCs. One kernel has to serve both systems, so the Debian
   kernel work would have to be redone against -4-3.
5. **No support behind it.** It is one author's tree: 4 commits on 2026-11-16, nothing since, no releases, and no
   OTA path.

## 1. Current state of the tree

| Item | Finding | Status |
|---|---|---|
| Repos | 8 jimmielin repos on branch `lineage-23.2`:<br>• `android_device_motorola_vegas26`<br>• `-vegas26-kernels`<br>• `mt6835-common`<br>• `android_vendor_motorola_vegas26`<br>• `mt6835-common-vegas26`<br>• `vendor_motorola_vegas` (2025 model)<br>• and others<br>Device tree: 4 commits, all on 2026-11-16 05:00–05:30Z; last push 2026-11-16T05:32Z; 2 stars; 0 issues | [verified: `gh api repos/jimmielin/...` commits and pushed_at] |
| Releases / builds | No releases or tags on any repo. Anyone who wants it must build it themselves. | [verified: gh api releases = empty] |
| Second-party build | One person (fergatronanator) built a `userdebug`/test-keys image (`23.2-20261118-UNOFFICIAL-vegas26`, patch 2026-11-01) and booted it on one -4-3 unit. Wi-Fi worked. They did not verify GApps or root. | [verified: fergatronanator/vegas26-lineageos-handoff AGENT-HANDOFF.md, as their own report] |
| Self-reported working | Display, touch, all 3 cameras, fingerprint, audio, vibration, rotation, Wi-Fi, BT, GPS, NFC, mobile data, calls, SMS, charging, MindTheGapps | [verified: vegas26 README says so; not reproduced] |
| Not verified by the author | VoLTE/VoWiFi; A/B updates from the LineageOS updater ("update by flashing images for now") | [verified: vegas26 README] |
| microG | Not supported. The README and flash script mention only MindTheGapps. LineageOS for microG builds only official LineageOS devices; its January 2026 snapshot lists lineage-21/20/18.1. Upstream LineageOS has carried restricted signature spoofing for microG since Feb 2024, so a self-build plus microG GmsCore could work, but nobody has done it for vegas26. | [verified: tree README; lineage.microg.org via search] / [unverified: microG on this tree] |
| Signing | The author has tested only with release keys, and warns that the Trustonic TEE behaved differently on test-keys builds on a sibling phone. The second-party build used test-keys and booted. | [verified: README; handoff] |

## 2. Firmware base

- **Firmware.** The tree requires stock `W1WEOS36.48-22-3-3-4-3` on slot A. `flash-vegas26.sh` aborts unless
  `version-bootloader` contains that string. All blobs (vendor, trustlets, modem-facing HALs) are extracted from
  -4-3. [verified: README, `tools/flash-vegas26.sh`, vendor repo commit "Import blobs from ...-4-3"]
- **Kernel.** Stock -4-3 GKI `5.15.189-android13-8-00018-g9c82b71884fd-ab14885418`, unmodified, plus stock DTB and
  dtbo. [verified: vegas26-kernels README]
  - #5's rebuilt kernel is 5.15.180 at `9b2308ac0ad6` (-4-2). [verified: linux/README.md]
- **No -4-3 package anywhere.** No stock -4-3 package is published, and `tools/locked/` holds only the base and -4-2
  zips. [verified: README "no stock firmware package for this build online"; `ls tools/locked`] The only way to
  reach -4-3 is a Motorola OTA, which installs to slot B and switches slots. Both the tree and the handoff forbid
  that unless slot B is populated (AGENTS.md rule 3). [verified]
- **Running it on -4-2 would mean porting it ourselves:**
  - re-extract blobs with `extract-files.py` from a -4-2 dump
  - swap in -4-2 kernel prebuilts or our rebuilt kernel
  - lower `BOOT/VENDOR_SECURITY_PATCH` and the rollback index to -4-2 values

  Nobody has tried this. [unverified] One encouraging data point: the vendor-ramdisk `modules.load` names in the
  tree match our -4-2 `linux/work/stock/vendor_ramdisk/lib/modules/modules.load` exactly when both are sorted.
  [verified: local diff today] Names match, but Motorola rebuilt every module for -4-3, so the binaries and CRCs
  differ. [verified: vegas26-kernels README]
- **Going -4-2 → -4-3 → -4-2 again.**
  - Downgrading from -4-3 is proven here: #7 and #8 went -4-3 → base → -4-2 and are now locked/green.
    [verified: the maintainer's phone status table, not published]
  - The OTA step would also overwrite the retail-patched `lk` and the SIM-unlock `md1img`. [verified:
    community-notes §6 "An OTA ... overwrites it"]
  - Whether an OTA even installs on #5 is unknown, because its `boot_a`, `init_boot_a` and `super` are all
    modified. [unverified; Virtual A/B normally checks source partitions]

## 3. What it flashes, and what that does to end state E

The tree's flash script writes, in order [verified: `tools/flash-vegas26.sh`]:
1. In the bootloader: `vbmeta_a`, `vbmeta_system_a` (rollback index 7, AOSP test key or own keys), `boot_a`,
   `init_boot_a`, `vendor_boot_a` (custom, holds LineageOS recovery), `dtbo_a`.
2. In fastbootd: **`fastboot wipe-super super_empty.img`**, then `system`, `system_ext`, `product`, `vendor`,
   `vendor_dlkm`.
3. Then the user runs `fastboot -w`. Stock `/data` cannot be reused.

Effect on each part of E:

| E component | Effect | Status |
|---|---|---|
| `linux` LP partition (rescue root, 3 GiB) | Deleted by `wipe-super`. Could be recreated afterwards in fastbootd if LineageOS leaves room in super; LineageOS images are usually smaller than Motorola's (size not measured). The script could also skip `wipe-super`, but then super's group sizing would have to fit by hand. | [verified: script] / [unverified: free space] |
| Pinned-file main root `/data/vegas` (32 GiB) | Deleted by `fastboot -w`, and the fsid changes, so `map` refuses the old table as designed. Rerunning `datadisk-create` is possible. Copy the Debian root to the Mac first. | [verified: script + docs §12 fsid logic] |
| Chooser in `init_boot_a` | Overwritten. It could be rebuilt on top of LineageOS's generic ramdisk, the same way it sits on the stock one now (lz4-legacy, exec of the renamed `/init`). `build_chooser.sh` would need a new base image. | [unverified] |
| Rebuilt kernel in `boot_a` | Replaced by stock -4-3. Our rebuilt kernel would not match -4-3 module CRCs, so `boot-4b` and the modcrc/btf gates would have to be redone against 5.15.189. The ACK commit `9c82b71884fd` would need to be found. The Motorola source tag the tree cites, `MMI-W1VKS36H.9-12-9-8-5`, belongs to another firmware line. | [unverified] |
| `vendor_boot_a` | Custom image. Our rules defer it on -4-2 (class D). On -4-3 the second-party log shows it accepted with the stock DTB inside. | [verified: docs §3.8/§6.1; LG-6 contested] |
| Debian vendor daemons (fuel gauge, Wi-Fi, chargeguard) | They depend on the -4-2 Android runtime closure captured by `android-capture` and on -4-2 vendor modules. They would need a fresh capture from LineageOS's vendor, which is built from -4-3 blobs. | [unverified] |
| Slot B | The tree uses slot A only and offers `copy-firmware-to-other-slot.sh`, which copies the running firmware to slot B, not the preloader. That matches our rule never to use slot B. Running the copy script would write slot-B firmware partitions, which we have never done on any phone. | [verified: README, AGENTS.md] |

## 4. Data encryption

- **The encryption config is the same as stock.** LineageOS's `fstab.mt6835` keeps
  `fileencryption=aes-256-xts:aes-256-cts:v2+inlinecrypt_optimized+wrappedkey_v0`,
  `metadata_encryption=aes-256-xts:wrappedkey_v0`, plus `checkpoint=fs`. That is the same FBE and hardware-wrapped
  key setup as stock. [verified: `mt6835-common/init/fstab.mt6835`; stock in docs §12]
  - So the libfiemap pinned-file disk design still applies in principle: Linux still can't decrypt `/data`, and
    the raw-partition dm-linear approach is unchanged. [unverified on LineageOS]
- **Pin-GC risk still applies.** The `gc_pin_file_thresh` move risk applies equally. The upside: a `userdebug`
  LineageOS has `adb root`, so `datadisk-check verify` could run without the KernelSU temp-root dance.
  [verified: handoff says `adb root` works on their userdebug build]
- **Format before first boot.** LineageOS cannot use stock's encrypted data, and so needs a format. [verified:
  README] Going back to stock later needs a wipe from stock recovery to recreate the wrapped key (VK-15).
  [unverified]

## 5. Play Integrity

- **No change from E.** #5 is already unlocked (orange), so stock E fails device integrity as well. LineageOS
  changes nothing here. [verified: README end state E text]
- **microG doesn't help.** microG would not pass Play Integrity either. Our memory notes NO_INTEGRITY on #1 across
  three configs even with spoofing, probably for lack of a keybox. [unverified]
- **Debian is unaffected.** It doesn't care about Play Integrity.

## 6. OTA and updates

- **Stock E has no updates.** OTA is disabled by design, so the stock side stays at the -4-2 platform patch.
  [verified: README/community notes]
- **LineageOS updates by reflashing.** The LineageOS updater's A/B OTA is unverified, and A/B OTAs would switch
  slots, which AGENTS.md forbids. Updates mean reflashing images, and the published script re-runs `init_boot_a`
  and `wipe-super` every time. A fork of the script would need to preserve `linux` and the chooser. [verified:
  README, AGENTS.md, script]
- **Newer platform patches, same base.** LineageOS does carry a newer AOSP platform patch (2026-11-01 in the
  second-party build). Vendor, kernel and TEE stay at -4-3. [verified: handoff]
- **No upstream to rebuild from.** The tree has not moved in a week. Rebuilding monthly means a full LineageOS
  checkout (~300 GB) and an x86_64 Linux build host. Our Mac is Apple Silicon, and `vegas-kbuild` runs x86_64 under
  Rosetta only for the kernel. A LineageOS build there would be very slow or impractical. [unverified, general
  AOSP build knowledge]

## 7. Pros and cons for #5

**Pros**
- No Motorola/Tracfone bloat or activation flow. The retail `lk` patch would matter less.
- Newer AOSP platform security patches than frozen -4-2.
- `userdebug`: `adb root` and a root-adb recovery in `vendor_boot`, which is a useful rescue environment that reads
  every partition (AGENTS.md).
- Same encryption scheme, so the pinned-disk design carries over in principle.
- Open sepolicy and init: e.g. the `genfs_contexts` label for the sc89890h charger at i2c-5 0x6a, and the module
  lists, which are useful reference for Debian's charger work.

**Cons**
- Requires -4-3, which can only be reached by a slot-switching OTA. The OTA overwrites the retail `lk` and the
  unlock modem. #5 would leave the build gate every other farm tool assumes.
- A -4-2 port is our own unbuilt, untested project.
- It destroys and forces a redo of every E component: `linux` LP partition, 32 GiB main root, chooser, the rebuilt
  kernel and its gates, and the vendor capture.
- It writes custom `vendor_boot_a` and `dtbo_a`, which our risk table classes D on -4-2. The tree author: "no known
  BROM rescue path: a damaged bootloader chain is a permanent brick."
- No microG out of the box; GApps only.
- One unsupported author, no releases, no updater OTA, VoLTE unverified, and a heavy build host requirement.
- E is nearly complete on #5 today. Switching resets weeks of verified work for no gain on Linux, and the Linux
  side is the point of #5.

## 8. Recommendation

**Use the tree as reference evidence only. Don't replace stock on #5.** Worth mining now:
- `fstab.mt6835`: confirms the encryption flags.
- The `BOARD_VENDOR_KERNEL_MODULES` list: modules stock loads from init scripts, e.g. `wlan_drv_gen4m_6835`,
  `wmt_*`, `qpnp_adaptive_charge`, `moto_f_usbnet`. Useful for Debian's module loading.
- The charger `genfs` sepolicy note.
- The rollback-index and patch-level invariants: index 7 and 2026-06-01 on -4-3.
- `copy-firmware-to-other-slot.sh`: its design is useful reference. Don't run it.

Revisit if:
- a -4-2 build or tagged releases appear;
- a microG-flavoured build appears; or
- a second unlocked unit is designated, so #5's E isn't sacrificed.

If the owner wants LineageOS anyway, do it on #5 only after:
1. backing up the Debian main root to the Mac;
2. completing a full `archive_backup.sh`;
3. porting the tree to -4-2 offline (never the OTA to -4-3);
4. forking the flash script to drop `wipe-super`, the `fastboot -w` step and the init_boot write, so the chooser
   gets layered on.

## 9. First safe step (offline, no phone)

Clone the 8 repos into the `vegas-kbuild` VM. Then:
1. Run the tree's `extract-files.py` logic against our -4-2 `super` dump (`lpunpack` to `vendor`, `system`, ...).
2. Diff each blob list for presence and hash between -4-2 and -4-3.
3. Diff the module CRCs of `vegas26-kernels/5.15` modules against our -4-2 modules with `linux/tools/modcrc.py`.

That measures how big a -4-2 port is before anyone decides anything. Nothing is written to any phone.

## 10. Risks of even trying

- Brick class D on `vendor_boot_a`/`dtbo_a` (no BROM path).
- Rollback-index ratchet: flashing an index-7 vbmeta might block -4-2 images or relocking to D later. On unlocked
  phones enforcement is contested (LG-12 vs LG-13). #7 and #8 came back from -4-3 to locked -4-2, which argues
  against a hard ratchet. [unverified]
- Losing the retail `lk` and the unlock modem if the OTA route is taken.
- Losing the Debian main root if it isn't backed up before `fastboot -w`.
- The modem must never be booted under Debian. LineageOS brings the modem up normally under Android, which is
  fine, but the Debian rules stay.

## Sources

- https://github.com/jimmielin/android_device_motorola_vegas26 (README, AGENTS.md, BoardConfig.mk, tools/flash-vegas26.sh), read via gh api 2026-11-23
- https://github.com/jimmielin/android_device_motorola_mt6835-common (README, init/fstab.mt6835)
- https://github.com/jimmielin/android_device_motorola_vegas26-kernels (README, 5.15/vendor_ramdisk.modules.load)
- https://github.com/fergatronanator/vegas26-lineageos-handoff (README, AGENT-HANDOFF.md)
- https://github.com/qfertig/vegas26-gsi (open issues list)
- https://lineage.microg.org/ ; https://www.github.com/microg/GmsCore/wiki/Signature-Spoofing (via web search)
- Repo: docs/linux-on-vegas.md §3.8, §6, §12; linux/README.md; README.md end state E; docs/community-notes.md
- Local files: tools/locked/ listing; linux/work/stock/vendor_ramdisk/lib/modules/modules.load
