# tools/locked — route D + downgrade (BL stays locked) files

Third-party files from USCardForum, downloaded from the OPs' Google Drive links. They are gitignored and kept only locally. Verify them with `shasum -a 256 -c SHA256SUMS`. Two sets:
- **topic 547067** (downloaded 2026-11-18): the route-D patched `lk` + unlock modem + full `-4-2` firmware (tables below).
- **topic 548192** (downloaded 2026-11-20): the *downgrade* set — brings a newer/OTA'd phone back to base `36.48-22-3-3` so the `-4-2` route-D tooling works on it. See "Downgrade set" below and `scripts/downgrade.sh`.

| File | Size | What it is | Status |
|---|---|---|---|
| `lk-moto2026.img` | 3.5 MB | patched `lk`: carrier→retail, BL stays locked. Flash with `fastboot flash lk_<slot>`. | sha256 matches the pin in the plan |
| `lk-moto2026-unlock.img` | 3.5 MB | patched `lk`: carrier→retail + BL unlock | not in our plan, kept for reference |
| `md1img-unlock.img` | 76 MB | patched modem (SIM/network unlock). Flash with `fastboot flash md1img_<slot>`. | sha256 matches the pin. Differs from our verified-live `f6bd718f…` (vegas-freedom) |
| `Moto-Clean.cmd` | 14 KB | Windows script: disables OTA/preloads via package-restrictions (needs temp root + KSU adb root) | reviewed (decoded), not run |
| `VEGAS_OG_SYS_W1WEOS36.48-22-3-3-4-2_…_cid50_CFC_Filewale.com.xml.zip` | 5.7 GB | full retail firmware for our exact build | `unzip -t` OK |

Constraints from the post:
- Works only on build `36.48-22-3-3-4-2` or lower.
- Pick the slot suffix to match the current boot slot.
- Factory reset after flashing.

**Status: in use.** `lk-moto2026.img` + `md1img-unlock.img` are route D (`scripts/route_d.sh`, which does the hash gate,
fastboot gates, typed confirms, readback hashes and an optional foreign-SIM test). Proven on #2 (fresh, `oem_locked`)
and #1 (converted from A, relocked with `fastboot flashing lock`, 2026-11-18).

## Downgrade set — topic 548192 (base `36.48-22-3-3`, VERIFIED 2026-11-20)

Why: our `lk-moto2026.img` was patched from build `-4-2`, and `route_d.sh` only flashes it onto base/`-4-2` phones.
Phones #7/#8 arrived on `-4-3` (newer); an OTA can also push a phone past `-4-2`. Topic 548192 downgrades such a phone
back to base retail `36.48-22-3-3` (patch 2025-12-01), from where route D works again. Driven by `scripts/downgrade.sh`.
**Verified 2026-11-20 on #7 and #8**: both `-4-3`→base booted green, then upgraded to
`-4-2` (`scripts/upgrade.sh`, below) and reached end state D with no brick. The base build's baseband is **not** P107;
it returns after the `-4-2` upgrade. Both the base firmware (`FW_BASE_ZIP`) and the `-4-2` package (`FW_42_ZIP`, in the
route-D table above) have their sha256 pinned in `SHA256SUMS`.

| File | Size | What it is | Status |
|---|---|---|---|
| `lk-rollback-3-3.img` | 3.5 MB | downgrade `lk`: allows rollback, **still verifies signatures**, AVB green, flashes while locked. `downgrade.sh` default. | sha256 pinned in SHA256SUMS |
| `lk-no-avb-3-3.img` | 3.5 MB | downgrade `lk`: **AVB fully off** (boots any system while locked). Needed only for persistent root while locked (`downgrade.sh --no-avb`; that end state is not built yet). | sha256 pinned |
| `md1img-unlock-3-3.img` | 76 MB | SIM/network-unlock modem for the base build. Flash with `fastboot flash md1img_<slot>`. | sha256 pinned |
| `XT2617-1_VEGAS_OG_RETUS_16_W1WEOS36.48-22-3-3_…_cid50_CFC.xml.zip` | 5.6 GB | full **official RETUS** base firmware (has `flashfile.xml`, `super.img_sparsechunk.0..25`, `lk.img`, `preloader.img`, `PGPT`). | `unzip -l` OK; sha256 pinned |

