# Cellular data and VoIP on #5 under Debian: updated picture (2026-11-23)

> Research report from the v1 build sessions, imported as written. `#5` is the maintainer's dual-boot phone.
> Paths starting `<scratch>/` are the session's working folder and are not in this repo. `linux/work/ref/<name>/` are
> local clones of the public sister-port repos; their URLs are in `docs/linux-on-vegas.md` section 8.

Scope: research only. No phone was touched. The modem was not booted. No NV partition and no `/metadata` was read
from or written to on any phone. The only NV-adjacent read was an offline `debugfs` read of #5's existing persist
backup image on the Mac.

Labels: **[verified: source]** means checked in this session against the named file or page. **[verified earlier:
source]** means it comes from a repo doc that already marks it verified. **[unverified]** and **[inference]** mean
what they say.

Main sources:
- `docs/telephony-on-vegas-debian.md` and `docs/linux-on-vegas.md` (§3.4, §11, §12).
- The vegas 2026 vendor partition, extracted by an earlier session at
  `<scratch>/fw/vendor`.
  It comes from the -4-2 firmware zip.
- `linux/work/stock/{vendor_dlkm,vendor_boot,dtbo.img,config.stock}`.
- The sister ports: `linux/work/ref/moto-g-power-2025-omarchy` (notes/audio-20261011.md, UCM2 files, audio-prepare)
  and `linux/work/ref/moto-pad-2026-arch-linux`.
- Web pages: karagos01/plinius-mainline (README, `mobile-data.py`, `ccci-server.py`), ModemManager MRs, kernel
  t7xx docs.
- The trixie arm64 VM `vegas-deb`, used for package checks only.

---

## 0. Headline changes from the existing research

1. **VoIP audio is much closer than the docs say.** `docs/linux-on-vegas.md` says "aw883xx untested". The sister
   port did get speaker, main mic, UCM2 and PipeWire working on plain Linux with the vendor 5.15 modules
   [verified: linux/work/ref/moto-g-power-2025-omarchy/notes/audio-20261011.md, "Result on the phone"]. Its
   hardware matches #5's:
   - The Awinic firmware `aw883xx_acf.bin` has the same SHA-256 on both (`c4c49f39…74ea6c`, project "Vegas")
     [verified: shasum of the vegas 2026 vendor/firmware file vs the note].
   - The amps sit at the same I2C addresses: aw883xx@34, @35 and aw883xx_smartpa@37 in dtbo fragment@88
     [verified: strings linux/work/stock/dtbo.img].
   - The machine driver is the same, `mediatek,mt6835-mt6377-sound` [verified: strings linux/work/stock/vendor_boot/dtb].
   - The card name is the same, `mt6835mt6377`, and the vext audio options are the same (SPEAKER_PATH
     smartpa_awinic_aw883xx, 2 speakers, 2 mics, `RCV_PATH_NO_ANA` and `SPK_PATH_NO_ANA` = yes,
     `MTK_AUDIODSP_SUPPORT` = no) [verified: vendor/etc/audio_device.xml and
     vendor/etc/audio_param/AudioParamOptions_vext.xml].
   - All 16 modules that port loads exist in our `vendor_dlkm` [verified: find in linux/work/stock/vendor_dlkm].
   So SIP VoIP on Debian is a days-scale userspace job with no modem involved.
2. **Mobile data probably does not need the Android RIL at all.**
   - Plinius brings data up with a 300-line Python script. It turns the radio on through MIPC and then uses plain
     AT: `+EIAAPN`, `+EGTYPE`, `+CGDCONT`/`+CGACT`, waits for the `+EIF` URC, and replies `AT+EIF=<id>,"ifst","up"`.
     It never uses rild, netagent or binder [verified: raw plinius-mainline/mobile-data.py].
   - The vendor 5.15 CCCI driver on vegas exposes the same kind of endpoints: `ttyC0..3/5/6` (AT), `ttyCMIPC0..9`,
     `ccci_fs` and `ccci_rpc` [verified: strings vendor_dlkm ccci_md_all.ko].
   - That makes "vendor `ccci_mdinit` to boot the modem against NV copies, then a Plinius-style AT/MIPC script"
     the smallest data route. It replaces the mtkfusionrild + servicemanagers + ofono-binder stack of the earlier
     Path A [inference].
