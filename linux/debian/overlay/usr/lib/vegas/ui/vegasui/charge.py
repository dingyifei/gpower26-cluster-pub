"""The charging word shared by the strip glyph, Home and the glance (UI spec 1.2; design page "The charging line").

word(bat, g) -> (word, role, glyph); bat = readers.battery(), g = readers.guard(). role is one of
"ok" (green), "warn" (amber), "limit" (red), "dim" - the same keys as theme.ROLE.
The reason is worked out from the guard's inputs, never from its 'state' line (that drops the reason once the battery
is back in band). Order matters: the first rule that matches wins.
"""

UP, HOLD, DOWN, UNKNOWN = "▲", "=", "▼", "?"


def word(bat, g):
    soc, t, online = bat.get("soc"), bat.get("temp"), bat.get("online")
    if soc is None:
        return "no gauge", "limit", UNKNOWN                    # 1: the guard stops charging without a gauge
    if g.get("control") == "none":
        return "no charge control", "limit", (UP if bat.get("status") == "Charging" else HOLD)   # 2
    want = g.get("want")
    if want is None:
        return "starting", "dim", (UP if bat.get("status") == "Charging" else HOLD)   # 3: guard runs 20 s after boot
    if online == 0:
        return "on battery", "warn", DOWN                      # 4
    if want == "off" and t is not None and t >= g["tresume"] and soc < g["stop"]:
        return "paused: warm", "warn", HOLD                    # 5
    if g.get("override") and soc >= 100:
        return "full", "ok", HOLD                              # 6
    if want == "on":
        return "charging", "ok", UP                            # 7
    return "holding", "ok", HOLD                               # 8
