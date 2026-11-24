# GPU rendering for the Debian UI on phone #5 (MT6835): research report

> Research report from the v1 build sessions, imported as written. `#5` is the maintainer's dual-boot phone.
> Paths starting `<scratch>/` are the session's working folder and are not in this repo. `linux/work/ref/<name>/` are
> local clones of the public sister-port repos; their URLs are in `docs/linux-on-vegas.md` section 8.

Date: 2026-11-23. No phone was touched. Every claim carries a tag:

- **[verified: source]**: checked in this session against a file, source tree or command output.
- **[report: source]**: someone else's written report (the sister ports). Not reproduced on #5.
- **[unverified]** / **[inference]**: not checked, or reasoned from other facts.

## 1. TL;DR

- The MT6835 (Dimensity 6300) GPU is an **Arm Mali-G57 MC2**: Valhall, **Job Manager** (not CSF), 2 cores, about
  1.07-1.1 GHz. [verified: MediaTek spec page; the 2025 port's ioctl property query gave product 0x9093,
  shader mask 0x5, 1,100,000 kHz, JM API 11.38 (`notes/gpu-bringup-20261007.md`)]
- The kernel driver on #5 is the vendor **mali_kbase r38p1 (JM)** module, `mali_kbase_mt6835.ko`, from
  `vendor_dlkm`. [verified: strings `.../mali_valhall/mali-r38p1/...mali_kbase_device_hw_jm.c` in
  `linux/work/stock/vendor_dlkm/lib/modules/mali_kbase_mt6835.ko`, sha256 `acc8b80d…e61e`]
- **"The GPU route the 2025 phone got working"** is: stock kbase modules loaded from Linux (no Android, no
  libhybris) + a **patched Mesa "panfork" (Panfrost userspace with a kbase backend)**, RandomCoderOrg/mesa-gfxstream
  branch `tensor-g1` commit `4a03b179` (Mesa 23.0.0-devel), installed in a private prefix `/opt/vegas-gpu/mesa-kbase`,
  driving **Hyprland/Aquamarine directly on card0** with GBM scanout buffers. It needed five Mesa patches and one
  Aquamarine patch (CPU wait on the render fence before each KMS commit). Result: 120 Hz, 13-16 ms commit-to-frame,
  ~9% compositor CPU vs ~380% peak on llvmpipe. [report: 2025 port `notes/gpu-bringup-20261007.md`,
  `notes/kms-fence-sync-20261011.md`, `port/vegas/patches/`]
