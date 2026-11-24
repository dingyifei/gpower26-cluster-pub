/* SPDX-License-Identifier: GPL-3.0-or-later
 * Vegas keyboard v2 colours, fonts and layer order for wvkbd 0.21 (spec 6.2; derived from config.mobintl.h).
 * Colours from the design page: keys #2B3746 (letters) / #1C2530 (word keys) on the app background #0B0F14,
 * text #E8EDF3, pressed and latched keys amber #F0B429 with dark ink #1C1400. No transparency (page rule).
 * Fonts [BUILDER CHOICE, measure on #5 with grim]: letters Sans 13, word keys Sans 8 so "Enter", "Shift",
 * "F1-12" fit a 1-unit key at 360 logical px wide. Do not pass --fn: it overrides both schemes with one font.
 * Colour values are 0xAARRGGBB.
 */
#ifndef config_h_INCLUDED
#define config_h_INCLUDED

#define DEFAULT_ROUNDING 4

struct clr_scheme schemes[] = {
{ /* 0: letters, digits, symbols */
  .bg = {.color = 0xFF0B0F14},
  .fg = {.color = 0xFF2B3746},
  .high = {.color = 0xFFF0B429},
  .swipe = {.color = 0xFFF0B429},
  .text = {.color = 0xFFE8EDF3},
  .text_press = {.color = 0xFF1C1400},
  .text_swipe = {.color = 0xFF1C1400},
  .font = "Sans 13",
  .rounding = DEFAULT_ROUNDING,
},
{ /* 1: word keys (Esc, Tab, Ctrl, Alt, Shift, Sym, Enter, Hide, F-keys, arrows) */
  .bg = {.color = 0xFF0B0F14},
  .fg = {.color = 0xFF1C2530},
  .high = {.color = 0xFFF0B429},
  .swipe = {.color = 0xFFF0B429},
  .text = {.color = 0xFFE8EDF3},
  .text_press = {.color = 0xFF1C1400},
  .text_swipe = {.color = 0xFF1C1400},
  .font = "Sans 8",
  .rounding = DEFAULT_ROUNDING,
}
};

/* portrait: letters first (start-up layer); the Sym / abc / F1-12 keys jump between them */
static enum layout_id layers[] = {
  Letters,
  Symbols,
  Fn,
  NumLayouts // end marker, may not be omitted
};

/* landscape (output wider than tall, e.g. vegas-rotate 90/270) */
static enum layout_id landscape_layers[] = {
  Landscape,
  Symbols,
  Fn,
  NumLayouts
};

#endif // config_h_INCLUDED
