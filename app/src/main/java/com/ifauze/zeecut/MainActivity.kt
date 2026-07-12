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
            onCut = { d -> withSubnet { s -> spoof.cut(d, s.iface, s.gateway); adapter.notifyDataSetChanged() } },
            onLag = { d -> withSubnet { s -> spoof.lag(d, s.iface, s.gateway); adapter.notifyDataSetChanged() } },
            onRestore = { d -> withSubnet { s -> spoof.restore(d, s.iface, s.gateway); adapter.notifyDataSetChanged() } }
        )
        binding.list.adapter = adapter

        binding.btnScan.setOnClickListener { doScan() }
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
            runOnUiThread {
                if (sub == null) {
                    Toast.makeText(this, "Gagal membaca info jaringan WiFi", Toast.LENGTH_SHORT).show()
                    return@runOnUiThread
                }
                subnet = sub
                val found = NetworkScanner.scan(sub, binaryPath)
                devices.clear()
                devices.addAll(found)
                adapter.notifyDataSetChanged()
                binding.status.text = "${found.size} perangkat ditemukan (${sub.iface})"
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
