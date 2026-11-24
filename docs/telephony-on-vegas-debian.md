<!-- Researched 2026-11-23 by a multi-agent workflow (research + adversarial verify); read-only, no phone touched. -->

# Cellular, SMS, calls and IMS in Debian on vegas (#5)

**Verdict: getting cellular data looks possible but has not been proven. SMS is uncertain. Calls depend on getting VoLTE working, and VoLTE and VoWiFi would be research projects with low odds.** Nobody has done this on MT6835 or on a vendor 5.15 kernel [unverified]. Today Debian never boots the modem: ccmni0-20 stay DOWN and md_state is 0 [confirmed: docs/linux-on-vegas.md §11]. Every cellular feature needs the modem booted, and a booted modem writes NV data. That conflicts with the current rule that Debian never writes NV. If you want working calls and texts in Debian this week, the only safe option is VoIP over Wi-Fi (Path C below).

## 1) What Debian could do, and how likely each is

| Feature | Likelihood | Why |
|---|---|---|
| Cellular data | Medium, after weeks of work | Needs a modem boot plus the MediaTek +EIF handshake to ccmni. The vegas RIL uses that same handshake [confirmed: vendor/lib64/libmtk-ril.so strings]. Plinius (MT6878, plain Debian) does it [confirmed: karagos01/plinius-mainline README]. |
| SMS | Low to medium | Plain SMS over LTE may work, but Verizon-family networks likely require SMS over IMS [inference]. Straight Talk says non-VoLTE devices lose texts [confirmed: straighttalk.com/support/networkchanges]. |
| Voice calls | Low | All three US carriers have shut down 2G and 3G, so voice falls back to nothing without VoLTE. T-Mobile retired its 2G network on 2026-08-03 [confirmed: macrumors.com 2026/08/06]. |
| VoLTE (IMS) | Low | The only open MediaTek IMS plugin (FuriLabs) targets the older HIDL interface `mtkradioex@3.0` [confirmed: its README and src/mtk_radio_ext_types.h]. Vegas ships only the newer AIDL `mtkradioex` V1 interfaces, under different instance names [confirmed: vendor/etc/vintf/manifest.xml]. So the plugin needs a port of unknown size [inference]. |
| VoWiFi | Lowest | There is no wfca or ePDG binary in vendor [confirmed]. The FuriLabs code sends Wi-Fi state to the modem [confirmed: src/mtk_ims.c], so VoWiFi may run in the modem. If so, it is about as hard as VoLTE plus a little more [inference]. Nobody has reported it working on any MediaTek Linux phone [unverified]. |

Some evidence helps:
- The IMS calling (SIP) stack probably runs inside the modem on vegas. The vendor ships no volte_stack, volte_ua or volte_imcb daemons, and sets `ro.vendor.md_auto_setup_ims=1` [confirmed: vendor/bin listing, vendor/build.prop]. So Linux would need to send control commands to the modem, not run a whole SIP stack [inference].
- The Volla Plinius (MediaTek, Halium 14) has an official Ubuntu Touch page listing VoLTE, calls and SMS as working [confirmed: devices.ubuntu-touch.io ansuz/releases/noble.md]. Carrier and region are not stated.
- Plinius on plain Debian (mainline kernel) does calls, SMS and data through ModemManager [confirmed: its README]. It does not say whether its calls use VoLTE [confirmed, by absence].

Against it:
- The closest phone on the same chip (BraX3, MT6835, Ubuntu Touch) has no voice calls in the US, and its SIM is often not recognised [unverified, contested forum reports].
- Ubuntu Touch users on Volla X23, Quintus and 22 report VoLTE not working [confirmed: forums.ubports.com topic 10889].

## 2) Realistic paths, ranked

**A. Vendor modem stack inside Debian.** This is the only route to native data, SMS and maybe VoLTE while Android stays installed.
- **What it involves:** extend the current Wi-Fi pattern (Android linker, property shim, nvguard) to `ccci_mdinit`, then `mtkfusionrild`, then ofono.
- `ccci_mdinit` has the modem file server built in [confirmed: strings]. `mtkfusionrild` serves the AIDL radio interfaces [confirmed: mtkrild.rc, manifest].
- ofono would use ofono-binder-plugin, whose AIDL backend already exists [confirmed: mer-hybris/ofono-binder-plugin binder_plugin.c].
- Host `servicemanager` and `vndservicemanager` as systemd units, as the Moto Pad port does [confirmed: linux/work/ref/moto-pad-2026-arch-linux/config/android-units/].
- `ccci_mdinit` reads about 40 properties that a shim must answer [confirmed: strings].
- **Effort:** weeks for data and SMS. VoLTE is open-ended, because it needs the IMS plugin ported to AIDL and separate call-audio work [inference].
- **NV/IMEI risk:** high unless sandboxed. The built-in file server opens `/mnt/vendor/{nvdata,nvcfg,protect_f,protect_s}` [confirmed: strings], and the modem writes NVRAM every 20-65 s on a similar chip [confirmed: Plinius README].
- libnvram resets NV files it judges bad back to defaults. The strings show this, but the exact order of restore and reset is [inference]. That reset is how an IMEI ends up null.
- **Brick risk:** low. No partition writes are needed beyond the existing Debian partition [inference].

