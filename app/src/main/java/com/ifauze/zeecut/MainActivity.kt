package com.ifauze.zeecut

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.ifauze.zeecut.databinding.ActivityMainBinding
import com.ifauze.zeecut.model.DeviceStatus
import com.ifauze.zeecut.net.NetworkScanner
import com.ifauze.zeecut.net.RootShell
import com.ifauze.zeecut.net.SpoofController
import com.ifauze.zeecut.ui.DeviceListAdapter
import java.io.File
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var adapter: DeviceListAdapter
    private val devices = mutableListOf<com.ifauze.zeecut.model.Device>()
    private var binaryPath = ""
    private var subnet: NetworkScanner.Subnet? = null
    private var rootOk = false
    private lateinit var spoof: SpoofController
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        setSupportActionBar(binding.toolbar)

        adapter = DeviceListAdapter(
            this,
            devices,
            onCut = { d -> runAction { s -> spoof.cut(d, s.iface, s.gateway) } },
            onLag = { d -> runAction { s -> spoof.lag(d, s.iface, s.gateway, lagRate()) } },
            onRestore = { d -> runAction { s -> spoof.restore(d, s.iface, s.gateway) } }
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

        executor.execute {
            rootOk = RootShell.isRootAvailable()
            runOnUiThread {
                if (!rootOk) {
                    Toast.makeText(this, "Root tidak tersedia — fitur tidak dapat berjalan", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun runAction(block: (NetworkScanner.Subnet) -> Unit) {
        val s = subnet
        if (s == null) {
            toast("Lakukan scan dulu")
            return
        }
        if (!this::spoof.isInitialized) spoof = SpoofController(binaryPath)
        executor.execute {
            try {
                if (binaryPath.isEmpty()) binaryPath = prepareBinary()
                if (!this::spoof.isInitialized) spoof = SpoofController(binaryPath)
                block(s)
            } catch (e: Exception) {
                runOnUiThread { toast("Gagal: ${e.message}") }
            }
            runOnUiThread { afterAction() }
        }
    }

    private fun lagRate(): Double = binding.seekLag.progress / 100.0

    private fun afterAction() {
        adapter.notifyDataSetChanged()
        updateSummary()
    }

    private fun updateSummary() {
        val cut = devices.count { it.status == DeviceStatus.CUT }
        val lag = devices.count { it.status == DeviceStatus.LAG }
        val norm = devices.size - cut - lag
        binding.status.text = "Normal: $norm   Cut: $cut   Lag: $lag"
    }

    private fun doScan() {
        if (!rootOk) {
            toast("Root tidak tersedia")
            return
        }
        binding.progress.visibility = View.VISIBLE
        binding.btnScan.isEnabled = false
        executor.execute {
            try {
                if (binaryPath.isEmpty()) binaryPath = prepareBinary()
                if (!this::spoof.isInitialized) spoof = SpoofController(binaryPath)
                val sub = NetworkScanner.getWifiSubnet()
                if (sub == null) {
                    runOnUiThread { toast("Gagal membaca info jaringan WiFi") }
                    return@execute
                }
                subnet = sub
                NetworkScanner.pingSweep(sub)
                val found = NetworkScanner.scan(sub, binaryPath)
                NetworkScanner.resolveHostnames(found)
                runOnUiThread {
                    devices.clear()
                    devices.addAll(found)
                    adapter.notifyDataSetChanged()
                    binding.status.text = "${found.size} perangkat ditemukan (${sub.iface})"
                    updateSummary()
                }
            } catch (e: Exception) {
                runOnUiThread { toast("Scan gagal: ${e.message}") }
            } finally {
                runOnUiThread {
                    binding.progress.visibility = View.GONE
                    binding.btnScan.isEnabled = true
                }
            }
        }
    }

    private fun prepareBinary(): String {
        val src = File(applicationInfo.nativeLibraryDir, "libarp_spoof.so")
        val dst = File(filesDir, "arp_spoof")
        if (!dst.exists() || dst.length() != src.length()) {
            src.inputStream().use { fi -> dst.outputStream().use { fo -> fi.copyTo(fo) } }
        }
        RootShell.run("chmod", "0755", dst.absolutePath)
        return dst.absolutePath
    }

    private fun toast(msg: String) {
        runOnUiThread { Toast.makeText(this, msg, Toast.LENGTH_SHORT).show() }
    }

    override fun onDestroy() {
        if (this::spoof.isInitialized && subnet != null) {
            spoof.restoreAll(devices, subnet!!.iface, subnet!!.gateway)
        }
        executor.shutdown()
        super.onDestroy()
    }
}
