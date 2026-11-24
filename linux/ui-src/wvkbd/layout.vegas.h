/* SPDX-License-Identifier: GPL-3.0-or-later
 * Vegas keyboard v2 layout for wvkbd 0.21 (design page "Vegas Touch UI", draft 6, Keyboard v2; spec 6.2).
 * Derived from wvkbd's layout.mobintl.h format (GPLv3, see COPYING in the wvkbd source). This file and
 * config.vegas.h are GPL, not covered by the repo's MIT licence; build.sh copies them into a wvkbd tree.
 *
 * Layers: Letters (portrait default), Symbols with navigation, Fn (F1-F12), Landscape (landscape default).
 * Widths are relative to a letter key (1.0). Every portrait row adds up to 10 units, landscape rows to 14.5.
 * wvkbd gives every row of a layer the same height (height / rows), so the page's shorter top row (94 vs 104 px)
 * is not reproduced: at -H 255 (765 px) each of the six rows is 127 px.
 * Modifiers (Shift, Ctrl, Alt) are one-shot in 0.21: tap -> highlighted, applies to the next key, then clears;
 * tap again to cancel. No caps lock, no long-press menus.
 * "Hide" sends KEY_F20 (XKB code 198, keysym XF86AudioMicMute in this keymap, so `bindsym F20` would NOT match);
 * sway binds the code: bindcode 198 exec "pkill -USR1 -x wvkbd-vegas && echo hidden > /run/vegas-ui/kbd"
 * (wvkbd has no hide key of its own).
 * Open point for the user: the page text says the top row is the same on every layer (with the arrows), its
 * drawing puts Home/PgDn/PgUp/End there on Symbols and moves the arrows a row down. This follows the drawing.
 */

/* default heights in logical px (overridden by -H / -L) */
#define KBD_PIXEL_HEIGHT 255           /* 765 px at scale 3, ~49.5 mm, 32 % of the panel */
#define KBD_PIXEL_LANDSCAPE_HEIGHT 150 /* 450 px of the 1080 px landscape height; 5 rows of 90 px */

/* spacing around each key (buffer px) */
#define KBD_KEY_BORDER 3

enum layout_id {
	Letters = 0,
	Symbols,
	Fn,
	Landscape,
	Index, /* required by keyboard.c (compose index); unreachable here: there are no Compose keys */
	NumLayouts,
};

static struct key keys_letters[], keys_symbols[], keys_fn[], keys_landscape[], keys_index[];

static struct layout layouts[NumLayouts] = {
  [Letters] = {keys_letters, "latin", "letters", true},
  [Symbols] = {keys_symbols, "latin", "symbols", false},
  [Fn] = {keys_fn, "latin", "fn", false},
  [Landscape] = {keys_landscape, "latin", "landscape", true},
  [Index] = {keys_index, "latin", "index", false},
};

/* scheme 0 = letters/symbols (larger font), scheme 1 = word keys (smaller font, darker key) */
#define W(label, width, code) {label, label, width, Code, code, .scheme = 1}
#define MOD(label, width, mod) {label, label, width, Mod, mod, .scheme = 1}
/* shifted symbol on its own key; reset_mod: always sent with Shift alone, even if Shift is latched */
#define SYM(label, code) {label, label, 1.0, Code, code, .code_mod = Shift, .reset_mod = true}
#define END {"", "", 0.0, EndRow}

/* portrait top row: same on Letters and Fn */
#define TOP_ROW_ARROWS                                                                                     \
  W("Esc", 1.0, KEY_ESC), W("Tab", 1.0, KEY_TAB), MOD("Ctrl", 1.0, Ctrl), MOD("Alt", 1.0, Alt),            \
  W("←", 1.0, KEY_LEFT), W("↓", 1.0, KEY_DOWN), W("↑", 1.0, KEY_UP), W("→", 1.0, KEY_RIGHT),               \
  W("Hide", 1.0, KEY_F20), END

static struct key keys_letters[] = {
  TOP_ROW_ARROWS,

  {"1", "!", 1.0, Code, KEY_1}, {"2", "@", 1.0, Code, KEY_2}, {"3", "#", 1.0, Code, KEY_3},
  {"4", "$", 1.0, Code, KEY_4}, {"5", "%", 1.0, Code, KEY_5}, {"6", "^", 1.0, Code, KEY_6},
  {"7", "&", 1.0, Code, KEY_7}, {"8", "*", 1.0, Code, KEY_8}, {"9", "(", 1.0, Code, KEY_9},
  {"0", ")", 1.0, Code, KEY_0}, END,

  {"q", "Q", 1.0, Code, KEY_Q}, {"w", "W", 1.0, Code, KEY_W}, {"e", "E", 1.0, Code, KEY_E},
  {"r", "R", 1.0, Code, KEY_R}, {"t", "T", 1.0, Code, KEY_T}, {"y", "Y", 1.0, Code, KEY_Y},
  {"u", "U", 1.0, Code, KEY_U}, {"i", "I", 1.0, Code, KEY_I}, {"o", "O", 1.0, Code, KEY_O},
  {"p", "P", 1.0, Code, KEY_P}, END,