- **It should transfer to #5**, because the 2025 phone is the same SoC, the same `vegas` codename and the same kbase
  DDK release (r38p1, JM API 11.38), and it ran on the same GKI 5.15 KMI with stock vendor modules. [inference
  from verified facts] It is not byte-for-byte: different kernel build (2025: stock Google GKI
  `-00021-g46a5565a0982`; #5: rebuilt CRC-preserving GKI `-g9b2308ac0ad6`), different module builds, and #5 runs
  **sway 1.10 / wlroots 0.18**, not Hyprland/Aquamarine, so the Aquamarine fence patch has to be redone for wlroots.
- wlroots 0.18.2's GLES2 renderer only calls `glFlush()` at the end of a render pass, with no fence
  [verified: `render/gles2/pass.c:20-49` of the wlroots 0.18.2 tarball], and the vendor mediatek-drm ignores
  `IN_FENCE_FD` [report: 2025 port], and kbase gives no implicit sync [report]. So **sway on the GPU needs a small
  wlroots patch** (e.g. `glFinish()` instead of `glFlush()`, or a CPU fence wait before the atomic commit), or it
  will show partly rendered frames.
- **Recommendation**: keep pixman sway as the default (all current clients are wl_shm: foot, swaybar, wvkbd,
  Textual in tmux, so a GPU only speeds up compositing). Do the GPU work as a separate, opt-in project in three
  gated phases: (1) load the GPU module closure in Debian and run the 2025 off-screen probes, (2) build the patched
  Mesa and pass the probes, (3) a patched wlroots + `WLR_RENDERER=gles2` sway behind a one-boot flag with a
  boot-confirm guard. Estimate 3-7 working days [inference]. Fallbacks: libhybris (Moto Pad route, weeks);
  Panfrost kernel driver: not on this kernel.

## 2. What GPU, and what kernel driver

| Fact | Status |
| --- | --- |
| MT6835 = Dimensity 6300, GPU Arm Mali-G57 MC2, TSMC 6 nm | [verified: mediatek.com Dimensity 6300 page; GSMArena announcement; 91mobiles lists MT6835 and 1.072 GHz] |
| Mali-G57 is Valhall and Job-Manager based (Panthor is for CSF GPUs only) | [verified: existing `docs/linux-on-vegas.md` Panfrost section, citing mainline bindings and Panthor docs] |
| 2025 phone: `/dev/mali0` API 11.38, product 0x9093, 2 cores, 1.1 GHz max | [report: 2025 `notes/gpu-bringup-20261007.md`] |
| #5 kbase is r38p1, JM backend, vermagic `5.15.180-android13-8-g72da1abbd4bf` | [verified: strings + `docs/linux-on-vegas.md`] |
| 2025 kbase is also r38p1 | [report: 2025 notes ("stock r38p1 kbase")] |
| Stock config has no Panfrost, no DRM_SCHED | [verified: `docs/linux-on-vegas.md` citing `linux/work/stock/config.stock`] |
| DT Mali node `/soc/mali@13000000` (`mediatek,mali`, `arm,mali-valhall`) with clocks/power domains on the vendor `gpufreq` node, `gpueb-support = 0` | [verified earlier: `docs/linux-on-vegas.md`, from `linux/work/stock/vendor_boot/dtb`] |
| Vendor display (`mediatek-drm`) exposes no render node; Mali is not a DRM driver (`/dev/mali0` misc device) | [verified earlier: `docs/linux-on-vegas.md` static inspection] |
| Vendor EGL blob: `vendor/lib64/egl/mt6835/libGLES_mali.so` r38p1-01eac0, bionic | [verified earlier: `docs/linux-on-vegas.md`] |

### GPU module closure on #5 (computed here)

From `linux/work/stock/vendor_dlkm/lib/modules/modules.dep`, the closure of `fhctl`, `mtk_gpufreq_mt6835`,
`mali_mgm_mt6835`, `mali_prot_alloc_mt6835`, `mali_kbase_mt6835` (the 2025 port's targets) is 28 modules
[verified: computed]. 27 are in `vendor_dlkm` and are **not** in the vendor ramdisk list
(`logs/<serial>/linux_b/p2/capture2/ramdisk_mods.lst`); `memory_group_manager` (softdep of kbase) is in the
ramdisk set:

```
fhctl ged gpueb gz_ipc_mod gz_trusty_mod gz_tz_system mali_kbase_mt6835 mali_mgm_mt6835
mali_prot_alloc_mt6835 mcupm mtk_battery_oc_throttling mtk_bp_thl mtk_dynamic_loading_throttling mtk_gpu_hal
mtk_gpu_qos mtk_gpufreq_mt6835 mtk_gpufreq_wrapper mtk_low_battery_throttling mtk_mbox mtk_mdpm mtk_pbm mtk_qos
mtk_rpmsg_mbox mtk_sec_heap mtk_tinysys_ipi sspm_v3 trusted_mem
```

- `fhctl` is a DT clock supplier for gpufreq with no symbol edge; without it (and `mcupm`) Mali probe defers.
  [report: 2025 notes, `scripts/prepare-vegas-gpu-modules.py`]
- kbase imports from the GenieZone modules (`gz_tz_system`, `gz_ipc_mod`, `gz_trusty_mod`) and from
  `trusted_mem` / `mtk_sec_heap`. [verified: modules.dep] Whether loading GenieZone pieces from Debian is harmless on
  #5 is [unverified]; the 2025 port's 62-module closure presumably included them and loaded [inference].
- `mtk_mdpm` (modem power meter) and `mtk_pbm` are in the closure. They do not depend on `ccci` in modules.dep
  [verified: not in closure], so they should not start the modem [unverified on #5; check `ccmni*` stays DOWN and
  ccci `md_state = 0` after loading, as was done for Wi-Fi].
- Which of these are already live in Debian on #5 today (some, like `mtk_tinysys_ipi`, may already be pulled in by
  other modules) is [unverified: read `lsmod` on the phone].
- After loading, MediaTek GED must be switched to loading mode 0 (`/sys/kernel/ged/hal/dvfs_loading_mode`), else the
  JM Mali sits at its 390 MHz floor (GED mode 5 reads CSF-only utilization fields).
  [report: 2025 `notes/project-report-20261011.md`, `port/vegas/root/usr/local/libexec/vegas/systemd/gpu-boot`]
- `/dev/mali0` and `/dev/dma_heap/system` need permissions for the rendering user (sway is root on #5, so only
  matters for non-root clients). [report: 2025 udev rule `70-vegas-devices.rules`]

## 3. Exactly what the 2025 phone did (moto-g-power-2025-omarchy)

Device: moto g power 2025 XT2515-1, also codename `vegas`, MT6835, Arch Linux ARM + Omarchy. [report: README]

1. **Kernel**: stock Google GKI `5.15.180-android13-8-00021-g46a5565a0982-ab13743836` (they later reproduced it
   byte-identically), stock unsigned vendor modules loaded with `insmod` in dependency order from
   `/opt/vegas-gpu/stock-modules` (`ORDER` file, SHA256SUMS), with a 90 s reboot watchdog and a battery-temp gate.
   [report: `port/vegas/root/usr/local/libexec/vegas/gpu-prepare`, `notes/kernel-build-20261010.md`]
2. **Userspace driver**: Panfork Mesa from RandomCoderOrg/mesa-gfxstream `tensor-g1` @ `4a03b179` (G57 model
   recognition, JM and CSF kbase backends), cross-built with Panfrost + EGL + GBM + Wayland into
   `/opt/vegas-gpu/mesa-kbase`, used through `LD_LIBRARY_PATH` and `LIBGL_DRIVERS_PATH`; system Mesa left alone.
   [report: `notes/gpu-bringup-20261007.md`] The branch still exists at that commit [verified: `git ls-remote`
   2026-11-23].
3. **Patches** (`port/vegas/patches/`) [report; files exist, verified]:
   - `mesa-kbase-modern-glibc.patch`: namespace Mesa's private `call_once` (glibc collision).
   - `mesa-kbase-init-ownership.patch`: DRI screen double-free on init failure.
   - `mesa-kbase-loader-fd.patch`: stock MediaTek JM kbase revokes a context when any fd for the file closes, so
     open a fresh kbase fd instead of `dup` [verified: patch text].
   - `mesa-kbase-jm-deferred-free.patch`: **the key fix**: on JM, BOs were freed while atoms still used them
     (the queue-idle check only worked for CSF), causing DATA_INVALID / TILE_RANGE / JOB_READ faults and flicker.
   - `mesa-kbase-native-fence-fd.patch`: `EGL_ANDROID_native_fence_sync` on JM (export via SOFT_FENCE_TRIGGER
     atom, import as CPU wait). Needed by Chrome and used by Hyprland's explicit path.
   - `mesa-kbase-vegas-trace.patch`: opt-in diagnostics only.
   - All 26 hard-linked `*_dri.so` aliases must be the patched build: **GBM on card0 loads `mediatek_dri.so`**
     (kmsro-style display+render split). [report]
4. **Compositor**: Hyprland 0.56.1 + Aquamarine 0.14.0 owning KMS on card0, DSI-1 1080x2388@120, DP-1 disabled,
   `HYPRLAND_EGL_SURFACELESS=1`, `AQ_NO_MODIFIERS=1`, `HYPRLAND_EGL_NO_MODIFIERS=1`, and
   `AQ_KMS_CPU_FENCE_WAIT=1` from `aquamarine-kms-cpu-fence-wait.patch`: `poll()` the render fence (100 ms cap)
   before each atomic commit, because `mtk_fb_wait()` has its `dma_resv` wait commented out and the driver never
   waits on `IN_FENCE_FD`. [report: `port/vegas/root/usr/local/bin/vegas-desktop-drm`,
   `notes/kms-fence-sync-20261011.md`]
5. **Safety**: `vegas-gpu on|off`, one-boot trial flag, boot-loop guard (two unconfirmed GPU boots disable GPU mode;
   confirm after 3 min uptime via `vegas-gpu-confirm.timer`). [report: notes, unit files exist (verified)]
6. **Results** [report]: GPU direct KMS 120 Hz: tap->PTY 7 ms, foot commit->frame callback 13-16 ms, Hyprland ~9%
   CPU (llvmpipe: 105-130 ms per frame, 380% CPU peak). Off-screen full-res frame ~1.5 ms (Mesa) / 5.7 ms
   (libmali trial). Fence wait cost: ~2-4 fps at 120 Hz, a few % more late frames. Chrome on Mesa GPU raster was
   slower than software for 2D canvas (9 vs 27-31 fps), so Chrome stayed software/GPU-composite only.
7. **Also tried** [report]: ARM glibc libmali r48 (Genio PPA) works off-screen after a product-ID binary patch, a
   64->72-byte JM atom stride shim and dma_heap permissions; **Hyprland would not start on it** (missing EGL
   extensions, shader compile failures); shelved. GPU frequency touch boost via
   `/proc/gpufreqv2/fix_target_opp_index` (`vegas-gpu-boost`).
8. **Display-side caveats seen there** [report]: killing the DRM master rebooted the phone within ~2 s (same as our
   D10); a phantom connected `DP-1` with 4K modes caused RDMA underflows until disabled.

## 4. What the Moto Pad 2026 port did (moto-pad-2026-arch-linux)

Device: Moto Pad 2026 / Lenovo Idea Tab, MT6835-platform (MT8755), Mali-G57 MC2, rebuilt GKI 5.15.185 with stock
vendor modules, Arch on userdata. [report: README]

- GPU through **libhybris + the vendor Android Mali blob**. Android `servicemanager`, `hwservicemanager`,
  `vndservicemanager` and MediaTek's gralloc allocator run in a chroot under systemd
  (`config/android-units/`), with an `LD_PRELOAD` property shim (`tools/src/propshim.c`) and a fake logd.
  [report; files exist, verified]
- A patched **wlroots 0.20.2** (`wlroots-pad/`): `hybris` renderer (`render/hybris.c`), AHardwareBuffer allocator,
  and a minimal `pad` display backend that only uses the KMS calls mediatek-drm handles safely (legacy SETCRTC /
  ADDFB / PAGE_FLIP, dumb buffers). labwc on top; Firefox and Chromium GPU-accelerated after extra libhybris
  patches (AHB gralloc backend, bionic TLS slots, EGL fixes, dma-buf import). [report]
- mediatek-drm oopses on plane enumeration, legacy cursor, gamma, SETCRTC with fb=0 and connector property writes
  (DPMS on DSI); `tools/src/noplanes.c` hides them from Xorg. [report; file verified]
- Transfer to vegas: same SoC family and kbase generation, but their vendor is Android 16 and ours is API 33 with a
  gralloc0 module, so their libhybris patches may not apply unchanged. [unverified, from `docs/linux-on-vegas.md`]
  It also requires running Android binder service managers on #5, which E state does not do today.

## 5. Driver options on this kernel

| Option | How | Fits #5 | Effort [inference] | Main risks |
| --- | --- | --- | --- | --- |
| **A. Panfork Mesa on vendor kbase (2025 route)** | Stock kbase modules + Mesa 23.0 panfork + 2025 patches in a private prefix; wlroots GLES2 | Same SoC, same r38p1 JM kbase, same KMI [verified]; wlroots instead of Aquamarine | 3-7 days | GPU faults/hangs; frozen Mesa 23.0 fork; mixing with system Mesa 25.0.7; no GPU thermal cap; single-author evidence |
| B. libhybris + vendor `libGLES_mali.so` (Moto Pad route) | Android service managers + gralloc in a chroot, property shim, patched libhybris, wlroots hybris renderer | Blob is on #5 [verified]; vendor API 33 vs their 36 | 2-5 weeks | Bionic/glibc TLS; Android daemons on the host; blob tied to firmware |
| C. ARM glibc libmali r48 | Genio PPA blob + product patch + atom-stride shim | Off-screen only on 2025 [report]; Hyprland failed; wlroots on it [unverified] | days to test, unknown to finish | Binary patching a vendor blob; licence; EGL gaps |
| D. PanVK + Zink over kbase | apexspan-svg/mesa-panvk-mali-g57 | Author reports Vulkan + Zink GL on Dimensity 6300, but for Android/Termux X11 [report]; glibc/Wayland [unverified] | unknown | Even less tested; Zink adds a layer for a 2-core GPU |
| E. Panfrost/Panthor kernel driver | Backport Valhall-JM Panfrost (mainline since 6.0) to 5.15 as out-of-tree modules, DT node, MFG power without mtk_gpufreq | No mt6835 compatible upstream; DT/dtbo are boot-chain partitions [verified earlier] | weeks-months | Power/voltage mistakes, boot-chain writes; nobody has done it |
| F. Halium 13 + hwcomposer/Lomiri, or Droidian wlroots hwcomposer backend | Full Android HAL container | A different end state | weeks | Replaces the current Debian design |
| G. llvmpipe | Software GL | Works anywhere | none | Worse than pixman for a compositor (105-130 ms per frame on 2025) [report] |
| H. Waydroid | Android apps | GPU only on a Halium host; CPU on plain Linux [inference, `docs/linux-on-vegas.md`] | n/a | Not a UI renderer |

Upstream Mesa has no kbase backend; kbase-capable forks are frozen on old Mesa. [verified earlier in
`docs/linux-on-vegas.md`; a 2026 web search found no change: Phoronix/Collabora results only cover upstream
Panfrost/Panthor]

## 6. How option A maps onto sway/wlroots on #5

Verified facts about the current setup:
- `vegas-sway.service` runs sway with `WLR_RENDERER=pixman WLR_NO_HARDWARE_CURSORS=1 LIBSEAT_BACKEND=noop`, never
  stopped, `Restart=no`. [verified: `linux/debian/overlay/.../vegas-sway.service`]
- Debian trixie: sway 1.10.1, libwlroots-0.18 0.18.2, libgbm1 25.0.7. [verified: `apt-cache policy` in vegas-deb]
- wlroots 0.18.2 falls back to the primary node when the DRM device has no render node (`render/egl.c:508`, `:936`)
  and then relies on Mesa's kmsro split to find the render device. [verified: source; behaviour on vendor
  mediatek-drm + panfork kmsro: inference, matches what the 2025 port saw with GBM loading `mediatek_dri.so`]
