package com.ifauze.zeecut.ui

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.TextView
import com.ifauze.zeecut.R
import com.ifauze.zeecut.model.Device

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

        val info = v.findViewById<TextView>(R.id.tvInfo)
        info.text = "${d.ip}\n${d.mac}\n${statusLabel(d)}"

        v.findViewById<Button>(R.id.btnCut).setOnClickListener { onCut(d) }
        v.findViewById<Button>(R.id.btnLag).setOnClickListener { onLag(d) }
        v.findViewById<Button>(R.id.btnRestore).setOnClickListener { onRestore(d) }
        return v
    }

    private fun statusLabel(d: Device): String = when (d.status) {
        com.ifauze.zeecut.model.DeviceStatus.NORMAL -> "Normal"
        com.ifauze.zeecut.model.DeviceStatus.CUT -> "CUT (diblokir)"
        com.ifauze.zeecut.model.DeviceStatus.LAG -> "LAG (lemot)"
    }
}
