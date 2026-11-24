# Disclaimer

- **You can brick your phone.** The scripts here flash bootloader, modem and boot partitions and erase user data. A
  wrong image, a wrong build or an interrupted flash can leave a phone that does not boot and cannot be recovered. You
  run everything at your own risk. There is no warranty of any kind (see [LICENSE](LICENSE)).
- **Tested on a few phones only.** The routes were verified on the maintainer's own moto g power (2026) XT2617V units
  on specific builds. Another model, carrier or build may behave differently. The scripts check the model and the
  build and refuse what they do not know; do not bypass those checks.
- **No firmware is shipped.** This repo holds no Motorola or MediaTek firmware, no patched bootloader, no modem image,
  no vendor module and no file extracted from a phone, and it publishes no binary releases. Where the docs link to
  files hosted by third parties, those files are not ours, we do not control them, and you are responsible for what you
  download and for checking its hash.
- **Your warranty and your service.** Unlocking a bootloader or changing a phone's software may void its warranty and
  may break apps that check device integrity. Changing carrier or network locks may be restricted by your contract or
  by the law where you live. Checking that is your job.
- **Not affiliated.** This project is not affiliated with, endorsed by or supported by Motorola, Lenovo, MediaTek,
  Tracfone, Google or any carrier. All trademarks belong to their owners.