- wlroots 0.18.2 GLES2 `render_pass_submit()` does `glFlush()` only. [verified: `render/gles2/pass.c`]

What sway on the GPU would need [inference unless marked]:
1. The patched Mesa's `libEGL`, `libgbm`, `libGLESv2` and `dri/` ahead of the system ones (`LD_LIBRARY_PATH`,
   `LIBGL_DRIVERS_PATH`), with all `*_dri.so` aliases being the patched build. System libgbm 25 cannot load Mesa 23
   DRI drivers (the DRI interface changed in 24.x) [unverified], so libgbm must also come from the prefix. Debian
   uses libglvnd: build Mesa with `-Dglvnd=false` so the prefix ships a plain `libEGL.so.1`, or with glvnd and an
   `__EGL_VENDOR_LIBRARY_FILENAMES` override [unverified which is simpler].
2. A wlroots 0.18.2 rebuild with `glFinish()` in `render_pass_submit()` (or a fence poll before the DRM commit,
   like the Aquamarine patch). sway 1.10.1 links `libwlroots-0.18.so`, so a patched library in the same prefix
   suffices; no sway rebuild. Cost: CPU blocks for the frame's GPU time (~1.5 ms full screen on 2025 [report]).
3. `WLR_RENDERER=gles2`, `WLR_DRM_NO_MODIFIERS=1` (2025 needed no-modifiers on Aquamarine/Hyprland [report]).
4. The scanout buffers come from GBM on card0 via kmsro, i.e. display-side buffers imported into kbase
   [inference], so the KMS atomic path sway already exercises with pixman dumb buffers should see the same kind of
   framebuffer. The separate Weston `need_recover`/dual-pipe oops on CRTC 95 is a display-commit issue and is not
   changed by the renderer [inference]; keep 60 Hz (the oopsing CRTC goes dual-pipe at 120 Hz).
