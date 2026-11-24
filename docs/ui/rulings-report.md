# Designer rulings of 23 Nov: build report (phone #5, Debian touch UI)

> Imported from the v1 build session's working notes. Paths starting `<scratch>/` are that session's working
> folder; its test suites are in `tests/ui-seed/`. The design page it refers to is the maintainer's private
> document and is not published. "Nothing has been committed" describes the day it was written.

Nothing has been committed and the phone was not touched. All testing ran on the Mac and in the OrbStack VM
`vegas-deb` (trixie arm64), with PYTHONDONTWRITEBYTECODE=1. No `__pycache__` was written into the overlay.
D10 still holds: no change runs `swaymsg exit` or `reload`, stops vegas-sway or seatd, or signals sway. The only new
signal goes to the strip feed's own pid, after a cmdline check. Touch handling and the touch mute are unchanged.
No passphrase appears in the repo, the logs or any output.

Paths below are relative to `linux/debian/overlay/` unless they are absolute.

## Per ruling

**2. Power-off warning.** Done in `usr/lib/vegas/vegas-menu`. With the cable in, the confirm list's prompt line reads
"Cable in: charges to full" in amber, and the rows are only "Power off now" and "Cancel". On battery the prompt is
"Power off the phone?". The main list keeps "Vol keys move · Power picks". The fallback third row is gone. Tests:
the session part's menu-test.sh with real bemenu (6 passed), and test-glue.sh, whose checks are now rewritten to
this ruling (they assert the prompt and two rows).

**3a. Band top only during charge-to-full.** Done in `usr/local/bin/vegas-status`. Normal running shows "78%▲" in
both orientations. During charge-to-full it shows "90%▲100" with an amber 100, which is never dropped.

**3b. kbd badge.** Shown: slate like MAIN. Hidden: plain dim " kbd " with the same width. An audit test checks that
every amber fill in every scenario is AWAY, AP, RESCUE or RESC. New in this round: the badge now follows a keyboard
change at once. The feed writes `/run/vegas-ui/strip.pid`, and `vegasui.uictl` sends that pid SIGUSR1 after every
change, only while its cmdline is `vegas-status --bar`. Before this, the badge lagged up to 10 s after the window
rule hid the keyboard. The old integ shot 02-home showed exactly that.

**3. Ruler.** `vegas-status --ruler on|off|status`. Cells are exactly 10 logical px (30 physical) and numbered
0 to 33 upright; every 5th number is amber. It switches with no sway reload, through a flag file and SIGUSR1 to a
feed that has a handler. It appears on #5 only after deployment and the next sway start, because the feed running
now is older code.

**5. Stock keyboard in landscape.** By default nothing kills the keyboard on rotation and there is no -H override.
With `/etc/vegas/kbd-landscape-restart` present, vegas-rotate restarts it and vegas-kbd uses -H 144 in landscape,
keeping the shown/hidden state. The files are `usr/lib/vegas/vegas-kbd` and `usr/local/sbin/vegas-rotate`.

- **VM finding, needs #5:** the VM's wvkbd 0.15 did not re-detect landscape after a live rotation of the headless
  output. It kept 250 px, which left the terminal at 132x3. With the switch on, the restart at -H 144 gave 132x12.
  The designer saw 13 rows on #5, so the default follows #5.
- **Check on #5:** on a shell window, run `vegas-rotate 90` and count the rows.
  - About 13 rows: nothing to do.
  - About 3 rows: `touch /etc/vegas/kbd-landscape-restart; pkill -x wvkbd-mobintl`.

integ-smoke now checks both paths.

**6. v2 keyboard is opt-in.** Unchanged (`/etc/vegas/kbd-v2`).

**7. Temperature step and /proc/net/tcp.** Unchanged. The strip moves the SoC temperature only by 2 °C or more (or
on a colour change). SSH sessions are counted from `/proc/net/tcp{,6}`.

**8. Keyboard down on Home and Network.**
- **The model:** `usr/lib/vegas/ui/vegasui/uictl.py` keeps these files: kbd (shown now), kbd-user (the person's
  choice), kbd-field-<app> (pid of a page with a text field open) and kbd-window. Home and Network raise the keyboard
  only from AskScreen (PIN, passphrase, hidden SSID) and drop it on close.
