"""PIN pad geometry, shared by the glance renderer (draws it) and vegas-keys (hit-tests raw touches): spec 5.5, D17/Q29.

The pad lives in the glance foot window (fullscreen, pad=0x0, so cell (0,0) is the panel's top-left corner in the
current rotation). Everything here is in terminal cells; the glance renderer publishes the real cell size it got from
foot in /run/vegas-ui/glance-geom ("cols rows cell_w cell_h"), so vegas-keys never guesses the font metrics.

Upright (20 columns): keys 6 cells wide x 2 rows tall, columns 0-5, 7-12, 14-19, one gap row between key rows, the
last key row ending at row rows-2 (thumb reach). Landscape (40+ columns): keys 1 row tall on the right half, text on
the left.
Key indices in reading order: 0-8 = digits 1-9, 9 = backspace, 10 = digit 0, 11 = OK.
R10 (25 Nov): when Home asks for the pad (Away off, setting the first PIN) it gets a fifth row: one quiet Cancel key
(index 12, name "cancel") as wide as the three key columns (20 cells), one gap row under the 0 row. The four digit
rows move up by one key row + gap to make room (upright: top = rows-15; landscape: (rows-9)//2; F8 replaces these
offsets, see below), so the Cancel row takes the old last row's place at the bottom. layout/key_at/hit take cancel=True for that pad only.
F8 (25 Nov, follow-on): the hint no longer has lines of its own (the glance puts it on the PIN line), so the text
block of Home's pad is 4 rows (blank, title, PIN, message) and one free row parts it from the keys. Under the Cancel
key at least one free row stays (clear of the rounded corners). Upright, #5's 20 x 20 grid: digit rows at 5, 8, 11,
14 (2 tall), Cancel at 17-18, row 19 free. Shorter grids (review fix): rows are given up in a fixed order (layout()),
first the free row above the keys, then Cancel's second row (designer: allowed), then gaps; the free row under Cancel
holds down to 14 rows upright and 6 landscape, and Cancel stays on the grid down to 9 upright, 5 landscape.
Landscape, #5's 44 x 9 grid: 4 key rows + Cancel + 4 gaps = 9 rows left nothing under Cancel, so with fewer than
10 rows one gap goes: the one above the bottom row (backspace 0 OK), where blue digit keys meet the darker quiet keys and
stay told apart. Rows: 1 2 3 at 0, 4 5 6 at 2, 7 8 9 at 4, backspace 0 OK at 5, gap 6, Cancel 7, row 8 free. The gap
above Cancel is the one kept: without it the quiet OK and backspace keys run into the quiet Cancel bar, one shape
(rendered 25 Nov). With 10+ rows every gap stays. [Landscape part replaced by G4, below; upright F8 stands.]
G4 (25 Nov, second follow-on; landscape only, upright unchanged): the right-half digit pad keeps every gap, exactly
the Away pad without Cancel (#5's 44 x 9: rows 1, 3, 5, 7). Cancel moves to the LEFT text column, under the text
block (blank, title, PIN, message = rows 0-3): as wide as the text (text_cols()), 2 rows tall, bottom-anchored with
one free row under it (#5: rows 6-7, row 8 free). Hit-testing walks layout(), so a key off the right half works.
Camera hole: upright it is at x 166-194 of 360 logical px on the top edge. vegas-keys maps a touch for transform 90
as (x, y) = (py, 1080 - px) and for 270 as (2388 - py, px) (vegas-rotate: "90 puts the camera cutout on the LEFT,
270 on the RIGHT"), so in landscape the hole sits at mid-height (166-194 of 360 px, the same span both ways as it is
centred) within 32 px (the cutout-side inset) of the left short edge (90) or the right one (270): hole_cells(). On
#5's 44 x 9 at 54 x 119 px that is row 4, columns 0-1 (90) or 42-43 (270). The landscape text column and Cancel
start at column hole_cols() (2 on #5) on every row, so they never touch the left hole at any grid size; they never
reach the right edge either (the pad is there). The digit pad itself is the unchanged Away pad: on 44 x 9 the hole
row 4 is its gap between 4 5 6 and 7 8 9 (270); other grids are not checked against the hole for the digit pad.
Short landscape grids: the digit pad gives up gaps under 7 rows (above backspace 0 OK, then 7 8 9, then 4 5 6), the
same for the Away pad, so no key falls off the grid (7+ rows unchanged). Cancel goes 1 row tall when the text block,
2 rows and the free row do not fit (< 7 rows), then the free row goes (< 6); below 5 rows Cancel climbs into the
text block and the glance drops the text on its row.
"""
import math
import os


