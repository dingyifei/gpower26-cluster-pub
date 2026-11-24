# Legacy route: end state A — "full-root" (BL unlocked + permanent root)

**In plain words:** A is the "I want root" option. The bootloader (the phone's lock) is unlocked and the phone has permanent root (KernelSU), so apps and modules that need root work. The price: an orange warning screen on every boot, Play Integrity / Wallet / DRM fail, and the unlock erases the phone. Most people should use end state D instead (`scripts/route_d.sh`, see the main [README](../README.md)).

No phone is in A now (phone #1 was converted to D on 2026-11-18). This is the old unlock + permanent-root route used on phone #1 before 2026-11-18, kept for reference and for a possible return to A ([../tools/locked/README.md](../tools/locked/README.md), UNVERIFIED).

**Then (BL unlock + root + backup), per [unlock-root-runbook.md](unlock-root-runbook.md):** temp-root (DirtyFrag + KernelSU, stays green) → `scripts/phone.sh backup` full dump (auto-skips if `backups/` already has this serial+build) → `patch_lk.py` → `fastboot oem unlock` (**wipes data**) → re-root → `init_boot` + KernelSU permanent root → `scripts/phone.sh ota-off-root`. Reviewed vegas-freedom code: no network/exec, backup is read-only `dd`, `patch_lk` only writes a file. SIM/network unlock is **not** part of init.

**After the unlock wipe, the node is re-rooted and cleaned fully over adb** — your only manual job is finishing
setup + enabling USB debugging. See [post-root-procedure.md](post-root-procedure.md):
1. `scripts/reroot.sh <serial>` — temp root (DFRoot+KernelSU UI automation via `scripts/uia.py`; runs `phone.sh wake` + `offline` first).
2. `scripts/permroot.sh <serial>` — **permanent root** (KernelSU LKM baked into `init_boot`; survives reboot, adb root every boot).
3. `scripts/postroot.sh <serial>` — remove work profile, uninstall sidemdm, debloat, basics (`apps`), `declutter`,
   `charge-protect` (Moto 80% charge cap), `home-clear`, `black`, `qs`, install KSU boot modules
   (`ksu-modules/`: `ota_block` durable OTA DROP, `hide_apps`), OTA block, record, park.
   Needs `tools/apps/` populated first (see [tools/apps/README.md](../tools/apps/README.md)).

The per-phone scripts take an explicit serial. They refuse to guess when more than one phone is attached, and `permroot.sh`
always requires one.

**Switching root off and on inside A.** The bootloader stays unlocked either way; only root changes. `scripts/root_toggle.sh <serial> unroot`
flashes the saved stock `init_boot_a` back (the BL stays unlocked and the SIM unlock stays). **KSU modules don't run
without root**: `ota_block` (OTA falls back to `ota-off` + staying offline) and `hide_apps`
(TFDevicePulse, PAKSFinance and Gboard come back) all stop. Everything stored as normal Android state survives: disabled apps,
default apps, home screen, wallpaper, QS tiles and settings. `scripts/root_toggle.sh <serial> reroot`
flashes the saved KSU image back, with no exploit needed. Both have `--dry-run` and ask you to type the serial before flashing.

**Rack safety (both end states).** Rack safety is built in: every session forces **Always-On Display off**, **minimum brightness**, **mute** and
**offline**. Charging is capped at **80%** by Moto **Battery protection** (charging capped at 80%, Manual schedule / Always): `phone.sh charge-protect`, works without root (system_server + Moto health HAL, so it holds rooted or not and survives
reboots). The old 57–60% `charge_limit` KSU module was retired 2026-11-18. `scripts/phone.sh park <serial>` sleeps the screen before racking. See
[post-root-procedure.md](post-root-procedure.md) and [ksu-modules/](../ksu-modules/README.md) (both legacy, end state A).
