# tools/root-apks/  (gitignored binaries — fetch locally)

Temp-root exploit + manager used by `scripts/reroot.sh`. Download from official GitHub releases, verify SHA-256:

```bash
gh release download v4.7    --repo diabl0w/DFRoot --pattern 'DFRoot_4.7.apk' --dir tools/root-apks
gh release download v3.3.1  --repo tiann/KernelSU --pattern 'KernelSU_v3.3.1_32680-release.apk' --dir tools/root-apks
gh release download v3.3.1  --repo tiann/KernelSU --pattern 'ksud-aarch64-apple-darwin'          --dir tools/root-apks
shasum -a 256 tools/root-apks/*
```

Verified 2026-11-18:
- DFRoot_4.7.apk                      `9e193ffdaada8577e14a04fb19403256b3fa4991fae1331c7956e083c098a7b1`
- KernelSU_v3.3.1_32680-release.apk   `b4a059ace71de2fa65cc7f12b1c58d55fc23ab25e057ee4230ce779742abe450`
- ksud-aarch64-apple-darwin           `6ccadcf7a903f7dbceae053d1793722e18ae401abfdd39b96bf9661658a3c4ed`

## play-integrity/  (optional, per-phone opt-in — DEVICE integrity stack)

KSU modules installed via `ksud module install <zip>` (see `docs/`). STRONG needs a
valid keybox you supply into `/data/adb/tricky_store/keybox.xml`; the bundled AOSP
keybox gives DEVICE only. Fetch from official GitHub releases, verify SHA-256:

```bash
gh release download v2.4    --repo JingMatrix/NeoZygisk     --pattern 'NeoZygisk-v2.4-289-release.zip'          --dir tools/root-apks/play-integrity
gh release download v19     --repo osm0sis/PlayIntegrityFork --pattern 'PlayIntegrityFork-v19.zip'               --dir tools/root-apks/play-integrity
gh release download v3.1.0  --repo beakthoven/TrickyStoreOSS --pattern 'Tricky-Store-OSS-v3.1.0-172-41383f5-Release.zip' --dir tools/root-apks/play-integrity
shasum -a 256 tools/root-apks/play-integrity/*
```

Verified 2026-11-18 (tested on #1 → all NO_INTEGRITY without a keybox):
- NeoZygisk-v2.4-289-release.zip                     `93a1425c67bb89f58a0dcb9fc823ec93f6472214f221e667a70b67c6a6e061a1`
- PlayIntegrityFork-v19.zip        (osm0sis fork)    `83b4d5f32743805c5b5a69361d73b8ab9c095325e24f20711afa1abea837b58f`
- PlayIntegrityFix_v4.9-inject-s.zip (KOWX712 fork)  `bc7a9d92638a6bd90a41b70d3aaf86bc549dd8d3a1e5e901b315a6c425852697`
- Tricky-Store-OSS-v3.1.0-172-41383f5-Release.zip    `f1df8a04d2d020b9c4dda304d22c69ac62be8bdd6187a7bf0a3b94ec2152c9c3`
- spic-v1.4.0.apk  (SPIC verdict checker, herzhenr)  `a9b0036ed4b78b486fcd957fc7038d441cd6e896961ffb6b1bccfd7f03b3e471`
