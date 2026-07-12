package com.ifauze.zeecut.ui

import android.content.Context
import android.content.res.ColorStateList
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.ifauze.zeecut.R
import com.ifauze.zeecut.model.Device
import com.ifauze.zeecut.model.DeviceStatus

class DeviceListAdapter(
    private val ctx: Context,
    private val items: List<Device>,
    private val onCut: (Device) -> Unit,
    private val onLag: (Device) -> Unit,
    private val onRestore: (Device) -> Unit
) : BaseAdapter() {

    override fun getCount(): Int = items.size
    override fun getItem(i: Int): Device = items[i]
    override fun getItemId(i: Int): Long = i.toLong()

    override fun getView(i: Int, convertView: View?, parent: ViewGroup?): View {
        val v = convertView ?: LayoutInflater.from(ctx).inflate(R.layout.device_row, parent, false)
        val d = items[i]

        val ip = v.findViewById<TextView>(R.id.tvIp)
        val mac = v.findViewById<TextView>(R.id.tvMac)
        val status = v.findViewById<TextView>(R.id.tvStatus)
        val host = if (d.hostname.isNotEmpty()) " (${d.hostname})" else ""
        ip.text = "${d.ip}$host"
        mac.text = d.mac

        val (colorRes, label) = when (d.status) {
            DeviceStatus.NORMAL -> R.color.ok to "NORMAL"
            DeviceStatus.CUT -> R.color.danger to "CUT"
            DeviceStatus.LAG -> R.color.warn to "LAG"
        }
        val color = ContextCompat.getColor(ctx, colorRes)
        status.text = label
        status.setTextColor(ContextCompat.getColor(ctx, android.R.color.black))
        status.background = ContextCompat.getDrawable(ctx, R.drawable.bg_chip)
        status.backgroundTintList = ColorStateList.valueOf(color)

        v.findViewById<Button>(R.id.btnCut).setOnClickListener { onCut(d) }
        v.findViewById<Button>(R.id.btnLag).setOnClickListener { onLag(d) }
        v.findViewById<Button>(R.id.btnRestore).setOnClickListener { onRestore(d) }
        return v
    }
}
