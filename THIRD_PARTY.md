# Third-party code and licences

The original code and docs in this repository are MIT ([LICENSE](LICENSE)). The parts below are not.

## Files in this tree under another licence

| Files | Licence | Origin |
|---|---|---|
| `linux/ui-src/wvkbd/layout.vegas.h`, `linux/ui-src/wvkbd/config.vegas.h`, `linux/ui-src/wvkbd/code-mod-release.patch` | GPL-3.0-or-later ([LICENSES/GPL-3.0-or-later.txt](LICENSES/GPL-3.0-or-later.txt)) | Derived from [wvkbd](https://github.com/jjsullivan5196/wvkbd). `linux/ui-src/wvkbd/build.sh` copies them into a wvkbd source tree and builds the keyboard there. wvkbd itself is not in this repo. |

## MIT-licensed code from other authors

| Files | Notice |
|---|---|
| `linux/tools/propshim/propshim.c` | Contains code under the MIT License, Copyright (c) 2026 Matt Cabrices. The full notice is in the file's header. |
| `linux/kernel/fragment.config` | Derived from the kernel configuration of the moto-pad-2026-arch-linux port (MIT). |

## Submodules

They are separate programs, referenced at a pinned commit. Their code is not copied into this tree.

| Path | Licence | Upstream |
|---|---|---|
| `vegas-freedom/` | AGPL-3.0 as a whole; it bundles GPL-3.0-or-later (`liblk`) and MIT parts. See its `LICENSE` and `LICENSE-NOTICE.md`. | https://github.com/andrewwm/vegas-freedom |
| `sidemdm/` | MIT | https://github.com/lukeponio/sidemdm |

Never copy code from `vegas-freedom/` into the MIT tree. Changes to a submodule go to its upstream.

## What the build scripts download or read

The build scripts fetch or read software that is never stored here: the Android common kernel (GPL-2.0), busybox
(GPL-2.0), Debian packages, and files from your own phone and firmware (proprietary to Motorola and MediaTek). Those
stay on your machine. This repo publishes no binary built from them.
