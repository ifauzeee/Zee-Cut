package com.ifauze.zeecut

import android.os.Bundle
import android.widget.Button
import android.widget.ListView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.ifauze.zeecut.databinding.ActivityMainBinding
import com.ifauze.zeecut.model.Device
import com.ifauze.zeecut.net.NetworkScanner
import com.ifauze.zeecut.net.RootShell
import com.ifauze.zeecut.net.SpoofController
import com.ifauze.zeecut.ui.DeviceListAdapter
import java.io.File
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var adapter: DeviceListAdapter
    private val devices = mutableListOf<Device>()
    private var binaryPath = ""
    private var subnet: NetworkScanner.Subnet? = null
    private lateinit var spoof: SpoofController
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        if (!RootShell.isRootAvailable()) {
            Toast.makeText(this, "Root tidak tersedia. Aplikasi tidak dapat berfungsi.", Toast.LENGTH_LONG).show()
        }

        adapter = DeviceListAdapter(
            this,
            devices,
            onCut = { d -> withSubnet { s -> spoof.cut(d, s.iface, s.gateway); afterAction() } },
            onLag = { d -> withSubnet { s -> spoof.lag(d, s.iface, s.gateway, lagRate()); afterAction() } },
            onRestore = { d -> withSubnet { s -> spoof.restore(d, s.iface, s.gateway); afterAction() } }
        )
        binding.list.adapter = adapter

        binding.seekLag.max = 90
        binding.seekLag.progress = 50
        binding.tvLagValue.text = "50%"
        binding.seekLag.setOnSeekBarChangeListener(object : android.widget.SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seek: android.widget.SeekBar?, p: Int, fromUser: Boolean) {
                binding.tvLagValue.text = "$p%"
            }
            override fun onStartTrackingTouch(seek: android.widget.SeekBar?) {}
            override fun onStopTrackingTouch(seek: android.widget.SeekBar?) {}
        })

        binding.btnScan.setOnClickListener { doScan() }
    }

    private fun lagRate(): Double = binding.seekLag.progress / 100.0

    private fun afterAction() {
        adapter.notifyDataSetChanged()
        updateSummary()
    }

    private fun updateSummary() {
        val cut = devices.count { it.status == com.ifauze.zeecut.model.DeviceStatus.CUT }
        val lag = devices.count { it.status == com.ifauze.zeecut.model.DeviceStatus.LAG }
        val norm = devices.size - cut - lag
        binding.status.text = "Normal: $norm   Cut: $cut   Lag: $lag"
    }

    private fun withSubnet(action: (NetworkScanner.Subnet) -> Unit) {
        val s = subnet
        if (s == null) {
            Toast.makeText(this, "Lakukan scan dulu", Toast.LENGTH_SHORT).show()
            return
        }
        action(s)
    }

    private fun prepareBinary(): String {
        val src = File(applicationInfo.nativeLibraryDir, "arp_spoof")
        val dst = File(filesDir, "arp_spoof")
        if (!dst.exists() || dst.length() != src.length()) {
            src.inputStream().use { fi -> dst.outputStream().use { fo -> fi.copyTo(fo) } }
        }
        RootShell.run("chmod", "0755", dst.absolutePath)
        return dst.absolutePath
    }

    private fun doScan() {
        executor.execute {
            if (binaryPath.isEmpty()) binaryPath = prepareBinary()
            if (!this::spoof.isInitialized) spoof = SpoofController(binaryPath)
            val sub = NetworkScanner.getWifiSubnet()
            if (sub == null) {
                runOnUiThread {
                    Toast.makeText(this, "Gagal membaca info jaringan WiFi", Toast.LENGTH_SHORT).show()
                }
                return@execute
            }
            subnet = sub
            val found = NetworkScanner.scan(sub, binaryPath)
            NetworkScanner.resolveHostnames(found)
            runOnUiThread {
                devices.clear()
                devices.addAll(found)
                adapter.notifyDataSetChanged()
                binding.status.text = "${found.size} perangkat ditemukan (${sub.iface})"
                updateSummary()
            }
        }
    }

    override fun onDestroy() {
        if (this::spoof.isInitialized && subnet != null) {
            spoof.restoreAll(devices, subnet!!.iface, subnet!!.gateway)
        }
        executor.shutdown()
        super.onDestroy()
    }
}
