# BL feasibility (read-only, three gates)

Nothing here writes partitions or wipes data. Actually unlocking (Valhalla) = factory reset; decide after this.

**Gate 1 — identity via adb** (`scripts/phone.sh check`): reads `ro.product.model`, `ro.product.device`,
`ro.boot.hardware.sku`, `ro.build.display.id`, `ro.build.version.security_patch`, `gsm.version.baseband`,
`ro.boot.slot_suffix`, `ro.boot.flash.locked`, `ro.boot.verifiedbootstate`, `ro.oem_unlock_supported`,
`vendor.gsm.sim.slot.lock.device.lock.remain.count`.

| Rule | Meaning |
|---|---|
| `vegas26` + `XT2617V` | model in scope; mismatch → stop, apply no patch |
| security patch ≤ **2026-09-01** | inside the exploit window — the hardest rule; **one OTA closes it** |
| `ro.oem_unlock_supported` empty | lk-patch route only; official `fastboot flashing unlock` gives no token |
| `flash.locked=1` + `green` | untouched starting point; `0`/`orange` = already unlocked |

**Gate 2 — fastboot getvar** (`scripts/phone.sh fastboot`): `product`=vegas, `sku`=XT2617V,
`securestate` (locked now — this firmware reports **`oem_locked`**; must be `flashing_unlocked` before any
modem flash), `current-slot`=a, `partition-size:md1img_a` (0x0C800000 = 209715200 bytes).

**Gate 3 — build vs known-verified values** (BL and modem are separate verdicts):

- **BL**: Valhalla lists "Moto G Power 2026 BL Confirmed Unlocked" (works with OEM toggle greyed out) but needs
  the **stock `lk.img` for your exact build** next to the script. BL feasible = patch ≤ 2026-09 + vegas26/XT2617V
  + matching `lk.img`. Final word: Valhalla **Check Device** (probe only, no writes) before **Run Valhalla**.
- **Modem patch**: verified only on `W1WEOS36.48-22-3-3-4-3` + baseband
  `MT6835O_NR17.RC.MP.V18.6.6.P107.02.309R`. Any other build (incl. `-4-2`) is unverified: do a full-image check
  (209715200 bytes + stock SHA256) first, or expect a brick.
- Patch > 2026-09 → not unlockable, don't try. SKU mismatch → stop.
