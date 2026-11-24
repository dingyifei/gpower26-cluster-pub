# Community notes: USCardForum moto g power 2026 threads

A distilled technical reference from two USCardForum threads about the Tracfone/Straight Talk **XT2617V / vegas26**. It is not a
transcript. The raw dump (snapshot 2026-11-18) is kept in the maintainer's private tree under `docs/sources/` and is not published: it is other people's posts.

- **P1** = topic 546212 (11-11 → 11-17): activation bypass, BL unlock + root, modem patch. **P2** = topic 547067 (11-15 → 11-18):
  patched `lk` flashed **with the BL locked**, retail channel, `md1img-unlock.img`, relock to locked/green, Moto-Clean.
- Cites look like (P2 #65). Status tags: **[multiple]** = multiple reports, **[single]** = single report, **[contradicted]** = threads disagree (the newer
  view comes first). "Our check" = verified locally in this repo. Many posters let an AI agent run the steps, so posts report outcomes more often than commands.
- End states: **A** = BL unlocked + permanent root. **D** = BL locked/green via the patched `lk`, unrooted, OTA disabled. (The forum calls the D method "route C"; in this repo it is always route D.)

## 1. Builds and versions

| Build | Patch | Baseband | Reported |
|---|---|---|---|
| `W1WEOS36.48-22-3-3-4-2` (ours) | 2026-04-01 | `…P107.02.309R` | every route works (P1 #55, P2 #1, #65). AVB rollback index 5 (P2 #44, #65) |
| `-4-3` | 2026-06 (P1 #66) | P144? (P2 #65) | BL unlock OK (P1 #66, #166). Rollback index 7, so it can't be downgraded to the -4-2 retail package (P2 #44) [single] |
| `-4-7` | ? | P144 (P2 #45) | lk + modem adapted from the phone's own images works (P2 #45) [single] |
| `-4-9` | 2026-10-01 | ? | asked about, no success (P1 #341, P2 #49) |

- Exploit window: MTK Moto with a patch **before 2026-09** (P1 #2, #31, #85; P2 #75) [multiple]. Phones from the same order can ship on different builds (P1 #155) [multiple].
- Phones auto-updated even with Smart updates off (P1 #397, #438; P2 #26, #28) [multiple]. One had `-4-3` staged into slot B while still running `-4-2` on A (P1 #350) [single].
- "Rollback level 5 on -4-3 can take the -4-2 files" (P2 #24, #39) vs 7 measured on a -4-3 (P2 #44): [contradicted]. Check the rollback index first.

## 2. Activation bypass

- ST terms allow a "Device Lock" on screen, Wi-Fi and offline apps until 12 months of paid service (P1 #25, #143, #177).
- Tap the welcome screen ×6 to open the QR scanner and enroll a work profile, then remove the profile. Options: TestDPC pre-made QR (P1 #33, #42, #145), ManageEngine trial with
  "Workspace Management" (not Full Device Management) then Corporate Wipe (P1 #213, #293; P2 #65), or `sidemdm` (P1 #166, #331) [multiple]. Use your own MDM (P1 #29).
- **An MDM bypass does not survive a factory reset.** After a reset, transfer/Wi-Fi/eSIM come back, then activation (P1 #108, #125, #139, #172) [multiple]. The retail `lk` (§4) fixes this.
- Pulling the SIM before first boot doesn't help (P1 #170) [single].
- `adb shell tradeinmode evaluate` skips the wizard. The phone auto-wipes on reboot unless you `rm /metadata/tradeinmode/wipe` (P1 #509). It works only from the setup
  wizard's limited adb at first boot (P1 #519). After setup it returned "command not available" (P1 #511, #516) [contradicted].

## 3. Route A: temp root → BL unlock → permanent root (P1 #55 ≈ our runbook)

- Start state: `oem_locked`, `flash.locked=1`, green, `ro.oem_unlock_supported` empty. Kernel `5.15.180-android13-8` (KMI `android13-5.15`).
- Temp root: DirtyFrag v1.17 (CVE-2026-43284) or DFRoot 4.7, plus KernelSU 3.3.1 in jailbreak mode. AVB stays green. The first run may give `su: inaccessible or not found`; reboot and re-run (P1 #55; P2 #65).
- Dump `lk_a` (16,777,216 B) with `su -c dd`. `fastboot fetch` isn't supported, and non-root `dd` reads 0 records. Match the full MBM string; **a wrong lk is a hard brick** (P1 #55).
- `lk_auto_patch.py lk_a.img -o lk.unlock-serial.img --preset unlock-serial --key-token-secret …` gives 3,477,904 B, `Result: VALID`. A `liblk` error really means missing
  `pyasn1`/`pycryptodome` (P1 #55). P2 #65 used val-protocol `dc7f41f9`. The preset patches FRP/OEM checker *calls*; it does not clear FRP.
- The patched lk flashes fine while locked. Then `fastboot oem unlock <serial-bound key>` wipes data and the phone goes orange (P1 #55; P2 #65) [multiple]. This lk's `oem unlock` path also
  erases `nvdata/md_udc` (P2 #65, static reading) [single].
- Permanent root: `ksud boot-patch -b init_boot_a.img -o <DIR> --kmi android13-5.15 -m android13-5.15_kernelsu.ko --out-name init_boot_ksu.img`, or on the device
  `ksud -b /sdcard/init_boot_a.img -o /sdcard/` (P1 #55, #137).
- Slots: "flash A and B, since factory only wrote A and an OTA to B bricks" (P1 #61) vs "A only, all-zero B is no rescue" (P2 #65): [contradicted].

## 4. Route D: patched `lk` with the BL locked (P2; the forum calls it "route C")

**Principle (P2 #8):** the sales channel lives in `cid`, which `lk` reads. **`lk` is outside the AVB chain**, so a re-signed `lk` flashes while locked. The patch
makes `lk` always report retail (`androidboot.carrier=retus`). `cid` is not touched.

**OP's files (P2 #1). They are third-party Google Drive links, already in `tools/locked/` (gitignored), and our SHA-256 check matches `tools/locked/SHA256SUMS`:**

| File | Purpose | SHA-256 / match |
|---|---|---|
| [`lk-moto2026.img`](https://drive.google.com/file/d/1PwIepOZS4zd_0LK3afnzjNMbbvEF9PR4/view) | carrier→retail, BL stays locked | `957b7db4…` = P2 #65 "retus LK container" |
| [`lk-moto2026-unlock.img`](https://drive.google.com/file/d/16tddDP86AaL1ask4fLL9ak39FgkQCb-I/view) | retail + BL unlock | `072434ae…` (no forum hash) |
| [`md1img-unlock.img`](https://drive.google.com/file/d/1UoMhj9Pg-fjHU01ReqE80lfLJLRtZ8eo/view) | SIM unlock, P107 | `6e28c7c1…`, 76,089,472 B = P2 #65 "P107 container" |
| [`Moto-Clean.cmd`](https://drive.google.com/file/d/1sXSc8hAWMkS-eUkkdWu8dtHOpM3LXx_n/view) | OTA + preload disable | `ad7bf5cd…` |
| [retail `…-4-2_…_cid50_CFC`](https://drive.google.com/file/d/1YLBQ9J-UCEOegaqgZN30KJwOHySARyvI/view) | full retail firmware | `0d88fbb5…`, 5,706,308,767 B = P2 #65 |

- **Version gate:** the files are for `-4-2` or lower; build your own for newer builds (P2 #1, #94). On `-4-3`: "the OP's files flashed directly worked" (P2 #110, #149) vs re-adapted
  lk + a baseband-matched modem (P2 #44), and P2 #65 says it doesn't apply to -4-3/P144: [contradicted]. A P107 modem on a P144 phone is the risky part.
- **The retail package isn't needed.** Flash lk + md1img only (P2 #45, #144, #176, #180) [multiple]. Its XML has NV erase, GPT/preloader and `efuseBackup` writes, so never run it blindly (P2 #65).

**Variant 1: never unlock. This is the OP's latest method (P2 #134) [multiple: P2 #147, #149, #164, #168, #176]**:
remove the SIM → fastboot → `fastboot flash lk_a lk-moto2026.img` + `fastboot flash md1img_a md1img-unlock.img` (the suffix follows the current slot) → factory reset
(`fastboot -w` / recovery) → set up **offline** → adb → temp root (+ KernelSU "ADB root") → disable OTA. Result: no activation page, no carrier logo, AVB green (P2 #1, #71).

**Variant 2: unlock → patch → relock (P2 #65 on 4 phones; #44, #58, #110) [multiple]**: route A unlock → `flash lk_a <retus>` → `reboot bootloader` → `flash md1img_a`
→ `erase userdata` + `erase metadata` → verify → remove temp root → relock (§6). End state: `locked + green + retus + P107 + OTA disabled + no su`. Phones already unlocked via P1 also convert (P2 #31, #161).

**P2 #65 details (one detailed report, 4 phones):**
- retus LK vs stock: **9 payload bytes** change. Other lk sub-images are unchanged, and 5 internal signature/hash checks pass.
- Base images: stock `lk_a` `136bf013…` and stock `md1img_a` (200 MiB) `432096bc…`. **Our check: both are byte-identical to phone #1's dumps.**
- Expected full-partition readback: lk_a (16 MiB) `d2660cc0c4b13cbac241c6b4f068334eb7b46fc46a3c74e4e7106a7256681de2`. md1img_a (200 MiB)
  `37de8e92352cf4ad44bb8a5b65f028b39ac029b5c96602871032c0c52cfafac4`.
- The retus LK **replaces the unlock-serial check**, so the old key doesn't guarantee you can unlock again after relock. Retus LK alone has still been followed by a
  "Phone Activation failure" once [single].
- Read-only backup list: A+B of `lk boot init_boot vbmeta md1img vendor_boot dtbo vbmeta_system`, with three-way SHA. `adb exec-out dd` can mix `dd` stats into the image.
- The patches survive factory reset but **the phone can't take OTA updates** (P2 #15, #43, #170; P1 #531) [multiple].

## 4A. Downgrade a newer/OTA'd phone to base `36.48-22-3-3` (topic 548192, VERIFIED 2026-11-20)

Source: USCardForum topic 548192 (OP @appletv, 2026-11-20). Tooling: `scripts/downgrade.sh`.
**Verified on our hardware 2026-11-20:** phones #7 and #8, both `-4-3`, downgraded to
base and **booted green** to the setup wizard (so a kept `-4-3` preloader does *not* enforce the rollback barrier §1
feared — AVB is the enforcer, and the rollback `lk` clears it). Post-downgrade reads: `ro.build.id =
W1WEOS36.48-22-3-3` (no sub-rev), `ro.build.fingerprint … /36.48-22-3-3/f9ed7c-f9aab`, `version-bootloader …
36.48-22-3-3-f9ed7c`, still `oem_locked`. Base baseband is **not P107** (`…V18.6.10.02.277.02R`); it returns to P107
after the `-4-2` upgrade in §4B. Both phones went base → `-4-2` (§4B) → end state D with no brick.

**Why we need it.** Our route-D `lk-moto2026.img` was patched from `-4-2`, so `route_d.sh` only flashes it onto a
base-or-`-4-2` phone. Phones #7/#8 shipped on `-4-3`; an OTA can also push a phone past `-4-2` (§1: auto-updates happen
even with Smart updates off). §1 also records the blocker this route answers: P2 #44/#65 measured `-4-3` at AVB rollback
index 7 and said it **can't** take the `-4-2` retail package. Topic 548192 sidesteps that by downgrading to **base
`36.48-22-3-3`** with a patched `lk` that handles rollback/AVB, not by force-flashing the `-4-2` package.

**The two `lk` (both keep AVB green, flash while BL locked):**
- `lk-rollback-3-3.img` — permits the downgrade but **still verifies signatures**. Our default (keeps an
  AVB-enforcing posture; fine because the base firmware is properly signed).
- `lk-no-avb-3-3.img` — **disables AVB entirely** (boots any system while locked). Only needed for persistent root
  while locked — a route we have **not** built (`downgrade.sh --no-avb` flashes it; the KSU-while-locked end state is TODO).

**Flow** (post #1; `downgrade.sh` automates with typed confirms, deriving the firmware steps from the zip's
`flashfile.xml` each run): flash the downgrade `lk` → **reboot bootloader** → flash the full base RETUS firmware
**except** its `lk`/`gpt`/`preloader` partitions and the `nvdata` erase (device-unique IMEI/RF cal; the flashfile's
`cid 0x0032` header + `oem fb_mode_*` bookkeeping are skipped too, ours is `0x0033`) → flash `md1img-unlock-3-3.img`.
The phone is left in fastboot on base; bring it up to the fleet's `-4-2` with `scripts/upgrade.sh` (§4B), then
`route_d.sh <serial>` for end state D. Pitfalls (post): won't flash → confirm the `lk` took; won't boot → the
firmware overwrote `lk`, reflash it.

**Outcome (2026-11-20).** Ran clean on #7 then #8. The `-4-3` → base boot came up **green**, settling the §1 worry:
the retained preloader/eFuses did **not** block the lower build, so the rollback barrier is AVB-only and the rollback
`lk` clears it. The BL stays locked throughout, so a wrong image would still be a brick risk — keep the typed confirms
and (for a brand-new build family) still validate on one phone before the rest. `md1img-unlock-3-3.img` is flashed here
but then overwritten by §4B's `-4-2` firmware, so for the downgrade→upgrade→D pipeline the real SIM unlock is route D's.

## 4B. Upgrade a base phone to the fleet's common `-4-2` (VERIFIED 2026-11-20)

Tooling: `scripts/upgrade.sh`. After §4A a phone is on base `36.48-22-3-3`, but the fleet (#1–#6) runs
`W1WEOS36.48-22-3-3-4-2`. `base → -4-2` is a **forward** flash (raises the AVB rollback index — allowed), unlike the
blocked `-4-3 → -4-2`; that is why a `-4-3` phone goes via base first (§4A), then here.

**Flow** (`upgrade.sh`, from the `-4-2` `flashfile.xml`): in fastboot, locked, slot a → flash the full `-4-2` firmware
**including `lk_a`** (we want the stock `-4-2` bootloader so the phone matches a fresh `-4-2` device and route D's proven
input) but **not** `gpt`/`preloader` — a `-4-2` preloader over a `-4-3` one is a *preloader downgrade*, the worst brick
risk on a locked BL, and the §4A green boot already proved the kept preloader is fine — and **not** the `nvdata` erase.
Stock `-4-2` `md1img` is flashed here; route D re-flashes the SIM-unlock modem. Leaves the phone in fastboot on a clean,
locked, stock `-4-2`; next is `route_d.sh <serial>`.

**Gotcha — stale baseband in fastboot.** After the `-4-2` flash, `getvar version-baseband` (and `version-bootloader`)
keep reporting the *base* values until a full Android boot loads the new modem/`lk`; a `reboot-bootloader` does **not**
refresh them. So route D's gate-fastboot (which pins P107) sees a false negative straight after an upgrade. Run it with
`GATE_BASEBAND_ANY=1` for that one invocation (`lib.sh` honours it); the real baseband is still verified later at
gate-android on live props (both #7/#8 read P107 / green / `retus` there). #7 and #8 finished end state D this way.

## 5. Modem / SIM unlock (`md1img`)

- The lock is in nanoMIPS `md1rom`. The patch makes 2 check functions return "allow" and skips 6 deny branches, about **32 bytes**, plus CERT2 hash metadata. No IMEI/NV edit, no NCK (P1 #293, #303, #340;
  P2 #65) [multiple].
- [`Sinclair19/vegas26-modem-unlock`](https://github.com/Sinclair19/vegas26-modem-unlock/blob/main/docs/vegas26-unlock.md) (from kansas, P1 #300) is verified on **`-4-3`**, slot A, 1 device (P1 #478).
  **Offsets are per build**: its builder rejects `-4-2` (P1 #477). `-4-2` works with the P2 file or an adapted patch (P1 #479, #515; P2 #25, #58, #65) [multiple].
- **Our check:** two different `-4-2` patched modems exist, the forum's `md1img-unlock.img` (76,089,472 B, `6e28c7c1…`) and vegas-freedom's on phone #1 (76,088,448 B, `f6bd718f…`).
- The patched success path can call `smu_nvram_write(0xef13)`, so new persistent baseband state can't be ruled out (P2 #65, static) [single].
- UI still shows **"Network lock: locked"** (About phone → Device details) while foreign SIMs work (P1 #233, #500, #545; P2 #53, #109, #116, #146) [multiple].
- Survives factory reset (P1 #542, #545) [multiple]. An OTA, official flash or slot switch overwrites it (P1 #303; P2 #65).
- "Flash md1img_b too after testing" (P1 #344) vs "A only" (P1 #334; P2 #65): [contradicted].
- Carriers that worked: T-Mobile (pSIM/eSIM), AT&T eSIM, Fi, Red Pocket, China Mobile/Unicom/Telecom, Cricket. VoLTE, Wi-Fi calling and 5G SA OK (P1 #302, #333; P2 #65, #105, #114).
  Verizon eSIM fails because of an IMEI whitelist (P2 #81, #111, #150), but a Visible line worked (P2 #162, #188): [contradicted]. Xfinity refused (P2 #106).

## 6. Relocking to locked/green

- **Newer view: relock works with the patched lk in place and gives green** (P2 #44, #58, #65, #110) [multiple]. The older P1 view was "don't relock" (P1 #194, #385), and its rollback = stock lk + `oem lock` (P1 #55).
- Use **`fastboot flashing lock`, not `oem lock`.** This lk's `oem lock` statically erases `userdata/metadata/nvdata/md_udc`; `flashing lock` has no direct erases (P2 #65) [single].
- The OEM-unlock permission must be on. Phone 1 printed OKAY but **did not lock** ("enable OEM permission first"). Check `getvar securestate` = `flashing_locked`. Fix (temp root):
  clear the `no_moto_oem_unlock` restriction with `pm set-user-restriction --user 0 no_moto_oem_unlock 0`, then `service call oem_lock 4 i32 1`. Getters are `oem_lock 5` (user) and `3` (carrier). Continue only if both are true, then go straight to
  fastboot. Transaction numbers are valid only for `framework.jar 062b644e…` / `services.jar 85c42262…` (P2 #65) [single].
- First boot after relock can show a **data-corruption prompt**, fixed by factory reset (P2 #44, #58, #65) [multiple]. Whether you can flash or unlock again once locked is unknown (P2 #65).
- **Ours (phone #1, 2026-11-18, A→D):** OEM-permission fix under root → in fastboot: stock `init_boot_a`, retus
  `lk_a`, `md1img-unlock` to `md1img_a`, `erase userdata` + `erase metadata` → `fastboot flashing lock` →
  `flashing_locked`. First boot: **no corruption prompt** (we erased userdata+metadata before locking), green,
  `carrier=retus`, no activation page. Then `route_d.sh --from setup`. Details: phone #1's record (`devices/<serial>.md`, kept local).
- Flashing `lk`/`md1img` while locked works on `oem_locked` (route D on #2). On a relocked phone (`flashing_locked`)
  it is expected to work too but is untested: #1's D images went in before the lock. Going back to A from D:
  `tools/locked/README.md` "Return to A" [UNVERIFIED].

## 7. Play Integrity / DRM

- **AVB green ≠ Play Integrity pass** (P2 #65). No PI verdict was posted for route D. P1 #391's "three green" had no details [single].
- Unlocked (orange) means PI fails (P1 #55). Widevine reports L1 but is broken after unlock (P1 #389) [single]. Detection keys on TEE/DRM (P1 #409).
- Locked/retail: a China Mobile app stopped flagging root (P2 #44), Google Wallet works (P2 #165, #167), and "TEE damaged" appeared after retail pkg + patch (P2 #154). All [single].
- **Our check on D (2026-11-20, one D phone, SPIC, online, no Google account): no verdict.** Play Store disabled (declutter default) → `-2 PLAY_STORE_NOT_FOUND`, the API needs Play Store. Play Store enabled → `-12 GOOGLE_SERVER_UNAVAILABLE` on 4 tries. D stays unverified; needs a signed-in account to settle.

## 8. OTA blocking and Moto-Clean

- Rooted: a KSU module doing UID REJECT on `ccc.ota`/`ccc.devicemanagement`/`tracfone.preload.accountservices` (P1 #166). UIDs differ per phone, so don't copy them (P2 #65).
- **Unrooted (D)**: temp root once, disable OTA, remove root. It stays disabled across reboots, and only a factory reset re-enables it (P2 #64, #101, #103, #171) [multiple]. Plain `pm disable-user` is refused even
  as root (P2 #61, #65). P2 #65's method: `service call package 90 s16 com.motorola.ccc.ota i32 3 i32 -2147483648 i32 <user> s16 root` (DISABLED_USER=3 +
  SKIP_PROTECTED_PACKAGES). Read back with `service call package 91 …` and expect 3. Add `ota_disable_automatic_update 1` + appops `RUN_IN_BACKGROUND`/`RUN_ANY_IN_BACKGROUND ignore`. Same framework-SHA caveat [single].
- **Moto-Clean.cmd**: PowerShell in a base64 zip payload, which is why the OP saw "encoded" package names. Our decode, not run: it needs temp root, **stops the framework and rewrites
  `/data/system/users/0/package-restrictions.xml`** to `enabled=3` for about 140 packages (incl. `ccc.ota`, `motorola.paks`, `com.google.android.setupwizard`, `motorola.setup*`,
  `provisioning`, `faceunlock`). It also clears their data, uninstalls FB/IG/WhatsApp/Glance for user 0, and sets `persist.sys.zram_wb_enabled false`. P2 #65 advises against XML edits. **Factory reset crashed
  after Moto-Clean** (P2 #112) [single].
- "OTA fails anyway: package verification failed" (P2 #142) [single]; don't rely on it. Whether an OTA overwrites lk/md1img is untested (P1 #531). Stock B lk/md1img are all-zero.

## 9. Failures, bricks, recovery

| Failure | Cause / fix | Ref |
|---|---|---|
| Red-text boot → brick | `cid` edited while locked. Recovered by unlocking via lk and restoring the `cid` backup | P1 #376 [single] |
| IMEI loss / `0xDEAD` | `cid` is Moto-signed, so never edit it. **Back up `cid` + `persist`** | P1 #385, #386 |
| No boot (AVB) | system file deleted while locked. Use `pm uninstall --user 0` | P2 #11 |
| Hard brick | lk from another build/phone | P1 #55 |
| Modem builder refuses | wrong build. Re-adapt, don't skip hash checks | P1 #477 |
| Lock OKAY but still unlocked | OEM permission off (§6) | P2 #65 |
| Corruption prompt after relock | factory reset | P2 #44, #58, #65 |
| Factory reset crashes | after Moto-Clean | P2 #112 |
| Play Store won't self-update | copy it from another phone | P2 #156 [single] |
| Lost fastboot | DA/auth rescue unverified. Stock-modem restore untested | P2 #65 |
| Exploit window closed | phone went online before OTA was blocked | P1 #397, #438 |

## 11. Relevance to our pipeline

**Route D (variant 1) looks cheaper than A for phones #2–#8.** No `oem unlock` means no `nvdata/md_udc` wipe, no orange state and no relock dance. It needs only fastboot + reset and
one temp root for the OTA disable. Phone #1's stock `lk_a`/`md1img_a` are byte-identical to P2 #65's base, and our `lk-moto2026.img`/`md1img-unlock.img` match P2 #65's verified
candidates. Every phone still needs the build/MBM/size gates.

| Finding | Maps to |
|---|---|
| lk + md1img flash while locked | `scripts/route_d.sh` (`tools/locked/README.md`): gate on `oem_locked`, not `flashing_unlocked` |
| readback `d2660cc0…` / `37de8e92…` | post-flash gate (full lk_a / md1img_a) |
| D has no KSU modules | no `ota_block`/`charge_limit`/`hide_apps`. OTA = temp-root `service call package 90` (check framework SHA) + `ota-off` + offline. No unrooted charge limit in the threads. **Our finding (2026-11-18):** Moto Battery protection (80%, `phone.sh charge-protect`) is enforced by system_server, so D gets a charge cap without root |
| factory reset is part of D | run `phone.sh apps/declutter/qs` after the last reset. `home-clear`/`black` need root |
| Moto-Clean | don't use as-is. `declutter` + binder OTA disable cover it |
| relock (variant 2) | only for A→D (e.g. phone #1). OEM-permission fix + `flashing lock`, corruption risk |
| `cid`/`persist` backup | already in phone #1's dump |
| PI / Wallet | only D could pass. Untested on D: no verdict yet (needs Play Store + a Google account, see §7). Phone #1 (A) = `NO_INTEGRITY` |

**Conflicts with our docs (not edited):**
1. [bl-feasibility.md](bl-feasibility.md) Gate 2 says "must be `flashing_unlocked` before any modem flash". P2 flashed `md1img_a` while `oem_locked` (P2 #1, #134, #147, #168, #176).
2. [bl-feasibility.md](bl-feasibility.md) Gate 3 says "Modem patch verified only on `-4-3`… (incl. `-4-2`) is unverified". That is stale against the SIM section in the maintainer's open-items notes (not published) and phone #1, and against P2.
3. Runbook *Rollback* says stock `lk_a` + `fastboot oem lock`. P2 #65: `oem lock` erases `nvdata/md_udc`; use `flashing lock` after the OEM-permission fix. Relock also works with the patched lk left in.
4. [ota.md](ota.md)/device notes say "`pm disable` refused even with root; durable block = `ota_block` module; unrooted falls back to `ota-off` + offline". P2 #65 persists DISABLED_USER=3 without root.
5. Runbook *Irreversible costs* (PI/Widevine fail) is true for A. For D the threads show green + retail, PI unproven.
6. A/B slot policy is unsettled in the threads (P1 #61 vs P2 #65 vs P1 #344). Not a conflict, but an OTA to all-zero B was flagged as a risk (P1 #61, #350).
7. post-root-procedure trade-in tip: `tradeinmode evaluate` only works from the first-boot wizard's limited adb (P1 #519). After setup it isn't available (P1 #511).

## 12. Other third-party links

Valhalla https://github.com/crabcakes97/Valhalla (fork https://github.com/emrickk/Valhalla) · kansas https://github.com/s0meguy1/kansas-unlock,
https://github.com/Articfox291/kansas-modem-unlock · TestDPC https://github.com/googlesamples/android-testdpc · ManageEngine https://mdm.manageengine.com/ ·
sidemdm https://github.com/lukeponio/sidemdm · detection tools (file host, not downloaded) https://share.feijipan.com/s/lfzTrB9k · Reddit bypass guide: r/StraightTalk `1wmesee` (deleted, P1 #581).
