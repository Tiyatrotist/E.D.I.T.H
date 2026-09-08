"""
core/sip_bridge.py — E.D.I.T.H VoIP / SIP Santral Köprüsü ve Sesli Sekreter

Kullanıcının cep telefonu kapalıyken operatör yönlendirmesiyle (*62*) gelen
SIP çağrılarını doğrudan bilgisayarda veya Oracle VPS'te karşılar.

Teknoloji:
- pyVoIP (RFC 3261 SIP & RFC 3550 RTP)
- G.711 PCMU/PCMA Ses İletişimi
- CallHandler ile Whisper STT ➔ LLM ➔ TTS yanıt zinciri

Debug: Tüm SIP oturumları, arayan numaralar ve çağrı akışı loglanır.
"""

from __future__ import annotations

import audioop
import io
import json
import logging
import os
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from app_config import load_app_config
from core.call_handler import CallHandler

logger = logging.getLogger("EDITH.SIPBridge")


class SIPBridge:
    """E.D.I.T.H VoIP / SIP İstemcisi ve Otomatik Çağrı Karşılayıcı."""

    def __init__(
        self,
        server: Optional[str] = None,
        port: int = 5060,
        username: Optional[str] = None,
        password: Optional[str] = None,
        my_ip: Optional[str] = None,
        on_call_started_callback: Optional[Callable[[str, str], None]] = None,
        on_call_ended_callback: Optional[Callable[[str, str, str], None]] = None,
    ):
        cfg = load_app_config().get("sip", {})
        self.server = server or cfg.get("server", "sip.netgsm.com.tr")
        self.port = int(port or cfg.get("port", 5060))
        self.username = username or cfg.get("username", "")
        self.password = password or cfg.get("password", "")
        self.my_ip = my_ip or cfg.get("my_ip", "")
        self.enabled = bool(cfg.get("enabled", False))
        self.greeting = cfg.get(
            "greeting",
            "Merhaba, ben Buğra'nın yapay zeka asistanı EDITH. Telefonu şu anda kapalı. Size nasıl yardımcı olabilirim?",
        )

        self.on_call_started = on_call_started_callback
        self.on_call_ended = on_call_ended_callback

        self._phone: Any = None
        self._is_running = False
        self._active_calls: Dict[str, Any] = {}

    def log(self, message: str) -> None:
        """Konsola zaman damgalı debug logu yazar."""
        t_str = time.strftime("%H:%M:%S")
        print(f"[{t_str}] [SIPBridge] {message}")

    def is_configured(self) -> bool:
        """Kullanıcı adı ve şifre girilmiş mi kontrol eder."""
        return bool(self.server and self.username and self.password)

    def start(self) -> bool:
        """SIP santral dinleyicisini arka planda başlatır."""
        if not self.is_configured():
            self.log("⚠️ SIP yapılandırması eksik (Kullanıcı adı veya şifre boş). Dinleyici başlatılmadı.")
            return False

        if self._is_running:
            return True

        try:
            from pyVoIP.VoIP import VoIPPhone

            def _incoming_call_handler(call):
                self._handle_incoming_call(call)

            kwargs = {
                "server": self.server,
                "port": self.port,
                "username": self.username,
                "password": self.password,
                "callCallback": _incoming_call_handler,
            }
            if self.my_ip:
                kwargs["myIP"] = self.my_ip

            self._phone = VoIPPhone(**kwargs)
            self._phone.start()
            self._is_running = True
            self.log(f"🟢 SIP Santrali Devrede: {self.username}@{self.server}:{self.port}")
            return True
        except Exception as e:
            self.log(f"❌ SIP başlatma hatası: {e}")
            self._is_running = False
            return False

    def stop(self) -> None:
        """SIP sunucu dinleyicisini durdurur."""
        if self._phone and self._is_running:
            try:
                self._phone.stop()
                self.log("🛑 SIP Santrali durduruldu.")
            except Exception as e:
                self.log(f"Durdurma uyarısı: {e}")
            finally:
                self._is_running = False
                self._phone = None

    def _extract_caller_info(self, call: Any) -> tuple[str, str]:
        """SIP paketinden arayan numara ve ismi ayıklar."""
        caller_name = "Bilinmeyen Numara"
        caller_number = ""

        try:
            # pyVoIP çağrı başlıklarını incele
            req = getattr(call, "request", None)
            if req and hasattr(req, "headers"):
                from_hdr = req.headers.get("From", "")
                if from_hdr:
                    # Format: "Ad Soyad" <sip:0532XXXXXXX@domain>
                    parts = from_hdr.split("<")
                    if len(parts) > 1:
                        name_part = parts[0].strip().replace('"', '')
                        uri_part = parts[1].split(">")[0]
                        num_part = uri_part.split("@")[0].replace("sip:", "")
                        caller_name = name_part or num_part or "Arayan"
                        caller_number = num_part
                    else:
                        caller_number = from_hdr.split("@")[0].replace("sip:", "")
                        caller_name = caller_number
        except Exception:
            pass

        return caller_name, caller_number

    def _handle_incoming_call(self, call: Any) -> None:
        """Gelen SIP aramasını iş parçacığında karşılar."""
        caller_name, caller_number = self._extract_caller_info(call)
        call_id = f"sip_{caller_number}_{int(time.time())}"

        self.log(f"📞 [GELEN SIP ÇAĞRISI]: {caller_name} ({caller_number})")

        # Masaüstü bildirim callback'i tetikle
        if self.on_call_started:
            try:
                self.on_call_started(caller_name, caller_number)
            except Exception as e:
                self.log(f"Arama başlangıç callback hatası: {e}")

        # Görüşmeyi arka plan thread'inde yürüt
        t = threading.Thread(
            target=self._run_call_session,
            args=(call, call_id, caller_name, caller_number),
            daemon=True,
        )
        t.start()

    def _run_call_session(self, call: Any, call_id: str, caller_name: str, caller_number: str) -> None:
        """Görüşme oturumu yaşam döngüsü."""
        handler = CallHandler(caller_name, caller_number)
        start_time = time.time()

        try:
            # 1. Aramayı Cevapla
            time.sleep(0.5)
            call.answer()
            self.log(f"✅ SIP Çağrısı cevaplandı. EDITH karşılama konuşması yapıyor...")

            # 2. Karşılama Anonsunu Oynat
            self._play_tts_to_call(call, self.greeting)

            # 3. Ses Al-Cevapla Döngüsü (Maksimum 3 tur veya kullanıcı kapatana kadar)
            turns = 0
            while call.state == getattr(call, "State", None).ANSWERED if hasattr(call, "State") else True:
                if time.time() - start_time > 180 or turns >= 4:
                    # 3 dakika güvenlik zaman aşımı
                    break

                # Arayanın konuşmasını dinle
                audio_bytes = self._record_from_call(call, record_seconds=6)
                if not audio_bytes or len(audio_bytes) < 4000:
                    break

                # STT ile metne dönüştür
                caller_text = self._transcribe_audio(audio_bytes)
                if not caller_text:
                    continue

                self.log(f"🗣️ Arayan ({caller_name}): '{caller_text}'")
                turns += 1

                # LLM ile sekreter yanıtı üret
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                reply = loop.run_until_complete(handler.generate_reply(caller_text))
                loop.close()

                # Yanıtı SIP hattına seslendir
                self._play_tts_to_call(call, reply)

        except Exception as e:
            self.log(f"Görüşme oturumu hatası: {e}")
        finally:
            # Çağrıyı sonlandır
            try:
                call.hangup()
            except Exception:
                pass

            duration = int(time.time() - start_time)
            self.log(f"📴 SIP Çağrısı bitti. Süre: {duration} sn")

            # Özeti hazırla ve kaydet
            self._finish_and_record_call(handler, caller_name, caller_number, duration)

    def _record_from_call(self, call: Any, record_seconds: float = 5.0) -> bytes:
        """SIP RTP kanalından ses verisi okur (8000 Hz, 8-bit PCMU)."""
        buffer = bytearray()
        chunk_size = 160  # 20ms @ 8kHz
        end_time = time.time() + record_seconds

        while time.time() < end_time:
            try:
                data = call.read_audio(chunk_size, blocking=False)
                if data:
                    buffer.extend(data)
                else:
                    time.sleep(0.02)
            except Exception:
                break

        return bytes(buffer)

    def _play_tts_to_call(self, call: Any, text: str) -> None:
        """TTS çıktısını SIP G.711 PCMU formatına dönüştürüp RTP kanalına yazar."""
        if not text:
            return

        try:
            from actions.tts import synthesize_to_wav_bytes
            wav_data = synthesize_to_wav_bytes(text)
            if not wav_data:
                return

            # WAV (16kHz/22kHz PCM) -> 8000 Hz 8-bit PCMU dönüşümü
            with wave.open(io.BytesIO(wav_data), "rb") as wf:
                in_rate = wf.getframerate()
                in_nchannels = wf.getnchannels()
                in_width = wf.getsampwidth()
                raw_pcm = wf.readframes(wf.getnframes())

            # Mono yap
            if in_nchannels == 2:
                raw_pcm = audioop.tomono(raw_pcm, in_width, 1, 1)

            # 8000 Hz örneklem oranına düşür
            if in_rate != 8000:
                raw_pcm, _ = audioop.ratecv(raw_pcm, in_width, 1, in_rate, 8000, None)

            # Linear PCM'den u-law (PCMU)'a çevir
            ulaw_bytes = audioop.lin2ulaw(raw_pcm, in_width)

            # 20ms'lik paketlerle (160 byte) SIP'e yaz
            chunk_size = 160
            for i in range(0, len(ulaw_bytes), chunk_size):
                chunk = ulaw_bytes[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = chunk + b"\xff" * (chunk_size - len(chunk))  # sessizlik dolgusu
                call.write_audio(chunk)
                time.sleep(0.019)  # 20ms ritmi koru

        except Exception as e:
            self.log(f"SIP TTS çalma uyarısı: {e}")

    def _transcribe_audio(self, ulaw_audio: bytes) -> str:
        """G.711 PCMU sesi 16kHz PCM'e çevirip Whisper STT'ye verir."""
        try:
            # u-law -> 16-bit Linear PCM (8kHz)
            pcm_8k = audioop.ulaw2lin(ulaw_audio, 2)
            # 8kHz -> 16kHz (Whisper için ideal oran)
            pcm_16k, _ = audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)

            # WAV belleğe yaz
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_16k)
            wav_bytes = wav_io.getvalue()

            # Yerel Whisper ile çözümle
            from actions.stt import transcribe_audio_bytes
            return transcribe_audio_bytes(wav_bytes) or ""
        except Exception as e:
            self.log(f"Transkripsiyon hatası: {e}")
            return ""

    def _finish_and_record_call(self, handler: CallHandler, caller_name: str, caller_number: str, duration: int) -> None:
        """Görüşmeyi özetler, hafızaya kaydeder ve masaüstü/Discord bildirimlerini tetikler."""
        summary = ""
        if len(handler.history) > 1:
            try:
                transcript_text = "\n".join([f"{m['role']}: {m['content']}" for m in handler.history])
                from local_llm import LocalLLMClient
                import asyncio
                client = LocalLLMClient()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                summary = loop.run_until_complete(client.generate_response(
                    prompt=f"Aşağıdaki telefon konuşmasını 1 cümlede özetle ve arayanın bıraktığı notu yaz:\n{transcript_text}",
                    system_instruction="Sen bir sekretersin. Sadece arayanın bıraktığı mesajı veya notu 1 kısa Türkçe cümleyle yaz.",
                    max_tokens=80,
                ))
                loop.close()
            except Exception:
                summary = f"{len(handler.history)} mesajlık görüşme yapıldı."
        else:
            summary = "Arayan mesaj bırakmadan kapattı."

        clean_summary = summary.strip()

        # 1. Çağrı loglarına yaz
        try:
            from dashboard.server import save_call_log
            save_call_log(caller_name, caller_number, handler.history, summary=clean_summary)
        except Exception as e:
            self.log(f"Log kaydetme hatası: {e}")

        # 2. Ortak sohbet geçmişine ekle
        try:
            from core.chat_history import get_chat_history
            get_chat_history().add_message(
                role="phone_call",
                content=f"Arayan (SIP Santral): {caller_name}. Bıraktığı Not: {clean_summary}",
                source="sip_secretary",
                metadata={"caller_name": caller_name, "caller_number": caller_number, "summary": clean_summary},
            )
        except Exception:
            pass

        # 3. Discord Zengin Bildirimi Gönder
        try:
            from discord_bot.bot import send_discord_alert
            send_discord_alert(
                title="📞 SIP Santral Çağrısı Tamamlandı",
                description=f"**Not:** {clean_summary}",
                caller_name=f"{caller_name} ({caller_number})",
            )
        except Exception:
            pass

        # 4. Masaüstü Bildirimini Tetikle
        if self.on_call_ended:
            try:
                self.on_call_ended(caller_name, caller_number, clean_summary)
            except Exception as e:
                self.log(f"Çağrı sonu callback hatası: {e}")


_global_sip_bridge: Optional[SIPBridge] = None


def get_sip_bridge() -> SIPBridge:
    """Tekil (Singleton) SIP Santral örneğini döndürür."""
    global _global_sip_bridge
    if _global_sip_bridge is None:
        _global_sip_bridge = SIPBridge()
    return _global_sip_bridge
