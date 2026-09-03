"""
discord_bot/bot.py — EDITH Discord Bot Ana Servisi

Özellikler:
1. Gerçek Discord Slash Komutları (/join, /leave, /speak, /nizami, /status, /search, /screen)
   ve tree.sync() ile Discord arayüzüne anında entegrasyon.
2. Dinamik Mod Değişimi:
   - Normal Mod (Varsayılan): Samimi, zeki, doğal insan; sürekli 'efendim' çekmez.
   - Nizami Mod: "nizami ol" dendiğinde askeri disiplin ve taktiksel Stark protokolüne geçer.
   - "rahatla" dendiğinde tekrar normal samimi moda döner.
3. Hem Slash komutları hem metin komutları hem doğal dil algılama.
"""

from __future__ import annotations

import asyncio
import io
import threading
from typing import Optional

try:
    import discord
    from discord import app_commands
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

    def __init__(self, token: str, privileged_intents: bool = True):
        self.token = token
        self.cfg = load_app_config().get("discord", {})
        self.text_engine = DiscordTextEngine()
        self.channel_modes: dict[int, str] = {}  # channel_id -> "natural" veya "nizami"

        intents = discord.Intents.default()
        if privileged_intents:
            intents.message_content = True
        intents.voice_states = True

        self.bot = commands.Bot(command_prefix=["/", "!"], intents=intents)
        self.voice_engine = DiscordVoiceEngine(self.bot)
        self._setup_slash_commands()
        self._setup_events()

    def _setup_slash_commands(self):
        """Discord yerel Slash (/) komutlarını tanımlar."""
        tree = self.bot.tree

        @tree.command(name="join", description="Sesli odaya katılır")
        async def slash_join(interaction: discord.Interaction):
            if interaction.user and isinstance(interaction.user, discord.Member) and interaction.user.voice:
                await self.voice_engine.join_channel(interaction.user.voice.channel)
                await interaction.response.send_message("🎙️ Sesli kanala katıldım.")
            else:
                await interaction.response.send_message("Önce bir sesli kanala girmelisin.", ephemeral=True)

        @tree.command(name="leave", description="Sesli odadan ayrılır")
        async def slash_leave(interaction: discord.Interaction):
            await self.voice_engine.leave_channel()
            await interaction.response.send_message("📴 Sesli odadan ayrıldım.")

        @tree.command(name="speak", description="Piper kadın sesiyle kanalda konuşur")
        @app_commands.describe(metin="Seslendirilecek cümle")
        async def slash_speak(interaction: discord.Interaction, metin: str):
            await interaction.response.defer()
            await self.voice_engine.speak_text(metin)
            await interaction.followup.send(f"🗣️ Seslendirildi: *{metin[:100]}*")

        @tree.command(name="nizami", description="Nizami askeri disiplin modunu açar veya kapatır")
        @app_commands.describe(mod="aç veya kapat")
        async def slash_nizami(interaction: discord.Interaction, mod: str = "aç"):
            is_on = mod.lower() in ("aç", "ac", "on", "aktif", "true")
            self.channel_modes[interaction.channel_id] = "nizami" if is_on else "natural"
            if is_on:
                await interaction.response.send_message("🛡️ **Nizami Protokol Devrede:** Taktiksel savunma ve askeri disiplin moduna geçildi. Emirlerinizi bekliyorum, Efendim.")
            else:
                await interaction.response.send_message("🌿 **Normal Mod:** Rahat moda geçtim. Normal konuşuyoruz.")

        @tree.command(name="status", description="Sunucu ve sistem durum raporu")
        async def slash_status(interaction: discord.Interaction):
            rep, _ = handle_system_command("status")
            await interaction.response.send_message(f"```{rep}```")

        @tree.command(name="search", description="İnternette canlı arama yapar")
        @app_commands.describe(sorgu="Aranacak konu")
        async def slash_search(interaction: discord.Interaction, sorgu: str):
            await interaction.response.defer()
            rep, _ = handle_system_command("search", sorgu)
            await interaction.followup.send(rep[:2000])

        @tree.command(name="screen", description="Bilgisayarın anlık ekran görüntüsünü alır")
        async def slash_screen(interaction: discord.Interaction):
            await interaction.response.defer()
            rep, file_bytes = handle_system_command("screen")
            if file_bytes:
                d_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                await interaction.followup.send(content=rep, file=d_file)
            else:
                await interaction.followup.send(rep)

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"[DiscordBot] 🤖 Bot hazır ve giriş yaptı: {self.bot.user} (ID: {self.bot.user.id})")
            await self.bot.change_presence(activity=discord.Game(name="EDITH // Online"))
            # Slash komutlarını Discord API ile eşitle
            try:
                synced = await self.bot.tree.sync()
                print(f"[DiscordBot] ⚡ {len(synced)} adet Slash komutu Discord ile senkronize edildi!")
            except Exception as e:
                print(f"[DiscordBot] ⚠️ Slash sync uyarısı: {e}")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user:
                return

            content = message.content.strip()
            ch_id = message.channel.id
            current_mode = self.channel_modes.get(ch_id, "natural")
            lower_content = content.lower()

            # ── 1. DİNAMİK KİŞİLİK GEÇİŞİ (Doğal Dil Algılama) ──
            if any(p in lower_content for p in ["nizami ol", "resmi ol", "taktiksel ol", "askeri moda geç", "nizamiye geç"]):
                self.channel_modes[ch_id] = "nizami"
                await message.channel.send("🛡️ Anlaşıldı. Nizami ve taktiksel protokole geçildi. Emirlerinizi bekliyorum, Efendim.")
                return

            if any(p in lower_content for p in ["rahatla", "normal konuş", "serbest ol", "nizami kapat", "normal takıl"]):
                self.channel_modes[ch_id] = "natural"
                await message.channel.send("🌿 Tamamdır, rahat moda geçtim. Ne yapıyoruz?")
                return

            # ── 2. PREFIX KOMUTLAR (Örn: !status, !join, /join) ──
            if content.startswith(("/", "!")):
                parts = content[1:].split(" ", 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if cmd == "join":
                    if message.author.voice and message.author.voice.channel:
                        await self.voice_engine.join_channel(message.author.voice.channel)
                        await message.channel.send("🎙️ Sesli kanala katıldım.")
                    else:
                        await message.channel.send("Önce bir sesli kanala geçmelisin.")
                    return

                if cmd == "leave":
                    await self.voice_engine.leave_channel()
                    await message.channel.send("📴 Sesli kanaldan ayrıldım.")
                    return

                if cmd == "speak":
                    if args:
                        await self.voice_engine.speak_text(args)
                        await message.channel.send("🗣️ Seslendirildi.")
                    return

                if cmd == "nizami":
                    is_on = args.lower() in ("aç", "ac", "on", "aktif", "true") if args else True
                    self.channel_modes[ch_id] = "nizami" if is_on else "natural"
                    if is_on:
                        await message.channel.send("🛡️ Nizami protokol aktif edildi.")
                    else:
                        await message.channel.send("🌿 Normal insan moduna dönüldü.")
                    return

                # Sistem komutları yönlendirici
                reply_text, file_bytes = handle_system_command(cmd, args)
                if file_bytes:
                    discord_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                    await message.channel.send(content=reply_text, file=discord_file)
                else:
                    await message.channel.send(reply_text)
                return

            # ── 3. DOĞAL DİL SOHBETİ ──
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = (self.bot.user in message.mentions) if self.bot.user else False
            starts_with_name = lower_content.startswith(("edith", "edit"))
            has_name = "edith" in lower_content

            # Boş içerik kontrolü (Intent kapalıyken gelen boş mesajları engelle)
            image_bytes = None
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                        image_bytes = await att.read()
                        break

            if not content and not image_bytes:
                return

            # Bot yalnızca kendisine seslenildiğinde (DM, Mention veya "edith") konuşsun
            should_respond = is_dm or is_mentioned or starts_with_name or has_name
            if not should_respond:
                return

            # "edith" ön ekini temizle
            clean_content = content
            if starts_with_name:
                clean_content = content.split(" ", 1)[1].strip() if " " in content else ""
            if not clean_content and not image_bytes:
                await message.channel.send("Efendim? Buradayım.")
                return

            async with message.channel.typing():
                chunks = await self.text_engine.generate_response(
                    channel_id=ch_id,
                    user_message=clean_content,
                    author_name=message.author.display_name,
                    image_bytes=image_bytes,
                    personality=current_mode,
                )

                for chunk in chunks:
                    delay = calculate_typing_delay(chunk)
                    await asyncio.sleep(delay)
                    await message.channel.send(chunk)

    def run(self):
        if not self.token:
            print("[DiscordBot] ⚠️ Bot tokeni belirtilmedi.")
            return
        self.bot.run(self.token)


def start_discord_bot_background(token: str = "") -> None:
    if not HAS_DISCORD:
        print("[DiscordBot] ❌ discord.py kurulu değil.")
        return

    cfg = load_app_config().get("discord", {})
    bot_token = token or cfg.get("bot_token", "")

    if not bot_token:
        print("[DiscordBot] ℹ️ Discord bot tokeni yapılandırılmamış.")
        return

    def _run():
        print("[DiscordBot] 🚀 Discord Bot başlatılıyor...")
        try:
            bot_instance = EdithDiscordBot(bot_token, privileged_intents=True)
            bot_instance.run()
        except discord.errors.PrivilegedIntentsRequired:
            print("[DiscordBot] ⚠️ Message Content Intent henüz açık değil, temel modda bağlanılıyor...")
            try:
                bot_instance = EdithDiscordBot(bot_token, privileged_intents=False)
                bot_instance.run()
            except Exception as ex:
                print(f"[DiscordBot] ❌ Bot temel modda da başlatılamadı: {ex}")
        except Exception as e:
            print(f"[DiscordBot] ❌ Bot çalışma hatası: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()
