package com.stark.edith.edith_app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telecom.TelecomManager
import android.telephony.TelephonyManager
import android.util.Log

/**
 * EdithCallReceiver — Gelen GSM telefon aramalarını dinleyen ve
 * EDITH Sekreter motoruna yönlendiren Android yerel alıcısı.
 */
class EdithCallReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "EdithCallReceiver"
        var listener: ((event: String, number: String) -> Unit)? = null
        var autoAnswerEnabled: Boolean = true

        fun answerRingingCall(context: Context): Boolean {
            return try {
                val telecomManager = context.getSystemService(Context.TELECOM_SERVICE) as? TelecomManager
                if (telecomManager != null) {
                    telecomManager.acceptRingingCall()
                    Log.i(TAG, "📞 [Native Kotlin] Arama kabul edildi (acceptRingingCall).")
                    true
                } else {
                    false
                }
            } catch (e: SecurityException) {
                Log.e(TAG, "⚠️ Arama cevaplama izni eksik: ${e.message}")
                false
            } catch (e: Exception) {
                Log.e(TAG, "⚠️ Arama cevaplanırken hata: ${e.message}")
                false
            }
        }
    }

    override fun onReceive(context: Context?, intent: Intent?) {
        if (context == null || intent == null) return

        if (intent.action == TelephonyManager.ACTION_PHONE_STATE_CHANGED) {
            val stateStr = intent.getStringExtra(TelephonyManager.EXTRA_STATE)
            val number = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER) ?: "Bilinmeyen"

            Log.d(TAG, "🔔 Telefon Durum Değişikliği: $stateStr (Numara: $number)")

            when (stateStr) {
                TelephonyManager.EXTRA_STATE_RINGING -> {
                    Log.i(TAG, "📞 Çalıyor: $number")
                    listener?.invoke("RINGING", number)

                    if (autoAnswerEnabled) {
                        Log.i(TAG, "🤖 Otomatik karşılama tetikleniyor...")
                        // Kısa bir beklemeden sonra aramayı cevapla
                        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                            answerRingingCall(context)
                        }, 1200)
                    }
                }
                TelephonyManager.EXTRA_STATE_OFFHOOK -> {
                    Log.i(TAG, "📞 Arama açıldı / Konuşma aktif.")
                    listener?.invoke("OFFHOOK", number)
                }
                TelephonyManager.EXTRA_STATE_IDLE -> {
                    Log.i(TAG, "📴 Arama kapandı / Boşta.")
                    listener?.invoke("IDLE", number)
                }
            }
        }
    }
}
