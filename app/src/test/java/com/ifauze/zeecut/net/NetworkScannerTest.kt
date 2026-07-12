package com.ifauze.zeecut.net

import org.junit.Assert.assertEquals
import org.junit.Test

class NetworkScannerTest {

    @Test
    fun parseScanOutput_filtersValidLines() {
        val out = "192.168.1.1,aa:bb:cc:dd:ee:ff\n" +
                "garbage line without comma\n" +
                "192.168.1.5,11:22:33:44:55:66\n"
        val devices = NetworkScanner.parseScanOutput(out)
        assertEquals(2, devices.size)
        assertEquals("192.168.1.1", devices[0].ip)
        assertEquals("aa:bb:cc:dd:ee:ff", devices[0].mac)
        assertEquals("192.168.1.5", devices[1].ip)
    }

    @Test
    fun parseScanOutput_skipsInvalidMac() {
        val out = "10.0.0.2,not-a-mac\n192.168.0.9,aa:bb:cc:00:11:22\n"
        val devices = NetworkScanner.parseScanOutput(out)
        assertEquals(1, devices.size)
        assertEquals("192.168.0.9", devices[0].ip)
    }
}
