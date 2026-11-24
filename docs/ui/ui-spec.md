# Vegas Touch UI v1: implementation spec

> Imported from the v1 build session's working notes. Paths starting `<scratch>/` are that session's working
> folder; its test suites are in `tests/ui-seed/` and move to `tests/ui/` with issue `ui-testing-01`. The design page
> ("Vegas Touch UI", drafts and versions v27 to v30) is the maintainer's private document and is not published; what
> it decided is restated here. The designer's later rulings are in `rulings-report.md` (23 Nov) and
> `rulings-24nov.md` (24 Nov, R1 to R7).

Source: approved design page "Vegas Touch UI", draft 6 (23 Nov 2026), read in full, corrected with the phone facts
verified on #5 on 2026-11-23 and with the repo's overlay as it stands at commit 137558a. Where the two disagree the
newer phone fact wins; every such place is marked **[CORRECTED]**. Defaults the page states for open questions are
marked **[DEFAULT Qn]**. Things the page leaves open and this spec picks are marked **[BUILDER CHOICE]**: change them
freely, they are not design decisions. **[UNVERIFIED]** = nobody has run it on #5.

---------------------------------------------------------------------------------------------------------------------

## 0. Ground rules for every builder (read first)

### 0.1 Hard rules
- **D10, never break**: the compositor must never exit (an exit oopses mediatek_drm and panics the phone). No UI code
  may run `swaymsg exit`, `swaymsg reload` (a reload re-sends a full modeset commit, like a rotation; the page says
  "nothing in this design stops, restarts or reloads the compositor"), kill/signal sway, `systemctl stop|restart
  vegas-sway`, stop seatd, or turn an output off through sway (`output ... dpms off` / `power off` / `disable`).
  Clients (foot, wvkbd, swaybar, bemenu, lisgd) may be killed and restarted.
- Never enable any output but DSI-1. Never `output DSI-1 transform` in a loop; one rotation per user action, never
  while a finger is down (start it from a key, a menu row, or a button *release*).
- The modem is never started: never bring a `ccmni*` interface up, never list them, never start ModemManager.
- Never write NV partitions or `/metadata`. Never touch usb0's config except through `vegas-usbshare`.
- The node comes first: SSH, `vegas-chargeguard`, `vegas-thermal` must never depend on any UI part. A UI crash must
  leave the phone a working farm node.
- No animation, no transparency, no blur, no seconds anywhere, no blinking cursor, whole-number scale, 60 Hz. Only
  CPU-drawn clients in the UI itself (foot, wvkbd, swaybar, bemenu). No GTK4/Qt/OpenGL in the UI.
- One writer of the backlight: `vegas-keys`. Everyone else asks it through `/run/vegas-ui/ctl`.
- Colour carries state only: amber `#F0B429` = warning, red `#FF6B63` = a limit is active, green `#7BD389` = ok,
  dim `#7F8B99`. Background `#0B0F14`, text `#D5DBE3`, strip `#141B24`, row `#17202A`, button `#2B3746`,
  highlight/latched = amber with ink `#1C1400`.

### 0.2 Phone facts the code depends on [CORRECTED where the page is older]
| Thing | Value |
|---|---|
| Compositor | sway 1.10.1, pixman, runs **as root** from `vegas-sway.service` (argv0 `@sway`, `LIBSEAT_BACKEND=noop`, **no seatd**, `RefuseManualStop`, `OOMScoreAdjust=-1000`). Page's "seatd by hand" is history. |
| sway config | `/etc/vegas/sway/config`, repo `linux/debian/overlay/etc/vegas/sway/config`. Config edits take effect at the **next boot** (no reload, see D10). For live tests, issue the same lines as runtime IPC commands (`swaymsg 'for_window [...] ...'`, `swaymsg exec ...`), which is not a reload. |
| Client env | `XDG_RUNTIME_DIR=/run/sway WAYLAND_DISPLAY=wayland-1 SWAYSOCK=$(ls /run/sway/sway-ipc.*.sock \| head -1) LANG=C.UTF-8 COLORTERM=truecolor` |
| Output | DSI-1 1080x2388@60, scale 3 → **360x796 logical**. 15.43 px/mm. |
| Bar | swaybar top, `height 36` logical = 108 px (covers the camera hole), `status_command /usr/lib/vegas/swaystatus`, `font monospace 10`, `status_edge_padding 20`. |
| Gaps (safe area) | left 10, right 10, bottom 16 logical = 30/30/48 px. |
| Terminal | foot 1.21, `font=JetBrains Mono:size=7.25` → 60 columns (cell 17x39 px); tmux 3.5a, `/etc/tmux.conf` already has `mouse on`, UTF-8 + RGB. 37 shell rows with stock keyboard up (+1 tmux bar). |
| Textual | python3-textual 2.1.2 works on #5 (Buttons, Input by finger, Enter submits). **Not in build.sh PKGS yet.** |
| Keyboard | stock `wvkbd-mobintl` 0.15, started `-H 250 --fn "Sans 10"`; SIGUSR1 hides, SIGUSR2 shows. |
| Not installed yet | `bemenu` (trixie 0.6.15), `python3-evdev` (trixie 1.9.1), `lisgd` (0.3.7), `qrencode` (4.1.1). grim is installed. |
| Keys | `mtk-kpd` = Vol-up only (was event0); `mtk-pmic-keys` = Power + Vol-down. Resolve devices **by name**, never by event number. |
| Touch | `ILITEK_TDDI`. Live at backlight 0 → screen-off must mute it. Verified mute: `swaymsg input type:touch events disabled` / `enabled`. EVIOCGRAB mute: **[UNVERIFIED]**. Separate `double-tap` gesture device: untested, ignore in v1. Touch coordinate range still open (Q20): read absinfo max at runtime. |
| logind | Power ignored by `/etc/systemd/logind.conf.d/50-vegas-keys.conf` (also long press, suspend, reboot keys). |
| uinput | `/dev/uinput` exists, root only. |
| Backlight | `/sys/class/backlight/ktd3136-bl/brightness`, max **2047**, boot default **889**. 0 = fully black, saves 60-70 mA. Never write `leds/lcd-backlight`. |
| Battery | `/sys/class/power_supply/battery/{capacity,status,current_now(µA,+ = into battery),voltage_now,temp(deci-°C)}`. capacity reads -1 / missing when `vegas-fuelgauged` is down. |
| Charger | `/sys/class/power_supply/primary_chg/online` (1/0, drops within 1 s). **Never use `type`** (stale). Read named files only (reading every property logs kernel errors). |
| Chargeguard | `/usr/lib/vegas/chargeguard`, oneshot `vegas-chargeguard.service` run by timer every 60 s (first 20 s after boot). Config `/etc/vegas/chargeguard.conf` (STOP=80 RESUME=70 TSTOP=42 TRESUME=40 TOFF=55 SOCOFF=5). State dir `/run/vegas-chargeguard/`: `want` (on/off), `state`, `control` ("control: cmd\|qpnp\|none"), `override-state`, `none` (warning). Override file `/run/vegas-chargeguard/override`: lines `STOP=<n>` `RESUME=<n>` (50..100, RESUME<STOP; else ignored). Charge-to-full = `STOP=100` `RESUME=99`. |
| SoC temp | `/sys/class/thermal/thermal_zone0/temp` (milli-°C) [CORRECTED: page said "zone soc_max"]. Cap: `vegas-thermal` service; compute cap from `/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq` vs `cpuinfo_max_freq` (no state file). |
| Wi-Fi | `wpa_supplicant@wlan0`, ctrl socket dir `/run/wpa_supplicant`, `update_config=1`, conf `/etc/wpa_supplicant/wpa_supplicant-wlan0.conf`; networkd DHCP; resolved. |
| USB | usb0 = 172.16.42.1/24, SSH lifeline. Link = `/sys/class/net/usb0/carrier` == 1 (the address stays without a cable). |
| Tools (`/usr/local/sbin`) | `vegas-usbshare on\|off\|status`; `vegas-hotspot on [min]\|off\|status\|show`; `vegas-rotate normal\|90\|270`; `reboot-rescue [-n]`. |
| Roots | `/etc/vegas/root-role` = `main` on the main root; absent on rescue. Boot counter `/var/lib/vegas/bootfail` (live). `/rescue` = one-shot rescue flag (written by `reboot-rescue`). |
| Load average | Reads ~14 idle (vendor kthreads). Never show it; use /proc/stat CPU share if needed. |

