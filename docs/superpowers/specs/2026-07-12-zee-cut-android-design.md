# Zee-Cut Android — Design Spec

**Date:** 2026-07-12
**Author:** ifauzeee
**Status:** Approved (design)

## 1. Purpose & Scope

Zee-Cut Android is a network administration tool for **your own WiFi network only**.
It lets you scan connected devices and control their connectivity via ARP spoofing:

- **Cut** — fully block a device's internet access (reliable).
- **Lag (throttle)** — slow a device down via best-effort packet drop/delay (experimental).
- **Restore** — return a device to normal connectivity.

All operations require **root**. On exit the app restores every device it touched, so no
disruption is permanent.

> Legal: use only on networks you own and administer. Unauthorized use is illegal.

## 2. Architecture

- **Kotlin** app: UI, orchestration, root-shell invocation, device state tracking.
- **C native binary** (`arp_spoof`), built with the **Android NDK** via CMake, executed
  through `su`. Self-contained — no third-party root binaries required.

Rationale: ARP spoofing needs raw L2 packet injection, which is impossible from normal
Kotlin. A bundled native executable run as root is the most reliable, device-independent
approach (chosen approach A).

### Build / test environment
The user builds and tests on a rooted device using Android Studio + NDK. This repo contains
a complete, correct project structure; compilation happens on the user's machine.

## 3. Project Structure

```
Zee-Cut/
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/ifauze/zeecut/
│       │   ├── MainActivity.kt
│       │   ├── net/RootShell.kt          # run "su -c <cmd>", capture output
│       │   ├── net/NetworkScanner.kt      # get subnet, call native scan, parse Device list
│       │   ├── net/SpoofController.kt     # start/stop native spoof per device, track state
│       │   ├── model/Device.kt            # ip, mac, hostname, status
│       │   └── ui/DeviceListAdapter.kt
│       ├── res/
│       │   ├── layout/  (activity_main.xml, device_row.xml)
│       │   ├── values/  (strings.xml, colors.xml, themes.xml)
│       │   └── drawable/
│       └── jni/
│           ├── CMakeLists.txt
│           ├── arp_spoof.c                # native binary: scan / spoof / restore / forward
│           └── net_common.h
├── build.gradle.kts          # root
├── settings.gradle.kts
├── gradle.properties
├── .gitignore
├── local.properties.example   # documents SDK/NDK paths (real local.properties gitignored)
└── README.md
```

The C binary is compiled as an executable and packaged under
`app/src/main/jniLibs/<abi>/arp_spoof`. At runtime the app copies it into its private
files directory (`getFilesDir()`), `chmod 0755`, then runs it via `su`.

## 4. Native Binary (`arp_spoof.c`)

Single executable with subcommands. Uses raw AF_PACKET sockets (Linux kernel, available on
Android) for ARP and packet forwarding.

| Subcommand | Arguments | Behavior |
|------------|-----------|----------|
| `scan` | `<iface>` | Send ARP "who-has" to the subnet + read `/proc/net/arp`; print `ip,mac` lines. |
| `spoof` | `<iface> <tip> <tmac> <gip> <gmac>` | Repeatedly send spoofed ARP replies: target←(we are gateway), gateway←(we are target). |
| `restore` | `<iface> <tip> <tmac> <gip> <gmac>` | Send correct ARP replies (real MACs) to undo spoofing. |
| `forward` | `<iface> <drop_rate>` | Enable IP forward (`/proc/sys/net/ipv4/ip_forward=1`), then loop receiving packets and re-sending them, dropping/delaying `drop_rate` fraction (Lag mode). |

**Cut mode** = `spoof` with IP forward OFF (target isolated). Reliable.
**Lag mode** = `spoof` + `forward` with IP forward ON (MITM + rate-limit). Best-effort; may
need per-device/ROM tuning and can affect other traffic.
**Restore** = `restore` to target and gateway, then stop `forward`.

The native binary must be robust: validate arguments, handle `SIGTERM` to stop cleanly, and
flush correct ARP on exit where feasible.

## 5. Kotlin Components

- **RootShell** — executes `su -c <cmd>`, returns stdout/stderr, detects missing root.
- **NetworkScanner** — obtains local IP + subnet (`ip addr` / `NetworkInterface`), invokes
  `arp_spoof scan`, parses output into `Device` objects, resolves hostnames best-effort.
- **SpoofController** — manages one native process per target, stores state
  (`NORMAL` / `CUT` / `LAG`), and performs full cleanup (restore all) on app exit /
  `onDestroy`.
- **MainActivity** — checks root on launch, requests permissions
  (`INTERNET`, `ACCESS_WIFI_STATE`, `POST_NOTIFICATIONS`), renders the device list with
  Cut / Lag / Restore buttons, dark-themed UI.
- **Device** — data model: `ip`, `mac`, `hostname`, `status`.

## 6. Data Flow

1. App launches → `RootShell` confirms `su` works.
2. User taps **Scan** → `NetworkScanner` gets subnet, runs `arp_spoof scan`, lists devices.
3. User taps **Cut** on a device → `SpoofController` starts `arp_spoof spoof` (IP forward off).
4. User taps **Lag** → `SpoofController` starts `spoof` + `forward` (IP forward on, drop rate).
5. User taps **Restore** (or closes app) → `restore` sent + `forward` stopped; ARP repaired.

## 7. Error Handling

- Root unavailable → show clear message, disable controls.
- Native binary missing/failed to copy → instruct to rebuild via NDK.
- Scan failure → retry / show error.
- Spoof already running for a device → ignore duplicate start.

## 8. Testing

- Build in Android Studio with NDK; install on rooted device.
- Manual `adb` verification commands documented in README (scan output, spoof packets via
  `tcpdump`/`arpspoof` check).
- Lightweight unit test for `NetworkScanner` output parsing (JUnit).

## 9. Known Limitations

- **Lag mode is experimental** and may degrade network quality; Cut/Restore should be solid.
- Requires root and a kernel allowing raw AF_PACKET + `ip_forward`.
- Real traffic-shaping (`tc`/HTB) is out of scope (not reliably available on stock Android).

## 10. Out of Scope (YAGNI)

- Cross-platform desktop (already exists as Zee-Cut Python).
- Scheduling, profiles, cloud sync, paid features.
