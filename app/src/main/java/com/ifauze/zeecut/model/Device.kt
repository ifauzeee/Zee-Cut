package com.ifauze.zeecut.model

enum class DeviceStatus { NORMAL, CUT, LAG }

data class Device(
    val ip: String,
    val mac: String,
    var hostname: String = "",
    var status: DeviceStatus = DeviceStatus.NORMAL
)