### 0.3 Packages to add to `linux/debian/build.sh` PKGS
`python3-textual,python3-evdev,bemenu,lisgd,qrencode` (v1). Optional travel set later (w3m, firefox-esr ...).
`libip4tc2` is **not** needed [CORRECTED]: `vegas-usbshare` uses `iptables-legacy` NAT, not networkd IPMasquerade.

### 0.4 Code layout [BUILDER CHOICE, keep consistent]
Repo paths are under `linux/debian/overlay/`; installed paths are the same without that prefix.
```
usr/lib/vegas/ui/vegasui/        shared Python package (sources.py = sysfs/tool readers, charge.py = charging word,
                                 ctl.py = /run/vegas-ui helpers, tmux.py, sway.py, pad.py = PIN pad geometry, theme.py)
usr/local/bin/vegas-status       report + strip feed + glance renderer (python3, imports vegasui)
usr/lib/vegas/swaystatus         becomes: exec /usr/local/bin/vegas-status --bar   (keep the path the config names)
usr/lib/vegas/vegas-keys         key daemon (python3-evdev), unit etc/systemd/system/vegas-keys.service
usr/local/bin/vegas-home         Textual app, tmux window 0
usr/local/bin/vegas-net          Textual app, tmux window 1
usr/lib/vegas/vegas-term         foot respawn loop (sh)
usr/lib/vegas/vegas-session      creates the tmux session group layout (sh)
usr/lib/vegas/vegas-gestures     lisgd respawn loop (sh)
usr/lib/vegas/vegas-menu         power menu (bemenu wrapper, called by vegas-keys)
usr/lib/vegas/vegas-glance       glance + PIN pad renderer run inside a foot window (or vegas-status --glance)
usr/local/sbin/vegas-away        on|off|status, iptables rules (sh), unit vegas-away.service
usr/local/sbin/vegas-charge      full|band|status (sh)
```
Every sysfs/proc path goes through one prefix env var `VEGAS_SYSROOT` (default empty) so the readers can be tested
in the trixie VM (`orb -m vegas-deb ...`) against a fake tree, the way chargeguard uses `VEGAS_BAT`.

### 0.5 Runtime directory `/run/vegas-ui/` (mode 0700, root; created by vegas-keys at start and by vegas-term)
| File | Writer | Content |
|---|---|---|
| `ctl` | FIFO, made by vegas-keys | line commands to vegas-keys (see 2.8) |
| `state` | vegas-keys | one word: `off\|glance\|on\|dim\|menu\|pin` |
| `brightness` | vegas-keys | current "on" level (0..2047) |
| `fontsize` | vegas-home | foot point size, default `7.25` |
| `home`, `net` | vegas-home / vegas-net | `highlight=0\|1` (a key-driven highlight exists) |
| `kbd` | strip / vegas-net | `shown\|hidden` (wvkbd 0.15 has no state query) |
| `rotation`, `rotation-last` | vegas-rotate | `normal\|90\|270`; last landscape direction (default 90) |
| `term.pid` | vegas-term | pid of the main foot |
| `pin` | vegas-keys | PIN pad view state for the glance renderer: `n=<digits entered> max=6 hl=<index\|-> msg=<text>` |

---------------------------------------------------------------------------------------------------------------------

## 1. vegas-status (text report + swaybar feed + glance data)

One program, three modes. Home and vegas-net import the same `vegasui.sources` readers instead of shelling out.