5. **D10 constraint**: switching the renderer means restarting sway, which is a compositor exit and panics the
   phone. So every renderer change must be a **reboot** with a flag read by `vegas-sway.service` (e.g. an
   `EnvironmentFile=-/etc/vegas/sway/gpu.env` or an `ExecStart` wrapper), plus a 2025-style guard: the flag is
   one-boot, cleared on a crash counter (`/var/lib/vegas/bootfail` exists) and confirmed after N minutes. A GPU hang
   inside sway will not exit sway, but a hung compositor with no way to restart it means a reboot via USB SSH
   (`reboot-rescue`) [inference].
6. Clients: foot, swaybar, wvkbd and Textual-in-tmux all use wl_shm [inference from their design; foot is a
   wl_shm/pixman terminal]. They gain nothing directly; only sway's compositing (scale 3, full-screen damage on
   scroll) gets cheaper. GL clients (browsers, glmark2) would need the same prefix in their environment.

## 7. Suggested plan (none of it touches a partition)

Phase 0, now: measure what pixman costs. Read sway CPU (`top -p $(pgrep -x sway)`), SoC temp and battery
`current_now` while scrolling foot/tmux and idle. If sway is a few % CPU for this UI, GPU work is a nice-to-have,
not a blocker. [inference]

Phase 1, modules (phone, reversible, sync first, from SSH over usb0):
- Load the 28-module closure in dependency order with `modprobe` from vendor_dlkm (as `vegas-modules` does), not
  from boot. Check: `/dev/mali0` appears; `ccmni*` stay DOWN and ccci `md_state = 0`; no oops in dmesg; GenieZone
  modules quiet. Set GED loading mode 0 and margin 70. Then `rmmod` is not guaranteed; plan a reboot.
