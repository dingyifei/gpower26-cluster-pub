# BL unlock + permanent root + full backup — runbook

Device-specific to **moto g power 2026 / XT2617V / Tracfone / `W1WEOS36.48-22-3-3-4-2`** (verified on phone #1).
Toolchain: [`vegas-freedom`](../vegas-freedom) submodule (bundles the Valhalla / val-protocol `lk` scripts).

Run each phone through this **after** the standard init (enrol → remove work profile → `ota-off`). Scope here is
**BL unlock + root + backup only**. SIM/network unlock (vegas-freedom Step 3, `md1img`) is a separate TODO.

## Irreversible costs (read first)
- **Unlock wipes `/data`.** Back up personal data; re-install the exploit/manager APKs afterward (they're wiped too).
- After unlock: `flash.locked=0`, `verifiedbootstate=orange` (boot warning), Play Integrity + Widevine L1 fail. Fine for a cluster.
- **`lk` must be this phone's own dump**, matched by MBM string — a wrong/other-build `lk` is a hard brick.
- **A/B:** `lk_b`/`md1img_b` ship all-zero. lk and init_boot: active slot `_a` only. Modem exception: after `md1img_a` is proven
  with a foreign SIM, flash the same image to `md1img_b` too (project policy, done on phone #1). Never flash `preloader/gpt/efuse/seccfg/nvram/nvdata/protect1/2/persist`.

## Code review (done 2026-11-18, vegas-freedom commit `ed78c7e`)
- No network / eval / pickle / base64 anywhere; only `subprocess` -> `adb`/`fastboot`/own signing scripts.
- `scripts/backup_partitions.py`: read-only (`dd if=` only), writes to local `backups/`, verifies each image against on-device `sha256sum`.
- `bootloader/patch_lk.py`: produces + CERT-verifies a file in `work/`, **never flashes**; rejects all-zero `lk_b` and already-patched input. Stock lk `136bf013...`(full)/`b6e5a74f...`(trimmed); patched output `914acfce...`.
- **Not in the repo:** DirtyFrag + KernelSU APKs (the temp-root exploit). External binaries — verify their SHA-256 against their GitHub releases before installing. This runbook does not auto-run them.

## Prereqs
- PC: `adb`, `fastboot`, `.venv` with `capstone`+`pyasn1` (`pip install -r vegas-freedom/requirements.txt`).
- Keep on the PC (wiped on unlock, needed again): **DirtyFrag v1.17**, **KernelSU v3.3.1** (manager `me.weishu.kernelsu`; vegas.json also accepts KSU-Next `com.rifsxd.ksunext`).

## Phase 1 — temp root (no unlock, stays green)
Physical taps on the phone; `adb` where noted.
1. `adb install KernelSU.apk`; open it once so the service registers.
2. `adb install DirtyFrag.apk`; in DirtyFrag set SU Manager = KernelSU, tap **Run exploit** (~10s -> KernelSU shows `LKM: Working [Jailbreak mode]`).
3. Verify: `adb shell su -c id` -> `uid=0`.
   - Gotcha: first try may say `su: inaccessible or not found` — reboot, run the exploit again. Jailbreak mode adds no overlay; `verifiedbootstate` stays `green`.

## Phase 2 — full backup (read-only, with temp root)
```
scripts/phone.sh backup
```
**Skips automatically if `backups/` already holds `<serial>_<build>_stock_*.tar.zst` for this exact phone+build.**
Otherwise it runs `vegas-freedom/scripts/backup_partitions.py` (dumps every `/dev/block/by-name/` partition, ~12.5 GB, 96 files incl. `super.img`, each on-device sha256-verified) and compresses it via `scripts/archive_backup.sh` into a gitignored `backups/<serial>_<build>_stock_<ts>.tar.zst`. Confirm `lk_a.img` (16,777,216 B) and `md1img_a.img` (209,715,200 B) are inside. **Also copy the archive off this machine** — a repo-local gitignored copy is not a real backup. Unique, non-stock partitions to never lose: `nvdata/nvram/nvcfg/protect1/2/persist/md1img_a`.

## Backup storage: per-build reuse to save space

**Always dump every phone in full** (read-only, sha256-verified) — the dump is free and safe. Reuse only changes
what gets *stored* and *re-flashed*, by partition class:

| Class | Same across same-build phones? | Partitions (vegas26) | Storage |
|---|---|---|---|
| Build images (bulk) | ✅ identical | `super` (~10 GB), `system*`, `md1img_a/b`, `boot_a/b`, `init_boot_a/b`, `vbmeta*`, `vendor*`, `gz_*`, `logo_*`, … | stored **once per build** |
| Device-unique (small) | ❌ per phone | `nvram nvdata nvcfg persist prodpersist protect1 protect2 seccfg sec1 cid carrier frp efuse efuseBackup boot_para` | stored **per phone** |

`scripts/archive_backup.sh` does this automatically by **content hash**, so classification is proven, not guessed:
- **First phone of a build** → full archive `backups/<serial>_<build>_stock_<ts>.tar.zst` (~8–12 GB). This is the build reference.
- **Later same-build phones** → `backups/<serial>_<build>_delta_<ts>.tar.zst` containing only partitions whose SHA-256
  isn't in the reference (the device-unique set, ~tens of MB) + `REUSES.txt` naming the reference. 8 phones ≈ one
  full archive + 7 small deltas instead of 8× ~12 GB.

**Restoring a delta phone:** build images from the reference `_stock_` archive + that phone's own `_delta_` partitions.
Never cross-flash device-unique partitions between phones — wrong `nvdata`/`persist`/`seccfg` bricks or corrupts IMEI/RF cal.
**Patched images:** stock `lk_a`/`init_boot_a`/`md1img_a` are build-identical, so the patched `init_boot_ksu.img` and patched
modem are reusable across same-build phones; the patched **unlock `lk` is per-serial** (`lk_keygen --serialno`), so re-patch it per phone.
(Delta mode is exercised from phone #2 on; phone #1 is the reference full archive.)

## Phase 3 — patch lk + unlock (WIPES DATA — stop here for go-ahead)
> Verified on phone #1: patched lk `914acfce…` CERT VALID; MBM `MBM-3.1-vegas_og_vext-5d518d-W1WEOS36.48-22-3-3-4-2-36210f`.
> The unlock key is **serial-bound** — generate with `--serialno <SN>`; the no-serial key fails `Code validation failure` (harmless, no wipe).
```
.venv/bin/python vegas-freedom/bootloader/patch_lk.py vegas-freedom/backups/stock_<ts>/lk_a.img
# -> work/lk.unlock-serial.img (3,477,904 B), CERT "Result: VALID"
```
Compare MBM identity string (not just version): `MBM-3.1-vegas_og_vext-5d518d-W1WEOS36.48-22-3-3-4-2-36210f`
```
adb reboot bootloader
fastboot flash lk work/lk.unlock-serial.img
fastboot reboot bootloader
fastboot getvar serialno
.venv/bin/python vegas-freedom/bootloader/lk_keygen.py --secret Valeria --serialno <SN> --count 1  # serial-bound key; the key is PER-PHONE
fastboot oem unlock <KEY>          # use the serial-bound key (NOT the no-serial/global one — that gives 'Code validation failure'); then confirm on-screen (Volume to select UNLOCK, Power to confirm); wipes userdata
fastboot getvar securestate        # expect flashing_unlocked
```

## Phase 4 — permanent root (init_boot + KernelSU)  →  **automated: `scripts/permroot.sh <serial>`**
The manual steps below are what that script does (ksud `--allow-shell --enable-adbd`, KMI `android13-5.15`).
Data wiped: re-install KernelSU + DirtyFrag, run the exploit again for temp root, then:
```
adb shell "su -c 'dd if=/dev/block/by-name/init_boot_a of=/sdcard/init_boot_a.img bs=1048576'"   # 8,388,608 B, magic ANDROID!
adb pull /sdcard/init_boot_a.img
# PC: ksud boot-patch -b init_boot_a.img -o <dir> --kmi android13-5.15 -m android13-5.15_kernelsu.ko --out-name init_boot_ksu.img
#   --kmi is exactly android13-5.15 ; -o is a DIR, name via --out-name ; Windows ksud needs explicit -m
# or on-device: ksud -b /sdcard/init_boot_a.img -o /sdcard/
fastboot flash init_boot_a init_boot_ksu.img
fastboot reboot
```
Verify: `su -c id` -> `uid=0 ... u:r:ksu:s0`; `/dev/df` does **not** exist; `ksud --version` -> 3.3.1.
Then: `scripts/phone.sh ota-off-root`.

## Keep these 5 files per phone (durable storage, not git)
stock `lk_a.img`, stock `init_boot_a.img`, stock `md1img_a.img` (209,715,200 B), patched `lk.unlock-serial.img`, patched `init_boot_ksu.img`.

## Rollback
```
fastboot flash init_boot_a <backup>/init_boot_a.img   # undo root only
fastboot flash lk_a <backup>/lk_a.img                 # stock lk back
fastboot oem lock                                     # re-lock; wipes data again
```
Anti-rollback: re-flashing the **same** build is fine; cannot downgrade to `-4-2` after a newer OTA lands.
