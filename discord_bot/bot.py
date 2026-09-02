"""
discord_bot/bot.py — EDITH Discord Bot Ana Servisi

Yapay zeka olduğu anlaşılmayacak kadar doğal metin sohbeti, sesli kanal
desteği ve uzaktan PC yönetim komutlarını birleştiren ana Discord botu.

Debug: Bot olayları ve mesaj trafiği loglanır.
"""

from __future__ import annotations

import asyncio
import io
import threading
from typing import Optional

try:
    import discord
    from discord.ext import commands
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False

from app_config import load_app_config
from discord_bot.command_router import handle_system_command
from discord_bot.personality import calculate_typing_delay
from discord_bot.text_engine import DiscordTextEngine
from discord_bot.voice_engine import DiscordVoiceEngine


class EdithDiscordBot:
    """EDITH Discord İstemcisi."""

    def __init__(self, token: str):
        self.token = token
        self.cfg = load_app_config().get("discord", {})
        self.text_engine = DiscordTextEngine()

        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        self.bot = commands.Bot(command_prefix="/", intents=intents)
        self.voice_engine = DiscordVoiceEngine(self.bot)
        self._setup_events()

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"[DiscordBot] 🤖 Bot hazır ve giriş yaptı: {self.bot.user} (ID: {self.bot.user.id})")
            await self.bot.change_presence(activity=discord.Game(name="EDITH // Online"))

        @self.bot.event
        async def on_message(message: discord.Message):
            # Kendi mesajlarına cevap verme
            if message.author == self.bot.user:
                return

            content = message.content.strip()

            # 1. SLASH / PREFIX KOMUT KONTROLÜ
            if content.startswith("/"):
                parts = content[1:].split(" ", 1)
                cmd = parts[0]
                args = parts[1] if len(parts) > 1 else ""

                if cmd == "join":
                    if message.author.voice and message.author.voice.channel:
                        await self.voice_engine.join_channel(message.author.voice.channel)
                        await message.channel.send("Geldim sesli kanala! 👀")
                    else:
                        await message.channel.send("Önce bir sesli kanala girmelisin.")
                    return

                if cmd == "leave":
                    await self.voice_engine.leave_channel()
                    await message.channel.send("Sesli kanaldan çıktım.")
                    return

                if cmd == "speak":
                    if args:
                        await self.voice_engine.speak_text(args)
                        await message.channel.send("🗣️ Söylüyorum...")
                    return

                # Sistem komutları
                reply_text, file_bytes = handle_system_command(cmd, args)
                if file_bytes:
                    discord_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                    await message.channel.send(content=reply_text, file=discord_file)
                else:
                    await message.channel.send(reply_text)
                return

            # 2. DOĞAL DİL SOHBETİ (DM veya bot mention veya genel mesaj)
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = self.bot.user in message.mentions

            # Eğer DM ise veya mention edildiyse cevap ver
            if is_dm or is_mentioned or self.cfg.get("respond_to_all", True):
                # Görsel ek var mı kontrol et
                image_bytes = None
                if message.attachments:
                    for att in message.attachments:
                        if any(att.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                            image_bytes = await att.read()
                            break

                # Typing (yazıyor...) simülasyonu
                async with message.channel.typing():
                    chunks = await self.text_engine.generate_response(
                        channel_id=message.channel.id,
                        user_message=content,
                        author_name=message.author.display_name,
                        image_bytes=image_bytes,
                        personality=self.cfg.get("personality", "casual"),
                    )

                    for chunk in chunks:
                        delay = calculate_typing_delay(chunk)
                        await asyncio.sleep(delay)
                        await message.channel.send(chunk)

    def run(self):
        """Botu başlatır."""
        if not self.token:
            print("[DiscordBot] ⚠️ Bot tokeni belirtilmedi.")
            return
        self.bot.run(self.token)


def start_discord_bot_background(token: str = "") -> None:
    """Discord botunu arka plan thread'inde başlatır."""
    if not HAS_DISCORD:
        print("[DiscordBot] ❌ discord.py kurulu değil. 'pip install discord.py' ile kurun.")
        return

    cfg = load_app_config().get("discord", {})
    bot_token = token or cfg.get("bot_token", "")

    if not bot_token:
        print("[DiscordBot] ℹ️ Discord bot tokeni yapılandırılmamış, bot başlatılmıyor.")
        return

    def _run():
        print("[DiscordBot] 🚀 Discord Bot başlatılıyor...")
        try:
            bot_instance = EdithDiscordBot(bot_token)
            bot_instance.run()
        except Exception as e:
            print(f"[DiscordBot] ❌ Bot çalışma hatası: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