- Run `bringup/gpu-props.py` / `gpu-context-probe.py` from the 2025 repo: confirms API 11.38, product 0x9093 and
  JM version negotiation, with no GPU jobs.

Phase 2, Mesa (build in the vegas-deb VM, arm64 native):
- Clone `tensor-g1` @ `4a03b179`, apply the five functional patches (+ trace), build Panfrost + EGL + GBM + Wayland
  (+ kmsro `mediatek`) into `/opt/vegas-gpu/mesa-kbase`; hard-link every `*_dri.so` alias to one patched build.
- On #5, as separate processes (never touching sway): `gpu-render-probe`, `gpu-hypr-probe` with the `t`/`sbctox`
  flags x300 (this is what exposed the deferred-free bug), `gpu-fence-probe`, `gpu-scanout-probe` with
  `PROBE_EGL_PLATFORM=gbm` on card0. Whether a non-master process may allocate GBM/dumb buffers on card0 while sway
  is DRM master is [unverified]; if not, skip the scanout probe until phase 3.

Phase 3, sway on the GPU:
- Build libwlroots-0.18.so (0.18.2, Debian patches) with the `glFinish` change into the same prefix.
- Add the opt-in flag + guard to `vegas-sway.service`, reboot, verify: sway log shows the GLES2 renderer on
  Panfrost, no kbase "Atom N reported event 0x5x" lines in dmesg, no tearing/partial frames, then measure CPU,
  current and temperature against Phase 0.