- **The hook:** `etc/vegas/tmux-vegas.conf` has a session-window-changed hook that runs `uictl kbd auto`. A shell
  window restores kbd-user.
- **Fixed in this round, strip tap:** the kbd tap went around the model. `toggle_keyboard()` in vegas-status
  signalled wvkbd and wrote kbd but never kbd-user, so a shell window restored a stale choice. It now calls
  `uictl.kbd(None, "toggle")`, which takes the lock and writes both files.
- **Fixed in this round, Mac session:** the hook is global, so the Mac's grouped session switching its own windows
  ran `auto` too. That could hide a keyboard the phone user had swiped up on Home. `auto` now acts only when main's
  window in front differs from kbd-window. The `window` and field verbs record kbd-window, so a window that closes
  still triggers the rule.
- **Layout:** Home fits 60x56 with no scrolling, and 132x23 in landscape (three columns). See the questions below.

**B1. Away and IPv6.**
- **The tool (`usr/local/sbin/vegas-away`):** Away closes SSH with the ip6tables-legacy rule. If that rule fails,
  it sets disable_ipv6 on every interface except lo, usb0 and wg*, plus "default", and adds a networkd drop-in for
  wlan0. If neither works, `on` refuses and Away stays off. `status` reads the state live. on, off, apply and
  status write `/run/vegas-ui/away-ssh` (closed or open).
- **Fixed in this round, the screens:** nothing read that file, so a failed boot `apply` still showed a plain amber
  AWAY while port 22 was open. `readers.away_ssh()` and `away_open()` now read it with no fork; a missing file
  counts as unknown and adds nothing. With Away on and the file saying open:
  - Strip: a red "AWAY ssh open" badge in landscape. Upright it is a red "SSH OPEN" (MAIN, and RESC next to it,
    drop first so the hole gap stays clear). A plain amber AWAY is never shown.
  - Glance: a red "SSH OPEN on Wi-Fi" line, and the PIN pad's AWAY turns red. B5's last line is unchanged.
  - Report: a red "away on: SSH OPEN on Wi-Fi ..." line.
  - Home: the Away button turns red (class `alarm`), and the SSH row's second line gets a red "OPEN on Wi-Fi".
  - Home shows the vegas-away line as returned: stdout's first line, or for a refusal stderr's last line. It is
    amber when the tool failed or the line contains "OPEN".

**B2. Join guard.**
- **The guard (`usr/lib/vegas/ui/vegasui/wpa.py`, `net.py`):** before select_network it writes a record and starts a
  transient systemd timer (`systemd-run --on-active`); a setsid sleeper is the fallback. On failure, vegas-net
  selects the old network explicitly. Every start of vegas-net runs heal() and enable_network all.
  `vegas-net --restore <token>` is the timer's entry point.
- **Fixed in this round, timing:** the guard fired at 60 s and then waited up to 20 s, so the old network could come
  back as late as 80 s. Now:
  - WAIT_SECS = 30: vegas-net's own wait.
  - GUARD_SECS = 38: the guard fires after vegas-net's own deadline.
  - BACK_SECS = 18: the wait for the old network.

  Worst case, the guard path has the old network back by about 38 + 2 + 18 = 58 s. The normal failure path has it
  back by about 48 s. A test checks GUARD + start + BACK ≤ 60 and WAIT < GUARD. The page text "within 60 s" is now
  true as written.

**B3. One reader and one format.** The glance, strip, report and Home all read through `vegasui.readers` (Home
through `uistatus`). The SoC zone is soc_max, with zone0 only as fallback. The current reads "+1.1 A", "-0.3 A",
"0.0 A" at zero, and "? A" when unknown. New in this round: an unknown temperature reads "? °C" in the report and on
Home, like "? A". The 20-column glance keeps a bare "?".

**B4. A warning is never dim.** On Home, `tui.StatusRow` takes (text, role) segments. "rescue pending" is amber;
"cap N %" below 100 is red; battery temperature is amber from 40 °C and red from 42 °C. "on battery" and
"charger ?" are amber as well; see the open items.

**B5. Glance last line with Away on.** It reads " main away    up 3d" with an amber "away"; on the rescue root it
reads "rescue away". With Away off it is "main root".

