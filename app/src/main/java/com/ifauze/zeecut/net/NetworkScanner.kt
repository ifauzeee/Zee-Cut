package com.ifauze.zeecut.net

import com.ifauze.zeecut.model.Device
import java.net.NetworkInterface

object NetworkScanner {

    data class Subnet(val iface: String, val ip: String, val gateway: String)

    fun getWifiSubnet(): Subnet? {
        val interfaces = NetworkInterface.getNetworkInterfaces()?.toList() ?: return null
        for (ni in interfaces) {
            if (ni.isLoopback || !ni.isUp) continue
            if (ni.name != "wlan0" && ni.name != "eth0" && ni.name != "wlan1") continue
            val addrs = ni.inetAddresses.toList().filter { !it.isLoopbackAddress && it.address.size == 4 }
            if (addrs.isNotEmpty()) {
                val ip = addrs[0].hostAddress ?: continue
                val gateway = resolveGateway(ni.name) ?: "192.168.1.1"
                return Subnet(ni.name, ip, gateway)
            }
        }
        return null
    }

    private fun resolveGateway(iface: String): String? {
        return try {
            RootShell.run("ip", "route", "show", "dev", iface).lines()
                .firstOrNull { it.contains("default") }
                ?.split(" ")
                ?.getOrNull(2)
        } catch (e: Exception) {
            null
        }
    }

    fun resolveMac(ip: String): String? {
        RootShell.run("ping", "-c", "1", "-W", "1", ip)
        val out = RootShell.run("cat", "/proc/net/arp")
        return out.lines()
            .firstOrNull { it.startsWith(ip) }
            ?.split("\\s+".toRegex())
            ?.let { if (it.size >= 4 && it[3] != "00:00:00:00:00:00") it[3] else null }
    }

    fun scan(subnet: Subnet, binaryPath: String): List<Device> {
        val out = RootShell.run(binaryPath, "scan", subnet.iface)
        return parseScanOutput(out).filter { it.ip != subnet.ip }
    }

    fun resolveHostnames(devices: List<Device>) {
        devices.forEach { d ->
            if (d.hostname.isNotEmpty()) return@forEach
            val name = resolveHostname(d.ip)
            if (name.isNotEmpty()) d.hostname = name
        }
    }

    private fun resolveHostname(ip: String): String {
        val holder = arrayOf<String?>(null)
        val t = Thread {
            try {
                holder[0] = java.net.InetAddress.getByName(ip).canonicalHostName
            } catch (e: Exception) {
            }
        }
        t.start()
        t.join(800)
        val name = holder[0]
        return if (name != null && name != ip) name else ""
    }

    fun parseScanOutput(output: String): List<Device> {
        return output.lines()
            .filter { it.contains(",") }
            .mapNotNull { line ->
                val parts = line.split(",")
                if (parts.size >= 2 && parts[1].matches(Regex("([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}"))) {
                    Device(ip = parts[0].trim(), mac = parts[1].trim())
                } else {
                    null
                }
            }
    }
}
