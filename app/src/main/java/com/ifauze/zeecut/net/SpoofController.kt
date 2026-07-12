package com.ifauze.zeecut.net

import com.ifauze.zeecut.model.Device
import com.ifauze.zeecut.model.DeviceStatus
import java.io.File

class SpoofController(private val binaryPath: String) {

    private data class Procs(val spoof: Process, val forward: Process?)

    private val active = mutableMapOf<String, Procs>()

    fun cut(device: Device, iface: String, gateway: String) {
        if (active.containsKey(device.ip)) return
        val gmac = NetworkScanner.resolveMac(gateway) ?: return
        val cmd = "$binaryPath spoof $iface ${device.ip} ${device.mac} $gateway $gmac"
        val p = Runtime.getRuntime().exec(arrayOf("su", "-c", cmd))
        active[device.ip] = Procs(p, null)
        device.status = DeviceStatus.CUT
    }

    fun lag(device: Device, iface: String, gateway: String, dropRate: Double = 0.5) {
        if (active.containsKey(device.ip)) return
        val gmac = NetworkScanner.resolveMac(gateway) ?: return
        val spoofCmd = "$binaryPath spoof $iface ${device.ip} ${device.mac} $gateway $gmac"
        val fwdCmd = "$binaryPath forward $iface $dropRate ${device.mac} $gmac"
        val spoof = Runtime.getRuntime().exec(arrayOf("su", "-c", spoofCmd))
        val forward = Runtime.getRuntime().exec(arrayOf("su", "-c", fwdCmd))
        active[device.ip] = Procs(spoof, forward)
        device.status = DeviceStatus.LAG
    }

    fun restore(device: Device, iface: String, gateway: String) {
        val procs = active[device.ip] ?: run {
            device.status = DeviceStatus.NORMAL
            return
        }
        procs.forward?.destroy()
        procs.spoof.destroy()
        val gmac = NetworkScanner.resolveMac(gateway)
        if (gmac != null) {
            RootShell.run(binaryPath, "restore", iface, device.ip, device.mac, gateway, gmac)
        }
        active.remove(device.ip)
        device.status = DeviceStatus.NORMAL
    }

    fun restoreAll(devices: List<Device>, iface: String, gateway: String) {
        devices.forEach { restore(it, iface, gateway) }
    }
}