**B6. No polling in the dark.** In `VegasApp.tick`, while `/run/vegas-ui/state` is "off", the 10 s refresh does one
file read and no fork. An inotify watch on /run/vegas-ui refreshes the page once when the state changes. Without
inotify, a 2 s file read runs while dark.

**B7. New hotspot passphrase.** `vegas-hotspot newpass` is root-only and refuses while the hotspot is on. It keeps
the SSID, writes the file at mode 0600 and prints only "new passphrase set". vegas-net calls it from under More and
says "New passphrase set …", never the passphrase.

**B8. Home's rotation.** Home only runs `vegas-rotate <t>`; vegas-rotate writes the rotation files and restarts
lisgd. Fixed in this round: after a rotation made elsewhere (a key, the menu or a shell), the SCREEN row stayed on
"upright" until the 10 s refresh. vegas-rotate writes the file just after the transform, so the resize can arrive
first. Home now moves the row when the file is written (the same inotify watch: `tui.rotation_changed`), and also
re-reads it on resize and 1.5 s after. It is a file read, never a gather. integ-smoke's 08-home-landscape shot now
shows "keys up".

**B9. Programs.** `pgrep -x` first. If the program is running, Home runs `swaymsg workspace 2`; otherwise
`swaymsg exec`. The list marks running programs with " · running".

**B10. OWE.** `wpa.security()` labels [WPA2-OWE-…] and [RSN-OWE-…] as OWE, shown "not supported yet" like 802.1X.
The open half of an OWE transition pair ([OWE-TRANS]) stays open.

**B11. Home's Wi-Fi row.** The first line is the address in green. The second line is "<ssid> · -52 dBm ›". When
down it reads "not connected" and "tap: Network ›".

**Firefox.** firefox-esr is in PKGS in `linux/debian/build.sh`; deb-update in `scripts/linux_b.sh` installs missing
PKGS. `etc/firefox-esr/vegas.js` sets layout.css.devPixelsPerPx = 2.0. `MOZ_ENABLE_WAYLAND=1` is set in
`etc/systemd/system/vegas-sway.service`.

**tmux client count.** The bar's right side reads
`#{?session_grouped,#{session_group_attached},#{session_attached}} attached`. The shots show "1 attached".

## The designer's questions

**06-glance.png: why did the glance and Home disagree?** It was test data, not a second reader. integ-smoke started
vegas-keys with VEGAS_SYSROOT pointing to a small fake tree (78 %, charger in, main root). The glance inherited it.
Home read the VM's real sysfs: no gauge, no primary_chg, no root-role file.

Since B3 the glance has no readers of its own. To make the new shots agree, integ-smoke now builds one #5-like fake
tree and exports VEGAS_SYSROOT into sway's environment, so the strip, Home, the glance and vegas-keys read the same
values. In integ-shots-v2, Home, the glance and the strip show the same 78 % holding, 31 °C, SoC 41 °C,
192.0.2.57, 1 session and main root.

Only the Network page differs: it shows "Not connected". Per ruling 4 it asks the tools (wpa_cli), and the VM has
no Wi-Fi.

**Does Home fit 60x56?** Yes, with the keyboard down, no scrolling, about 46 rows used. A test checks
max_scroll_y == 0 and that every row and button is inside the screen. integ-smoke confirms the real foot grid is
60x56 with Home in front (see 02-home.png). Landscape is 132x23 with the keyboard down, in three columns, all
visible, with no scrolling (08-home-landscape.png).

## Cross-part requests: how each was resolved

- **Status part:** the strip's kbd tap goes through `uictl.kbd(None, "toggle")`. Done; a test checks that a tap
  writes kbd and kbd-user and sends the expected signal.
- **Status and home-net parts:** read away-ssh and show a red warning. Done on the strip, glance, PIN pad, report and
  Home (B1 above).
- **Home-net part:** show the vegas-away line as returned, amber when it contains OPEN. Done.
- **Home-net part:** StatusRow segments, the *_detail helpers and fmt_amps. These were already done by the home-net
  part, and the signatures are kept. The Home/Net suite was rerun: 67 passed.