  {"", "", 0.5, Pad},
  {"a", "A", 1.0, Code, KEY_A}, {"s", "S", 1.0, Code, KEY_S}, {"d", "D", 1.0, Code, KEY_D},
  {"f", "F", 1.0, Code, KEY_F}, {"g", "G", 1.0, Code, KEY_G}, {"h", "H", 1.0, Code, KEY_H},
  {"j", "J", 1.0, Code, KEY_J}, {"k", "K", 1.0, Code, KEY_K}, {"l", "L", 1.0, Code, KEY_L},
  {"", "", 0.5, Pad}, END,

  MOD("Shift", 1.5, Shift),
  {"z", "Z", 1.0, Code, KEY_Z}, {"x", "X", 1.0, Code, KEY_X}, {"c", "C", 1.0, Code, KEY_C},
  {"v", "V", 1.0, Code, KEY_V}, {"b", "B", 1.0, Code, KEY_B}, {"n", "N", 1.0, Code, KEY_N},
  {"m", "M", 1.0, Code, KEY_M},
  W("⌫", 1.5, KEY_BACKSPACE), END,

  {"Sym", "Sym", 1.5, Layout, 0, &layouts[Symbols], .scheme = 1},
  {"/", "?", 1.0, Code, KEY_SLASH}, {"-", "_", 1.0, Code, KEY_MINUS},
  {"", "", 4.0, Code, KEY_SPACE},
  {".", ">", 1.0, Code, KEY_DOT},
  W("Enter", 1.5, KEY_ENTER),

  {"", "", 0.0, Last},
};

static struct key keys_symbols[] = {
  W("Esc", 1.0, KEY_ESC), W("Tab", 1.0, KEY_TAB), MOD("Ctrl", 1.0, Ctrl), MOD("Alt", 1.0, Alt),
  W("Home", 1.0, KEY_HOME), W("PgDn", 1.0, KEY_PAGEDOWN), W("PgUp", 1.0, KEY_PAGEUP), W("End", 1.0, KEY_END),
  W("Hide", 1.0, KEY_F20), END,

  SYM("!", KEY_1), SYM("@", KEY_2), SYM("#", KEY_3), SYM("$", KEY_4), SYM("%", KEY_5),
  SYM("^", KEY_6), SYM("&", KEY_7), SYM("*", KEY_8), SYM("(", KEY_9), SYM(")", KEY_0), END,

  SYM("~", KEY_GRAVE), {"`", "`", 1.0, Code, KEY_GRAVE}, SYM("|", KEY_BACKSLASH),
  {"\\", "\\", 1.0, Code, KEY_BACKSLASH}, SYM("{", KEY_LEFTBRACE), SYM("}", KEY_RIGHTBRACE),
  {"[", "[", 1.0, Code, KEY_LEFTBRACE}, {"]", "]", 1.0, Code, KEY_RIGHTBRACE},
  SYM("<", KEY_COMMA), SYM(">", KEY_DOT), END,

  SYM("_", KEY_MINUS), SYM("+", KEY_EQUAL), {"=", "=", 1.0, Code, KEY_EQUAL}, SYM(":", KEY_SEMICOLON),
  {";", ";", 1.0, Code, KEY_SEMICOLON}, SYM("\"", KEY_APOSTROPHE), {"'", "'", 1.0, Code, KEY_APOSTROPHE},
  SYM("?", KEY_SLASH), {",", ",", 1.0, Code, KEY_COMMA}, {".", ".", 1.0, Code, KEY_DOT}, END,

  {"F1-12", "F1-12", 2.0, Layout, 0, &layouts[Fn], .scheme = 1},
  W("←", 1.0, KEY_LEFT), W("↓", 1.0, KEY_DOWN), W("↑", 1.0, KEY_UP), W("→", 1.0, KEY_RIGHT),
  W("Ins", 1.0, KEY_INSERT), W("Del", 1.0, KEY_DELETE), W("⌫", 2.0, KEY_BACKSPACE), END,

  {"abc", "abc", 1.5, BackLayer, .scheme = 1},
  {"/", "/", 1.0, Code, KEY_SLASH}, {"-", "-", 1.0, Code, KEY_MINUS},
  {"", "", 4.0, Code, KEY_SPACE},
  {".", ".", 1.0, Code, KEY_DOT},
  W("Enter", 1.5, KEY_ENTER),

  {"", "", 0.0, Last},
};

static struct key keys_fn[] = {
  TOP_ROW_ARROWS,

  W("F1", 1.0, KEY_F1), W("F2", 1.0, KEY_F2), W("F3", 1.0, KEY_F3), W("F4", 1.0, KEY_F4), END,
  W("F5", 1.0, KEY_F5), W("F6", 1.0, KEY_F6), W("F7", 1.0, KEY_F7), W("F8", 1.0, KEY_F8), END,
  W("F9", 1.0, KEY_F9), W("F10", 1.0, KEY_F10), W("F11", 1.0, KEY_F11), W("F12", 1.0, KEY_F12), END,

