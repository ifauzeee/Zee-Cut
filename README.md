# Zee-Cut (Android)

Network device controller for **your own WiFi network** — scan connected devices and
control their connectivity via ARP spoofing. Inspired by NetCut.

> **Legal notice:** Use ONLY on networks you own and administer. Unauthorized use on
> networks you do not own is illegal and unethical.

## Features

- **Scan** — discover devices on your WiFi (reads ARP table after an ARP sweep).
- **Cut** — fully block a device's internet (ARP MITM, IP forwarding off).
- **Lag** — throttle a device (best-effort packet drop/delay; experimental).
- **Restore** — repair ARP tables; all devices are auto-restored when the app closes.

Requires **root**.

## How it works

A small native binary (`arp_spoof`, built with the NDK) is copied into the app's private
data dir and executed via `su`. It performs raw L2 ARP operations that Kotlin cannot do
directly:

```
Target  <---- spoofed ARP ---->  Zee-Cut (phone, rooted)  <---- spoofed ARP ---->  Gateway
```

- `cut` = spoof + phone does not forward → target isolated.
- `lag` = spoof + phone forwards traffic but drops/delays a fraction of packets.
- `restore` = sends correct ARP replies (real MACs) to undo spoofing.

## Build

Requirements: Android Studio, Android SDK, NDK (side-by-side), a rooted device.

1. Copy `local.properties.example` to `local.properties` and set `sdk.dir` / `ndk.dir`
   (Android Studio also fills this in automatically).
2. Open the project in **Android Studio** (File → Open). It will generate the Gradle
   wrapper and sync. Then Build → Build Bundle(s) / APK(s) → Build APK.
3. Install on the rooted device:
   ```
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```
   To build from the command line instead, generate the wrapper first
   (`gradle wrapper`, requires Gradle installed) then `./gradlew assembleDebug`.

## Test on device (manual)

Verify root and the native binary from a shell:

```bash
adb shell
su
id            # should show uid=0

# locate the binary the app extracts
ls -l /data/data/com.ifauze.zeecut/files/arp_spoof

# run a scan manually (replace wlan0 with your interface)
/data/data/com.ifauze.zeecut/files/arp_spoof scan wlan0
```

Watch ARP traffic during a Cut to confirm spoofing is active:

```bash
adb shell su -c "tcpdump -en -i wlan0 arp"   # or use a packet capture app
```

## Caveats

- **Lag mode is experimental** and may degrade overall network quality; Cut/Restore are
  reliable. Real traffic-shaping (`tc`/HTB) is out of scope on stock Android kernels.
- Raw sockets require a kernel that permits `AF_PACKET` for root (standard on rooted devices).
- Some devices mount the native lib dir as `noexec`; the app copies the binary to a writable
  private dir and `chmod 0755` to avoid this.

## Troubleshooting

- **App says the binary is missing / `FileNotFound` at `prepareBinary`**: the NDK-built
  binary is packaged as `libarp_spoof.so` (renamed so AGP includes it) and extracted to
  `nativeLibraryDir` thanks to `android:extractNativeLibs="true"` +
  `packaging.jniLibs.useLegacyPackaging`. Verify it is inside the APK:
  ```
  unzip -l app/build/outputs/apk/debug/app-debug.apk | grep arp_spoof
  ```
  Expected: `lib/arm64-v8a/libarp_spoof.so` (and other ABIs you built). If absent, ensure
  `externalNativeBuild` points at `jni/CMakeLists.txt` and a CMake/NDK build actually ran
  (Build → Refresh Linked C++ Projects). The app copies it to a writable private dir and
  `chmod 0755`, so a `noexec` system partition is handled.

- **Cut works but Lag is unstable / hurts other traffic**: Lag is best-effort. Lower the
  `dropRate` in `SpoofController.lag` (e.g. `0.2`) or avoid Lag on busy networks.

## Project layout

```
app/src/main/
  AndroidManifest.xml
  java/com/ifauze/zeecut/
    MainActivity.kt
    net/RootShell.kt
    net/NetworkScanner.kt
    net/SpoofController.kt
    model/Device.kt
    ui/DeviceListAdapter.kt
  res/  (layout, values)
  jni/  (arp_spoof.c, net_common.h, CMakeLists.txt)
```
