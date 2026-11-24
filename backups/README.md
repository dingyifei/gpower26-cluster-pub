# backups/

Compressed full-partition dumps, one archive per phone (gitignored — too large and device-unique for git).

- Source: `vegas-freedom/scripts/backup_partitions.py` → `vegas-freedom/backups/stock_<ts>/` (per-partition, sha256-verified).
- Archived here as `<serial>_stock_<ts>.tar.zst`, created by `scripts/archive_backup.sh <stock_dir>`.
- These are the way back (`lk_a`, `init_boot_a`, `md1img_a`, `nvdata/nvram/protect*/persist`, etc.).

Extract: `zstd -dc <archive>.tar.zst | tar -xf - -C <dest>`  ·  Verify: `cd <extracted> && sha256sum -c SHA256SUMS`
