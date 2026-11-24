# Contributing

Thank you for helping. This page is short on purpose; the M0 issues extend it.

## How work is organised

- Work comes in **batches**. A batch is one GitHub issue (title `[B07] ...`, label `batch`) that holds 1 to 8 related
  tasks in working order. One batch, one pull request.
- Batches are grouped into milestones: **M0 repo ready**, **M1 start here**, **M2 offline next**, **M3 phone queue**.
- Each batch says what hardware it needs (`hardware:` label), its highest risk (`risk:` label), its dependency wave
  (`wave:` label, lower waves first) and which batches must be closed before it starts.
- A task keeps its own id (for example `ui-testing-04`). The docs and other tasks refer to tasks by id, and
  `docs/batches.json` tells you which batch a task is in.
- Comment on a batch before you start, so two people (or two agents) do not do the same work.

To find something to do:

```bash
gh issue list --label batch --milestone "M1 start here" --label hardware:none   # startable now, nothing needed
gh issue list --label batch --label wave:1                                       # no dependencies at all
```

## Hard rules

1. **Nothing that identifies a phone, a SIM or a network.** No serial numbers, IMEIs, MAC addresses, phone numbers,
   ICCIDs, Wi-Fi names or passwords, in code, docs, logs, issues, pull requests or screenshots. Write `<serial>`.
   Redact a log before you paste it.
2. **No binaries.** No firmware, boot images, kernel modules, APKs, archives, keyboxes or files extracted from a
   phone. This repo publishes no binary releases. Everyone builds from their own phone and their own firmware.
3. **Never weaken a safety gate.** The typed confirmations (`FLASH <serial>`, `ERASE <serial>`, `DOWNGRADE <serial>`,
   `FLASHFW <serial>`), `pick_serial` and the identity and build gates stay as strict as they are.
4. **Never write the NV partitions or `/metadata`** (`nvram`, `nvdata`, `nvcfg`, `protect1`, `protect2`, `persist`,
   `proinfo`, `seccfg`, `efuse`), and never `preloader` or `gpt`. Work on per-phone copies only.
5. **Modem and boot-chain work is gated.** An issue that boots the modem or changes the boot chain needs the
   maintainer's written go-ahead for that phone, in the issue, before the run.
6. **Do not copy code from `vegas-freedom/`.** It is AGPL-3.0 and this tree is MIT. Changes to it go upstream.

## Pull requests

- One pull request per batch, titled like the batch (`[B07] ...`) with `Closes #<batch issue>` in the body.
- One commit per task, with the task id at the start of the subject (`ui-testing-04: ...`), so a task can be
  reviewed and reverted alone.
- If a task of the batch cannot be finished, leave its box open in the batch issue, say why in the pull request and
  finish the tasks that do not need it. A follow-up pull request can close the batch later.
- Say what you ran and on what: nothing, a Linux VM, or a phone (its end state and build, never its serial).
- A change that could not be tested without a phone is marked untested. That is fine; hiding it is not.
- A pull request that flashes a phone is merged only after a hardware run by you or the maintainer.
- `bash -n` every script you touch. Run `python -m pytest sidemdm/tools -q` if you touch Python.

## Licence

Your contribution is licensed under the MIT licence of this repo, except changes to the GPL-3.0-or-later files listed
in [THIRD_PARTY.md](THIRD_PARTY.md), which stay under that licence.
