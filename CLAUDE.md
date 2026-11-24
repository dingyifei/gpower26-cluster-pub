# CLAUDE.md

This file gives guidance to Claude Code (and other coding agents) working in this repository.

## What this repo is

Tooling to turn Motorola moto g power 2026 phones (XT2617V, Tracfone, product `vegas`, MediaTek MT6835) into a phone
cluster, driven from a Mac over adb/fastboot. Mostly bash, plus two Textual TUIs and a Debian image for the phone.
Real hardware is the only real test: most code paths flash partitions, so a wrong image can brick a phone.

End states of a phone:

- **D** (default): bootloader locked / AVB green, patched retail `lk` (`carrier=retus`, skips Tracfone activation),
  optional SIM-unlock modem, **unrooted at rest** (temp root via DFRoot + KernelSU only for one-time config), Moto 80%
  charge cap.
- **E** (dual boot): bootloader unlocked, unrooted Android by default, Debian in the LP partition `linux` on a Vol-up
  tap. Route `scripts/route_e.sh` (runs `scripts/linux_b.sh`), runbook `linux/README.md`.
- **A** (legacy): unlocked + permanent root.

## Hard rules

These hold for every change and every command you propose. `CONTRIBUTING.md` has the same list for people.

1. **You have no phone.** Never run `adb`, `fastboot`, a route script or anything else that talks to a device unless
   the person at the keyboard asked for that exact run on that exact phone. A change that cannot be tested without a
   phone is reported as untested.
2. **Never weaken a safety gate.** Destructive steps need a typed token (`FLASH <serial>`, `ERASE <serial>`,
   `DOWNGRADE <serial>`, `FLASHFW <serial>`). In `--auto` mode the tokens are pre-supplied with `--confirm`; pass them
   only on the owner's explicit go-ahead for that phone. `pick_serial` refuses to guess when more than one phone is
   attached. The identity and build gates (`gate_fastboot`, `gate_android`) stay as strict as they are.
3. **Never write the NV partitions or `/metadata`**: `nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`,
   `proinfo`, `seccfg`, `efuse`, and never `preloader` or `gpt`. Work on per-phone copies only. The modem is started
   only in an issue that says so and with the owner's go-ahead.
4. **No identifiers and no binaries in the repo, in issues or in pull requests.** No serial numbers, IMEIs, MAC
   addresses, SIM numbers, Wi-Fi names or passwords; write `<serial>`. No firmware, boot images, kernel modules, APKs,
   archives or files extracted from a phone. `devices/`, `logs/`, `backups/` and `linux/work/` stay local.
5. **State what was verified.** Docs mark each claim as verified or unverified, and so should you. Read a phone's
   state live rather than trusting a note.

## Working a batch

Work is handed out as batch issues (label `batch`, title `[Bnn] ...`): 1 to 8 tasks in working order, one pull request.
The top of each batch issue has a `yaml` block (`batch`, `issue`, `wave`, `hardware`, `risk`, `depends_on`, `unblocks`,
`tasks`) and `docs/batches.json` holds the same data for all batches, plus a map from task id to batch.

1. Pick a batch whose `depends_on` issues are all closed and whose `hardware` you really have. With no phone, take
   only `hardware: none` or `hardware: vm` batches.
2. Do the tasks in order. One commit per task; start the subject with the task id (`ui-testing-04: ...`).
3. Run what each task's "Done when" asks for and report the real result. A check you could not run is reported as
   not run.
4. Open one pull request titled like the batch, with `Closes #<issue>` and one line per task on what was run and on
   what. Tick the task boxes in the batch issue.
5. If a task is blocked, leave its box open, say why, and continue with the tasks that do not need it. Do not widen
   the batch: a new idea becomes a comment on the batch, not extra changes in the pull request.

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt -r vegas-freedom/requirements.txt
python -m pytest sidemdm/tools -q        # the automated tests in the submodule (expect 12 passed)
bash -n scripts/<file>.sh                # syntax check: the usual "test" for a script change with no phone attached