def P(path):   # $VEGAS_SYSROOT prefix for tests (kept local: this module must not depend on the rest of vegasui)
    return os.environ.get("VEGAS_SYSROOT", "") + path


LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK"]
NAMES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "del", "0", "ok"]   # what vegas-keys feeds to its PIN logic
BACK, ZERO, OK, CANCEL = 9, 10, 11, 12
CANCEL_LABEL, CANCEL_NAME = "Cancel", "cancel"
KEY_W = 6
PAD_W = 3 * KEY_W + 2           # the three key columns with their gaps: the Cancel key's width (R10)
GEOM_FILE = "/run/vegas-ui/glance-geom"
DEFAULT_CELL = (54, 119)        # JetBrains Mono 22.5 pt at scale 3, planned (spec 5.4); real value from GEOM_FILE


TEXT_ROWS = 4                   # Home's pad text block (blank, title, PIN, message; F8)
# Camera hole on #5 (logical px, portrait 360 x 796): x 166-194 on the top edge, within the 32 px cutout-side inset
HOLE_SPAN = (166 / 360, 194 / 360)     # along the short edge
HOLE_DEPTH = 32 / 796                  # into the panel along the long edge


def hole_cols(cols: int) -> int:
    """Landscape: how many columns from a short edge the camera hole may reach (2 on #5's 44 columns)."""
    return max(1, math.ceil(cols * HOLE_DEPTH))


def hole_cells(cols: int, rows: int):
    """{(col, row)} the camera hole may cover. Landscape: both short edges at mid-height, as the rotation (90 left,
    270 right) is not known here; upright: the top edge's centre."""
    if cols >= 40:
        rr = range(int(rows * HOLE_SPAN[0]), math.ceil(rows * HOLE_SPAN[1]))
        m = hole_cols(cols)
        return {(c, r) for r in rr for c in (*range(m), *range(cols - m, cols))}
    cc = range(int(cols * HOLE_SPAN[0]), math.ceil(cols * HOLE_SPAN[1]))
    return {(c, r) for r in range(max(1, math.ceil(rows * HOLE_DEPTH))) for c in cc}


def text_cols(cols: int):
    """(first, last) column the pad's text may use. Upright 1..cols-2 (as before); landscape (G4) from hole_cols() to
    two columns short of the digit pad (one margin column, one gap column), so it never meets the camera hole."""
    if cols >= 40:
        return hole_cols(cols), cols - PAD_W - 3
    return 1, cols - 2


def names(cancel=False):
    """Key names in highlight order (vegas-keys' Vol keys walk this list); the Cancel key last (R10)."""
    return NAMES + [CANCEL_NAME] if cancel else list(NAMES)


