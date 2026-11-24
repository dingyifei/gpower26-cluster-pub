# tools/apps/  (gitignored APKs — fetch locally)

Replacement "basics" installed on every phone by `scripts/phone.sh apps` (run from `postroot.sh`), before
`declutter` disables the stock Google/carrier apps. `phone.sh` pins each file's SHA-256 (`APPS=` near the
top) and refuses to install on a mismatch. When you bump a version, update both this file and `APPS=`.

| App | Package | File | Source |
|---|---|---|---|
| Fossify Messages 1.10.2 (default SMS) | `org.fossify.messages` | `messages-26-foss-release.apk` | github.com/FossifyOrg/Messages releases |
| Fossify File Manager 1.6.4 | `org.fossify.filemanager` | `file-manager-16-foss-release.apk` | github.com/FossifyOrg/File-Manager releases |
| Firefox 160.0.1 (default browser) | `org.mozilla.firefox` | `fenix-160.0.1.multi.android-arm64-v8a.apk` | archive.mozilla.org/pub/fenix/releases |
| F-Droid 2000053 | `org.fdroid.fdroid` | `org.fdroid.fdroid_2000053.apk` | f-droid.org/repo |
| Aurora Store (vc 76) | `com.aurora.store` | `com.aurora.store_76.apk` | f-droid.org/repo |
| Fossify Keyboard 1.9.1 (default IME, replaces Gboard) | `org.fossify.keyboard` | `keyboard-14-foss-release.apk` | github.com/FossifyOrg/Keyboard releases |

```bash
cd tools/apps
curl -LO https://github.com/FossifyOrg/Messages/releases/download/1.10.2/messages-26-foss-release.apk
curl -LO https://github.com/FossifyOrg/File-Manager/releases/download/1.6.4/file-manager-16-foss-release.apk
curl -LO https://archive.mozilla.org/pub/fenix/releases/160.0.1/android/fenix-160.0.1-android-arm64-v8a/fenix-160.0.1.multi.android-arm64-v8a.apk
curl -LO https://f-droid.org/repo/org.fdroid.fdroid_2000053.apk
curl -LO https://f-droid.org/repo/com.aurora.store_76.apk
curl -LO https://github.com/FossifyOrg/Keyboard/releases/download/1.9.1/keyboard-14-foss-release.apk
shasum -a 256 *.apk
```

Verified 2026-11-18 (file SHA-256 · signer cert SHA-256):
- messages-26-foss-release.apk `7077dae6613d7a9d775841c4c10be16e255f8af8d5152bc84a5e6984740b56e1` · Fossify `affdb124…ff292` (= GitHub asset digest)
- file-manager-16-foss-release.apk `6e4656b8947966a2853681691bb0005e802ee89983fb141ec0f7186497dcd5f4` · Fossify `affdb124…ff292` (= GitHub asset digest)
- fenix-160.0.1.multi.android-arm64-v8a.apk `1c811bbdc8d7488b9340d379889cf04105525596d21a7c596b3a664d833858ea` · Mozilla Release Engineering `a78b62a5…19b04`
- org.fdroid.fdroid_2000053.apk `dac55a0d17b1edf7e7286b48cfbd70c7c52fbb32a00af062c68830a437c47959` · F-Droid client `43238d51…9ccab`
- com.aurora.store_76.apk `fd9c75d90d0f4a7c132b9b4a5a2cf1992a45e03b8d8ff988b7dcfbc0db2c4d11` · f-droid.org repo key `5c83c767…5f532`

- keyboard-14-foss-release.apk `e326885c08b68212fd9fdda9be8a4fa492d5daba7ff37bb4ff4511826f40a8d0` · Fossify `affdb124…ff292` (= GitHub asset digest)

Check a signer: `~/Library/Android/sdk/build-tools/36.0.0/apksigner verify --print-certs <apk>`.
