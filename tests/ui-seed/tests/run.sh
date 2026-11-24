#!/bin/sh
# run the vegas-home / vegas-net tests in the trixie VM
cd "$(dirname "$0")" && orb -m vegas-deb sh -c "cd '$PWD' && python3 -m pytest -q -p no:cacheprovider -o asyncio_mode=auto $* 2>&1"
