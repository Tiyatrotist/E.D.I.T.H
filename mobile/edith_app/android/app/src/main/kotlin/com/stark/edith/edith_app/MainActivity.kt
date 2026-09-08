package com.stark.edith.edith_app

import android.os.Bundle
import android.util.Log
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * MainActivity — Flutter ile Android Yerel Telefon API'leri arasında köprü kurar.
 */
class MainActivity : FlutterActivity() {

    private val CHANNEL = "com.stark.edith/telephony"
    private var methodChannel: MethodChannel? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        methodChannel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        methodChannel?.setMethodCallHandler { call, result ->
            when (call.method) {
                "setAutoAnswer" -> {
                    val enabled = call.argument<Boolean>("enabled") ?: true
                    EdithCallReceiver.autoAnswerEnabled = enabled
                    Log.i("MainActivity", "⚙️ Otomatik cevaplama: $enabled")
                    result.success(true)
                }
                "answerCall" -> {
                    val ok = EdithCallReceiver.answerRingingCall(this)
                    result.success(ok)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }

        // Gelen arama olaylarını Flutter'a ilet
        EdithCallReceiver.listener = { event, number ->
            runOnUiThread {
                val data = mapOf("event" to event, "number" to number)
                methodChannel?.invokeMethod("onCallEvent", data)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        EdithCallReceiver.listener = null
    }
}
