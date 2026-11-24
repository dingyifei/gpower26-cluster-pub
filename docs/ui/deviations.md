# Vegas Touch UI v1: where the build differs from the design page

> Imported from the v1 build session's working notes. Paths starting `<scratch>/` are that session's working
> folder; its test suites are in `tests/ui-seed/` and move to `tests/ui/` with issue `ui-testing-01`. The design page
> ("Vegas Touch UI", drafts and versions v27 to v30) is the maintainer's private document and is not published; what
> it decided is restated here. The designer's later rulings are in `rulings-report.md` (23 Nov) and
> `rulings-24nov.md` (24 Nov, R1 to R7).

Compared: design page v30 (draft 7, all 1701 lines) plus designer-points.md, against the uncommitted repo files under
`linux/debian/overlay/`, `linux/ui-src/wvkbd/`, `linux/debian/build.sh` and `scripts/linux_b.sh`, read on 23 Nov.
Nothing here has run on #5. Each item gives: **Page** (section or D/Q number), **Build** (file), **Why** (if known).
"Builder choice" means the page gave no value and a builder picked one.

---------------------------------------------------------------------------------------------------------------------

## 1. Strip (swaybar + `vegas-status --bar`, `usr/lib/vegas/swaystatus`)

1. **Right-hand content.** Page (Screens > Terminal, "Strip"): "Wi-Fi, SoC temperature, battery and a keyboard
   button on the right." Build: up to `wifi usb 41° cap 80% 78%▲80 AP 2 kbd`. Added: a `usb` word, a `cap N%` block,
   the charge-band top after the battery glyph (amber `100` during charge-to-full), and the AP badge. Upright, these
   drop in a fixed order to keep clear of the camera hole: band top, AP count, `usb`, the cap block (the SoC
   temperature turns red instead), `wifi`, then `kbd` becomes `k`, then the AP badge. Rotated (796 logical wide), all
   of it shows. Normal upright reads `09:14 vegas5 MAIN | gap | wifi 41° 78%▲ kbd`. Why: the status table asks for a
   cap block, AP badge and charge-to-full state in the strip; the drop order is a builder choice for the hole.
2. **Camera-hole gap.** Page: "Nothing in the middle, where the camera hole is"; hole size is a guess (Q5). Build: a
   centred gap of 20 logical px (60 px, 3.9 mm), tunable with `VEGAS_STRIP_HOLE`. Why: hole size unmeasured; builder
   choice, to check with grim on #5.
3. **Left side when rescue is pending.** Page (Power menu > Rescue root, designer point 9): Home and the strip show
   "rescue pending" in amber. Build: the strip replaces the hostname and the MAIN badge with amber `rescue pending`,
   shortened to `rescue` when space runs out. Off the main root, `RESCUE` is shortened to `RESC` when AWAY must also fit.
4. **Block names.** Page (Gestures table): the strip has "wifi" and "kbd" to tap. Build: blocks `home`, `net`, `soc`,
   `cap`, `bat`, `ap` and `kbd`. The links block is `net` ("wifi usb"), and a tap on it opens tmux window 1. Taps on
   `soc`, `cap`, `bat` and `ap` open Home, like the left block.
5. **Tap targets.** Page: a tap anywhere on the left block opens Home. Build: the same. Also, if workspace 2 (a
   graphical program) is in front, a tap switches to workspace 1 first. This matches the page's "Back: tap the strip".
6. **kbd badge colour.** Page drawing: a plain "kbd". Build: amber while the keyboard is shown, grey while hidden.
   This bends the page's rule that colour carries state only and amber means a warning.
7. **Strip sideways swipe for workspaces.** Page (Keys and gestures; v28 change 5): "A sideways swipe along the strip
   switches sway workspaces." Build: not built. swaybar gets no swipe, and vegas-gestures binds only the bottom,
   left and right edges. The designer asked for a report if swaybar cannot do it. It was not attempted.
8. **SoC temperature updates.** Page (Status data): every 5 s, rounded to whole degrees. Build: the reading is every
   5 s, but the strip only changes the shown value after a move of at least 2 °C or a change of colour band. Why:
   builder choice, to avoid repainting the whole bar on 1 °C jitter.
9. **Hotspot source for USB sharing.** v28 change 4 / designer point 6: the status sources are `vegas-hotspot status`
   and `vegas-usbshare status`, "not a /run file". Build: the strip and the glance check
   `/run/systemd/network/05-usb0-share.network` for USB sharing, and `/run/vegas-hotspot` before asking
   `vegas-hotspot status`. Only the Network screen asks both tools. Why: no fork in steady state.
10. **SSH count method.** Page (Status data): open connections on port 22, "counted with ss". Build: the strip, Home
    and the report read `/proc/net/tcp{,6}`, so no fork. The glance does use `ss`.
