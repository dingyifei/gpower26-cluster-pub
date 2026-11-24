# Disable OTA

Two stages. Stage 1 is part of every phone's standard init; stage 2 only applies once BL is unlocked and rooted.

## Stage 1 — init, no root (`scripts/phone.sh ota-off`)

Do it **after the QR enrollment reaches the home screen and before joining any internet Wi-Fi**.

1. **UI (manual)**: Settings → search "update" → Moto **Smart updates** off.
2. **`scripts/phone.sh ota-off`** (reversible with `ota-on`), measured on `-4-2` firmware:

| Layer | Command | Result on this firmware | Survives reboot |
|---|---|---|---|
| auto-install flag | `settings put global ota_disable_automatic_update 1` (= Developer options → Automatic system updates off) | ✅ | ✅ |
| user-0 uninstall | `pm uninstall -k --user 0 com.motorola.ccc.ota` | ❌ `Failure: package is non-disable` | — |
| disable / suspend / hide | `pm disable-user`, `pm suspend`, `pm hide` | ❌ refused / denied | — |
| background run | `cmd appops set … RUN_ANY_IN_BACKGROUND ignore` | ✅ | ✅ |
| per-app network firewall | `cmd connectivity set-chain3-enabled true` + `set-package-networking-enabled false com.motorola.ccc.ota` (all networks) | ✅ | ❌ **re-run `ota-off` after every boot** |
| background data (metered only) | `cmd netpolicy add restrict-background-blacklist <uid>` | ✅ | ❌ |

The script tries the uninstall first and only falls back to the other layers if it is refused, so a firmware that
allows it gets the strong result automatically.

3. **Network (most reliable without root)**: Moto downloads OTA on Wi-Fi. Keep phones off internet Wi-Fi
   (LAN-only SSID / router per-MAC block); never leave them charging on Wi-Fi overnight.

## Stage 2 — after BL unlock + root (`scripts/phone.sh ota-off-root`)

```bash
adb shell su -c 'pm disable-user --user 0 com.motorola.ccc.ota'
adb shell su -c 'pm disable --user 0 com.motorola.ccc.ota'
adb shell dumpsys package com.motorola.ccc.ota | grep enabled=   # expect enabled=2 or 3
```

Don't delete the APK from the system partition (more risk than benefit).

Verify either stage with `scripts/phone.sh ota-status`; Settings → System update should stop offering a version
for a week. Google Play system updates are unaffected. sidemdm can't push an update-blocking policy: it
deliberately never becomes device owner.

## OTA open items

- [ ] **Every phone, by hand:** Settings → search "update" → Moto **Smart updates** off (adb can't do this).
- [ ] **Never connect a phone to internet Wi-Fi during the QR enrollment if avoidable.** Phone #1 picked up an update
      offer while on Wi-Fi during enrollment (before `ota-off`); Settings → System update now says
      *"Software download is in progress"*. It's stalled (Wi-Fi off, no network) but **resumes as soon as the phone
      gets internet**. Prefer a LAN-only SSID for enrollment (the APK is served from the Mac, no WAN needed).
- [ ] Don't tap anything on the System update page; don't leave phones charging on internet Wi-Fi.
- [ ] **Confirmed (static look at `/system_ext/priv-app/3c_ota/3c_ota.apk`):** the Moto OTA app has `ABUpdate` and
      `StreamingUpdate` installers that call `UpdateEngine.applyPayload`, i.e. in streaming mode the payload is
      downloaded by `update_engine` (root), not by the app. It also has a "resume streaming download on cellular"
      path, so a SIM is a second channel. Stage-1 `ota-off` therefore does **not** reliably stop an already-started
      download.
- [ ] Caveat: the per-app firewall only blocks `com.motorola.ccc.ota`. On A/B devices the payload may be fetched or
      applied by `update_engine` (root daemon, not covered by that firewall; its status isn't readable from adb
      without root). Real guarantee until root = no internet. Before and after any reboot, check
      `ro.boot.slot_suffix` (still `_a`) and `ro.build.display.id` (unchanged) with `scripts/phone.sh check`.
- [ ] After any reboot: `scripts/phone.sh ota-off` (firewall layer resets).
- [ ] **LAN DNS for the farm (e.g. AdGuard Home)** — block OTA at DNS so phones can use the internet for apps without
      the update risk. Needs a LAN DNS resolver on an always-on machine and a router that can force DNS. Not set up
      or tested yet.
  - Split: **the resolver** (AdGuard Home, or Unbound with a blocklist) = per-client query log, allowlist mode;
    **the router** = enforcement: a farm VLAN (+ an SSID tagged on the access point), DHCP on that VLAN hands out
    the resolver as DNS, NAT port-forward any outbound 53 from the farm VLAN to the resolver, block outbound 853
    (DoT), allow farm → Mac:8080 (sidemdm) and farm → resolver:53, optionally farm VLAN isolated from the rest of
    the LAN. (Fewer moving parts alternative: a router's built-in Unbound blocklist + host overrides, but allowlist
    mode and per-client logs are clumsier there.)
  - Open: the access point must support a VLAN-tagged extra SSID.
  - Why: blocks OTA hosts for *every* process, including `update_engine` (not just `ccc.ota`); server-side, so it
    survives phone reboots; per-phone query log shows any update attempt; one rule set for all 8.
  - Host on an always-on machine (not the Mac, which sleeps). AdGuard Home: per-client query log, allowlist mode.
  - **Default-deny first** (allowlist mode), connect a phone, read the query log, allow only what's needed.
    Do not guess Moto OTA/CDN domains from old lists; record the observed ones here.
  - Close bypasses: `adb shell settings put global private_dns_mode off` (add to `ota-off`); on the router block
    outbound TCP/UDP 853 (DoT) and direct outbound 53 to anything but the resolver. App-level DoH / hard-coded IPs
    (e.g. Chrome) are not covered; system update is not expected to use them.
  - Point phones at it: preferred = dedicated farm SSID/VLAN whose DHCP hands out the resolver as DNS; fallback =
    static DNS in each phone's Wi-Fi settings.
  - sidemdm enrollment can run on the same SSID (APK comes from the Mac; no WAN needed).
  - Phone #1 already has a pending download: give it internet only after the OTA block is verified in the query log.
- [ ] After BL unlock + root: `scripts/phone.sh ota-off-root`, then the stalled download can be cleared.
