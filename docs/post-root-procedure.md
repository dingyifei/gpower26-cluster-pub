# Post-unlock standard procedure (re-root → clean node)

> **Legacy: end state A (BL unlocked + permanent KernelSU).** No phone runs A since 2026-11-18; the default is route D
> (`scripts/route_d.sh`, see README). Kept for reference and for a possible return to A (`tools/locked/README.md`).

After `fastboot oem unlock` the phone is wiped and back at the setup wizard. From here on, **your only manual
job is: finish the setup wizard OFFLINE → enable Developer options → turn on USB debugging → accept the RSA
prompt.** Everything else is driven over adb (installs + UI automation). This is the standard sequence for
every phone after BL unlock.

Proven on phone #1 (XT2617V / `W1WEOS36.48-22-3-3-4-2`), 2026-11-18.

## Manual (you), on the phone
1. Setup wizard: **skip Wi-Fi / stay offline** (no SIM, no Google account). If activation is blocked and won't
   skip, run sidemdm enrollment on the LAN (six-tap QR) — the wizard's "Getting your phone ready…" is work-profile
   provisioning, NOT a firmware update. Reach the home screen.
2. **Disable Moto Smart updates** while still offline: Settings → search "update" → **Smart updates OFF**. (Do this
   before enabling Developer options; it's the one OTA toggle that lives only in the UI. The adb-settable
   `ota_disable_automatic_update` flag is handled later by `ota-off`/`ota_block`.)
3. **Settings → About phone → Device details → tap Build number ×7** → Developer options → **USB debugging ON**.
4. Plug in USB, accept the **"Allow USB debugging"** prompt (check "always"). `adb devices` should show `device`.

> **Future / trade-in tip (setup-wizard bypass).** `adb shell tradeinmode evaluate` one-shot bypasses the OOBE
> setup wizard (Trade-In Mode — binary `/system/bin/tradeinmode` is present on this build, `/metadata/tradeinmode/`
> exists). Handy to skip the wizard quickly. It arms an **auto factory-reset** on exit; if you do **not** want it to
> auto-wipe, delete the flag as root: `rm /metadata/tradeinmode/wipe`. (Verified the binary/dir exist on `-4-2`;
> `evaluate` behavior per field tip, confirm before relying on it at scale.)

## Automated (adb) — from here Claude does it all
Every adb session starts by keeping the screen awake (`svc power stayon true` + max screen timeout) so you
never have to poke the screen.

1. **Temp root:** `scripts/reroot.sh [serial]`  (also forces Always-On Display off + min brightness)
   - keep-awake, dismiss keyguard, install KernelSU v3.3.1 + DFRoot v4.7 (from `tools/root-apks/`),
   - DFRoot: select SU Manager = KernelSU (UI tap), tap **LAUNCH ROOT** (LKM loads, "Working [Jailbreak mode]").
   - **Key wiring step:** `su` is NOT auto-installed on this GKI LKM setup (`su: inaccessible or not found`,
     no `/system/bin/su`). Fix = KernelSU → **Settings → ADB Root** (runs adbd as root). The script toggles it;
     then `adb shell id` → `uid=0 … u:r:ksu:s0`. (Falls back to one reboot + re-exploit if needed.)
   - Note: DFRoot's SU-manager choice is an in-app SharedPreference; it can't be set from adb without root, so the
     spinner pick is a UI tap (automated via `scripts/uia.py`), not an adb setting.
2. **Permanent root:** `scripts/permroot.sh [serial]` — dumps `init_boot_a`, `ksud boot-patch` (KMI
   `android13-5.15`, `--allow-shell --enable-adbd`), flashes it. Root then **survives reboot with no exploit**
   and `adb shell` is root on every boot. Saves `backups/<serial>_<build>_init_boot_{a.stock,ksu}.img`
   (stock = bootloop fallback: `fastboot flash init_boot_a <stock>`). Verified: `/dev/df` gone after reboot.
