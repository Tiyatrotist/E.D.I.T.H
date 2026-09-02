"""
discord_bot/voice_engine.py — Discord Ses Kanalı (Voice Channel) Motoru

Discord sesli odalarına katılma, kullanıcıları dinleme ve Edge-TTS
ile üretilen doğal sesi FFmpeg üzerinden kanala oynatma işlemlerini yürütür.

Debug: Ses kanalı bağlantıları ve ses çalma işlemleri loglanır.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import discord
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False


class DiscordVoiceEngine:
    """Discord ses kanalı işlemlerini yöneten motor."""

    def __init__(self, bot_client):
        self.bot = bot_client
        self.voice_client: Optional[discord.VoiceClient] = None
        self._is_speaking = False

    async def join_channel(self, channel: discord.VoiceChannel) -> bool:
        """Ses kanalına katılır."""
        try:
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.move_to(channel)
            else:
                self.voice_client = await channel.connect()
            print(f"[DiscordVoice] 🎙️ Ses kanalına bağlanıldı: {channel.name}")
            return True
        except Exception as e:
            print(f"[DiscordVoice] ❌ Kanala bağlanılamadı: {e}")
            return False

    async def leave_channel(self) -> None:
        """Ses kanalından ayrılır."""
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
            self.voice_client = None
            print("[DiscordVoice] 📴 Ses kanalından ayrılındı.")

    async def speak_text(self, text: str, language: str = "tr") -> None:
        """Metni Piper TTS kadın sesi ile sentezleyip Discord ses kanalında oynatır."""
        if not self.voice_client or not self.voice_client.is_connected():
            print("[DiscordVoice] ⚠️ Bot herhangi bir ses kanalında değil.")
            return

        try:
            temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_path = temp_wav.name
            temp_wav.close()

            # 1. Öncelik: Piper Neural TTS (Kadın Sesi)
            synthesized = False
            try:
                from actions.piper_tts import synthesize_to_wav
                synthesized = synthesize_to_wav(text, temp_path, language=language)
            except Exception as e:
                print(f"[DiscordVoice] ⚠️ Piper sentezleme hatası: {e}")

            # Fallback: Edge-TTS
            if not synthesized:
                try:
                    import edge_tts
                    temp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    temp_path = temp_mp3.name
                    temp_mp3.close()
                    communicate = edge_tts.Communicate(text, "tr-TR-EmelNeural")
                    await communicate.save(temp_path)
                except Exception as ex:
                    print(f"[DiscordVoice] ❌ TTS motorları başarısız: {ex}")
                    return

            # Sesi Discord'da oynat
            source = discord.FFmpegPCMAudio(temp_path)
            self._is_speaking = True

            def _after_play(error):
                self._is_speaking = False
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
                if error:
                    print(f"[DiscordVoice] ⚠️ Oynatma hatası: {error}")

            self.voice_client.play(source, after=_after_play)
            print(f"[DiscordVoice] 🗣️ Piper kadın sesiyle ses kanalında konuşuluyor: '{text[:30]}...'")

        except Exception as e:
            print(f"[DiscordVoice] ❌ TTS çalma hatası: {e}")