def layout(cols: int, rows: int, cancel=False):
    """[(index, label, col, row, w, h)] for a grid of cols x rows cells; cancel=True adds the R10 Cancel row."""
    wide = cols >= 40
    h, x0 = (1, cols - PAD_W) if wide else (2, max(0, (cols - PAD_W) // 2))
    gaps = [1, 1, 1]                                # gap rows above 4 5 6, 7 8 9, backspace 0 OK
    ch = 0
    if not cancel or wide:                          # the Away pad, as before R10/F8; G4: landscape too
        if wide:                                    # G4: under 7 rows gaps go (above backspace 0 OK, 7 8 9, 4 5 6)
            for g in (2, 1, 0):                     # so no digit key falls off the grid (was: rows 6+ cut off)
                if 4 + sum(gaps) > rows:
                    gaps[g] = 0
        top = max(0, (rows - 4 - sum(gaps)) // 2) if wide else max(5, rows - 12)
    else:
        # F8: from the top (upright): 4 text rows + 1 free row, key rows, gap, Cancel, >= 1 free row (rounded corners).
        # (Landscape: G4, Cancel in the left column below; the digit rows are the Away pad's.)
        # Fix (review): on short grids rows are given up one at a time, in this order, so Cancel stays on the grid
        # with its free row under it for as long as possible: the free row above the keys, then Cancel's second row
        # (F8: allowed), then the gap above backspace 0 OK, the gap above 7 8 9, the gap above 4 5 6, the gap above
        # Cancel. Only then the free row under Cancel, and last the text rows themselves. All of it from 20 rows;
        # the free row under Cancel holds down to 14 rows.
        st = {"lead": 5, "ch": 2, "cgap": 1, "free": 1}
        def need():
            return st["lead"] + 4 * h + sum(gaps) + st["cgap"] + st["ch"] + st["free"]
        steps = [("lead", None), ("ch", None), (None, 2), (None, 1), (None, 0), ("cgap", None), ("free", None)]
        for k, g in steps:
            if need() <= rows:
                break
            if k:
                st[k] -= 1
            else:
                gaps[g] = 0
        while need() > rows and st["lead"] > 0:     # unplanned tiny grid: the keys climb over the text
            st["lead"] -= 1
        ch = st["ch"]
        below = 4 * h + sum(gaps) + st["cgap"] + ch + st["free"]
        top = max(st["lead"], rows - below)
        cgap = st["cgap"]
    keys = []
    y = top
    for i, label in enumerate(LABELS):
        r, c = divmod(i, 3)
        if c == 0 and r:
            y += h + gaps[r - 1]
        keys.append((i, label, x0 + c * (KEY_W + 1), y, KEY_W, h))
    if cancel and wide:                             # G4: Cancel in the left text column, under the text block
        lo, hi = text_cols(cols)
        ch, free = 2, 1
        if rows - free - ch < TEXT_ROWS:
            ch = 1
        if rows - free - ch < TEXT_ROWS:
            free = 0
        keys.append((CANCEL, CANCEL_LABEL, lo, max(0, rows - free - ch), hi - lo + 1, ch))
    elif cancel:
        keys.append((CANCEL, CANCEL_LABEL, x0, keys[ZERO][3] + h + cgap, PAD_W, ch))
    return keys


def key_at(col: int, row: int, cols: int, rows: int, cancel=False):
    """Key index under a cell, or None (gaps and the text above count as no key)."""
    for i, _label, x, y, w, h in layout(cols, rows, cancel):
        if x <= col < x + w and y <= row < y + h:
            return i
    return None


def hit(x, y, w, h, cancel=False):
    """vegas-keys' entry point: a touch at (x, y) px in the rotated panel of w x h px -> key name or None.
    Grid and cell size come from the running glance window (GEOM_FILE), so the hit test matches what was drawn;
    w x h only picks the fallback grid when the glance has not published one."""
    c, r, cw, ch = read_geom(fallback=(int(w // DEFAULT_CELL[0]), int(h // DEFAULT_CELL[1])))
    i = key_at(int(x // cw), int(y // ch), c, r, cancel)
    return None if i is None else names(cancel)[i]


def read_geom(fallback=(20, 20)):
    """(cols, rows, cell_w, cell_h) as published by the glance renderer, else fallback grid with the planned cell."""
    try:
        c, r, w, h = (int(v) for v in open(P(GEOM_FILE)).read().split()[:4])
        if c > 0 and r > 0 and w > 0 and h > 0:
            return c, r, w, h
    except (OSError, ValueError):
        pass
    return (*fallback, *DEFAULT_CELL)