3. **Cleanup:** `scripts/postroot.sh [serial]` runs:
   - `phone.sh rm-workprofile` — sidemdm makes an **org-owned** managed profile, so `pm remove-user` /
     `dpm remove-active-admin` are refused even as root. Only the DPC's own wipe works → the script launches
     sidemdm's `MainActivity` in the work-profile user and taps **Remove Work Profile → Continue → Remove Work
     Profile** via `uia.py`.
   - `phone.sh rm-sidemdm` — uninstall the user-0 app copy (works once it's no longer a device admin).
   - `phone.sh debloat` — `pm uninstall -k --user 0` for `BLOAT_PKGS` (Facebook suite, `com.motorola.ccc.ota`,
     ccc.devicemanagement, ccc.notification, Fitbit). `pm uninstall -k --user 0` removes the OTA app for user 0
     where `pm disable` was refused ("package is non-disable"). Reversible: `cmd package install-existing --user 0`.
   - `scripts/install_modules.sh` — installs the KernelSU boot modules (see `ksu-modules/`):
     **`ota_block`** (durable OTA egress DROP — `pm` can't remove the protected `ccc.ota`, and iptables clears on
     reboot, so a boot module re-applies it) and `hide_apps`. (`charge_limit`, a 57–60% charge-off module, was retired 2026-11-18 in favour of
     Moto Battery protection, below.)
   - `phone.sh ota-off-root` + `phone.sh record`.

## Rack safety (burn-in + battery)
- `scripts/phone.sh wake <serial>` (run at the start of every scripted session; built into reroot/postroot/permroot):
  keep screen awake on USB, **Always-On Display off** (`doze_always_on 0`), **minimum brightness** (`screen_brightness 1`).
- `scripts/phone.sh park <serial>`: rack-safe idle — stay-on off, AOD off, min brightness, 30s timeout, screen slept.
  Run before leaving phones on the rack (full screen left on while charging is the main burn-in risk).
- `phone.sh charge-protect`: Moto **Battery protection** (charging capped at 80%, Manual schedule / Always): `phone.sh charge-protect`, works without root.
  It enables `com.motorola.actions` (owner of the feature, so `declutter` keeps it), switches the setting on through the UI
  (`uia.py set`), then verifies `content://com.motorola.batteryconfiguration/config` → `charging_upper_limit=80` and
  `dumpsys battery` → `mUpperLimit:80`. BatteryService only binds the limit if actions was enabled at boot, so on a phone
  where declutter had disabled it, reboot once and re-run to verify. It does not drain: a phone at 100% sits *Not charging*
  and drifts down. UNVERIFIED: the resume point below 80% (`charging_lower_limit=-1`) over long holds.
- Declutter (all in `postroot.sh`, each also a `phone.sh` command): `apps` installs Fossify Messages/File Manager, Firefox,
  F-Droid, Aurora (hash-pinned from `tools/apps/`) and makes Fossify the default SMS app and Firefox the default browser; *then*
  `declutter` disables ~50 carrier/Moto/Google apps (Play Store and Gemini included; `pm enable <pkg>` undoes it).
  `com.tracfone.preload.accountservices` and `com.motorola.paks` are framework-protected and stay. `home-clear` empties the
  launcher, `black` sets a black wallpaper on home + lock plus dark theme, and `qs` trims the pull-down tiles. `wake` also sets animation scales to 0.
- Root off/on with the BL still unlocked: `scripts/root_toggle.sh <serial> unroot|reroot` (see [route-a-legacy.md](route-a-legacy.md)).

## UI automation helper
`scripts/uia.py -s <serial> {dump|find|tap|wait} "<text-or-desc>"` — `uiautomator dump` + `input tap` by element
text/content-desc (substring, case-insensitive). Used by `reroot.sh` and `rm-workprofile`.

## Still pending per phone (not yet automated)
- *(done, automated)* Permanent root via `scripts/permroot.sh` — see step 2 above.
- **Play Integrity / detection hiding** (KernelSU, not Magisk): with orange state + unlocked BL, Play Integrity
  BASIC fails regardless. For apps that only check SELinux/root: KernelSU "Hide SELinux modification" (Settings) +
  a module (e.g. Tricky Store / Play Integrity Fix) + per-app umount. Optional for a cluster node; record per phone.
- **Smart updates** UI toggle (Settings → search "update") — can't be set via adb; do once if the UI still shows it.
