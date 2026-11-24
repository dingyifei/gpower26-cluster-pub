# Designer rulings of 24 Nov 2026 (R1 to R7 and the follow-ups)

> Written by the phone-side build session from the designer's messages of that day, imported as written.
> The design page is the maintainer's private document and is not published. The commit ids (`7c96732`, `ee21c51`,
> `ae6f596`, `ce7929b`, `eb944b3`, `c4e123d`) and the branch name belong to the maintainer's private history; here
> all of them arrived in one commit, "Touch UI: rulings of 24 Nov ...". `#5` is the maintainer's dual-boot phone.
> The tests for these rulings are in `tests/ui-seed/` (`tests/test_rulings_24nov.py`, `status-tests/test_hole.py`,
> `keys-test/test.py`).

Source: the designer session's messages to the phone session on 24 Nov 2026, after the first captures from phone #5
(grim shots of Home and Network, the strip ruler reading, the vegas-keys journal). Each entry says what the ruling
asks and where it was built on branch linux-ui-v1. "VM" means verified in the OrbStack VM only; the glass check
follows the next boot of #5.

## From the first captures of Home and Network

**R1, one background colour.** The shell, Home, Network and the side margins showed three colours (foot's default
#242424, the pages' #0B0F14, a blue test colour #1D3B53). Rule: one colour. foot background 0b0f14 and foreground
d5dbe3 (vegas-term's foot command line); the sway output background #0b0f14. foot applies at its next restart, sway
at its next start; never a reload (D10). Built in 7c96732.

**R2, buttons at the bottom.** Spare rows go between the read-only block and the first button group, so what you
press sits at the bottom within reach of a thumb; the message line stays the last line. On Network the in-range list
takes that room and scrolls, so the buttons do not move when a scan fills the list. Landscape unchanged. Built in
7c96732 (`VegasApp.fit()` sizes one flex widget per page).

**R3, scan when Network comes to the front.** One scan when window 1 comes to the front and the last scan is older
than 2 minutes. Never in the background, never repeated on failure, and not automatically while the Wi-Fi hotspot is
on (a scan takes the one radio off its channel); Rescan still forces one. Built in 7c96732, review fixes in ce7929b
(no automatic scan while wpa_supplicant is silent; only a tapped Rescan reports a refusal).

**R4, buttons that show a state** (Away, Charge, Hotspot): name, then state. One line when it fits the button's
inside; otherwise the name on line 1 and the whole state on line 2 ("Charge" / "80 %"). A state is never split. An
explicit line break computed from the button's inside width, not Textual's wrap; recomputed on resize. Built in
7c96732 (`state_label()`, `StateButton`).

**R5, empty list text.** "No other networks in range" while connected, "No networks in range" otherwise. Built in
7c96732.

## From the ruler reading and the keys journal

**R6, the strip's camera-hole band.** The ruler put the hole within x 170 to 190 logical (510 to 570 px at scale 3),
centred on 180. Rule: nothing is drawn between x 166 and 194 logical (498 to 582 px) in any upright state,
including the most crowded states and the swaystatus fallback line. Landscape unaffected. Built in ee21c51, review
fixes in ae6f596, measured geometry in eb944b3.

**R7, Cancel in the power menu returns to where the menu was opened.** A menu opened from the glance or from the dark
goes back to the glance on Cancel or Esc, with touch still muted and a fresh 10 s glance timer; opened from "on"
(terminal, Home, a program; "dim" counts as on) it goes back to "on". The 60 s idle close still ends dark; Away
locked unchanged. A finger Cancel waits for the finger to lift, then mutes, then lights the glance. Left as built,
on the page as "for you to know": the menu itself takes touch when opened from the dark with Away off. Built in
ee21c51 and ae6f596.

## Follow-up rulings on the strip's drop order after R6

1. **The everyday upright strip reads in full:** "wifi 41° 78%▲ kbd". The right edge moves from x 340 to 342 logical
   (status_edge_padding 18, a layout value: back to 20 means editing the sway config and RPAD, no code change); the
   band stays 166 to 194. "kbd" → "k" stays in the order for crowded states only, and "wifi" outlives the full "kbd"
   there. Glass check after the next boot: does the slate kbd badge's top right corner clear the panel's rounded
   corner? If clipped, the edge goes back to 340. Built in eb944b3, with the glyph widths measured in the VM
   (one cell for the triangle glyphs, a sub-pixel trim on each right block's first character).
2. **"SSH OPEN" → "SSH" beside resc / RESC** is accepted: the red fill is the alarm; Home, the glance, the PIN pad and
   the report say "OPEN" in words. Away from the rescue word the badge keeps its long forms. (ae6f596)
3. **What the person switched on is never dropped upright** (AWAY or its red SSH badge, the rescue word, AP, the
   amber 100); plain words go first, so the SoC temperature drops before the AP badge, even while red (Home and the
   glance keep it). (ae6f596)

## Smaller answers in the same exchange

- Charge-to-full: the bare status word on Home's message line is said in words (c4e123d).
- The neighbours' network names never go on the page or in public text; captures of a filled Network list are
  shared only with the names painted over.
