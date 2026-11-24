"""Vegas UI colours (spec 0.1, design page): colour carries state only.

amber = warning, red = a limit is active, green = ok, dim = secondary. Shared by every UI part; the Textual CSS of
Home/Network lives in tui.py.
"""
BG = "#0B0F14"
TEXT = "#D5DBE3"
STRIP = "#141B24"
ROW = "#17202A"
BUTTON = "#2B3746"
AMBER = "#F0B429"
RED = "#FF6B63"
GREEN = "#7BD389"
DIM = "#7F8B99"
INK = "#1C1400"      # dark ink on amber (highlight / latched)

# role -> colour, the role keys of vegasui.readers' *_role helpers and charge.word (None = the view's plain colour)
ROLE = {"ok": GREEN, "warn": AMBER, "limit": RED, "dim": DIM}