  {"abc", "abc", 1.5, BackLayer, .scheme = 1},
  {"Sym", "Sym", 1.5, Layout, 0, &layouts[Symbols], .scheme = 1},
  {"", "", 4.0, Code, KEY_SPACE},
  W("⌫", 1.5, KEY_BACKSPACE),
  W("Enter", 1.5, KEY_ENTER),

  {"", "", 0.0, Last},
};

/* landscape: one 5-row layer with digits, letters, arrows and Hide; Sym/Fn reuse the portrait layers */
static struct key keys_landscape[] = {
  W("Esc", 1.0, KEY_ESC),
  {"1", "!", 1.0, Code, KEY_1}, {"2", "@", 1.0, Code, KEY_2}, {"3", "#", 1.0, Code, KEY_3},
  {"4", "$", 1.0, Code, KEY_4}, {"5", "%", 1.0, Code, KEY_5}, {"6", "^", 1.0, Code, KEY_6},
  {"7", "&", 1.0, Code, KEY_7}, {"8", "*", 1.0, Code, KEY_8}, {"9", "(", 1.0, Code, KEY_9},
  {"0", ")", 1.0, Code, KEY_0}, {"-", "_", 1.0, Code, KEY_MINUS}, {"=", "+", 1.0, Code, KEY_EQUAL},
  W("⌫", 1.5, KEY_BACKSPACE), END,

  W("Tab", 1.5, KEY_TAB),
  {"q", "Q", 1.0, Code, KEY_Q}, {"w", "W", 1.0, Code, KEY_W}, {"e", "E", 1.0, Code, KEY_E},
  {"r", "R", 1.0, Code, KEY_R}, {"t", "T", 1.0, Code, KEY_T}, {"y", "Y", 1.0, Code, KEY_Y},
  {"u", "U", 1.0, Code, KEY_U}, {"i", "I", 1.0, Code, KEY_I}, {"o", "O", 1.0, Code, KEY_O},
  {"p", "P", 1.0, Code, KEY_P}, {"[", "{", 1.0, Code, KEY_LEFTBRACE}, {"]", "}", 1.0, Code, KEY_RIGHTBRACE},
  {"\\", "|", 1.0, Code, KEY_BACKSLASH}, END,

  MOD("Ctrl", 1.75, Ctrl),
  {"a", "A", 1.0, Code, KEY_A}, {"s", "S", 1.0, Code, KEY_S}, {"d", "D", 1.0, Code, KEY_D},
  {"f", "F", 1.0, Code, KEY_F}, {"g", "G", 1.0, Code, KEY_G}, {"h", "H", 1.0, Code, KEY_H},
  {"j", "J", 1.0, Code, KEY_J}, {"k", "K", 1.0, Code, KEY_K}, {"l", "L", 1.0, Code, KEY_L},
  {";", ":", 1.0, Code, KEY_SEMICOLON}, {"'", "\"", 1.0, Code, KEY_APOSTROPHE},
  W("Enter", 1.75, KEY_ENTER), END,

  MOD("Shift", 2.25, Shift),
  {"z", "Z", 1.0, Code, KEY_Z}, {"x", "X", 1.0, Code, KEY_X}, {"c", "C", 1.0, Code, KEY_C},
  {"v", "V", 1.0, Code, KEY_V}, {"b", "B", 1.0, Code, KEY_B}, {"n", "N", 1.0, Code, KEY_N},
  {"m", "M", 1.0, Code, KEY_M}, {",", "<", 1.0, Code, KEY_COMMA}, {".", ">", 1.0, Code, KEY_DOT},
  {"/", "?", 1.0, Code, KEY_SLASH},
  W("↑", 1.0, KEY_UP), W("Hide", 1.25, KEY_F20), END,

  {"Sym", "Sym", 1.5, Layout, 0, &layouts[Symbols], .scheme = 1},
  MOD("Alt", 1.5, Alt),
  {"`", "~", 1.0, Code, KEY_GRAVE},
  {"", "", 6.0, Code, KEY_SPACE},
  W("←", 1.0, KEY_LEFT), W("↓", 1.0, KEY_DOWN), W("→", 1.0, KEY_RIGHT),
  {"F1-12", "F1-12", 1.5, Layout, 0, &layouts[Fn], .scheme = 1},

  {"", "", 0.0, Last},
};

static struct key keys_index[] = {
  {"abc", "abc", 1.0, Layout, 0, &layouts[Letters], .scheme = 1},
  {"Sym", "Sym", 1.0, Layout, 0, &layouts[Symbols], .scheme = 1},
  {"F1-12", "F1-12", 1.0, Layout, 0, &layouts[Fn], .scheme = 1},
  {"", "", 0.0, Last},
};

#undef W
#undef MOD
#undef SYM
#undef END
#undef TOP_ROW_ARROWS