Flow (post #1; `downgrade.sh` automates it, typed confirms, derives the firmware steps from `flashfile.xml` each run):
1. flash `lk-rollback-3-3.img` (or `--no-avb`) to `lk_<slot>` → **reboot bootloader**.
2. flash the full base firmware **but NOT** its `lk`/`gpt`/`preloader` partitions, and **NOT** the `nvdata` erase
   (device-unique IMEI/RF cal — see §"Retail zip vs #1"; the flashfile's `cid 0x0032` header and `oem fb_mode_*`
   bookkeeping are also skipped, ours is `0x0033`). Pitfall: if it won't boot afterwards, the firmware overwrote `lk` —
   reflash the downgrade `lk`.
3. flash `md1img-unlock-3-3.img`.
4. `scripts/upgrade.sh <serial>` → forward-flash the full `-4-2` package (`FW_42_ZIP`) **including `lk_a`** but not
   `gpt`/`preloader` (keeping the preloader avoids a preloader downgrade) and not the `nvdata` erase. Lands on a clean,
   locked, stock `-4-2` — the fleet's common build and route D's proven input.
5. then `scripts/route_d.sh <serial>` → end state D (flashes `lk-moto2026.img` carrier=retus + unlock modem, erases,
   configures). Straight after an upgrade, fastboot still reports the stale base baseband, so run route D once with
   `GATE_BASEBAND_ANY=1` (gate-android re-checks the real P107 on live props).

## Return to A from D (UNVERIFIED — nobody has done it on our phones)

D is a locked phone with a different `lk`, which is the same starting point #1 had before its original unlock. So the
A route should work again:

1. **While locked, flash an unlock-capable `lk`** to the active slot (`lk` is outside AVB, so it flashes while locked):
   - the serial-bound one built from that phone's stock `lk_a` with vegas-freedom `lk_auto_patch.py --preset unlock-serial`
     (what #1 used: `914acfce…`, key from `lk_keygen --serialno <serial>`), or
   - the forum's `lk-moto2026-unlock.img` (retail + unlock; not used by us).
   Stock `lk` alone (retail zip `lk.img` = Tracfone stock `b6e5a74f…`) **cannot unlock**: it is carrier-locked
   (`oem_locked`, carrier allow = false). Use it only to restore stock.
2. OEM-unlock permission on (temp root: `pm set-user-restriction --user 0 no_moto_oem_unlock 0`, `service call oem_lock 4 i32 1`).
3. `fastboot oem unlock <serial-bound key>` → wipes data, orange. Per P2 #65 (static reading, single source) this path
   also **erases `nvdata`/`md_udc`**: the modem normally rebuilds them from `nvram` (IMEI/RF cal backup, not erased);
   if IMEI comes back null, restore that phone's own `nvdata` from its backup. Never cross-flash between phones.
4. Then the legacy A flow: `reroot.sh` → `permroot.sh` → `postroot.sh` (`docs/post-root-procedure.md`).

Risks: an `lk` for the wrong build/phone is a hard brick (match the full MBM string). Keep the retail zip as the unbrick image.

## Retail zip vs phone #1 (live read, 2026-11-18)

I took the sha256 of the first N bytes of each phone #1 partition, where N is the size of the matching image in the zip. Every boot-chain image is byte-identical to the retail zip: preloader, tee, mcupm, pi_img, sspm, dtbo, logo, spmfw, scp, **vbmeta, vbmeta_system**, dpm, gz, vcp, connsys_bt, boot, vendor_boot.

Only three partitions differ, and all three are ones we patched on #1:
- `lk_a`: the retail `lk.img` is `b6e5a74f…`, the same as the Tracfone stock lk.
- `md1img_a`: the retail `md1img.img` is `dab9e69e…`, the same as the Tracfone stock modem.
- `init_boot_a`: KSU-patched on #1.

Since vbmeta is identical, the signed system is very likely the same build. The "retail" behaviour comes from the patched `lk` (carrier→retail), not from the zip. The zip still has two uses: a full signed restore/unbrick image for locked phones, and its stock `lk.img` and `md1img.img`. Note the zip's flashfile also flashes `gpt` + `preloader`, **erases `nvdata`** and expects `cid 0x0032`, while our phones report `0x0033`. The `super` contents were not compared directly.

## What `carrier=retus` changes (rules read from phone #1, 2026-11-18)

Here is how it works. The lk passes `androidboot.carrier` at boot, which becomes `ro.carrier`. On first boot (fresh `/data`), Moto's package manager applies two sets of rules:
- `{product,system_ext}/etc/enable-disable-packages/*.xml`: per package, a `default_action` plus `<criteria channel=... [mccmnc/gid]>`.
- `{product,system_ext}/etc/filter-system-apps/*.xml`: a module is installed only if `ro.carrier` is in its list.

That's why route D needs `fastboot -w`.

There are 147 rules and 34 of them differ between tracfone and retus. I computed this with `scripts/carrier_eval.py <dir-with-pulled-etc> tracfone retus`. A `*` marks rules that also depend on the SIM's mccmnc/gid.

**retus turns these OFF (they were on under tracfone):**
- Activation and accounts: `tracfone.preload.accountservices` (protected, which `pm disable` refuses), `motorola.tracfone.setup`, `motorola.tracfone.rsu`, `motorola.setupwizard.devicesetup`, `motorola.extensions.tracfone`.
- Overlays: `setup.overlay.tracfone`, `launcherconfig.overlay.tracfone`.
- Apps: `swishme.tracfone`, `tracfone.generic.mysites`, `handmark.expressweather`, `huub.tiger`.
- Modules: TFGamesHub, TFIgnite, VzwMVS, expressweatherFull.

**retus turns these ON:**
- Modules: MotorolaIgnite (app installer), IqiMotMetrics (telemetry), MVS-Lite, expressweatherStub.
- `inmobi.weather`*, `aura.oobe.motorola`*, `launcher.overlay.motolauncheroverlayna`, `setup.overlay.skipglance.vegas26`, `euiccpartnerapp.overlay.na`.

These still need our declutter pass afterwards.

**Not carrier-gated (present either way):** `ccc.ota`, `motorola.paks`, Gboard, and the Google/Moto consumer apps.