- Add a GPU temperature/frequency cap: MediaTek thermal limits are Android userspace here, and `vegas-thermal`
  covers the CPU only [inference from `docs/linux-on-vegas.md` thermal gap].

Exit criteria to drop back to libhybris (option B): kbase faults that the 2025 patches do not cover, or kmsro
GBM on #5's mediatek-drm not producing scanout-able buffers.

## 8. Risks and open questions

- GPU faults and hard resets: the 2025 port had hard resets running a nested GPU Hyprland on the unpatched driver
  with modules loaded live. [report] A hard reset on #5 is recoverable (rescue root, bootfail counter) but loses
  unsynced writes.
- Frozen Mesa 23.0 fork + glibc 2.41 (trixie) + GCC 14: the glibc patch exists, other build breaks are likely.
  [unverified]
- Module closure includes GenieZone (`gz_*`), secure heap and the modem power meter: must be checked live.
- No GPU thermal throttling in Debian unless added. Mali at fixed OPP bypasses MediaTek thermal limits. [report]
- JM atom layout: the 2025 libmali trial found the Motorola kernel reads 64-byte atoms as V2 and 72-byte as V3.
  Mesa panfork worked unmodified on that kernel [report]; #5's module is a different build of the same r38p1
  [verified r38p1; layout identity unverified].
