package com.ifauze.zeecut.net

import java.io.BufferedReader
import java.io.InputStreamReader

object RootShell {

    private const val TIMEOUT_MS = 15000

    fun isRootAvailable(): Boolean {
        return try {
            val out = run("id")
            out.contains("uid=0")
        } catch (e: Exception) {
            false
        }
    }

    fun run(vararg cmd: String): String {
        val full = cmd.joinToString(" ")
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", full))
            val sb = StringBuilder()
            val reader = Thread {
                try {
                    BufferedReader(InputStreamReader(p.inputStream)).forEachLine { sb.appendLine(it) }
                    BufferedReader(InputStreamReader(p.errorStream)).forEachLine { sb.appendLine(it) }
                } catch (_: Exception) {
                }
            }
            reader.start()
            val waiter = Thread {
                try {
                    p.waitFor()
                } catch (_: Exception) {
                }
            }
            waiter.start()
            waiter.join(TIMEOUT_MS.toLong())
            if (waiter.isAlive) {
                p.destroyForcibly()
                waiter.interrupt()
                sb.appendLine("TIMEOUT")
            }
            reader.join(500)
            sb.toString()
        } catch (e: Exception) {
            e.message ?: "exec failed"
        }
    }
}
