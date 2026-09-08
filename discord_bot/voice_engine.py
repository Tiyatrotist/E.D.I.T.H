"""
discord_bot/voice_engine.py — Discord Ses Kanalı (Voice Channel) Holografik Akustik Motoru

Discord sesli odalarına katılma, kullanıcıları dinleme, Edge-TTS (tr-TR-EmelNeural) /
Piper Neural ile üretilen doğal sesi holografik akustik filtrelerle (Warmth EQ + Spatial Reverb)
işleyip FFmpeg üzerinden kristal berraklığında oynatma işlemlerini yürütür.

Debug: Ses kanalı bağlantıları, filtreleme ve ses çalma işlemleri zaman damgasıyla loglanır.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import discord
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False

from app_config import load_app_config
from core.audio_processor import process_voice_audio


class DiscordVoiceEngine:
    """Discord ses kanalı işlemlerini ve holografik ses sentezini yöneten motor."""

    def __init__(self, bot_client):
        self.bot = bot_client
        self.voice_client: Optional[discord.VoiceClient] = None
        self._is_speaking = False

    @property
    def is_connected(self) -> bool:
        """Botun bir ses kanalına bağlı olup olmadığını döner."""
        return bool(self.voice_client and self.voice_client.is_connected())

    @property
    def is_speaking(self) -> bool:
        """Ses kanalında şu anda konuşulup konuşulmadığını döner."""
        return bool(self._is_speaking and self.voice_client and self.voice_client.is_playing())

    def get_voice_status(self) -> Dict[str, Any]:
        """Ses motorunun anlık telemetri durumunu sözlük olarak döner."""
        ch_name = None
        guild_name = None
        if self.voice_client and self.voice_client.channel:
            ch_name = self.voice_client.channel.name
            guild_name = self.voice_client.channel.guild.name
        
        cfg = load_app_config()
        return {
            "connected": self.is_connected,
            "speaking": self.is_speaking,
            "channel_name": ch_name,
            "guild_name": guild_name,
            "primary_voice": cfg.get("voice_primary", "tr-TR-EmelNeural"),
            "effects_enabled": cfg.get("voice_effects_enabled", True),
            "warmth": cfg.get("voice_warmth", 0.45),
            "spatial": cfg.get("voice_spatial", 0.12),
        }

    async def join_channel(self, channel: discord.VoiceChannel) -> bool:
        """Ses kanalına katılır veya mevcutsa kanalı taşır."""
        try:
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()
            print(f"[DiscordVoice] 🎙️ Ses kanalına bağlanıldı: {channel.name} ({channel.guild.name})")
            return True
        except Exception as e:
            print(f"[DiscordVoice] ❌ Kanala bağlanılamadı: {e}")
            return False

    async def leave_channel(self) -> None:
        """Ses kanalından ayrılır ve istemciyi temizler."""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
            self._is_speaking = False
            print("[DiscordVoice] 📴 Ses kanalından ayrılındı.")

    def stop_speaking(self) -> None:
        """Ses çalmayı anında durdurur."""
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.stop()
            self._is_speaking = False
            print("[DiscordVoice] ⏹️ Ses çalma durduruldu.")

    async def synthesize_speech_wav(
        self,
        text: str,
        output_wav_path: str,
        language: str = "tr",
        apply_holographic: bool = True,
    ) -> bool:
        """
        Metni Edge-TTS (tr-TR-EmelNeural) veya Piper ile sentezler,
        ardından Stark holografik akustik filtrelerini uygular.
        """
        t0 = time.time()
        cfg = load_app_config()
        voice = cfg.get("voice_primary", "tr-TR-EmelNeural")
        rate = cfg.get("voice_rate", "-3%")
        pitch = cfg.get("voice_pitch", "+2Hz")
        warmth = float(cfg.get("voice_warmth", 0.45))
        spatial = float(cfg.get("voice_spatial", 0.12))

        # 1. Aşama: core.voice_engine üzerinden merkezi sentezleme denemesi
        try:
            from core.voice_engine import get_voice_engine
            ve = get_voice_engine()
            success = ve.synthesize_to_file(
                text=text,
                output_path=output_wav_path,
                language=language,
                apply_effects=apply_holographic,
                voice=voice,
                rate=rate,
                pitch=pitch,
                warmth=warmth,
                spatial=spatial,
            )
            if success and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 100:
                print(f"[DiscordVoice] ⚡ Holografik sentez başarılı ({time.time() - t0:.2f}s)")
                return True
        except Exception as ex:
            print(f"[DiscordVoice] ℹ️ Merkezi VoiceEngine fallback: {ex}")

        # 2. Aşama: Bağımsız Edge-TTS ve Piper Fallback Zinciri
        temp_raw_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_raw_path = f.name

            edge_ok = False
            try:
                import edge_tts
                comm = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
                await comm.save(temp_raw_path)
                edge_ok = os.path.exists(temp_raw_path) and os.path.getsize(temp_raw_path) > 100
            except Exception as e:
                print(f"[DiscordVoice] ⚠️ Edge-TTS hatası: {e}")

            if not edge_ok:
                # Piper TTS yerel fallback
                try:
                    from actions.piper_tts import synthesize_to_wav
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        temp_piper = f.name
                    if synthesize_to_wav(text, temp_piper, language=language):
                        if os.path.exists(temp_raw_path):
                            os.unlink(temp_raw_path)
                        temp_raw_path = temp_piper
                except Exception as ex:
                    print(f"[DiscordVoice] ❌ Piper fallback hatası: {ex}")
                    return False

            # Holografik akustik filtreleme
            if apply_holographic and os.path.exists(temp_raw_path):
                # MP3 ise WAV'a dönüştür veya doğrudan işle
                try:
                    process_voice_audio(
                        temp_raw_path,
                        output_wav_path,
                        warmth=warmth,
                        spatial_reverb=spatial,
                    )
                except Exception as ef:
                    print(f"[DiscordVoice] ⚠️ Akustik filtre hatası: {ef}, ham dosya kopyalanıyor.")
                    import shutil
                    shutil.copy2(temp_raw_path, output_wav_path)
            else:
                import shutil
                shutil.copy2(temp_raw_path, output_wav_path)

            return os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 100
        finally:
            if temp_raw_path and os.path.exists(temp_raw_path):
                try:
                    os.unlink(temp_raw_path)
                except Exception:
                    pass

    async def speak_text(self, text: str, language: str = "tr", apply_holographic: bool = True) -> bool:
        """
        Metni holografik kadın sesiyle sentezleyip bağlı olunan Discord ses kanalında çalar.
        """
        if not self.voice_client or not self.voice_client.is_connected():
            print("[DiscordVoice] ⚠️ Bot herhangi bir ses kanalında değil.")
            return False

        if not text or not text.strip():
            return False

        temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_wav.name
        temp_wav.close()

        try:
            ok = await self.synthesize_speech_wav(
                text=text.strip(),
                output_wav_path=temp_path,
                language=language,
                apply_holographic=apply_holographic,
            )
            if not ok:
                print("[DiscordVoice] ❌ Ses sentezi başarısız.")
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                return False

            if not HAS_DISCORD:
                print("[DiscordVoice] ℹ️ discord.py kurulu değil (mock/test ortamı).")
                return True

            source = discord.FFmpegPCMAudio(temp_path)
            self._is_speaking = True

            def _after_play(error):
                self._is_speaking = False
                try:
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
                except Exception:
                    pass
                if error:
                    print(f"[DiscordVoice] ⚠️ Oynatma hatası: {error}")

            self.voice_client.play(source, after=_after_play)
            print(f"[DiscordVoice] 🗣️ Holografik kadın sesiyle ses kanalında konuşuluyor: '{text[:40]}...'")
            return True

        except Exception as e:
            print(f"[DiscordVoice] ❌ TTS çalma hatası: {e}")
            try:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
            except Exception:
                pass
            return False

    async def play_sound_effect(self, sound_type: str = "chime") -> bool:
        """
        Discord ses odasında taktiksel Stark ses efekti çalar.
        """
        if not self.voice_client or not self.voice_client.is_connected():
            return False

        # Ses efekt dosyasını tespit et veya sentezle
        sound_dir = Path(__file__).resolve().parent.parent / "sounds"
        target_file = None
        if sound_dir.exists():
            for f in sound_dir.glob("*.wav"):
                if sound_type.lower() in f.stem.lower():
                    target_file = str(f)
                    break
            if not target_file and list(sound_dir.glob("*.wav")):
                target_file = str(list(sound_dir.glob("*.wav"))[0])

        if not target_file:
            print(f"[DiscordVoice] ℹ️ '{sound_type}' ses efekti dosyası bulunamadı.")
            return False

        if not HAS_DISCORD:
            return True

        try:
            source = discord.FFmpegPCMAudio(target_file)
            self.voice_client.play(source)
            print(f"[DiscordVoice] 🔔 Ses efekti çalındı: {Path(target_file).name}")
            return True
        except Exception as e:
            print(f"[DiscordVoice] ⚠️ Efekt çalma hatası: {e}")
            return False