- **vegas-hotspot newpass.** Already done by the session part, and vegas-net uses it.
- **"? °C" for an unknown temperature.** Done (`readers.fmt_deg`).
- **SCREEN row after `vegas-rotate`.** Done (B8 above).
- **Shared harnesses.**
  - test-glue.sh: the confirm checks now assert the prompt line and two rows.
  - integ-smoke.sh, rotation: it asserts no restart and no -H override by default, keeps a hidden keyboard across a
    rotation, and checks the switch (-H 144 with --hidden, upright -H 250, at least 10 rows with the keyboard up).
  - integ-smoke.sh, new checks: Home in front means the keyboard is down at 60x56, and strip.pid is written. It
    uses one shared fake tree and writes its shots to integ-shots-v2.
  - Backups of the old copies: <scratch>/integ-smoke.sh.pre-rulings2 and <scratch>/test-glue.sh.pre-rulings2.
- **deviations.md.** A new section 18 lists what the rulings resolved, changed and added.
- **Rejected: prefixing Programs' and the sign-in check's `swaymsg exec` with `env MOZ_ENABLE_WAYLAND=1`.** Trixie's
  firefox-esr (128 and later) already uses Wayland whenever WAYLAND_DISPLAY is set, which is true for every `swaymsg
  exec` child. The service variable is only belt and braces, so the prefix would add churn (and test churn) for no
  effect.

## Review findings

| # | Finding | Verdict | Fix |
|---|---|---|---|
| 1, 6 | The strip kbd tap bypasses uictl, so kbd-user goes stale | Confirmed | vegas-status `toggle_keyboard()` calls `uictl.kbd(None, "toggle")`; the old `pids()` helper was removed. Tests: status-tests KbdTap, and the feed test updated. |
| 6b | The global hook re-applies the rule on the Mac's own window switches | Confirmed | `auto` does nothing when main's window is unchanged (kbd-window). Tests: two new unittest cases in test_uictl_kbd, and a kbd-integ check with a real grouped session. |
| 2, 5 | Nothing reads away-ssh, so AWAY claims protection while SSH is open | Confirmed | See B1 above. Tests: 9 in status-tests test_rulings2 (strip, glance, PIN pad, report) and 3 in tests/test_rulings_home2. |
| 3, 7 | The old network comes back only at about 62-80 s | Confirmed | Timing changed to 30/38/18 s. Tests: a constants test and a test that back_to gives up after BACK_SECS polls. |
| 4 | The harnesses still expect -H 150 and the third menu row | Confirmed | Harnesses updated; see the cross-part requests above. |

Found while taking the new shots, and fixed:
- The kbd badge lagged up to 10 s after the window rule changed the keyboard. Fixed by strip.pid and SIGUSR1; a
  unittest (Linux /proc) checks it.
- The SCREEN row stayed stale after a rotation made elsewhere. Fixed by inotify on the rotation file; a pytest
  checks it.

## Files changed in this round

**Overlay:**
- `usr/lib/vegas/ui/vegasui/readers.py`: `away_ssh`, `away_open`, `fmt_deg` "? °C"
- `usr/lib/vegas/ui/vegasui/uistatus.py`: `away_open`
- `usr/local/bin/vegas-status`: the tap goes through uictl, the red Away badge with LSHRINK 4 and 5, the report
  line, strip.pid
- `usr/lib/vegas/vegas-glance`: the red line and the red AWAY on the PIN pad
- `usr/lib/vegas/ui/vegasui/home.py`: the alarm button, SSH row warning, vegas-away message, rotation follow
- `usr/lib/vegas/ui/vegasui/tui.py`: Button.alarm CSS, `rotation_changed` through inotify
- `usr/lib/vegas/ui/vegasui/wpa.py`: timing constants and docstring
- `usr/lib/vegas/ui/vegasui/uictl.py`: `auto` acts only on a change, the field verbs record the window,
  `poke_strip`

**Tests:**
- status-tests: test_rulings2.py (new, 11 tests), test_status.py (feed test updated), vm/mk.py (awayopen and
  busyopen scenarios)
- tests: test_rulings_home2.py (new, 7 tests), test_rulings_net.py (2 new, 2 updated), test_net.py (30 s)
- session-tests: test_uictl_kbd.py (3 new), kbd-integ.sh (2 new checks)
- integ-smoke.sh and test-glue.sh, as above