### 1.1 Sources, refresh periods, formats, colour rules (page "Status data", corrected)
| Value | Read from | Every | Shown as | Colour |
|---|---|---|---|---|
| Battery | `battery/capacity`, `battery/status` | 60 s | `78%` + glyph: `▲` charging, `=` holding, `▼` draining; `?` if capacity invalid | amber ≤15 %, red ≤5 % (guard powers off at 5); `?` red |
| Charging word | see 1.2 | 60 s | `charging`, `holding`, `full`, `on battery`, `paused: warm`, `no charge control`, `? no gauge`, `starting` | see 1.2 |
| Band | `/etc/vegas/chargeguard.conf` STOP/RESUME; if `/run/vegas-chargeguard/override` exists and `override-state` starts with `override:` → its values | 60 s | `band 70-80 %` / `band 99-100 %` | amber if `control` = `control: none` |
| Battery temp | `battery/temp` /10 | 60 s | `31 °C` | amber ≥40, red ≥42 (charging stops); guard powers off at 55 |
| Charger | `primary_chg/online` | 60 s | `charger in` / `on battery` | amber `on battery` |
| Current | `battery/current_now` µA → A, 1 decimal, signed | 60 s | `+1.1 A`, `0.0 A`, `-0.3 A` | none |
| SoC temp | `thermal_zone0/temp` /1000, rounded | 5 s | `41°` | amber ≥70, red ≥80 |
| CPU cap | min over policies of scaling_max/cpuinfo_max | 5 s | strip: hidden at 100 %, else `cap 80 %`; report/home/glance: `no cap` or `cap 80 %`, plus `2000 / 2400 MHz` = scaling_max of policy0 / policy6 (first and last policy) | red while <100 % |
| Wi-Fi | `/sys/class/net/wlan0/operstate`, `ip -4 -br addr show wlan0`, `iw dev wlan0 link` (SSID, `signal: -52 dBm`, freq) | 10 s | strip `wifi`; home/report `192.0.2.57`, `connected · -52 dBm` | dim when down |
| USB | `usb0/carrier`, address | 10 s | `172.16.42.1` + `Mac connected` / `no link` | amber `no link` on glance |
| USB sharing | `vegas-usbshare status` (`on via wlan0 (...)` / `off`) | 10 s | kind `usb` for the hotspot badge | amber while on |
| Wi-Fi hotspot | `vegas-hotspot status` → `on: <ssid>, N device(s)` / `off` [CORRECTED: page planned a /run kind file + hostapd_cli; the tool's status line already gives both] | 10 s | strip `AP n` badge; home/glance `hotspot wifi · 2 devices` / `hotspot usb` | amber badge |
| Mobile data | constant in v1 | – | `no modem` | dim |
| Away | `/etc/vegas/away` exists | inotify or 10 s | strip `AWAY` badge; glance `away` | amber |
| Root | `/etc/vegas/root-role` | once | `MAIN` badge if `main`, else `RESCUE` | RESCUE amber |
| Rescue pending | `/rescue` exists | 10 s | `rescue pending` | amber |
| SSH | `ss -Htn state established '( sport = :22 )'` line count | 10 s | `1 session`; tmux shows `N attached` | none |
| Health | `systemctl --failed --plain --no-legend \| wc -l`, `/proc/uptime` | 60 s | `0 failed units`, `up 3d 04:12` | amber when >0 |
| Disk | `df -B1 /` free | 60 s | `28 GB free` | none |
| Clock | local time | minute boundary | `09:14` | none |

Traps: never read `primary_chg/type`; read named files only; usb link = carrier only; capacity -1 = no gauge;
never show load average. `vegas-hotspot status` must run as root (reads root-only conf) - all UI runs as root.

### 1.2 Charging word (shared by strip glyph, Home, glance) - page table "The charging line"
Inputs: `want` (`/run/vegas-chargeguard/want`, missing = guard has not run), `soc`, battery temp `t`, `online`,
`control`, override active, STOP/RESUME/TRESUME. Evaluate in this order:
1. soc not an int 0..100 → `?` + `no gauge`, **red** (the guard stops charging then).
2. `control` file says `control: none` → `no charge control`, **red**.
3. `want` file missing → `starting` (guard first runs 20 s after boot), dim.
4. `online` = 0 → `on battery`, **amber** (glyph `▼`).
5. `want=off` and `t ≥ TRESUME` and `soc < STOP` → `paused: warm`, **amber**, temperature line amber too.
6. override active and soc ≥ 100 → `full`, green (glyph `=`); band reads `99-100 %`.
7. `want=on` → `charging`, green (glyph `▲`).
8. otherwise (online, want=off) → `holding`, green (glyph `=`).
Do **not** use the guard's `state` line for the reason (it drops the reason once back in band).

### 1.3 `vegas-status` (no args, or `--report`): plain text report for any shell (SSH, rescue)
Exact layout (60 columns max, values from 1.1):
```
vegas5 Debian 13 main root up 3d 04:12
battery 78 % holding band 70-80 % 31 °C
soc 41 °C no cap (2000/2400 MHz)
wifi up -52 dBm 192.0.2.57
usb up 172.16.42.1
ssh 1 session units 0 failed
```
Extra lines only when relevant: `hotspot wifi: vegas-7k2, 2 device(s)` / `hotspot usb: on via wlan0`,
`away on`, `rescue pending`, `charge to full (override)`. Column-aligned with spaces; colour only when stdout is a tty.
Root word: `main root` / `rescue root`. Exit 0 always (missing values print `?`).

### 1.4 `vegas-status --bar`: swaybar feed + tap handler
- Speaks the **i3bar JSON protocol** (needed for taps). Header `{"version":1,"click_events":true}`, then `[`, then one
  JSON array per update. Every block: `"markup":"pango"`, `"separator":false`, `"separator_block_width":0`.
- Prints a new array **only when a shown value changes** (swaybar repaints the whole 1080x108 bar per line). Never
  more than a few times a minute in steady state. Clock changes on the minute boundary (sleep to it, no polling sub-minute
  except the 5 s SoC/cap read, which only prints if the rounded value changed).
- Layout (page "Terminal" → Strip; nothing in the middle where the camera hole is):
  - **Left block** `name:"home"`: `09:14 vegas5 MAIN`, with `MAIN` as a badge (pango span with background) -
    one wide block, `"align":"left"`, `"min_width"` = enough pixels to fill from the left edge to the start of the right
    group, so a tap anywhere on the left half opens Home. swaybar right-aligns all status blocks, so this padding is
    what puts the text on the left. **[BUILDER CHOICE]** compute `min_width` from the output's logical width
    (`swaymsg -t get_outputs`: 360 upright, 796 landscape) minus the right group's width; tune with `grim` on #5.
    Variants: `RESCUE` (amber) instead of `MAIN`; `rescue pending` (amber) replaces `vegas5 MAIN`; `AWAY` badge
    (amber) after MAIN.
  - **Right blocks**, in this order: `name:"wifi"` text `wifi` (dim when down); `name:"soc"` `41°` (amber/red per
    1.1); optional `name:"cap"` `cap 80 %` red; `name:"bat"` `78%` + dim glyph; optional `name:"ap"` badge `AP 2`
    amber; `name:"kbd"` badge `kbd`.
  - Right group budget ≈ 20 characters; if badges overflow, drop hostname from the left block first, then show `AP`
    without the count. **[BUILDER CHOICE]**; check on the phone that nothing lands over the hole.
- Taps (read JSON click events from stdin in a thread; button 1 only):
  - `home` → `tmux select-window -t main:0` and, if workspace 2 is focused, `swaymsg workspace number 1`.
  - `wifi` → `tmux select-window -t main:1` (+ workspace 1 as above).
  - `kbd` → toggle keyboard: read `/run/vegas-ui/kbd`; shown → `pkill -USR1 -x wvkbd-mobintl`, write `hidden`;
    else `pkill -USR2 -x wvkbd-mobintl`, write `shown`. (v2 build: same signals; binary name differs.)
  - others: same as `home`.
- Must survive swaybar restarts (it is a child of swaybar) and never exit on a read error (print `?`).
- Replace `/usr/lib/vegas/swaystatus` content with `exec /usr/local/bin/vegas-status --bar`.

### 1.5 `vegas-status --glance`: content for the glance window (see 5.4)

---------------------------------------------------------------------------------------------------------------------

## 2. vegas-keys (key daemon, root, python3-evdev)

### 2.1 Unit `vegas-keys.service`
`Type=simple`, `ExecStart=/usr/lib/vegas/vegas-keys`, `Restart=always`, `RestartSec=1`,
`ConditionPathExists=/etc/vegas/root-role` (main root only, D9), `Before=vegas-sway.service` (Away must be in force
before a screen appears), `After=systemd-udevd.service vegas-modules.service`, `WantedBy=multi-user.target`.
Default dependencies are fine (it may be stopped at shutdown; sway must not). It must not need sway to start: if sway
is not up yet it still owns keys, backlight and idle; UI actions wait for `SWAYSOCK`.

### 2.2 Devices
- At start: find `mtk-kpd`, `mtk-pmic-keys`, `ILITEK_TDDI` by `evdev.InputDevice(path).name`; rescan on udev add or
  every 5 s if one is missing.
- **EVIOCGRAB both key devices** permanently (neither logind nor sway sees raw keys). Only KEY_POWER,
  KEY_VOLUMEUP, KEY_VOLUMEDOWN matter; ignore any KEY_POWER from the touch device (Q20: it advertises one).
- Touch device: opened **without** grab for idle tracking; grabbed only to mute (2.5).
- **uinput** virtual keyboard named `vegas-keys` with keys: PAGEUP, PAGEDOWN, UP, DOWN, LEFT, RIGHT, ENTER, ESC,
  TAB, LEFTSHIFT. It stays present always (bemenu crashed when the seat had no keyboard).

### 2.3 Press vs hold (page "Hardware keys")
- Power **press** = released before 0.8 s. Power **hold** = still down at 0.8 s: the hold action fires at 0.8 s while
  still held (not on release). If still held at **5.0 s**: emergency reboot (2.7) regardless of state, even if sway
  or anything else is hung. 5 s must stay shorter than the hardware forced reset (Q18, unmeasured).
- Volume keys: act on press; autorepeat (value 2) of volume keys is forwarded as repeat only in `on` state for
  PageUp/PageDown, ignored elsewhere **[BUILDER CHOICE]**.
- No double press, no key combinations anywhere (page rule).

### 2.4 State machine (states `off`, `glance`, `on`, `dim`, `menu`, `pin`)
Context while `on`: `term` (foot focused, tmux window not 0/1), `home` (tmux `main` current window 0), `net`
(window 1), `prog` (a graphical program focused / workspace 2). Determine at key-press time:
`swaymsg -t get_workspaces` (focused num) + `tmux display-message -p -t main '#{window_index}'`.

| State / context | Power press | Power hold 0.8 s | Vol-up | Vol-down | Timeout |
|---|---|---|---|---|---|
| off | → glance | → menu | nothing | nothing | – |
| glance | → off | → menu | → on (Away: → pin) | same as Vol-up | 10 s → off |
| on/term | → off | → menu | uinput PageUp | uinput PageDown | idle 45 s → dim |
| on/home, on/net | if `/run/vegas-ui/{home,net}` says `highlight=1` → uinput ENTER, else → off | → menu | uinput UP | uinput DOWN | idle → dim |
| on/prog | → off | → menu (with Close program) | PageUp | PageDown | idle → dim |
| dim | any key or touch → on (restore brightness); the waking key does nothing else | → menu | (wake) | (wake) | 15 s more → off |
| menu | uinput ENTER (select) | uinput ESC (cancel) | uinput UP | uinput DOWN | screen-off by idle cancels the menu |
| pin (Away) | press highlighted pad key; if none → off | → short menu | highlight back | highlight forward | 30 s → off |
| any | – | **5 s hold: sync + reboot** | – | – | – |

Timers (page "Screen states", **[DEFAULT Q15]**): dim after 45 s idle (backlight to 10 %), off after 60 s idle
(i.e. 15 s after dim), glance 10 s, pin pad gives up after 30 s; same on the charger. While Away is on: dim at
2 min, off at 3 min. Idle = no event from the three key devices and the touch device (read by the daemon itself, so
it works with sway hung; no swayidle).

### 2.5 Screen on/off mechanics (D4)
- **Off**: backlight → 0 immediately; then wait until no finger is down (BTN_TOUCH 0 / no active tracking id,
  max 3 s), then mute touch. Kill the glance window and bemenu if open. Panel and compositor keep running; nothing is
  suspended. Never use sway output power/dpms (Q3 open).
- **Mute touch**: primary = `EVIOCGRAB` on ILITEK_TDDI (keeps working with sway hung, and lets the daemon read PIN
  pad taps) **[UNVERIFIED on #5: test first]**; fallback/belt = `swaymsg input type:touch events disabled`
  (verified on #5). Unmute = ungrab + `events enabled`. Grab also silences lisgd (it reads the same device).
- **Glance**: start the glance foot window (5.4), wait until it is mapped (poll `swaymsg -t get_tree` for
  `app_id=vegas-glance`, ≤1.5 s), only then raise the backlight, so no shell content is ever lit. Touch stays muted.
- **On** (from glance by a volume key): close the glance window, set backlight to the saved level, unmute touch.
- **Dim**: backlight = min(saved level, 205) (10 % of 2047) **[BUILDER CHOICE: page says "10 %"]**; touch not muted.
- Backlight writes only to `/sys/class/backlight/ktd3136-bl/brightness`. Saved level starts at the value read at
  daemon start, or 889. Kept in `/run/vegas-ui/brightness` (resets each boot) **[BUILDER CHOICE]**.
- At daemon start: Away off → state `on`, touch unmuted. Away on → state `off` (backlight 0, touch muted).

### 2.6 Power menu trigger (5.3) and the PIN pad (5.6)
vegas-keys starts `vegas-menu` as a child with the client env, passes the variant (`full`, `full-prog`
(Close program instead of Restart terminal), `short` (Away locked)) and rotation; reads the chosen row on stdout and
executes it **as root itself**. While the menu is open in Away-locked mode, keep touch muted (keys only), because
taps above the menu would reach the terminal.

### 2.7 Actions executed by vegas-keys
- **Reboot to Android**: `sync`, `systemctl reboot` (verified clean with vegas-sway alive, Q4).
- **Reboot to rescue root**: `/usr/local/sbin/reboot-rescue` (refuses off the main root; prints the Vol-up hint).
- **Power off**: `sync`, `systemctl poweroff` **[UNVERIFIED: power-off with sway alive not yet tested, Q4]**.
- **5 s emergency reboot**: `os.sync()` then the reboot syscall directly (ctypes `reboot(0x01234567)`) so it works
  with systemd or sway hung; lands in Android. Do not route it through sway or bemenu.
- **Screen off**: state → off.
- **Restart terminal**: kill the pid in `/run/vegas-ui/term.pid` (vegas-term reopens it). Never touch sway.
- **Close program**: `swaymsg '[workspace=2] kill'` (or the focused non-`vegas-*` con), then `workspace number 1`.
- **Home**: `swaymsg workspace number 1; tmux select-window -t main:0`.
- **Rotate**: `vegas-rotate <normal or rotation-last>` (toggle upright ↔ last landscape direction).
Never: `swaymsg exit|reload`, stopping vegas-sway, stopping seatd.

### 2.8 Control FIFO `/run/vegas-ui/ctl` (root 0600, line protocol)
`brightness up` · `brightness down` · `brightness set <0..2047>` · `screen off` · `menu` · `away changed` ·
`glance` (debug). vegas-keys recreates the FIFO at start; writers open non-blocking and drop on ENXIO.
Brightness steps **[BUILDER CHOICE]**: `20 40 70 110 170 250 360 520 700 889 1200 1600 2047`.

### 2.9 Away/PIN in vegas-keys (D17)
- Away on ⇔ `/etc/vegas/away` exists (survives reboot; daemon starts before the screen). PIN hash in
  `/etc/vegas/away-pin` (0600, `pbkdf2_sha256$<iter>$<salt>$<hash>`), PIN 4..6 digits.
- Glance + volume key → `pin` state: the glance window switches to the pad (it re-reads `/run/vegas-ui/pin`).
  Touch stays **grabbed**; the daemon maps raw touch coordinates to pad keys itself (geometry from `vegasui.pad`,
  scaled by the device's absinfo max to 1080x2388, honour current rotation) and lets go only after the right PIN.
- Wrong PIN: after 5 wrong tries, a lockout of 30 s that doubles each further failure; counter in
  `/var/lib/vegas/away-fails` (survives reboot) **[BUILDER CHOICE on persistence]**.
- Correct PIN → state `on` until the next screen-off; Away itself stays on.
- Known limit (page): if vegas-keys crashes, touches flow until systemd restarts it (1 s).

---------------------------------------------------------------------------------------------------------------------

## 3. vegas-home (Textual, tmux window 0)

Runs in a respawn loop (5.1). Same page over SSH. Colours per 0.1. One text size (the terminal's); bold labels.

### 3.1 Layout (upright, 60 columns; page drawing "Home (status)")
Top = what you read; bottom = what you press, within thumb reach. Padding: 1 cell row top.
```
vegas5                          up 3d 04:12 · 0 failed units
Battery   78 % holding        (2nd line, dim) charger in · 0.0 A · band 70-80 % · 31 °C
Processor 41 °C               no cap · 2000 / 2400 MHz
Wi-Fi     192.0.2.57        connected · -52 dBm            ← tap: tmux window 1
USB       172.16.42.1         Mac connected | no link
Root      main                disk in /data · 28 GB free  (+ "rescue pending" amber if /rescue)
SSH       1 session           ssh root@192.0.2.57
(blank)
BRIGHTNESS            [ − ] ▇▇▇▇▇▇▇▇▇▇▇▇▇░░░░░░░░░░░░░ [ + ]
TEXT SIZE, COLUMNS    [ 51 ] [ 60 ] [ 68 ] [ 72 ]
SCREEN                [ upright ] [ keys up ] [ keys down ]
WINDOWS               [ 1 net ] [ 2 sh ] [ 3 logs ] [ + new ]
TRAVEL, PROGRAMS, POWER [ Away off ] [ Charge 80 % ] [ Programs ] [ Power ]
```
- Status rows: two text lines each (80 px), label left, value right-aligned, second line dim; row background `#17202A`.
  Value colours per 1.1 (charging word green/amber/red).
- Section labels dim caps on their own line above each button row.
- Buttons: **four text rows tall** (156 px, 10.1 mm), button bg `#2B3746`; the active choice (current text size,
  current rotation) amber with dark ink; "quiet" buttons (`+ new`, `Programs`, `Power`) row-coloured. `−`/`+` fixed
  width (≈13 cols), the bar between them shows the level in 26 cells.
- WINDOWS row lists the live tmux windows of `main` except 0 (`<index> <name>`), max 3, plus `+ new`.
- Refresh: status values every 5-10 s, repaint only changed widgets (no timers faster than 5 s).
- Over 100 columns wide (landscape, 127-132 cols): two columns, status left, buttons right; Home checks its own size
  (Textual 2.1.2 has no breakpoints).

### 3.2 Behaviour of each control
- `−` / `+`: write `brightness down|up` to `/run/vegas-ui/ctl`; bar from `/run/vegas-ui/brightness`. Never sysfs.
- Text size `51 60 68 72` → point sizes `8.25 7.25 6.25 5.75` (cells 20/17/15/14 px inside the 30 px margins; only
  60 is measured on #5). Write `/run/vegas-ui/fontsize`, then kill the main foot (`term.pid`); vegas-term reopens it.
- SCREEN: `upright` → `vegas-rotate normal`; `keys up` → `vegas-rotate 90`; `keys down` → `vegas-rotate 270` (5.8).
  Act on button release only.
- WINDOWS: tap → `tmux select-window -t main:<n>`; `+ new` → `tmux new-window -t main` (it becomes current).
- Wi-Fi row tap / `1 net` → `tmux select-window -t main:1`.
- `Away off|on` → 5.6. `Charge 80 %|full` → 5.7 (label reflects the override live).
- `Programs` → a list (modal) of installed graphical programs (`command -v` over a fixed table: `firefox-esr`,
  `netsurf-gtk3`, `zathura`); tap → `swaymsg exec <cmd>`; empty list → "No graphical programs installed".
- `Power` → write `menu` to the ctl FIFO.
- Keys only: Up/Down (from vegas-keys) move a **key highlight** through the buttons in reading order (focus
  previous/next); Enter presses it. Write `/run/vegas-ui/home` `highlight=1` while a key highlight exists; clear it
  (`highlight=0`) on any mouse/touch event, after 15 s without a key, and when `/run/vegas-ui/state` becomes `off`
  **[BUILDER CHOICE on the clearing rules]**. A finger tap must not leave a highlight (else Power would press it).
- Never put network set-up or the hotspot on Home (page draft 6).

---------------------------------------------------------------------------------------------------------------------

## 4. vegas-net (Textual, tmux window 1)

Talks to wpa_supplicant through its control socket (`wpa_cli -p /run/wpa_supplicant -i wlan0 ...`, or a direct
unix-datagram client). No NetworkManager, no new service (D14). Shares widgets/theme with Home.

### 4.1 Layout (upright, page drawing "Network")
```
Network                                    scanned 0:12 ago
harbour-guest  connected   192.0.2.57 · -52 dBm · 5 GHz · WPA2
IN RANGE
▂▄▆█ harbour-guest
     -52 dBm · 5 GHz                         ● WPA2 saved
▂▄▆█ cafe-lumen
     -61 dBm · 2.4 GHz                       ○ open
... (6 rows)
▼ 9 more
SHARE THIS CONNECTION
[ Hotspot off ]            [ Mobile data · no modem ]
NETWORK
[ Rescan ] [ Sign-in check ] [ More ]
```
- Top block: SSID, `connected` (green), address · dBm · band · security. Not connected → `Not connected` amber.
- List: networks in range, strongest first, deduplicated by SSID (strongest BSS), hidden SSIDs omitted, saved marked
  `saved` (green). Each row **three text rows tall** (120 px, 7.8 mm). 6 rows shown, `▼ N more` expands.
- Bars: lit part green, rest dim; 4 bars ≥ -55, 3 ≥ -67, 2 ≥ -75, else 1 dBm **[BUILDER CHOICE]**.
- Marks: `●` protected, `○` open, with `WPA2` / `WPA3` / `open` written out (no padlock glyph in the fonts).
  Security from scan flags: `SAE` only → WPA3; `WPA2-PSK`/`WPA-PSK` (with or without SAE) → WPA2; `EAP` →
  `802.1X` (not joinable in v1, show "not supported"); `[ESS]` only → open. Band: freq < 3000 → `2.4 GHz`, else `5 GHz`.
- Buttons four text rows tall (160 px, 10.4 mm). No Back button (it is a window). Never list `ccmni*`.
- Landscape (wide): list left, buttons right.
- Header shows time since the last scan result; scan at start, on Rescan; refresh status every 10 s.
- SSIDs: wpa_cli prints them escaped (`\xNN`); decode to UTF-8 for display, always send them to wpa_supplicant as
  **hex** (`set_network <id> ssid <hex>`), as `linux/tools/wifi-conf.sh` does; match saved entries by quoted or hex
  form. Names outside ASCII and spaces must work.

### 4.2 Tap a row
- **Saved network**: dialog `Connect` / `Forget` / `Move up` / `Move down` / `Cancel`.
  - Connect: `select_network <id>`, wait `wpa_state=COMPLETED`, then `enable_network all` (select disables the
    others), no save needed. Steps shown as for Join.
  - Forget: `remove_network <id>`, `save_config`.
  - Move up/down: `set_network <id> priority <n>`, `save_config`.
- **New protected (WPA2)**: passphrase page (4.3).
- **New open**: `add_network`, `ssid <hex>`, `key_mgmt NONE`, `enable_network`, wait, `save_config` on success,
  then run the sign-in check (4.5).
- **New WPA3-only** (SAE without PSK): passphrase page; `key_mgmt SAE`, `sae_password "<as typed>"`,
  `ieee80211w 2`, global `set sae_pwe 2`. Label it "WPA3: may not work yet" - wpa_supplicant on #5 does not list SAE
  among its key types (Q27) **[UNVERIFIED]**.

### 4.3 Passphrase page (page "Joining a network")
- Field hidden as you type (Textual `Input(password=True)`), `Show passphrase` toggle that **returns focus to the
  field**, `Join`, `Cancel`. 8..63 characters for WPA2 (validate before sending).
- Keyboard: on opening the field, show wvkbd (SIGUSR2, write `kbd=shown`); hide after Join/Cancel (SIGUSR1).
- Join (WPA2): compute the PSK on the phone, `hashlib.pbkdf2_hmac('sha1', pass, ssid_bytes, 4096, 32).hex()`, and
  store the **hash**, never the passphrase: `add_network`, `set_network id ssid <hex>`, `psk <64-hex>` (unquoted),
  `enable_network id`. Show steps: `joining` → `getting an address` → `connected` (`wpa_state=COMPLETED`, then an IPv4
  on wlan0). On success `save_config`.
- Wrong passphrase: wpa_supplicant event `CTRL-EVENT-SSID-TEMP-DISABLED ... reason=WRONG_KEY` (or poll
  `list_networks` flags `[TEMP-DISABLED]`) → `remove_network`, say `Wrong passphrase?`, reopen the field.
- Timeout 60 s without COMPLETED → remove the new entry, say so.
- Over-SSH guard: if an established SSH session's local address is wlan0's address, show "This cuts your SSH over
  Wi-Fi" and offer `Join, go back if it fails`: if no address within 60 s, `select_network <old id>` +
  `enable_network all`. usb0 is never affected.
- With three keys a new passphrase cannot be typed: needs touch keyboard or SSH (same page).

### 4.4 Hotspot switch (D15) [CORRECTED: both kinds exist as tools now]
- Button `Hotspot off` / `Hotspot on · wifi` / `Hotspot on · usb`. Tap when off → kind chooser:
  `USB to laptop` / `Wi-Fi hotspot` / `Mobile data · no modem` (greyed, does nothing) / `Cancel`.
- **USB to laptop**: second confirm ("changes how the laptop reaches the internet; the cable is also the farm's
  management link") → `vegas-usbshare on`. Show its output (the laptop must renew its DHCP lease). Off:
  `vegas-usbshare off`. Lasts until reboot (`/run` file); the tool has no auto-off.
- **Wi-Fi hotspot**: `vegas-hotspot on 60` **[CORRECTED]**: the tool's own limit (default 60 min, 1..720) replaces the
  page's "10 minutes with no device". Off: `vegas-hotspot off`. It fails cleanly when the uplink is on a 5 GHz DFS
  channel or 5 GHz without a country: show the tool's stderr and stay off. Never retry in a loop (chip reset loops).
- Only one kind on at a time in the UI (the tools themselves tolerate both).
- Hotspot page while on: kind, SSID, passphrase as plain text (from `vegas-hotspot show`), devices
  (`vegas-hotspot status`), feeding network (wlan0 SSID), battery, SoC temp; QR code from
  `qrencode -t UTF8 'WIFI:T:WPA;S:<ssid>;P:<psk>;;'` (≈33x17 cells); buttons `Turn off`, `New passphrase`
  (only while off: rewrite `/etc/vegas/hotspot.conf` with the same SSID and a new 16-char PSK of
  `[a-km-zA-HJ-NP-Z2-9]`, mode 0600 via temp+rename).
- Page rules not yet in the tool (follow-up for `vegas-hotspot run`, not UI code): off below 25 % without charger,
  off at SoC 75 °C, off when the uplink goes away, off after 10 min with no device. Never on after a boot: already
  true (state in /run).

### 4.5 Sign-in check
`curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://connectivitycheck.gstatic.com/generate_204` **[BUILDER
CHOICE of URL]**: 204 = online; anything else = a sign-in page is in the way. Also read a portal URL from
`networkctl status wlan0` (Captive Portal line) if present. Then offer `Open in w3m` (`tmux new-window -t main -n
signin "w3m <url>"`, only if w3m is installed) and `Open in Firefox` (`swaymsg exec 'firefox-esr <url>'`, only if
installed). No real sign-in page tried yet.

### 4.6 Mobile data row (D16)
`Mobile data · no modem`, dim, no action; tap shows "Reboot to Android for calls and mobile data". Never start or
query the modem; never show IMEI/SIM numbers.

### 4.7 More (v1 scope)
Page: "the Network screen starts small: list, join, forget, address. The items under More come later." v1 More =
`Saved networks` (forget / priority) and `Hidden network` (SSID + passphrase, `scan_ssid 1`). `Country`,
`Time zone`, `VPN`, `Borrow a device address` shown dim as "later".

### 4.8 Keys only
Up/Down move a key highlight through list rows and buttons; Enter presses it; same `/run/vegas-ui/net`
`highlight=` file and clearing rules as Home. Joining saved/open networks, forgetting, and the hotspot work by three
keys.

---------------------------------------------------------------------------------------------------------------------

## 5. Session glue

### 5.1 tmux session group (D6) - `/usr/lib/vegas/vegas-session`
- Phone session `main`. If it does not exist, create (env `LANG=C.UTF-8 COLORTERM=truecolor`):
  - window 0 `home`: `while :; do vegas-home; sleep 1; done`
  - window 1 `net`: `while :; do vegas-net; sleep 1; done`
  - window 2 `sh`: login shell (current window at start: the terminal is the home screen)
  - window 3 `logs`: `journalctl -f -n 50 -o short` **[BUILDER CHOICE; the drawing shows a logs window]**
- The Mac joins with `tmux new -A -s mac -t main -f ignore-size` (own current window; never resizes the phone).
  Phone-side commands always name the session (`-t main` / `main:0`).
- Add to `/etc/tmux.conf`: `status-position top`, status bar background `#1D2733`, left `[#{session_name}]` + window
  list (`0:home 1:net 2:sh* 3:logs`), right `#{session_group_attached} attached`; and the PageUp-at-a-prompt binding:
  `bind -n PPage if -F '#{||:#{==:#{pane_current_command},bash},#{==:#{pane_current_command},sh}}' 'copy-mode -eu' 'send-keys PPage'`
  **[UNVERIFIED]**. Keep `mouse on`.

### 5.2 Terminal loop - `/usr/lib/vegas/vegas-term` (started from sway config)
```
mkdir -p -m700 /run/vegas-ui
while :; do
  size=$(cat /run/vegas-ui/fontsize 2>/dev/null || echo 7.25)
  /usr/lib/vegas/vegas-session
  foot -a vegas-term -o "font=JetBrains Mono:size=$size" -o dpi-aware=no tmux attach -t main &
  echo $! > /run/vegas-ui/term.pid; wait $!
  sleep 1   # back off to 5 s after 5 fast exits
done
```
So `exit`, detaching tmux, or a text-size change never leaves only the strip. sway exec splits at spaces: keep the
font option quoted. Cursor blink off, foot DPI-aware sizing off (else a rotation could change the font size).
[CORRECTED] Today's config starts plain foot directly (`exec choom -n 0 -- env ... foot -o "font=..."`), with no
tmux and no loop. Replace it with `exec choom -n 0 -- /usr/lib/vegas/vegas-term` (keep `choom -n 0`: clients must
not inherit sway's -1000 OOM score).

### 5.3 Power menu - `/usr/lib/vegas/vegas-menu <full|full-prog|short> <upright|landscape>` (bemenu 0.6.15)
- `BEMENU_BACKEND=wayland bemenu -l 8 -b -W 1.0 -H 50 -p 'Power · volume keys move, Power selects'
  --fn 'JetBrains Mono 15'` plus colours (`--tb/--nb #0F151C`, `--tf #F0B429`, `--hb #F0B429 --hf #1C1400`, `--nf #D5DBE3`).
  Rows 150 px (= `-H 50` at scale 3; planned, unmeasured). Landscape: `-H 36` (108 px) so all rows fit.
  Font size **[BUILDER CHOICE]**; covers the lower half, terminal visible above. Taps work in list mode.
- Rows, in order (full): `Screen off`, `Rotate`, `Reboot to Android`, `Reboot to rescue root`, `Power off`,
  `Restart terminal`, `Home`, `Cancel`. `full-prog`: `Close program` replaces `Restart terminal` (list stays 8 rows).
  `short` (Away, PIN not entered): `Screen off`, `Reboot to Android`, `Power off`, `Cancel`.
- `Power off` opens a two-row confirm list (`Power off now`, `Cancel`).
- No "Reboot to Debian" row (needs a boot-chooser flag, Q10).
- While `/rescue` exists, Home and the strip show `rescue pending` amber.
- Prints the chosen row to stdout; vegas-keys executes it (2.7). Exit ≠ 0 = cancel → back to `on`.

### 5.4 Glance screen
- A separate foot window: `foot -a vegas-glance -o 'font=JetBrains Mono:size=22.5' -o pad=0x0 vegas-status --glance`
  (20 columns, cells 54x119 px, capitals 4.3 mm). Started by vegas-keys on each wake, killed on leave.
- sway rule: `for_window [app_id="vegas-glance"] floating enable, fullscreen enable, border none` - covers strip and
  keyboard, leaves the terminal at full size (plain fullscreen squeezed it to 30 cols).
- Content (1-space left margin, values right-aligned to column 19; top padding ≈150 px):
```
 09:14   Mon 23 Nov          (time bold, date dim)
 BATTERY        78%
 holding     70-80%          (charging word coloured per 1.2)
 charger in   0.0 A
 temperature   31°C
 PROCESSOR     41°C
 no cap
 NETWORK
 wifi 192.0.2.57           (addresses never cut short; drop label padding instead)
 usb   172.16.42.1           (or "usb no link", amber)
 ssh     1 session
 hotspot wifi  2             (only while on: kind and device count)
 main root    up 3d          ("away" amber here while Away is on)
```
- Landscape: two columns, 44x9 at the same type size.
- Touch muted throughout; Power → off; Vol → continue (on, or PIN pad); 10 s → off.

### 5.5 PIN pad (drawn in the glance window)
```
 09:14   Mon 23 Nov
 AWAY   78% holding          (AWAY amber)
 PIN   ● ● ○ ○ ○ ○           (● entered, ○ remaining up to 6)
 [1] [2] [3]
 [4] [5] [6]
 [7] [8] [9]
 [⌫] [0] [OK]                (⌫ and OK quiet-coloured, smaller glyph)
```
Keys 6 cells wide x 2 rows tall (324x238 px, 21x15 mm), 1-cell column gap, 1-row gap: columns 0-5, 7-12, 14-19
(3x324+2x54 = 1080). The geometry lives in `vegasui.pad` and is used both to draw and by vegas-keys to hit-test.
Highlighted key amber. Lockout message on the PIN line. Gives up after 30 s → off.

### 5.6 Away switch (D17, **[DEFAULT Q29: own touch pad]**, **[DEFAULT Q31: SSH closed on Wi-Fi]**)
`/usr/local/sbin/vegas-away on|off|status` + `vegas-away.service` (oneshot at boot, re-applies rules if
`/etc/vegas/away` exists).
- Home `Away off` → if no `/etc/vegas/away-pin`: ask a new 4..6 digit PIN twice (Textual Input, password, digits);
  then create `/etc/vegas/away`, apply rules, write `away changed` to ctl. `Away on` → ask the PIN; correct → remove
  `/etc/vegas/away`, drop rules.
- SSH rules (iptables-legacy; no nftables on this kernel), own chain:
  `-N VEGAS-AWAY`; `-A VEGAS-AWAY -i lo -j RETURN`; `-i usb0 -j RETURN`; `-i wg+ -j RETURN`;
  `-p tcp --dport 22 -j DROP`; hook `-I INPUT -p tcp --dport 22 -j VEGAS-AWAY`. Must never match usb0. Idempotent.
- Effects: glance → PIN pad; short power menu until PIN; timers 2/3 min; strip `AWAY` badge; glance `away`.
- Limits (state them in UI help): guards the running phone, not the disk; weaker than a real lock.

### 5.7 Charge-to-full switch - `/usr/local/sbin/vegas-charge full|band|status`
- `full`: write `/run/vegas-chargeguard/override` with `STOP=100\nRESUME=99\n` (temp + rename), then
  `systemctl start vegas-chargeguard.service` to apply now instead of within 60 s (oneshot; safe).
- `band`: remove the file, run the guard once.
- `status`: `full` if `override-state` starts with `override: STOP=100`, `band`, or `ignored` if it starts with
  `WARNING`.
- Home button label: `Charge 80 %` (band) / `Charge full` (amber). Ends by itself at reboot (/run). Temperature
  limits still apply (pauses at 42 °C). Separate from Away.

### 5.8 Rotation entry points (D13; manual only, **[DEFAULT Q23: keys up]**, **[DEFAULT Q24: no auto]**)
- Mapping [CORRECTED from #5]: `keys up` = transform **90** (camera/top edge to the left, cable right);
  `keys down` = **270**; upright = `normal`. 180 is never offered.
- Entry points: Home's three SCREEN buttons; power-menu `Rotate` (upright ↔ `/run/vegas-ui/rotation-last`,
  default 90); the command `vegas-rotate` (works over SSH).
- Extend `vegas-rotate` (repo overlay) to: write `/run/vegas-ui/rotation` and, for 90/270, `rotation-last`; then
  `pkill -x lisgd` (vegas-gestures restarts it with the new `-o`). It already moves the gaps (cutout side 32 logical =
  96 px gap, opposite 16).
- After rotating: bemenu uses `-H 36`; Home/Net/glance switch to two-column layouts by their own size. foot/tmux,
  the strip and touch follow by themselves (`input type:touch map_to_output DSI-1` is in the config).
- Add `output DSI-1 ... subpixel none` to the config (sway does not rotate subpixel order). Fixed directions only.

### 5.9 sway config changes (all take effect next boot; live test via `swaymsg` runtime commands)
- `output DSI-1 enable mode 1080x2388@60Hz scale 3 position 0 0 subpixel none ...`
- `exec choom -n 0 -- /usr/lib/vegas/vegas-term` (replaces plain foot)
- keep `exec choom -n 0 -- wvkbd-mobintl -H 250 --fn "Sans 10"` (v1); write `shown` to `/run/vegas-ui/kbd` at start
- `exec choom -n 0 -- /usr/lib/vegas/vegas-gestures`
- `for_window [app_id="vegas-glance"] floating enable, fullscreen enable, border none`
- Graphical programs on workspace 2, tiled, never fullscreen (D18):
  `for_window [app_id="^(?!vegas-term$|vegas-glance$).*"] move container to workspace number 2, workspace number 2`
  (bemenu and wvkbd are layer-shell surfaces, not windows, so the rule does not touch them).
- (v2 keyboard) `bindsym F20 exec pkill -USR1 -x wvkbd-vegas` for the Hide key.

---------------------------------------------------------------------------------------------------------------------

## 6. Keyboard v2 and gestures

### 6.1 v1 keyboard (ships now): stock wvkbd-mobintl 0.15, `-H 250 --fn "Sans 10"`
Ctrl locks (stays until tapped again), no Alt on layer 1, no F-keys. Show/hide only by signal: strip `kbd` badge and
bottom-edge swipe. Never `--auto`.

### 6.2 v2 keyboard: our build of wvkbd 0.21 (approved; build step 5)
- Source: `linux/work/ref/moto-g-power-2025-omarchy/vendor/wvkbd` (0.21, upstream e14b53a, gitignored; has an
  optional `WVKBD_IMMEDIATE_DRAW=1` patch and a 2025 five-row phone layout from
  `scripts/build-vegas-phone-keyboard.py` there). GPLv3: keep it out of the MIT tree, install as `wvkbd-vegas`.
- Custom `layout.vegas.h` / `config.vegas.h`. Layers: **letters**, **symbols with navigation**, **F1-F12**, plus a
  landscape layer of its own.
- Letters layer (widths relative, 1 = letter key):
  - top row (94 px tall): `Esc Tab Ctrl Alt ← ↓ ↑ → Hide`
  - `1 2 3 4 5 6 7 8 9 0` (104 px)
  - `q w e r t y u i o p`
  - `a s d f g h j k l`
  - `Shift(1.5) z x c v b n m ⌫(1.5)`
  - `Sym(1.5) / - [space 4] . Enter(1.5)`
- Symbols layer (page drawing): top `Esc Tab Ctrl Alt Home PgDn PgUp End Hide`; `! @ # $ % ^ & * ( )`;
  `~ \` | \ { } [ ] < >`; `_ + = : ; " ' ? , .`; `F1-12(2) ← ↓ ↑ → Ins Del ⌫(2)`; `abc(1.5) / - [space 4] . Enter(1.5)`.
  Note: the page text says the top row is the same on every layer (with arrows) while the symbol drawing puts
  Home/PgDn/PgUp/End there and arrows lower; follow the drawing **[BUILDER CHOICE, flag to user]**.
- F layer: F1..F12 + top row + `abc`.
- Height **764 px** total (49.5 mm, 32 %): `-H 255` logical **[BUILDER CHOICE: 764/3 ≈ 255]**; letter keys
  102x124 px on a 108 px pitch.
- Modifiers one-shot (0.16+): tap Ctrl → amber, applies to next key, then clears; tap again to cancel. No lock, no
  long press (holding repeats).
- Labels two sizes: letters use scheme 0 font; word keys (Esc, Tab, Ctrl, Alt, Shift, Sym, Enter, Hide, F1-12...)
  use scheme 1 with a smaller font so each fits its key. Exact sizes measured on #5 **[BUILDER CHOICE]**.
- Hide: wvkbd has no hide key: `Hide` emits an unused keycode (F20) that sway binds to `pkill -USR1 -x wvkbd-vegas`.
- Show/hide stays manual (no `--auto`). Colours: keys `#1C2530`/`#2B3746`, text `#E8EDF3`, latched amber `#F0B429`.
- Fallback with no build: squeekboard 1.43 (GTK, Esc only on page 2).

### 6.3 lisgd gestures - `/usr/lib/vegas/vegas-gestures`
Loop: find the ILITEK_TDDI event node by name; orientation from `/run/vegas-ui/rotation` (`normal`→0; 90/270 → 1/3
**[UNVERIFIED: confirm direction on #5]**); run
```
lisgd -d /dev/input/eventN -o <o> \
  -g '1,DU,B,*,R,pkill -USR2 -x wvkbd-mobintl; echo shown > /run/vegas-ui/kbd' \
  -g '1,LR,L,*,R,tmux previous-window -t main' \
  -g '1,RL,R,*,R,tmux next-window -t main'
```
restart on exit (sleep 1). Swipe up from the bottom edge = show keyboard; swipe in from the left edge = previous
tmux window, from the right edge = next. Stock edge band 50 px (3.2 mm); the design's 96 px needs a rebuild or a
scaled `-w/-h` **[UNVERIFIED]**. lisgd does not consume touches: an edge swipe also reaches the terminal as a short
scroll. Strip taps are swaybar's (1.4). Terminal gestures (tap = click, quick drag = scroll, hold 0.4 s then drag =
select) are foot's own (`[touch] long-press-delay=400`), passed to tmux.

---------------------------------------------------------------------------------------------------------------------

## 7. Build order and acceptance (page "Build order", corrected)
1. Packages (0.3) into build.sh; in the VM: `orb -m vegas-deb sudo apt-get install python3-textual python3-evdev
   bemenu lisgd qrencode` for tests.
2. vegas-status (report, `--bar`, `--glance`) - testable in the VM with `VEGAS_SYSROOT`. Done when the strip shows
   the badges and taps open Home/Net/keyboard.
3. Session glue: vegas-session, vegas-term, tmux.conf, sway config lines. Done when typing `exit` or changing text
   size reopens the terminal in the same tmux place, and the Mac attaches as `mac` without resizing the phone.
4. vegas-keys + vegas-menu + glance. Done when: Reboot to Android works by keys alone; a tap on the dark screen does
   nothing; Power off really powers off (Q4, still open). The page's test "with the compositor frozen in a debugger"
   (screen on/off and the 5 s reboot still work) is a supervised test for the user only: builders never signal,
   stop or attach to sway.
5. vegas-home. Done when everything on Home works by touch alone and by keys alone.
6. vegas-net incl. hotspot page. Done when you join a new network on the glass, reboot, and the phone is back on it;
   a laptop on the cable reaches the internet through `USB to laptop`.
7. Away, charge-to-full, rotation entry points, gestures.
8. Keyboard v2.

## 8. Open questions and the page's defaults (for builders)
Q6 wake → glance first, volume key continues (touch muted on glance). Q7 no PIN at home, PIN only with Away. Q8 one
user: root (sway must stay root). Q9 volume keys = PageUp/PageDown in the terminal. Q10 no "Reboot to Debian".
Q13 rescue root stays headless. Q14 double-tap wake not in v1. Q15 45 s / 60 s / 10 s; Away 2 / 3 min. Q18 5 s
reboot hold (hardware reset time unmeasured). Q21 answered (primary_chg/online, current_now µA). Q22 rotation
survives (transform 90 verified; touch follows per vegas-rotate header). Q23 keys up, 96 px gap. Q24 no auto
rotation. Q25 Wi-Fi hotspot verified on 2.4 GHz per vegas-hotspot header [CORRECTED]. Q26 USB sharing verified per
vegas-usbshare header, via iptables-legacy [CORRECTED]. Q27 WPA3 unconfirmed. Q28 terminal set + NetSurf + PDF viewer
+ Firefox; no sound. Q29 own touch pad. Q30 encrypted folder (not in v1 UI). Q31 Away closes SSH on Wi-Fi (USB, VPN
open). Q33 "no modem" row only. Q35 tmux mouse on (already set). Q38 keep our own screens, no NetworkManager.

## 9. Corrections applied (page vs newer phone facts)
1. sway runs as root from vegas-sway.service with `LIBSEAT_BACKEND=noop`; no seatd at all (page's stack table/report
   mock lists seatd). Report must not check seatd.
2. Glance/menu/clients need `XDG_RUNTIME_DIR=/run/sway`, `WAYLAND_DISPLAY=wayland-1`, SWAYSOCK glob.
3. Config changes are next-boot only; no `swaymsg reload` (D10 spirit). Use runtime swaymsg commands for testing.
4. Current config runs plain foot without tmux or loop; vegas-term replaces it.
5. SoC temp from `thermal_zone0/temp` (milli-°C).
6. Touch mute: `swaymsg input type:touch events disabled` is verified; EVIOCGRAB is not yet.
7. Hotspot (`vegas-hotspot`) and USB sharing (`vegas-usbshare`) exist and, per their headers, ran on #5; the UI is a
   front-end to them. Wi-Fi hotspot auto-off = the tool's time limit (default 60 min), not the page's 10-min idle
   rule; the page's other auto-off rules are a follow-up inside the tool. libip4tc2 not needed.
8. Rotation: `vegas-rotate normal|90|270` exists; 90 = camera left = keys up; it already moves the gaps.
9. Chargeguard override path/format confirmed; apply immediately by starting the oneshot service.
10. python3-textual works on #5 but is not in build.sh; bemenu, python3-evdev, lisgd, qrencode not installed.
11. Stock keyboard runs at `-H 250` (750 px) with `--fn "Sans 10"`.
12. Boot counter is live; RESCUE badge covers the fallback boot.