3. **ModemManager MBIM/QMI is out.** The vegas kernel has `CONFIG_WWAN`, `MHI_BUS`, `USB_NET_CDC_MBIM` and
   `USB_NET_QMI_WWAN` all unset, and the CCCI modules contain no "mbim" string [verified: config.stock, strings].
   ModemManager could only drive the modem over AT, through a custom plugin like Plinius's `mm-plugin-mtk-ccci`.
   Its stock generic plugin cannot do the `+EIF` handshake [inference from mobile-data.py docstring: "the modem
   keeps the PDN data path closed until this confirmation"].
4. **A new hazard for the UI work.** `gnome-calls` in trixie hard-depends on `modemmanager` [verified: apt-cache
   show in vegas-deb]. Once the Wi-Fi unit loads `ccci_md_all`, the `ttyC*` / `ttyCMIPC*` nodes exist even though
   the modem is down [inference from the module strings, plus verified on #5 that ccci loads with Wi-Fi]. A running
   ModemManager may probe them. It cannot boot the modem, but it should never touch these ports by accident
   [inference]. If any package pulls in ModemManager or ofono, mask the service or add a udev
   `ENV{ID_MM_DEVICE_IGNORE}="1"` rule for `ttyC*` and `ttyCMIPC*` first.

---

## 1. Mobile data: what exactly is needed

### 1.1 What the vegas vendor stack does under Android [verified unless marked]

- `ccci_mdinit` (class core, user system, oneshot) boots the modem. It also has the modem file-system server built
  in, and touches `/sys/kernel/ccci/boot` [verified: vendor/etc/init/init.cccimdinit.rc and
  init/hw/init.modem.rc; strings of ccci_mdinit list `/dev/ccci_fs`, `/dev/ccci_rpc`, `/dev/ccci_md1_sta`, ...].
  The kernel side has `boot_md_store` and `CCCI_IOC_SET_MD_BOOT_MODE` [verified: strings ccci_md_all.ko].
- `ccci_rpcd` serves modem RPC and reads `/dev/block/by-name/md1img` [verified: strings vendor/bin/ccci_rpcd].
  Plinius does the same job in Python (`ccci-server.py`: GPIO/EINT/DTSI/DRDI, copying md1drdi from the modem image)
  [verified: plinius ccci-server.py].
- `nvram_daemon` and the NVRAM HAL service also run. Writes to the raw `nvram` partition come from `libfile_op`
  callers (factory, mot_tcmd, the NVRAM HAL), so those must never run [verified earlier:
  docs/telephony-on-vegas-debian.md §3].
- `mtkfusionrild -l libmtk-ril.so` starts on `vendor.ril.mtk=1` or `ro.vendor.mtk_mipc_support=1`.
  - The device sets `ro.vendor.mtk_mipc_support=1` and `ro.vendor.mtk_ril_mode=c6m_1rild` [verified:
    vendor/build.prop, vendor/etc/init/mtkrild.rc].
  - So the Android RIL talks MIPC over `/dev/ttyCMIPC0` [verified: strings libmipc.so] and also opens AT ttys
    such as `/dev/ttyC6` [verified: strings in the RIL libraries; which tty serves which role is unverified].
- IMS: `ro.vendor.md_auto_setup_ims=1`, `persist.vendor.volte_support=1`, `persist.vendor.mtk_wfc_support=1`
  [verified: vendor/build.prop].
  - Correction to telephony doc §1: vendor/bin does contain `volte_clientapi_ua`, `volte_rcs_ua` and
    `rcs_volte_stack`, but they are RCS components [verified: ls vendor/bin].
  - The classic `volte_stack`, `volte_ua` and `volte_imcb` are still absent, so the earlier conclusion that IMS
    runs in the modem stands [verified: ls].
- ccmni interfaces: the kernel creates `ccmni0..20`. Android tunes RPS on them at early-init [verified:
  init.modem.rc]. On #5 under Debian they exist and stay DOWN with `md_state = 0` [verified earlier:
  docs/linux-on-vegas.md §11].

### 1.2 Candidate routes, ranked by smallest working data path

| Route | Pieces | NV exposure | Effort | Notes |
|---|---|---|---|---|
| **D1. `ccci_mdinit` + Plinius-style `mobile-data`** (recommended) | Vendor `ccci_mdinit`, run under the existing Android linker + propshim pattern, inside a mount namespace whose `/mnt/vendor/{nvdata,nvcfg,protect_f,protect_s}` are per-phone copies. Plus `ccci_rpcd` (or its function). Then a script on `ttyC*` (AT) and `ttyCMIPC*` (radio-on MIPC frame), then `ip addr`/route on `ccmniN` and DNS from `+CGCONTRDP` into resolved | All modem FS traffic goes to copies; raw NV block nodes hidden in the namespace | 1-3 weeks [inference] | The radio-on MIPC frame Plinius sends is prebuilt for MT6878 firmware. The vegas modem (`MT6835O_NR17...` baseband [verified earlier]) may need a different one [unverified]. Capturing the frame Android's RIL sends would need root plus an strace of mtkfusionrild in Android (temp root, state E root-on) [inference] |
| D2. Plinius full stack (own FS/RPC server + modemd + `mm-plugin-mtk-ccci` + ModemManager + GNOME Calls) | Python FS/RPC servers, generated NV image (`mk-modem-nvram.py`), MM plugin | Copies by design | 3-6 weeks [inference] | Written for a mainline CCCI driver: boots via `/sys/bus/platform/drivers/mtk-ccci/10209000.modem/state` [verified: ccci-server.py]. vegas runs vendor eccci with a different boot ABI, so the servers need porting [inference]. It does give SMS and calls through MM and GNOME Calls |
| D3. Vendor RIL (earlier Path A) | `ccci_mdinit`, `mtkfusionrild`, servicemanager + vndservicemanager, propshim for about 40+ props, ofono + ofono-binder-plugin (AIDL) | As D1 | Weeks to months | Only route that might ever reach VoLTE through `mtkradioex` (needs an AIDL port of the FuriLabs IMS plugin) [verified earlier: telephony doc] |
| ModemManager MBIM/QMI | — | — | Not possible | No WWAN/MBIM in the kernel or CCCI [verified] |
| USB LTE dongle (CDC-ECM/NCM only) | Hub + dongle | None | Hours | QMI/MBIM/option serial are off in config.stock [verified]. It blocks the usb0 SSH lifeline unless a powered hub and OTG work [inference] |

What all routes need (none of it exists yet):
- A **modem boot**, which writes NVRAM about every 20-65 s on a similar chip [verified earlier: Plinius README].
  The standing rule forbids this without an explicit go-ahead.
- A **fresh NV backup set** (telephony doc §4).
- **nvguard rework.** It currently fails if any NV path is not on the Debian root [verified: overlay nvguard], so
  loop-mounted copies need a namespace-aware check.

### 1.3 Smallest read-only or reversible first steps (no modem boot)

1. **Offline, done in this session.** The CCCI device inventory and MIPC/AT channel names are confirmed in the
   vegas vendor kernel modules. The MBIM route is closed.
2. **Offline, next.**
   - Diff Plinius `ccci_fs.py` against the vendor `ccci_mdinit` FS server (strings) to list which NV files the
     modem asks for at boot. That gives the size of the sandbox copy.
   - Collect the property names `ccci_mdinit` reads for the propshim.
   - Neither step touches a phone.
3. **Read-only on #5, Debian side, modem down.** `ls -l /dev/ttyC* /dev/ttyCMIPC* /dev/ccci_*`,
   `cat /sys/kernel/ccci/*` (no writes, no `open()` of tty nodes), `ip -br link | grep ccmni`.
   - This confirms the node names exist with Wi-Fi's ccci load.
   - Do not open the AT or MIPC ttys. Do not run ModemManager [inference: an open on a down modem is likely
     harmless, but untested].
4. **Read-only on #5, Android side** (as in telephony doc §3).
   - IMS/VoLTE registration on the user's SIM, both IMEIs, the baseband, and the full process list plus getprop.
   - Optionally, with the established temp-root toggle and the user's go-ahead, an strace of
     `mtkfusionrild`'s writes to `/dev/ttyCMIPC0` during airplane-mode off. That captures the vegas radio-on MIPC
     frame. Android does that boot anyway, so Debian rules are not involved [inference].
5. **First reversible modem step (needs explicit go-ahead).** Boot the modem in Debian with `ccci_mdinit` in the
   copy-sandbox namespace, airplane mode (no radio-on), and watch `md_state`.
   - Reversal: stop the modem with `CCCI_IOC_DO_STOP_MD` or a reboot [unverified that stop works cleanly], and
     re-diff the copies.
   - The real partitions are never mounted, and nvguard checks the block nodes.

### 1.4 Carrier caveats [verified earlier: telephony doc]

US networks have no 2G or 3G left. SMS on Verizon-family MVNOs may need IMS. Data is the realistic first target;
calls and SMS over the modem are low-odds.

---

## 2. VoIP (SIP over Wi-Fi now, cellular data later)

### 2.1 Audio path on MT6835 under Debian: yes, ALSA works without any Android HAL

- **Hardware.** The SoC AFE is `mt6835-afe-pcm`. The codec is the MT6377 PMIC: headphone amp, ADCs, analog mics
  AIN0 (bottom), AIN2 (back) and AIN1 (headset), and accdet jack detection. There are three Awinic smart amps on
  I2S3 (0x34/0x35 AW88394 stereo speakers; 0x37 AW88166 for HAC). The **earpiece is aw_dev_0 in its "Receiver"
  profile**, with aw_dev_1 off. There is no separate analog earpiece path [verified: sister note, matched to our
  vendor files and dtbo above].
- **Kernel.** The 16 vendor_dlkm modules load in order:
  `mtk-btcvsd snd-soc-aw883xx adsp mtk-afe-external scp mtk-scp-audiocommon audio_ipi snd-soc-audiodsp-common
  mtk-scp-audio mtk-sp-spk-amp snd-soc-mtk-common snd-soc-mt6835-afe nvmem-mt635x-efuse mt6377-accdet
  snd-soc-mt6377 mt6835-mt6377`.
  - The card `0 [mt6835mt6377]` binds with PCMs Playback_1=0 (speaker/earpiece), Playback_2=2 (headphones) and
    Capture_1=10 [verified on the sister phone].
  - All the `.ko` files are in our `linux/work/stock/vendor_dlkm`, and `build.sh` already copies every vendor_dlkm
    module into `/lib/modules/<rel>/vendor` with depmod [verified: build.sh lines 61-66].
  - `mt6835-mt6377.ko` depends on `ccci_md_all`, `ccmni`, `ccci_util_lib` and `ccci_auxadc` [verified:
    modules.dep]. These are the same modules the Wi-Fi unit already loads on #5 without booting the modem
    [verified earlier: docs §11]. So audio adds no new modem exposure [inference].
  - `aw883xx_acf.bin` must be in `/usr/lib/firmware`, or `firmware_class.path` must point at `/vendor/firmware`,
    which wifi-up already sets [verified: wifi-up line `echo -n /vendor/firmware > .../firmware_class/parameters/path`].
    So once Wi-Fi is up, the amp firmware may already resolve from `/vendor/firmware` [inference].
  - Vermagic differs from the sister phone (`...-g72da1abbd4bf` on ours vs `...-gd63125a6a58d`). It is
    irrelevant because we load our own vendor_dlkm [verified: strings].
- **Speaker calibration.** #5's per-unit Re values are in its persist backup:
  `backups/nv_refresh_20261121_232156_<serial>/persist.img:/factory/audio/aw_cali.bin` is 20 bytes and holds
  two per-unit values [verified: read-only debugfs in vegas-deb].
  - The sister port mounted `persist` read-only at boot to copy it. **Do not do that here**: nvguard refuses while
    `persist` is mounted [verified: nvguard PARTNAME list includes persist].
  - Instead, bake the 20-byte file from the backup into the image at
    `/mnt/vendor/persist/factory/audio/aw_cali.bin` (the path the driver reads) [inference].
- **UCM2.** The sister port's `MediaTek/mt6835/mt6377-aw88394/{mt6835-mt6377.conf,init.conf,HiFi.conf}` and the
  conf.d link match our card name. Its HiFi verb has Speaker, Earpiece, Headphones, Mic and Headset devices
  [verified: file read]. For calls, add a **VoiceCall-like device or verb** that uses aw_dev_0 `Voice`/`Receiver`.
  The ACF profiles are `Bypass Music Receiver Voice` [verified on the sister phone].
- **Gotchas carried over** [verified on the sister phone]:
  - `Headset Volume` is inverted.
  - Changing `aw_dev_N_prof` resets rx_volume at the next stream start.
  - The jack has no ALSA kcontrol, only an input device.
  - Mic level is low: PGA 24 dB plus no HW gain.
  - Speaker volume was loud even at about −60 dB: test only attended and at low level.
- **Still unverified on any vegas**: earpiece, headphones, headset mic, and full-duplex speaker+mic at the same
  time (needed for calls).

### 2.2 Userspace for SIP

- Packages in trixie [verified: apt-cache policy in vegas-deb]:
  - `baresip` 1.1.0
  - `linphone-cli` 5.3 (no linphone-desktop)
  - `gnome-calls` 48.2: SIP via sofia, GTK4/libadwaita, **depends on modemmanager**
  - `pipewire` 1.4.2, `wireplumber` 0.5.8
  - `alsa-ucm-conf` 1.2.14
  - `callaudiod` 0.1.10
- **Echo cancellation is required for speaker and earpiece calls** [inference]. PipeWire ships
  `libpipewire-module-echo-cancel` and `libspa-aec-webrtc` in trixie [verified: dpkg -c in vegas-deb]. Debian's
  baresip has no webrtc_aec module, but it has `alsa`, `ctrl_tcp`, `ctrl_dbus`, `opus` and `g722`
  [verified: dpkg -c baresip-core].
- **Recommended stack for the existing sway + tmux + Textual UI** [inference]:
  - PipeWire + WirePlumber + pipewire-alsa, with an echo-cancel virtual source/sink.
  - `baresip` headless with `ctrl_tcp`, driven by a small Textual "Phone" app: dialpad, call, hang up,
    speaker/earpiece toggle that switches the UCM device, mute.
  - Avoid gnome-calls: it needs GTK4 on pixman with `GSK_RENDERER=cairo`, pulls in ModemManager, and is heavy
    [inference].
- **Session caveat.** sway runs as root with no logind seat. PipeWire as root needs either a `user@0` systemd user
  session or a system-wide PipeWire instance, and `XDG_RUNTIME_DIR` must match the clients [inference].
- **Image changes needed**: add `alsa-utils,pipewire,pipewire-alsa,wireplumber,baresip-core` (+`rtkit`) to
  build.sh PKGS. Add an `audio-up` unit with the 16 modules and a one-strike guard like the sister's.
- **Network.** Wi-Fi works today [verified earlier]. SIP over NAT: use a provider with TLS/SRTP plus ICE/STUN
  (baresip `ice`, `stun`, `turn`, `srtp` and `dtls_srtp` modules are present [verified]). Cellular data, once D1
  works, would carry the same SIP stack with no changes [inference].
- **Number continuity.** Forwarding the Tracfone number to the SIP DID needs Android or a carrier feature
  [unverified that Tracfone allows it].

### 2.3 VoIP first steps

1. **Offline, no phone.**
   - Stage the UCM2 files and `aw_cali.bin` into `linux/debian/overlay`.
   - Add `audio-up` (module list from §2.1, without the persist mount).
   - Parse-check the UCM with `alsaucm` in vegas-deb.
   - Prototype the baresip + Textual front-end against `ctrl_tcp` in the VM, using `aufile` / `ausine` audio.
2. **On #5, no sound (needs go-ahead; modem-neutral).**
   - Load the 16 modules after Wi-Fi.
   - Check `/proc/asound/cards`, `amixer contents`, that aw_dev_0/1/2 probed, and dmesg for SCP/AEE.
   - `scp.ko` is the first-time-on-this-kernel module; it was fine on the sister phone [verified there].
   - Reversal is a reboot.
3. **On #5, attended and quiet.** Run the sister `test-vegas-audio.sh` steps: speaker at −30 dBFS with amps
   attenuated, mic RMS, earpiece. Then full-duplex loopback through echo-cancel. Then a SIP test call over Wi-Fi.

---

## 3. Risks

- **Modem boot means NV writes.** IMEI loss is possible if any writer reaches real `nvdata`/`nvram`, and raw
  nvdata restore is unproven on vegas [verified earlier: docs §6.5]. Always use the copy-sandbox, and get a fresh
  NV backup first.
- **ModemManager or ofono pulled in by packages** (gnome-calls) would probe `ttyC*`. Mask the services or add the
  udev ignore rule before installing.
- **Audio.**
  - `scp.ko` first load on this kernel build.
  - Loud speaker even at low digital levels: never run unattended.
  - Without `aw_cali.bin` the amps use the generic Re, so only low volume is safe [verified on the sister phone].
  - PipeWire as root under a seatless sway is untested.
- **Compositor rule D10.** Nothing in the audio or VoIP path touches sway. UI restarts only affect clients.
- **Halting risk.** A kernel oops in an audio module could panic the phone. The one-strike guard plus bootfail
  counter cover it, and the rescue root stays available [inference].
