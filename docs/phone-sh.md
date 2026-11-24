# `scripts/phone.sh` reference

```bash
scripts/phone.sh <command> [serial|all]     # no target = the single connected phone
```

| Command | What it does | Changes device? |
|---|---|---|
| `info` | identity, boot state, users/owners, hardware, battery, network | no |
| `check` | BL gate 1 (getprop) + PASS/FAIL verdict | no |
| `fastboot` | BL gate 2: `adb reboot bootloader`, `getvar` only, reboot back | reboots only |
| `ota-off` | OTA stage 1 (init, no root; see [ota.md](ota.md)) + verify — re-run after every reboot | yes, reversible |
| `ota-off-root` | OTA stage 2 (after root): `pm disable` + iptables DROP on OTA uid (v4+v6) | yes, reversible |
| `ota-status` | show every OTA layer's state | no |
| `ota-on` | undo `ota-off` / `ota-remove` | yes |
| `backup` | full partition dump → gitignored `backups/<serial>_<build>_stock_*.tar.zst`; **skips if it already exists** (needs root) | reads only |
| `rm-workprofile` | remove org-owned sidemdm work profile via the DPC's own UI (needs root) | yes |
| `debloat` | `pm uninstall -k --user 0` of `BLOAT_PKGS` (FB/Fitbit); reports `KEEP` for protected priv-apps (`ccc.ota`, `ccc.devicemanagement`): use the module | yes, reversible |
| `wake` | keep screen awake + Always-On Display off + min brightness + mute + animations off | settings |
| `park` | rack-safe idle: stay-on off, AOD off, min brightness, mute, offline, screen slept | settings |
| `offline` | Wi-Fi + mobile data + Bluetooth off (a foreign SIM brings data up otherwise) | settings |
| `apps` | install the basics from `tools/apps/` (hash-pinned): Fossify Messages (default SMS), Fossify File Manager, Firefox (default browser), F-Droid, Aurora Store | yes |
| `declutter` | `pm disable-user` of the carrier/Moto/Google app lists (`DECLUTTER_*` in `phone.sh`, incl. Play Store, Gemini, Moto Secure, Dolby UI); falls back to a user-0 uninstall; reports protected `KEEP`s | yes, reversible (`pm enable`) |
| `home-clear` | empty home screen: delete all icons/widgets from the launcher DB (old DB backed up in `logs/`) + stop auto-adding new icons (root) | yes |
| `black` | black wallpaper for home + lock (writes `/data/system/users/0/wallpaper*`, restarts SystemUI) + dark theme (root) | yes |
| `qs` | Quick Settings tiles = `QS_TILES` via `cmd statusbar set-tiles` (no Wallet, GIF maker, System update, …) | yes |
| `no-anim` | all animation scales 0 (also run by `wake`) | settings |
| `mute` | every audio stream to its own minimum (some streams can't go below 1) + ringer SILENT | settings |
| `rm-sidemdm` | uninstall the leftover sidemdm app copy in the personal profile | yes |
| `record` | write/refresh `devices/<serial>.md` (auto snapshot; manual notes kept) | no |
| `full` | `info` + `check` + `ota-off` + `fastboot` + `record` | as above |

Every run is appended to `logs/<serial>.log` (gitignored). Needs USB debugging on
(Settings → About phone → Device details → tap **Build number** ×7 → System → Developer options → **USB debugging**).

**Standard init per phone (stock / A only; D phones use `route_d.sh`):** enroll (QR) → remove work profile → Smart updates off + USB debugging →
`scripts/phone.sh ota-off` (before any internet Wi-Fi) → `rm-sidemdm` → `check` → `fastboot` → `record`.
After any reboot: `ota-off` again (or `scripts/reroot.sh` once permanent root isn't in place yet).

Activation (QR enrollment): [activation-qr.md](activation-qr.md). BL gates behind `check`/`fastboot`: [bl-feasibility.md](bl-feasibility.md). OTA layers behind `ota-off`: [ota.md](ota.md).

## Working on several phones at once

Every `scripts/phone.sh` call is pinned with `adb -s <serial>`, and `backup` sets `ANDROID_SERIAL`, so phones never
collide — drive each by its serial (from `adb devices`). USB 2.0 (~35 MB/s) on individual per-port controllers means
concurrent dumps each run full-speed (~12 GB ≈ 6 min), so 8 phones dump in ~6 min wall-clock, not ~48.

```bash
adb devices                                   # list serials
for S in SERIAL1 SERIAL2 SERIAL3; do
  scripts/phone.sh backup "$S" &              # parallel, each pinned; archives into backups/
done; wait
```

Caveats:
- **One unpinned job breaks the rest:** never launch `backup_partitions.py` directly (bare `adb`) while other devices
  are attached — use `scripts/phone.sh backup <serial>`. The very first phone-#1 dump was launched unpinned, so finish
  it before plugging in a second phone.
- Physical per phone: the DFRoot **Run exploit** tap (temp root) and the data-wiping `fastboot oem unlock`.
- `scripts/phone.sh <cmd> all` loops **sequentially**; for real parallelism launch per-serial jobs as above.