**B. Plinius-style: our own modem daemon plus a ModemManager plugin, without Android RIL.**
- Plinius serves the modem a generated copy of NV built from the phone's own backups, not the real partitions [confirmed: mk-modem-nvram.py docstring].
- It runs on a mainline kernel with an out-of-tree CCCI driver. Porting it to the vegas 5.15 vendor kernel is untested [inference].
- The MT6895 project's ModemManager stack has IMS control but says "IMS/VoLTE is not yet validated" [confirmed: modemmanager-mtk-soc README].
- **Effort:** similar to A or larger. **NV risk:** lower by design, because it uses copies.

**C. VoIP over Debian's working Wi-Fi.**
- Use a SIP provider with an SMS API, or Google Voice in a browser. No modem and no NV access [inference]. Wi-Fi works [confirmed: docs §11].
- Microphone and earpiece routing in Debian are untested [unverified].
- Optionally, forward the Tracfone number to the VoIP number. Whether Tracfone allows forwarding is [unverified].
- **Effort:** days. **Risk:** none to the phone.

**D. A USB modem for data only.** It works only if the modem uses CDC-ECM or NCM. The stock kernel has CDC_NCM and CDCETHER on, and QMI, MBIM and RNDIS_HOST off [confirmed: linux/work/stock/config.stock]. It conflicts with the current SSH over the USB-C port unless you use a powered hub [inference].

**Not worth it:**
- **Halium, Ubuntu Touch or Droidian.** No vegas port exists [confirmed: search, 2026-11-23]. Installing one replaces Android and wipes userdata, which breaks end state E [confirmed: docs §3.6].
- **Waydroid.** The stock kernel lacks the PID and IPC namespaces it needs [confirmed: config.stock].

## 3) A first safe step (read-only or reversible)

1. **Offline, no phone needed.** Design the NV sandbox on paper:
   - Run `nvram_daemon` and `ccci_mdinit` in a private mount namespace where `/mnt/vendor/{nvdata,nvcfg,protect_f,protect_s}` are loop mounts of per-phone copies.
   - Hide `/dev/block/by-name/{nvram,nvdata,nvcfg,protect1,protect2}` and the matching `/dev/sdcN` nodes in that namespace.
   - Never run `factory`, `mot_tcmd` or the NVRAM HAL service. These are the callers of the code that writes the raw `nvram` partition [confirmed: lib64/libfile_op.so and its callers].
   - nvguard must be changed for this. Today it checks only `/proc/mounts`, and a loop mount would fail its check [confirmed: linux/debian/overlay/usr/lib/vegas/nvguard] [inference: the fix].
2. **Read-only, in Android on #5, with a SIM inserted:**
   - Record both IMEIs.
   - Check that IMS/VoLTE actually registers on your carrier under Android.
   - Capture a full process list and `getprop` (the existing capture2/procs.txt only covers Wi-Fi and charging [confirmed]).
   - List `/dev/ccci_*` and `/dev/ttyC*`.
   - If Android can't do VoLTE on your SIM, Debian won't either [inference].
3. Only after the backups in section 4: boot the modem in Debian against the copies and aim for data first.

## 4) Back up before any modem experiment

- **Fresh raw images** of `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`, `prodpersist`, `md1img_a/b` and `mcf_ota_a/b`, with SHA256SUMS. Also `proinfo` and `utags*`, which nvguard already treats as protected [inference].
- **Why a fresh set:** the newer backup `backups/nv_refresh_20261121_232156_<serial>/` has no `nvcfg` [confirmed]. nvcfg changes between reads [confirmed: docs §6.5, a doc-reported note]. The full set at `vegas-freedom/backups/stock_20261120_005818_<serial>/` is older, and nvdata and protect differ between the two backups [confirmed: cmp].
- **Write down both IMEIs, the serial and the baseband version** (currently `MT6835O_NR17.RC.MP.V18.6.6.P107.02.309R` [confirmed: getprop.txt, 11-20 snapshot]).
- **Make the sandbox copies from that fresh set** and treat them as disposable. Never write them back to the phone.
- **Know the limit:** restoring nvdata from a raw image has not been proven to work on vegas [confirmed: docs §6.5]. A null IMEI may need Windows SN Writer or an SP Flash format [unverified]. The BraX3 IMEI losses all followed a flashing step, not Linux running [confirmed: community.braxtech.net thread 4444].

**Refuted claims, not used above:**
- The modem writes mot_md_log files into nvdata (no trace in either backup).
- The BinRegion backup code is in libnvram (it is in libfile_op).
- A hovatek user erased nvcfg, nvdata and nvram and could not restore the IMEI (only nvdata was lost, and the IMEI was restored).
- Vegas needs AP-side volte_stack, volte_ua and volte_imcb daemons.
- Every working Droidian VoLTE report is from Qualcomm (most reports name no device).
- Plinius VoLTE is "experimental" (it is listed as working).
- T-Mobile's 2G shutdown is unconfirmed (it happened).
- VoWiFi has no reusable piece and is not realistic (it may live in the modem).
