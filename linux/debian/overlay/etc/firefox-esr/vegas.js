// vegas (#5 touch UI): Debian's firefox-esr reads every *.js in /etc/firefox-esr (see firefox-esr.js there).
// sway runs the panel at scale 3; Firefox would draw at 3 device pixels per CSS px and cut off its right edge on the
// 360-logical-px screen. 2.0 = two thirds of that, what #5 uses set by hand (design page "Programs for a trip").
// A default, not locked: about:config can still change it per profile.
pref("layout.css.devPixelsPerPx", "2.0");