11. **Strip background.** Spec colours give the strip as `#141B24`. Build: sway's bar block keeps `background #000000`.
12. **Fallback.** Not on the page. `swaystatus` first probes `vegas-status --bar-once` with a 15 s timeout. If that
    fails, it falls back to the old plain 20 s line, so the strip never goes blank.
13. **Rotation refit.** Not on the page. A read-only sway IPC output subscription re-fits the strip right after a
    rotation.

## 2. Text report (`vegas-status`, no arguments)

1. **Layout.** Page (The idea / Terminal drawing): six lines (host / battery / soc / wifi / usb / ssh). Build: the
   same order with these changes:
   - A second battery line, `charger in|on battery|charger ?  +0.0 A`. The current is printed signed, so zero shows
     as `+0.0 A`.
   - The wifi line adds the SSID, cut with `~` to stay within 60 columns.
   - The ssh line adds `disk N GB free`.
   - Extra amber lines when they apply: `hotspot wifi: <name>, N device(s)`, `hotspot usb: …`, `away on`,
     `rescue pending`, and `charge to full (override)` / `charge override ignored`.
   - Fields are separated by single spaces, not the drawing's column alignment.
2. **USB down** reads amber `no link`. The page gives the amber rule only for the glance.

## 3. Terminal, tmux and session (`vegas-term`, `vegas-session`, `tmux-vegas.conf`, `/etc/tmux.conf`)

1. **Session start.** Page (Terminal): foot runs `tmux new -A -s main`. Build: `vegas-session` (with flock) creates
   `main` with windows 0 home, 1 net, 2 sh and 3 logs if they are missing, then foot runs `tmux attach -t main`.
   2:sh is the current window at the first start. Same effect.
2. **2:sh on `exit`.** Not on the page. Window 2 is `while :; do bash -l; sleep 0.3; done`, so `exit` gives a fresh
   shell in the same place. Windows made with `+ new` close on exit as usual. A missing window 0-3 comes back the next
   time foot restarts.
3. **3:logs** is `journalctl -f -n 50`, restarted after 5 s if it exits. The page only says "a log tail".
4. **Mac attach.** Page (Terminal > Sharing, D6): `tmux new -A -s mac -t main -f ignore-size`. Build documents
   `ssh -t root@172.16.42.1 '/usr/lib/vegas/vegas-session; exec tmux new -A -s mac -t main -f ignore-size'`, so the
   group exists even before the phone's terminal has run.
5. **PageUp binding.** Page (Keys and gestures): Page up at a shell prompt opens tmux's scrollback. Build: a
   `bind -n PPage` that enters copy-mode only when the pane's command is `bash` or `sh`. Any other shell (for example
   zsh) gets a plain PageUp. Unverified on #5.
6. **tmux look.** Build: `status-interval 0`, colours from the page palette, `[main] `, `#I:#W` with `*` on the
   current window, right side `N attached`. `/etc/tmux.conf` now sources `/etc/vegas/tmux-vegas.conf`. Matches the
   drawing.
