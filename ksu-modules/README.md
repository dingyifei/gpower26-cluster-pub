# ksu-modules/  — KernelSU boot modules

> **Legacy: end state A (BL unlocked + permanent KernelSU).** No phone runs A since 2026-11-18; the default is route D
> (`scripts/route_d.sh`, see README). Kept for reference and for a possible return to A (`tools/locked/README.md`).

Version-controlled KernelSU modules, installed by `scripts/install_modules.sh` (or `postroot.sh`) into
`/data/adb/modules/<id>/`. KernelSU runs each module's `service.sh` at late_start on every boot.

| Module | What it does at boot | Why a module (not a one-shot) |
|---|---|---|
| `ota_block` (v2) | DROP all network for `com.motorola.ccc.ota` (IPv4+IPv6, `iptables -w`, `-C` first so no duplicates) + `ota_disable_automatic_update=1` + stop `update_engine` + bind-mount `system/etc/hosts` null-routing Moto OTA domains | `ccc.ota` is a protected priv-app `pm` can't remove; iptables rules clear on reboot, so they must be re-applied |
| `hide_apps` | `post-fs-data.sh` bind-mounts an empty dir over each app dir in `hidden.list` before PackageManager scans, so protected preloads (TFDevicePulse, PAKSFinance, Gboard) are not installed | They refuse `pm disable`/`uninstall` even as root (firmware protected-package policy). Remove the module + reboot to restore |

**None of these run on an unrooted phone** (`scripts/root_toggle.sh … unroot`): KernelSU in the patched `init_boot` is what runs
them. They stay on disk and come back with `reroot`.

**Retired: `charge_limit`** (2026-11-18). It held 57–60% by writing `0 1`/`0 0` to `/proc/mtk_battery_cmd/current_cmd` from a
`setsid` monitor loop (worked on phone #1, root only). Replaced by Moto **Battery protection** (80%, `scripts/phone.sh
charge-protect`), which is enforced by system_server + the Moto health HAL and so works unrooted and on locked phones.
`install_modules.sh` stops and flags it for removal on phones that still have it. Lesson kept: the ~100 mA
`input_current_limit` floor is above idle draw, so throttling never holds a level; only charge-off does.
`ota_block` waits for boot, runs once and exits.
