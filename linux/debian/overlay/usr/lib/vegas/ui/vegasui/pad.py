"""PIN pad geometry, shared by the glance renderer (draws it) and vegas-keys (hit-tests raw touches): spec 5.5, D17/Q29.

The pad lives in the glance foot window (fullscreen, pad=0x0, so cell (0,0) is the panel's top-left corner in the
current rotation). Everything here is in terminal cells; the glance renderer publishes the real cell size it got from
foot in /run/vegas-ui/glance-geom ("cols rows cell_w cell_h"), so vegas-keys never guesses the font metrics.

Upright (20 columns): keys 6 cells wide x 2 rows tall, columns 0-5, 7-12, 14-19, one gap row between key rows, the
last key row ending at row rows-2 (thumb reach). Landscape (40+ columns): keys 1 row tall on the right half.
Key indices in reading order: 0-8 = digits 1-9, 9 = backspace, 10 = digit 0, 11 = OK.
"""
import os


def P(path):   # $VEGAS_SYSROOT prefix for tests (kept local: this module must not depend on the rest of vegasui)
    return os.environ.get("VEGAS_SYSROOT", "") + path


LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "⌫", "0", "OK"]
NAMES = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "del", "0", "ok"]   # what vegas-keys feeds to its PIN logic
BACK, ZERO, OK = 9, 10, 11
KEY_W = 6
GEOM_FILE = "/run/vegas-ui/glance-geom"
DEFAULT_CELL = (54, 119)        # JetBrains Mono 22.5 pt at scale 3, planned (spec 5.4); real value from GEOM_FILE


def layout(cols: int, rows: int):
    """[(index, label, col, row, w, h)] for a grid of cols x rows cells."""
    if cols >= 40:                                  # landscape: right half, 1-row keys, 1-row gaps
        h, x0, top = 1, cols - (3 * KEY_W + 2), max(0, (rows - 7) // 2)
    else:                                           # upright
        h, x0, top = 2, max(0, (cols - (3 * KEY_W + 2)) // 2), max(5, rows - 12)
    keys = []
    for i, label in enumerate(LABELS):
        r, c = divmod(i, 3)
        keys.append((i, label, x0 + c * (KEY_W + 1), top + r * (h + 1), KEY_W, h))
    return keys


def key_at(col: int, row: int, cols: int, rows: int):
    """Key index under a cell, or None (gaps and the text above count as no key)."""
    for i, _label, x, y, w, h in layout(cols, rows):
        if x <= col < x + w and y <= row < y + h:
            return i
    return None


def hit(x, y, w, h):
    """vegas-keys' entry point: a touch at (x, y) px in the rotated panel of w x h px -> key name or None.
    Grid and cell size come from the running glance window (GEOM_FILE), so the hit test matches what was drawn;
    w x h only picks the fallback grid when the glance has not published one."""
    c, r, cw, ch = read_geom(fallback=(int(w // DEFAULT_CELL[0]), int(h // DEFAULT_CELL[1])))
    i = key_at(int(x // cw), int(y // ch), c, r)
    return None if i is None else NAMES[i]


def read_geom(fallback=(20, 20)):
    """(cols, rows, cell_w, cell_h) as published by the glance renderer, else fallback grid with the planned cell."""
    try:
        c, r, w, h = (int(v) for v in open(P(GEOM_FILE)).read().split()[:4])
        if c > 0 and r > 0 and w > 0 and h > 0:
            return c, r, w, h
    except (OSError, ValueError):
        pass
    return (*fallback, *DEFAULT_CELL)