7. **foot options.** Builder additions: `-a vegas-term`, `dpi-aware=no`, `cursor.blink=no`,
   `touch.long-press-delay=400` (the page's 0.4 s hold). The font size comes from `/run/vegas-ui/fontsize`, accepting
   4-19.99 and otherwise 7.25.
8. **Restart backoff.** Not on the page. The loop sleeps 1 s between restarts, and 5 s after 5 fast exits in a row.
9. **UI program respawn.** Not on the page. vegas-home and vegas-net run in respawn loops. A crash within 5 s waits
   10 s. A missing program prints "<name> is not installed" every 60 s.

## 4. Home (`vegas-home`, `vegasui/home.py`, `tui.py`)

1. **Wi-Fi row detail.** Page drawing: `192.0.2.57  connected · -52 dBm`. Build: `<ssid> · -52 dBm  ›`. When down,
   it shows `not connected` (dim) with `tap: Network  ›`.
2. **"rescue pending" colour.** Designer point 9: Home shows "rescue pending" in amber. Build: the Root row's value
   (`main`) turns amber, but "rescue pending ·" is in the second line, which is always dim. So the words themselves
   are not amber.
3. **Hotspot not on Home.** Page (Status data > Hotspot): "Kind and count on home and glance". Build: Home shows no
   hotspot state at all. Why: draft 6 moved networks off Home ("Home keeps its Wi-Fi and USB rows"). The status table
   was not updated to match, and the builder followed draft 6.
4. **CPU cap colour.** Page (Status data > CPU cap): "Red while below 100 %". Build: on Home, `cap N %` sits in the
   dim second line. Only the SoC temperature value turns amber at 70 °C and red at 80 °C.
5. **Battery temperature colour.** Page (charging line table): "paused: warm" makes the temperature line amber too;
   amber at 40 °C, red at 42 °C. Build: on Home the battery temperature sits in the dim detail line with no colour
   rule. The glance and the report do colour it.
6. **Current sign.** Page: "+1.1 A on glance and home". Build: Home prints `+1.1 A`, but forces zero to `0.0 A`.
7. **Brightness bar.** Page drawing: 26 cells. Build: 26 cells filled by step index (13 steps:
   20/40/70/110/170/250/360/520/700/889/1200/1600/2047), not in proportion to the backlight level. The step table is
   a builder choice.
8. **WINDOWS row.** Page drawing: `1 net 2 sh 3 logs + new`. Build: always `1 net`, then up to three windows with
   index 2 or higher (labels cut to 9 characters), then `+ new`. Page (Network > Open it): "a tap on the Wi-Fi row,
   or on 1 net" opens Network. There is no separate `1 net` link besides this row.
9. **Text size.** Page: writes the file and closes foot. Build: the same, but it kills foot only if
   `/proc/<term.pid>/comm` is `foot`. Otherwise it says the size applies at the next terminal restart. The 51/68/72
   column counts are still arithmetic and unmeasured (designer point 2).
10. **Away PIN entry on Home.** Page (Away): the PIN is "set when Away is first switched on. Switching Away off asks
    for it." The pad is drawn in the glance window. Build: on Home, setting the PIN (typed twice) and the PIN to turn
    Away off are entered in a Textual text field limited to 6 digits, with the on-screen keyboard. The glance-window
    pad is used only when waking.
11. **Charge button.** Page: `Charge 80 %` / `Charge full`. Build: the same, plus `Charge ? (ignored)` when the guard
    rejected the override file. If `vegas-charge` is missing, Home writes the override itself.
12. **Programs.** Page: lists the graphical programs that are installed. Build: checks for `firefox-esr`,
    `netsurf-gtk3` and `zathura` only. Programs start through `swaymsg exec 'choom -n 0 -- <cmd>'`. If none is
    installed, it says "No graphical programs installed".
13. **Key highlight.** Page: the volume keys move a highlight and Power presses it. Build: the highlight clears on
    any touch, after 15 s without a key, or when the screen goes off (builder choice). It is published as
    `/run/vegas-ui/home` `highlight=0|1`.
14. **Landscape.** Page: Home switches to two columns when its terminal gets wide. Build: two columns when the
    terminal is wider than 100 columns (builder threshold). Status rows go on the left, buttons on the right.
15. **Rotation buttons.** Page: three buttons. Build: the same, acting on button release. After `vegas-rotate`
    succeeds, Home also writes the rotation files and runs `pkill -x lisgd` itself. That repeats what `vegas-rotate`
    now does.
16. **Polling.** Not on the page. Home refreshes every 10 s even with the screen off: about 3 to 4 forks
    (systemctl, iw, tmux), plus swaymsg if the rotation file is missing.

## 5. Network screen (`vegas-net`, `vegasui/net.py`, `wpa.py`)

1. **Scan age.** Page drawing: `scanned 0:12 ago`. Build: `scanned N min ago`, `scanned just now`, `scanning` or
   `not scanned`. Why: no seconds anywhere (page rule).
2. **Top block when Wi-Fi is down.** Page: "Not connected" in amber. Build: the same, plus a dim second line with
   wpa_supplicant's state, and a separate `Wi-Fi is off / wpa_supplicant is not answering`.
3. **Security labels.** Page: ● WPA2 / WPA3, ○ open. Build: any PSK flag is labelled WPA2, so WPA1 and mixed
   WPA2/WPA3 show as WPA2. SAE only is WPA3. EAP is `802.1X` and WEP is `WEP`; both say "not supported yet" when
   tapped. A network with both EAP and PSK is labelled 802.1X even though PSK would work. OWE shows as open and would
   fail to join.
4. **Signal bars.** Builder thresholds: 4 bars at -55 dBm or better, 3 at -67, 2 at -75, otherwise 1.
5. **List rows.** Page: three text rows each, six shown, `▼ N more`. Build: the same, plus `▲ fewer` when expanded.
   Each row holds two lines of content in a 3-row box.
6. **Mobile data tap.** Page (Network): "Reads 'no modem' and does nothing." Build: a tap opens a notice "Reboot to
   Android for calls and mobile data". That is the hint from the page's Cellular table. Nothing queries ModemManager
   (page Status data: "ModemManager on the system bus, if there is one"). Why: spec 0.1, the modem is never touched.
7. **Over-SSH join guard.** Page (Joining a network > Over SSH): "Join, go back if it fails: no address within 60 s,
   and it returns to the old network." Build: the button text is right. On failure, though, it removes the new entry
   and runs `enable_network all`. It does not explicitly select the old network. If vegas-net is killed in the middle
   of a join, the networks that `select_network` disabled stay disabled in memory until a reboot.
8. **WPA3 join.** Page: `sae_pwe=2` is needed; the passphrase is stored as typed. Build: sets `sae_pwe 2`, key_mgmt
   SAE, `sae_password` and `ieee80211w 2`. The dialog says "WPA3: may not work yet on this phone". Untried (Q27).
   Secrets go to wpa_cli as argv, so they are briefly visible in /proc.
9. **Hotspot switch.** Page (Hotspot, D15): one switch; turning it on asks which kind; USB asks once more. Build: the
   same chooser and USB confirmation. Changes:
   - Both kinds can be on at once (v28). The button reads `Hotspot on · wifi + usb`.
   - The page while sharing has a "Turn off" button per active kind, plus "Also a Wi-Fi hotspot" / "Also share over
     USB" and Close.
   - The Wi-Fi hotspot starts with `vegas-hotspot on 60`.
10. **Hotspot auto-off.** Page (Hotspot > Turns itself off): after 10 minutes with no device, when the feeding network
    goes away, below 25 % battery with no charger, and at 75 °C SoC. Build: none of these. Only the tool's 60-minute
    timer applies. Why: spec correction 7 makes the tool's limit the v1 rule; the rest is a follow-up in
    `vegas-hotspot`.
11. **New hotspot passphrase.** Page (Hotspot > Name, passphrase): "New passphrase makes another" (on the hotspot
    page). Build:
    - It is an entry under More, greyed out while the Wi-Fi hotspot is on.
    - vegas-net writes `/etc/vegas/hotspot.conf` itself (`SSID=` / `PSK=`, 16 characters from vegas-hotspot's set).
      This is a small second implementation, which designer point 6 says to avoid. It depends on vegas-hotspot's
      file format.
    - The new passphrase stays on the message line until the next message.
12. **QR code.** Page: 33 columns × 17 rows, about 36 × 43 mm. Build: `qrencode -t UTF8 -m 1`. The 1-module margin
    makes it a little smaller than the page's size; the exact size depends on the code's version. A camera scan off
    the panel is untested.
13. **Hotspot page text.** Page: shows kind, name, device count, the feeding network, battery and SoC temperature.
    Build: all of these, plus the passphrase as plain text and the line "turns itself off after 60 min".
14. **Sign-in check.** Page: two buttons, Open in w3m (new tmux window) and Open in Firefox (workspace 2). Build:
    - The check is a fixed URL, `http://connectivitycheck.gstatic.com/generate_204` (builder choice).
    - Each button appears only if its browser is installed. `firefox-esr` is not in build.sh PKGS, so a freshly built
      image shows only w3m.
    - The URL is checked: http/https only, with unsafe characters percent-encoded. w3m opens as
      `tmux new-window -t main -n signin -- w3m <url>`; Firefox through `swaymsg exec` with a quoted URL (the
      designer's SECURITY item, fixed).
    - After joining an open network, the check runs by itself.
15. **More.** Page: saved networks, a hidden network, country, time zone, VPN. Build:
    - Saved networks and Hidden network work.
    - Country, Time zone, VPN and "Borrow a device address" are greyed out as "· later".
    - "New hotspot passphrase" is added here.
16. **Polling.** Not on the page. Every 10 s even with the screen off: wpa_cli ×2, `vegas-hotspot status` and
    `vegas-usbshare status`.

## 6. Power menu (`vegas-menu`, bemenu)

1. **Title.** Page drawing: `Power · volume keys move, Power selects`. Build: `Vol keys move · Power picks`. Why: bemenu
   indents rows by the prompt's width, and the long prompt pushed every row off the 360-wide screen. The build also
   passes `-s` and shrinks the filter cursor (`--cw 1 --ch 1`).
2. **Power-off confirm line.** Page / designer point: with a charger present, the confirm list adds the line "On the
   cable it will charge to full". Build: the confirm list is `Power off now`, `Cancel`, and with the charger in a
   third row `Cable in: charges to full`. Picking that row counts as Cancel. Why: bemenu has one prompt line, so the
   warning has to be a row. The text was shortened to fit 27 characters at 15 pt.
3. **Confirm row name.** Page: "Opens a two-row confirm list" (names not given). Build: only the row `Power off now`
   powers off. A bare `Power off` from `--do` does nothing.
4. **Row height and font.** Page: 150 px rows upright and 108 px in landscape. Build: `-H 50` / `-H 36` at scale 3,
   font `JetBrains Mono 15` (builder choice). Unmeasured.
5. **Menu size.** Page: "The menu covers the lower half". Build: 8 rows plus a prompt line at 150 px is about 1350 px,
   about 57 % of the screen (unmeasured).
6. **Touch with Away locked.** Page: "It works the same by touch and by keys." Build: with Away on and the PIN not
   entered, touch stays muted in the short menu (keys only). Why: taps above the menu would reach the terminal.
7. **Idle.** Not on the page. The menu is cancelled after 60 s idle (180 s with Away on) and the screen goes off.
8. **Rotate row.** Page: switches between upright and the last landscape direction. Build: the same. It reads
   `/run/vegas-ui/rotation` and `rotation-last` (default 90), and falls back to read-only `swaymsg -t get_outputs`.
   vegas-keys waits up to 3 s for the finger to lift before rotating. Whether bemenu selects on touch-down or
   touch-up is unverified.
9. **Reboot to Android.** Build: sync, then `systemctl reboot`. vegas-keys syncs with a 2 s cap. Same as the page.
10. **"Reboot to Debian"** is absent, as the page says (Q10).

## 7. Glance screen and PIN pad (`vegas-glance`, `vegasui/pad.py`, `vegasui/pin.py`)

1. **Separate readers.** Page (Status data): one script, vegas-status, reads the values, and Home reads the same
   sources. Build: vegas-glance has its own copy of the readers, so values can disagree:
   - SoC temperature comes from `thermal_zone0`. The strip, Home and the report use the `soc_max` zone, falling back
     to zone0.
   - The IP address comes from forking `ip -4 -br addr`.
   - The SSH count comes from `ss`.
   - The charging word follows the same rule list, but in a second copy.
   Why: spec 0.2 "corrected" the zone to thermal_zone0, while the status builder kept soc_max, the zone vegas-thermal
   reads. The two were never reconciled.
2. **Current sign.** Page: "+1.1 A on glance and home". Build: the glance prints the current unsigned with `%.1f A`.
   A discharge shows as `-0.3 A`, and charging shows `0.4 A` with no `+`.
3. **Last line.** Page: "Which root is booted, and uptime. 'away' in amber while the Away switch is on." Build: with
   Away on, the root name is replaced by amber `away` (`away   up 3d`) rather than added next to it.
4. **Extra lines.** Build: an amber `rescue pending` line while `/rescue` exists. The hotspot line reads
   `hotspot wifi  N` or `hotspot usb`. The page wants "its kind and how many devices use it", and USB has no count.
5. **Top padding.** Build: one blank row (about 119 px) above the clock, to clear the camera band. Not checked
   against the real hole.
6. **Wake lighting.** Page (Glance > How): "The key daemon shows the window first and raises the backlight after, so
   no shell content is ever lit." Build: vegas-keys waits up to 1.5 s for the window to map. If it has not mapped and
   Away is off, the backlight comes on anyway, so shell content can show. With Away on, the screen stays dark until
   the window maps. Why: builder choice, so a hung or slow glance does not make the phone look dead.
7. **Redraw loop.** Page rule: paint only what changes. Build: the screen is only rewritten on change, but the
   process wakes every 0.5 s (every 0.15 s on the PIN pad) to check. It runs only while the glance is up (at most
   10 s, or 30 s on the pad).
8. **PIN pad drawing.** Page: keys 6 cells wide and 2 tall (324 × 238 px); `AWAY 78% holding`; `PIN ● ● ○ ○ ○ ○`.
   Build:
   - Upright: the same sizes. The labels sit on the top row of each 2-row key, not centred (cosmetic).
   - Landscape: keys are 1 row tall in the right half.
   - The AWAY line drops the charging word when it does not fit in 20 columns.
   - A message line (`wrong PIN`, `wait Ns`) is added.
9. **PIN lockout.** Page (Away > Wrong PIN): after five wrong tries, a wait that doubles each time, starting at 30 s.
   Build: the same, capped at 1 hour (builder choice). The counter is kept in `/var/lib/vegas/away-fails`, so it
   survives a reboot. The PIN is stored as pbkdf2-sha256 with 100k iterations in `/etc/vegas/away-pin`.
10. **Pad hit test in landscape.** Page: no detail. Build: the mapping for rotations 90 and 270 is unverified, and so
    is the raw touch range (Q20).

## 8. Key daemon (`vegas-keys`, `vegas-keys.service`, `vegas-keys-backoff`)

1. **Touch mute method.** Designer point 4: EVIOCGRAB inside vegas-keys, "NOT the swaymsg stopgap". Build: EVIOCGRAB
   first. Only if the grab fails does it fall back to `swaymsg input type:touch events disabled`, with a marker file,
   undone at the next unmute or when the daemon stops.
2. **Finger lift before muting.** Page (Screen states > What "off" means): waits for the finger to lift. Build: waits
   at most 3 s, then grabs anyway.
3. **Restart while dark.** Not on the page; the spec says the daemon starts in `on`. Build: if the daemon restarts
   while `/run/vegas-ui/state` says off, glance or pin, or while Away is on, it comes back dark and muted.
4. **Stop.** Not on the page. On SIGTERM it undoes a swaymsg fallback mute and, unless Away is on, relights a dark
   screen. Without that, after `systemctl stop vegas-keys` the screen would stay at backlight 0 with nothing to wake
   it.
5. **Dim level.** Page (Screen states): "Dimmed: backlight 10 %". Build: `min(level, 205)`, where 205 is 10 % of the
   2047 maximum, not 10 % of the current level. Below 205, dimming changes nothing.
6. **Brightness steps.** Page: steps, one repaint per tap. Build: a fixed table of 13 levels (builder choice). The
   default 889 is one of them.
7. **Volume autorepeat.** Not on the page. A held volume key repeats PageUp/PageDown, but only in the `on` state with
   the terminal or a graphical program in front.
8. **`away changed` while lit.** Not on the page. If Away is switched on from Home while the screen is on, dim or in
   the menu, the holder counts as unlocked and keeps the full menu. Away locks at the next screen-off.
9. **Menu from a dark screen.** Page table: Screen off + Power hold opens the Power menu. Build: the screen lights
   and touch is unmuted, unless Away is locked.
10. **Unit ordering.** Not on the page. `Before=vegas-sway.service`, so sway now waits for vegas-keys, which starts
    after basic.target (a little later than today). Other additions: a condition on python3-evdev being installed,
    `ExecStartPre=modprobe uinput`, and a restart backoff script (0, 1, 3, 7, 15, 31, then 60 s for repeated
    start-up failures; it resets after a run of 30 s or more).
11. **Device rescan.** Not on the page. Every 1 s for the first 2 minutes (the touch module is loaded by vegas-sway's
    ExecStartPre), then every 5 s while a device is missing.
12. **Sway socket discovery.** Page (How the parts reach each other): "sway writes its socket names to a file when it
    starts. vegas-keys reads that file." Build: no such file. vegas-keys globs `/run/sway/sway-ipc.*.sock`.
13. **Users.** Page (two-user plan): vegas-keys starts UI programs as the user `phone`. Build: everything runs as root,
    the page's own current default (Q8). The sudo rule and the `phone` user do not exist.
14. **Double-tap wake** (Q14; build step 5): not built.
15. **Panel off** (Q3, D4 "later"): not built. Screen off is backlight 0 only, as the page says for now.

## 9. Keyboard (`vegas-kbd`, `linux/ui-src/wvkbd/`)

1. **v2 is opt-in.** Page (Keyboard, Q11): v1 is stock, v2 is our build (approved; build step 5; Travel says v2 should
   come before the travel steps). Build: wvkbd-vegas is built and, if its .deb is present, installed by build.sh and
   deb-update. It runs only when `/etc/vegas/kbd-v2` exists. The stock wvkbd-mobintl stays the default. After 3 fast
   v2 failures it falls back to stock.
2. **v1 in landscape.** Page (Rotation > Keyboard): stock wvkbd 0.15 switches to its landscape layer by itself, at
   40 % of the height (432 px). Build: in the VM, 0.15 kept its `-H` height on rotation, so `vegas-kbd` starts it with
   `-H 150` (450 px) when the rotation file says 90 or 270. `vegas-rotate` kills wvkbd-mobintl so the loop restarts
   it.
3. **v1 start state.** Not on the page. A restarted keyboard starts hidden (`--hidden`) if `/run/vegas-ui/kbd` says
   hidden.
4. **v2 row heights.** Page (Version 2): top row 94 px; letter keys 102 × 124 px on a 108 px pitch; 764 px in all.
   Build: wvkbd makes every row of a layer the same height, so at `-H 255` (765 px) all six rows are 127 px.
5. **v2 Symbols top row.** Page text: "Top row Esc, Tab, Ctrl, Alt, four arrows, Hide … The same on every layer."
   Page drawing (symbol layer): Esc Tab Ctrl Alt Home PgDn PgUp End Hide, with the arrows on the row with F1-12, Ins,
   Del and ⌫. Build: follows the drawing. Letters and Fn keep the arrows in the top row. This is an open point for
   the designer.
6. **v2 label sizes.** Page: two sizes, smaller for word keys (no numbers). Build: Sans 13 for letters and Sans 8 for
   word keys (builder choice), checked with VM fonts only.
7. **v2 colours.** Build: letter keys `#2B3746`, word keys `#1C2530`, text `#E8EDF3`, pressed or latched keys amber
   with `#1C1400` ink, background `#0B0F14`. The spec's text colour is `#D5DBE3`.
8. **v2 landscape.** Page: "Our build gets a landscape layer of its own." Build: a 5-row layer at `-L 150` (450 px)
   with digits, letters, Esc, Tab, Ctrl, Alt, arrows, Hide, Sym and F1-12.
9. **Hide key.** Page: "Hide sends an unused key that sway binds to the hide signal." Build: Hide sends KEY_F20
   (keycode 198). Its keysym is XF86AudioMicMute, so the sway config binds `XF86AudioMicMute`, and also with Ctrl,
   Mod1 and Shift for when a modifier is latched. The spec's `bindsym F20` would never match.
10. **Modifier fix.** Not on the page. `code-mod-release.patch` makes wvkbd release a forced Shift (Symbols keys like
    `!`) with the key. Upstream left it down.
11. **Locking Ctrl.** Page: "a small patch of ours" if Ctrl should stay down across keys. Build: not done. Ctrl is
    one-shot only.
12. **Bottom corners.** Page (Terminal > Bottom): 48 px kept clear for the rounded corners. Build: both keyboards are
    anchored at the very bottom edge with no margin. Whether the corners clip Sym/Enter is unchecked.

## 10. Gestures (`vegas-gestures`, lisgd)

1. **Edge band.** Page: edges drawn 96 px; stock lisgd is 50 px, so "a rebuild, or stock lisgd started with a scaled
   screen size". Build: stock lisgd with `-w 563 -h 1244`, so 50 units ≈ 96 px. Travel `-t 65` ≈ 125 px (builder
   choice). It assumes libinput scales the touch range linearly.
2. **Orientation.** Page: the rotate command restarts lisgd. Build: vegas-rotate runs `pkill -x lisgd` while the
   vegas-gestures loop runs, and the loop restarts it with `-o 1` for 90 and `-o 3` for 270. These values are
   unverified and can be overridden with environment variables.
3. **Bottom swipe over a shown keyboard.** Page: "a bottom swipe over the keyboard also presses a key" and suggests
   two ways out. Build: neither is built. The swipe only shows the keyboard, and with the keyboard up it can type a
   bottom-row key.
4. **Holding touch during an edge swipe** (page's "later" option): not built.

## 11. Rotation (`vegas-rotate`, Home, menu)

1. **Gaps.** Page: 96 px beside the hole, 48 px on the other side, 30 px at the bottom. Build: 32 / 16 / 10 logical
   px, which matches.
2. **Recording and restarts.** Page (designer point 8): call vegas-rotate, restart lisgd, and start bemenu with smaller
   rows in landscape. Build: vegas-rotate now writes `/run/vegas-ui/rotation` and `rotation-last` and restarts lisgd.
   It also restarts the stock keyboard, which is not on the page. vegas-menu picks 108 px rows from the rotation file.
3. **`subpixel none`** is now on the DSI-1 output line (page: "The config sets subpixel none"). It takes effect at the
   next boot.
4. **Landscape for Home and Network:** two columns above 100 columns. The glance uses two columns from 40 columns.

## 12. Away (`vegas-away`, `vegas-away.service`)

1. **SSH rule.** Page (Away > SSH): SSH answers on the USB link and inside a VPN only, via the older iptables. Build:
   an own chain `VEGAS-AWAY` with RETURN for `lo`, `usb0` and `wg+`, then DROP tcp/22, for IPv4 and IPv6. IPv6 is
   skipped silently if `ip6tables-legacy` or its table is missing, but `status` still says closed. "Inside a VPN"
   means only WireGuard interfaces named `wg*`.
2. **Turning Away off from a shell.** Page: "Switching Away off asks for it [the PIN]." Build: Home asks for the PIN.
   `vegas-away off` in a root shell does not, because a root shell is already trusted.
3. **Turning Away on.** `vegas-away on` refuses until a PIN is set, and refuses (Away stays off) if the iptables rules
   did not apply.
4. **Boot unit.** Not on the page. A oneshot with DefaultDependencies=no, before network-pre, ssh and ssh.socket. It
   fails visibly if Away is on but the rules could not be applied.
5. **Strip and glance.** Matches the page: AWAY badge in the strip, "away" on the glance, Away timers of 2 and 3
   minutes, PIN pad after the glance.

## 13. Charge to full (`vegas-charge`)

1. **Apply time.** Page: the guard follows "within a minute". Build: `vegas-charge full|band` writes or removes
   `/run/vegas-chargeguard/override` and starts the guard's oneshot at once.
2. **Status words.** Build: `vegas-charge status` gives `full`, `band`, `full (pending)` or `ignored`.

## 14. Image, packages and deployment (`build.sh`, `linux_b.sh`)

1. **PKGS added:** python3-textual, python3-evdev, bemenu, libbemenu-wayland, lisgd, qrencode, curl, w3m.
2. **Not added**, though the page counts on them: firefox-esr (Q37, "wanted by you"; it is on #5 by hand), netsurf,
   zathura, and the travel set (mosh, pass, WireGuard tools, nnn, tldr, PDF to text, terminal picture tools, a notice
   program). A rebuilt image therefore has no Firefox, no sign-in "Open in Firefox" and an empty Programs list.
3. **Firefox drawing at two thirds.** Page (Programs for a trip): Firefox must be set to draw smaller or its right
   edge is cut off. Build: no Firefox preference or profile ships in the overlay.
4. **Units enabled:** vegas-keys and vegas-away, in build.sh and in deb-update.
5. **deb-update** (`scripts/linux_b.sh`) now apt-installs missing PKGS on the live phone (offline is a warning) and
   dpkg-installs the local wvkbd-vegas .deb. Not on the page.
6. **__pycache__** is stripped from the image and from the deb-update tarball.
7. **Stale comment.** The sway config's comment "top 84 camera band (the bar)" is out of date; the bar is 36 logical =
   108 px, as the page says.

## 15. Small rule-level differences

1. **Strip clock.** The strip wakes on the minute plus 50 ms.
2. **Restart pacing.** The kbd, gestures and term loops restart clients after 1 s, or 5 s after repeated fast
   failures. Nothing reloads or stops sway. D10 checked by the reviewers: no swaymsg exit/reload, no stop of
   vegas-sway or seatd, no signal to sway.
3. **Touch muted on a dark screen.** Kept as long as the grab or the fallback works. There is a safety unmute if the
   fallback is still in force while lit.
4. **Strip and Home can disagree on the CPU cap's colour.** The strip shows the cap in red, while Home keeps it dim
   (see 4.4).

---------------------------------------------------------------------------------------------------------------------

## 16. Drawn or described on the page but not built in v1

- **Strip:** sideways swipe along the strip to switch workspaces (v28 change 5).
- **Hotspot:** auto-off after 10 min with no device, when the feeding network goes away, below 25 % battery without a
  charger, and at a SoC temperature of 75 °C. Only the 60-minute timer exists.
- **Hotspot:** "New passphrase" on the hotspot page itself. It is under More instead, and written by vegas-net, not
  by the tool.
- **Network > More:** Country, Time zone picker (with the strip clock following), VPN, and "Borrow another device's
  address". All are greyed out "later".
- **Mobile data / cellular:** strip signal and operator, APN, data used, mobile data as a hotspot source. Only the
  "no modem" row exists (D16, by design).
- **Glance:** double-tap wake (Q14).
- **Screen off:** turning the panel off through the compositor (Q3, after a soak).
- **Keyboard:** v2 as the default (built, opt-in only). Locking Ctrl patch. Shorter 94 px top row.
- **Gestures:** keeping edge swipes out of the terminal and keyboard (key daemon holding touch for the length of a
  swipe).
- **Two-user plan:** the `phone` user, the sudo rule, and the sway socket-name file (Q8 default is root, so expected).
- **Travel:**
  - The encrypted folder for secrets and its tool (D19, Q30).
  - The travel package set (step 1).
  - NetSurf and zathura (step 2).
  - Firefox in the image (step 3) and its two-thirds scaling setting.
  - pass and WireGuard set-up.
  - Timers and alarms (screen and notice, vibration motor).
  - Sound.
  - A softphone slot in Programs.
- **Automatic rotation** (Q24, default off; expected).
- **labwc stand-in configuration** (D2 names it; nothing is set up for it).
- **"Reboot to Debian"** (Q10, boot work; absent on purpose).
- **Rendering tests:** foot render-timer, tap-to-glyph delay, wake time, 30 Hz current. None is part of the build.

## 17. Built but not on the page

- **Strip and report:** the `usb` word, the charge-band top in the strip, and the report's extra lines.
- **Away:** the PIN lockout cap of 1 h; the Away boot unit's failure mode.
- **vegas-keys:** restart backoff, staying dark after a restart, relighting on SIGTERM, idle cancel of the menu,
  volume autorepeat paging.
- **Keyboard:** the wvkbd modifier-release patch; the v1 landscape height override and restart on rotation;
  `/etc/vegas/kbd-v2` opt-in; Hide bindings with modifiers.
- **deb-update:** apt install of the UI packages, and the wvkbd-vegas .deb install.
- **Home:** "Charge ? (ignored)", "needs vegas-keys" and "needs vegas-away" messages; Home writes the rotation files
  and kills lisgd after its own rotations.
- **Network:** `▲ fewer`; "Wi-Fi is off"; 802.1X/WEP "not supported"; the sign-in check runs after an open join.

## 18. Status after the designer's rulings of 23 Nov (build updated; details in [rulings-report.md](rulings-report.md))

- **Resolved:** 1.1 (no band top in normal running; amber 100 only during charge-to-full), 1.6 (kbd badge slate when
  shown, dim when hidden), 1.12 (swaystatus fallback reads the soc_max zone), 2.1/7.2 (current "+1.1 A", "-0.3 A",
  "0.0 A" everywhere), 4.1 (Wi-Fi row: address first), 4.2/4.4/4.5 (warnings coloured inside the dim line), 4.12
  (a running program is switched to), 4.15 (Home no longer writes the rotation files or kills lisgd), 4.16/5.16 (no
  refresh with the screen off), 5.3 (OWE labelled, not supported), 5.7 (join guard: old network back within 60 s),
  5.11 (`vegas-hotspot newpass`), 7.1 (the glance uses the shared readers), 7.3 ("main away" last line), 12.1 (Away
  closes SSH on IPv6 too, or refuses; a failed boot apply shows red "AWAY ssh open" / "SSH OPEN" everywhere).
- **Changed by ruling:** power-off confirm warning is the prompt line (6.x); the stock keyboard is no longer restarted
  on rotation unless /etc/vegas/kbd-landscape-restart exists (then -H 144); the keyboard is down while Home or
  Network is in front unless a text field has focus (9.x); the tmux bar counts clients.
- **New, not on the page:** the camera-hole ruler (`vegas-status --ruler on|off|status`); /run/vegas-ui/strip.pid
  (uictl wakes the strip so the kbd badge follows at once); /run/vegas-ui/away-ssh (closed|open).