scripts/route_d.sh <serial> [--from STAGE | --only STAGE] [--list]       # take a phone to end state D
scripts/downgrade.sh <serial>   # newer than -4-2 (e.g. -4-3) -> base 36.48-22-3-3
scripts/upgrade.sh <serial>     # base -> -4-2; then route_d.sh with GATE_BASEBAND_ANY=1
.venv/bin/python scripts/bench.py        # TUI over route_d.sh for phones on USB
.venv/bin/python scripts/farm.py status [--json] | run <action> [serial ...|all]   # racked-phone maintenance
scripts/phone.sh <command> [serial|all]  # single-phone helpers (info, record, park, charge-protect, ...); see its header
```

## Architecture

- **`scripts/lib.sh`** is sourced by every bash script (callers set `ROOT` and `S`=serial). It holds the adb/fastboot
  wrappers (`ash`, `rsh` = root shell via base64, `fbv` = fastboot getvar), waits, the **stage system**, human-input
  gates, and the **identity/build gates** with the expected product/SKU/CID/build/baseband constants and firmware
  image paths.
- **Stage protocol**: scripts print machine-readable lines (`::stage <name> start|done|fail|skip`,
  `::confirm <token>|<text>`, `::manual <text>`) that `bench.py` parses to drive dialogs. Stage state persists in
  `logs/<serial>/stages.json`, so runs resume with `--from`. A stage is a function `st_<name>` (dashes become
  underscores) using `STAGE`/`STAGE_DONE`/`die`.
- **Build gate**: the patched `lk` was made from build `-4-2`, so route D only accepts `W1WEOS36.48-22-3-3` base or
  `-4-2`. `downgrade.sh` derives its fastboot command list from Motorola's `flashfile.xml` inside the firmware zip on
  each run (skipping lk/gpt/preloader and the nvdata erase).
- **`bench.py`** (setup bench) and **`farm.py`** (racked phones) are thin Textual front-ends that run the bash scripts
  as subprocesses, one job per phone, in parallel.
- **`linux/`**: the kernel recipe (`kernel/`), the boot chooser and initramfs (`initramfs/`), host tools (`tools/`),
  and the Debian image (`debian/build.sh` plus `debian/overlay/`, which is copied onto the root filesystem). The touch
  UI is in `debian/overlay/usr/lib/vegas/` and `linux/ui-src/`. Everything built goes to `linux/work/`, which is
  gitignored and never published.
- `reroot.sh` does temp root after a wipe, driving the phone UI via `scripts/uia.py`. `permroot.sh`, `postroot.sh`,
  `root_toggle.sh`, `install_modules.sh` and `ksu-modules/` are legacy end-state-A tooling.
- **Submodules**: `sidemdm/` (QR enrollment, MIT) and `vegas-freedom/` (lk patch scripts, AGPL-3.0). Never copy
  code from `vegas-freedom/` into this MIT tree; changes to it go upstream.
- **Gitignored binaries**: `tools/locked/`, `tools/root-apks/`, `tools/apps/` hold only a README and hashes here.

## Conventions and pitfalls

- macOS `fastboot devices` can miss a phone under concurrent calls; use `in_fastboot` (retries), not a single check.
- `ash` redirects stdin from `/dev/null` so it never eats a caller's input (confirm/manual read stdin).
- `phone.sh` uses `set -eu` without `pipefail` on purpose (early-closing pipes); `route_d.sh` uses `set -Eeuo pipefail`.
- Right after `upgrade.sh`, fastboot reports a stale baseband until first boot, hence `GATE_BASEBAND_ANY=1`.
- The build scripts take the phone serial as a required argument or `VEGAS_SERIAL`; nothing has a default serial.
- In the docs, "#1" to "#8" are the maintainer's phones. They are labels, not identifiers.
- One batch, one pull request, one commit per task. Say in the pull request what was run and on what (nothing, a VM,
  a phone).