- The D10 rule makes every compositor-level experiment cost a reboot.
- MT6835 GPU details beyond the model (exact revision, OPP table on #5) are [unverified on #5] until phase 1.

## Sources

Local (repo): `docs/linux-on-vegas.md` (sections "GPU and display UI options", "Display"),
`linux/work/ref/moto-g-power-2025-omarchy/{README.md, notes/gpu-bringup-20261007.md,
notes/kms-fence-sync-20261011.md, notes/project-report-20261011.md, notes/kernel-build-20261010.md,
port/vegas/patches/*, port/vegas/root/usr/local/{bin/vegas-desktop-drm, libexec/vegas/gpu-prepare,
sbin/vegas-gpu-boost}, scripts/prepare-vegas-gpu-modules.py}`,
`linux/work/ref/moto-pad-2026-arch-linux/{README.md, docs/FINDINGS.md, tools/src/noplanes.c, wlroots-pad/,
config/android-units/}`, `linux/work/stock/vendor_dlkm/lib/modules/{modules.dep, mali_kbase_mt6835.ko}`,
`logs/<serial>/linux_b/p2/capture2/ramdisk_mods.lst`, `linux/debian/overlay/.../vegas-sway.service`.

Web:
- [MediaTek Dimensity 6300](https://www.mediatek.com/products/smartphones/mediatek-dimensity-6300)
- [GSMArena: Dimensity 6300 announced](https://www.gsmarena.com/mediatek_dimensity_6300_chipset_announced-news-62516.php)
- [91mobiles: Dimensity 6300](https://www.91mobiles.com/processor/mediatek-dimensity-6300-pdp)
- [wlroots 0.18.2 source tarball](https://gitlab.freedesktop.org/wlroots/wlroots/-/archive/0.18.2/wlroots-0.18.2.tar.gz)
- [wlroots MR 4372: open platform device render node](https://gitlab.freedesktop.org/wlroots/wlroots/-/merge_requests/4372)
- [wlroots split render/display workaround commit](https://git.nixnet.services/blankie/wlroots/commit/b89bcffea4fccdf4727f65b58576ba05903daa75)
- [RandomCoderOrg/mesa-gfxstream tensor-g1](https://github.com/RandomCoderOrg/mesa-gfxstream/tree/tensor-g1)
- [apexspan-svg/mesa-panvk-mali-g57](https://github.com/apexspan-svg/mesa-panvk-mali-g57)
- [Collabora: conformant open-source support for Mali-G57](https://www.collabora.com/news-and-blog/news-and-events/conformant-open-source-support-for-mali-g57.html)
- [Mesa Panfrost docs](https://docs.mesa3d.org/drivers/panfrost.html)
- [Phoronix: Mali G1 Pro with PanVK/Panfrost (Mesa 26.2)](https://phoronix.com/news/arm-mali-g1-pro-mesa-26.2)
