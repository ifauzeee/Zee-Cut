package com.ifauze.zeecut.net

import java.io.BufferedReader
import java.io.InputStreamReader

object RootShell {

    fun isRootAvailable(): Boolean {
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val out = BufferedReader(InputStreamReader(p.inputStream)).readLine() ?: ""
            p.waitFor()
            out.contains("uid=0") || out.contains("0(uid")
        } catch (e: Exception) {
            false
        }
    }

    fun run(vararg cmd: String): String {
        val full = cmd.joinToString(" ")
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", full))
            val sb = StringBuilder()
            BufferedReader(InputStreamReader(p.inputStream)).forEachLine { sb.appendLine(it) }
            BufferedReader(InputStreamReader(p.errorStream)).forEachLine { sb.appendLine(it) }
            p.waitFor()
            sb.toString()
        } catch (e: Exception) {
            e.message ?: "exec failed"
        }
    }
}
