# Activation via sidemdm QR enrollment (stock / end state A only)

Route D phones skip this: the patched retail `lk` skips the Tracfone activation (see the [README](../README.md)).

Route D phones need **no activation step**: the patched retail `lk` skips the Tracfone activation, so they go straight
to `scripts/route_d.sh`. Only a stock (Tracfone `lk`) or end-state-A phone needs activation: enroll it through the
first-run **six-tap QR** flow using a local, LAN-only "MDM" ([`sidemdm`](https://github.com/lukeponio/sidemdm), vendored
here as a git submodule), then remove the work profile so the phone ends up clean and unmanaged.

> sidemdm lists this exact model (Android 16 / API 36, locked bootloader, verified boot green) as tested.
> It does **not** bypass FRP / Google-account lock: each phone must be one you can factory-reset and set up.

## Computer side

Needs the repo set up first (clone with submodules + venv, see the [README](../README.md)).

### 1. Download the signed DPC APK

```bash
gh release download v1.0.1 --repo lukeponio/sidemdm --pattern '*.apk' --dir sidemdm/dist
shasum -a 256 sidemdm/dist/sidemdm-1.0.1.apk
```

| | |
|---|---|
| APK file SHA-256 (v1.0.1) | `6fec06d246f927456278223327a657a7b6b940b4be6d7da7083f3d78d7ab5d12` |
| Signer cert SHA-256 (from release notes) | `d6ff5d92fc5ed1d50ad1800e602354160658dd911f8879c05eee09e43b300321` |

`sidemdm/dist/*.apk` and all generated files (`release-*/`, `server/site/...`) are gitignored inside
the submodule, so it stays clean.

### 2. Start the enrollment server

```bash
IP=$(ipconfig getifaddr en0)            # Mac's Wi-Fi LAN IP, e.g. 192.168.1.x
.venv/bin/python sidemdm/sidemdm.py --ip "$IP" --port 8080
```

It prints a QR in the terminal (also saved as `sidemdm/release-1.0.1-<IP>-8080/enrollment.png`) and
serves the APK at `http://<IP>:8080/releases/dpc-1.0.1.apk`.

- **One QR / one running server covers all 8 phones.** Keep it running until every phone has downloaded
  the APK; Ctrl+C when done (removal needs no network).
- Reachability check: open `http://<IP>:8080/` in a phone browser, or `curl -I` the APK URL from the Mac.
  If the phone can't reach it, allow incoming connections for Python in
  System Settings → Network → Firewall.
- Port busy? Use another `--port`.


## Per-phone steps (only you can do these)

手机端（只有你能做）：

1. 恢复出厂（enrollment 只能从首次开机流程进）
2. 欢迎页连点 6 下 → 打开内置扫码器
3. 扫码 → 连同一个 Wi-Fi
4. 接受 work profile 设置 → 抽屉里出现 Work 标签
5. 抽屉 → Work 标签 → 打开 Work Profile → Remove Work Profile（两次确认）

它的 DPC 只会申请 managed profile、拒绝成为 device owner，所以移除时只清工作资料，个人分区不受影响；
QR 里带 SHA-256，APK 被换会拒绝。

English:

1. Factory reset (enrollment only starts from first-run setup).
2. On the welcome screen, tap 6 times → built-in QR scanner opens.
3. Scan the QR → join the **same Wi-Fi** as the Mac.
4. Accept the work-profile setup → a **Work** tab appears in the app drawer.
5. App drawer → Work tab → open **Work Profile** → **Remove Work Profile** (two confirmations).

The DPC only ever requests a managed profile and refuses to become device owner, so removal wipes only
the work profile and leaves the personal side alone. The QR pins the APK by SHA-256; a swapped APK is
rejected. If the phone says "App blocked to protect your device", this method can't work on it.

### Optional read-only check (USB debugging on)

```bash
adb shell pm list users                 # work profile present after step 4, gone after step 5
adb shell dumpsys device_policy         # no profile/device owner left after removal
adb shell getprop ro.build.fingerprint  # record firmware
```