## Test results (final runs)

| Suite | Where | Result |
|---|---|---|
| status-tests (`test_rulings2 test_rulings test_status`) | Mac | 56 OK |
| status-tests (same) | VM | 56 OK |
| tests, Home/Net pytest (`-o asyncio_mode=auto`) | VM | 67 passed |
| session-tests/test_uictl_kbd | Mac | 17 OK (1 skipped: needs /proc) |
| session-tests/test_uictl_kbd | VM | 17 OK |
| keys-test/test.py | VM, sudo | FAILED: none |
| test-glue.sh | VM, sudo | 52 passed, 0 failed |
| glue-live/run.sh | VM, sudo | 23 passed, 0 failed |
| status-tests/vm/ruler-live.sh | VM | 8 passed |
| status-tests/vm/glance-glue.sh | VM | 9 passed |
| session-tests/kbd-integ.sh | VM | 29 passed |
| session-tests/away-test.sh | VM | 40 passed |
| session-tests/hotspot-newpass-test.sh | VM | 11 passed |
| session-tests/menu-test.sh | VM | 6 passed |
| strip-test/run.sh | VM | rendered; no pass/fail of its own |
| status-tests/vm/strip.sh normal hidden full busy busyopen awayopen ruler | VM | rendered |
| integ-smoke.sh (full sway session) | VM, sudo | 62 passed, 0 failed |

firefox-pref-test.sh was not re-run: the session part purged firefox-esr from the VM after its run. Firefox files
did not change in this round.

## Screenshots

All are in <scratch>/ui/integ-shots-v2/:
- **Home, keyboard down, upright 60x56:** 02-home.png. The kbd badge is dim.
- **Network:** 03-net.png
- **Glance:** 06-glance.png (the same values as Home)
- **Home, keyboard down, landscape 132x23:** 08-home-landscape.png. SCREEN shows "keys up".
- **Landscape shell:** 08c-landscape-shell-kbd.png shows the VM limit (3 rows); 08d-landscape-switch-kbd.png shows
  the switch on at -H 144 (12 rows).
- **Strip, normal, upright and rotated:** strip-normal-normal.png and strip-normal-90.png
- **Strip, busy + AP + Away, upright and rotated:** strip-busy-normal.png and strip-busy-90.png
- **Strip, Away with SSH open (B1):** strip-busyopen-normal.png, strip-busyopen-90.png, strip-awayopen-normal.png
  and strip-awayopen-90.png
- **Also there:** 01, 04, 05, 07, 08b and 09, plus text captures of Home and Network.

## Still open

1. **Ruling 5 on #5:** whether the stock keyboard changes height by itself after a live `vegas-rotate 90`. The VM's
   wvkbd did not. The switch file is the fix if #5 shows about 3 rows.
2. **The ruler and the strip.pid poke need the new feed,** which means deployment and the next sway start
   (reboot), because D10 allows no reload. Until then the kbd badge follows on the feed's 10 s read, and the ruler
   is ignored. The ruler's 5.5 pt labels are checked only in the VM render.
3. **B2 timing is not proven on #5.**
   - WAIT_SECS is now 30 s for association plus DHCP; a slow AP or DHCP server may fail a join that 50 s would have
     allowed.
   - The real wpa_supplicant go-back and the systemd-run guard have not been run on the phone.
   - The OWE flag strings from #5's wpa_cli are assumed, not seen.
4. **B1 staleness:** away-ssh changes only when vegas-away on, off, apply or status runs. If the firewall rules
   disappeared at runtime, the screens would keep "closed" until the next `vegas-away status`. A periodic check
   would cost a fork, so I left it out.
5. **B4 scope:** "on battery" and "charger ?" are amber on Home too, the same as the glance and report. That is one
   step beyond the three words the designer named; the designer should confirm.
6. **Network at 132x22 still scrolls** its network list. The fit ruling covered Home only.
7. **Strip upright with charge-to-full** drops "wifi" to fit the amber 100, and the 20 px hole gap needs the one look
   at the glass with the ruler.
8. **uictl `auto` edge case:** if the tmux server restarts and its first window matches a stale kbd-window, the rule
   applies only at the next window change. /run is cleared at boot, so this needs a server restart within a boot.
