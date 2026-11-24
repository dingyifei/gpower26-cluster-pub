# Designer corrections (2026-11-23, after page v27; page v28 pending with possible small text changes)

> Imported from the v1 build session's working notes. Paths starting `<scratch>/` are that session's working
> folder; its test suites are in `tests/ui-seed/` and move to `tests/ui/` with issue `ui-testing-01`. The design page
> ("Vegas Touch UI", drafts and versions v27 to v30) is the maintainer's private document and is not published; what
> it decided is restated here. The designer's later rulings are in `rulings-report.md` (23 Nov) and
> `rulings-24nov.md` (24 Nov, R1 to R7).

Safe to build as on the page: vegas-status (strip feed), vegas-term loop, vegas-keys, power menu on bemenu. vegas-home / vegas-net layouts: expect small text changes in v28.
1. Grid: 60 x 37 in tmux with keyboard up, cells 17 x 39 px. Buttons are 4 rows tall. Drawings are 7.5 pt full width; do not copy pixel numbers from them.
2. Text-size presets: 8.25 / 7.25 / 6.25 / 5.75 pt -> expected 51 / 60 / 68 / 72 columns (only 60 measured; report what foot reports).
3. Brightness: one writer. Home sends steps to vegas-keys over /run/vegas-ui/ctl; vegas-keys alone writes ktd3136-bl.
4. Screen off: backlight 0 + EVIOCGRAB on the touch device inside vegas-keys, taken after the finger lifts, held through glance. NOT the swaymsg stopgap.
5. tmux: one session, windows 0 home, 1 net, 2 sh, 3 logs, mouse on; the Mac attaches through its own session in a group (D6).
6. Hotspot switch calls vegas-hotspot and vegas-usbshare and shows their status fields; no second implementation in vegas-net.
7. Sign-in check: after it finds a portal page, two buttons: Open in w3m (new tmux window) and Open in Firefox (workspace 2).
8. Rotation: Home's three buttons and the power menu's Rotate row call vegas-rotate; also restart lisgd and start bemenu with smaller rows in landscape.
9. Rescue: menu item calls reboot-rescue; Home and the strip show "rescue pending" in amber while /rescue exists.
10. Status traps: named sysfs files only; primary_chg/type is stale after unplug; battery level reads -1 without the gauge daemon; never show loadavg.
11. Keyboard v1: stock wvkbd --fn "Sans 10"; shown/hidden by the strip's kbd button and the bottom-edge swipe.
12. Sway clients keep `choom -n 0`, including the vegas-term loop.
Power off confirm: when a charger is present add a second line "On the cable it will charge to full" (still a confirm).
Defaults confirmed: Q29 PIN pad read by vegas-keys; Q30 encrypted folder later; Q8 one user (root).
Report every deviation from the page; send grim screenshots of Home and Network on first draw.

# Page v28 ("draft 7") changes vs v27 (no interface moved)
1. Sizes on #5: Home/Network buttons 4 rows = 156 px; a Home row = 2 text lines = 78 px; a Network list row = 3 rows = 117 px; hotspot QR 33 x 17 cells (~36 x 43 mm).
2. Stock keyboard 750 px tall (-H 250), 31 % of the screen; terminal keeps 38 rows above it.
3. Power off confirm adds "On the cable it will charge to full" when a charger is present.
4. Hotspot switch row runs vegas-hotspot / vegas-usbshare and shows what they report (name + device count for Wi-Fi, link for USB); both kinds can be on at once. Status row sources: `vegas-hotspot status`, `vegas-usbshare status` (not a /run file).
5. Strip swipe: sideways swipe along the strip switches sway workspaces (ws 2 = graphical program, D18). Untried; if swaybar can't do it with workspace_buttons off, report it.
6. Nothing may depend on touch; touch is muted whenever the screen is dark (D4).
7. Rescue: boot counter is the way out when Debian fails after mounting; 2 s hold is last resort.
8. D7 approved: 60 columns, margins, 7.25 pt.
When a piece first runs on #5, tell the designer (moves to "runs today").
- SECURITY (must fix after build): vegasui/net.py interpolates the captive-portal URL into shell strings (tmux new-window "w3m '{url}'", swaymsg exec "firefox-esr '{url}'"). Validate http/https + shlex.quote; tmux: pass argv after --.
