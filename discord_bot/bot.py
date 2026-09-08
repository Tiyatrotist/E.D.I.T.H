"""
discord_bot/bot.py — EDITH Discord Bot Ana Servisi (Stark UI & Anlık Slash Senkronizasyonu)

Özellikler:
1. Discord Guild Bazlı Anlık Slash Komut Senkronizasyonu (1 saniyede Discord menüsünde belirir).
2. Fütüristik Stark Industries Embeds (Zengin arayüz kartları, ikonlar, renkler).
3. "Bir isteğin mi var?" tarzında olgun, saygılı ve akıllı insan kişiliği.
4. Dinamik Nizami / Normal mod geçişi.
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
from discord_bot.command_router import handle_system_command, is_user_authorized
from discord_bot.embeds import (
    activity_embed,
    briefing_embed,
    browse_embed,
    help_embed,
    mode_embed,
    phone_call_embed,
    reminders_embed,
    search_embed,
    status_embed,
    triple_mode_embed,
    vision_embed,
    voice_embed,
)
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
        self.text_engine.set_bot_instance(self)
        self._setup_slash_commands()
        self._setup_events()

    def _setup_slash_commands(self):
        """Discord yerel Slash (/) komutlarını tanımlar."""
        tree = self.bot.tree

        @tree.command(name="yardim", description="E.D.I.T.H komut rehberi ve özellikleri")
        async def slash_help(interaction: discord.Interaction):
            emb = help_embed(self.bot.user)
            await interaction.response.send_message(embed=emb)

        @tree.command(name="join", description="Bulunduğunuz sesli odaya katılır")
        async def slash_join(interaction: discord.Interaction):
            if interaction.user and isinstance(interaction.user, discord.Member) and interaction.user.voice:
                channel = interaction.user.voice.channel
                await self.voice_engine.join_channel(channel)
                emb = voice_embed("join", channel.name, bot_user=self.bot.user)
                await interaction.response.send_message(embed=emb)
            else:
                await interaction.response.send_message("Önce bir sesli kanala geçmelisin.", ephemeral=True)

        @tree.command(name="leave", description="Sesli odadan ayrılır")
        async def slash_leave(interaction: discord.Interaction):
            await self.voice_engine.leave_channel()
            emb = voice_embed("leave", bot_user=self.bot.user)
            await interaction.response.send_message(embed=emb)

        @tree.command(name="speak", description="Holografik kadın sesiyle sesli odada konuşur")
        @app_commands.describe(metin="Seslendirilecek metin")
        async def slash_speak(interaction: discord.Interaction, metin: str):
            await interaction.response.defer()
            await self.voice_engine.speak_text(metin)
            emb = voice_embed("speak", text=metin, bot_user=self.bot.user)
            await interaction.followup.send(embed=emb)

        @tree.command(name="sound", description="Ses odasında taktiksel Stark ses efekti çalar")
        @app_commands.describe(efekt="Ses efekti türü (chime, alert, notification)")
        async def slash_sound(interaction: discord.Interaction, efekt: str = "chime"):
            ok = await self.voice_engine.play_sound_effect(efekt)
            if ok:
                await interaction.response.send_message(f"🔔 Ses odasında '{efekt}' efekti çalındı.")
            else:
                await interaction.response.send_message("Ses efekti çalınamadı (bot bir ses odasında olmalıdır).", ephemeral=True)

        @tree.command(name="briefing", description="Günlük hava, sistem ve çağrı sabah brifingini sunar")
        async def slash_briefing(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                from actions.morning_briefing import generate_morning_briefing
                b_data = generate_morning_briefing()
                emb = briefing_embed(b_data, bot_user=self.bot.user)
                await interaction.followup.send(embed=emb)
            except Exception as ex:
                await interaction.followup.send(f"Brifing alınamadı: {ex}")

        @tree.command(name="vision", description="Bilgisayar ekranını yakalayıp yapay zeka ile analiz eder")
        @app_commands.describe(soru="Ekranda neye odaklanılmasını istersiniz?")
        async def slash_vision(interaction: discord.Interaction, soru: str = "Ekranda açık olan içeriği analiz et."):
            uid = interaction.user.id if interaction.user else None
            if not is_user_authorized(uid):
                await interaction.response.send_message("⚠️ Bu taktiksel komut için Stark Industries yönetici yetkisi gereklidir.", ephemeral=True)
                return
            await interaction.response.defer()
            rep, file_bytes = handle_system_command("vision", args=soru, user_id=uid)
            if file_bytes:
                d_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                emb = vision_embed(soru, rep.replace("👁️ **Stark Ekran Görsel Analizi:**\n\n", ""), bot_user=self.bot.user)
                await interaction.followup.send(embed=emb, file=d_file)
            else:
                await interaction.followup.send(rep)

        @tree.command(name="activity", description="PC refakatçisi: çalışma süresi, aktif pencere ve mola durumu")
        async def slash_activity(interaction: discord.Interaction):
            try:
                from actions.activity_supervisor import get_activity_supervisor
                st = get_activity_supervisor().get_status()
                emb = activity_embed(st, bot_user=self.bot.user)
                await interaction.response.send_message(embed=emb)
            except Exception as ex:
                await interaction.response.send_message(f"Etkinlik durumu alınamadı: {ex}")

        @tree.command(name="browse", description="Verilen web sayfasını reklamsız okur ve temiz özet çıkarır")
        @app_commands.describe(url="İncelenecek web adresi (http...)")
        async def slash_browse(interaction: discord.Interaction, url: str):
            await interaction.response.defer()
            try:
                from actions.browser import scrape_and_clean_page
                md = scrape_and_clean_page(url, max_chars=2500)
                emb = browse_embed(url, md, bot_user=self.bot.user)
                await interaction.followup.send(embed=emb)
            except Exception as ex:
                await interaction.followup.send(f"Sayfa okunamadı: {ex}")

        @tree.command(name="reminders", description="Bugünkü kayıtlı hatırlatıcıları ve görevleri listeler")
        async def slash_reminders(interaction: discord.Interaction):
            try:
                from actions.reminders import get_reminders
                r_text = get_reminders()
                emb = reminders_embed(r_text, bot_user=self.bot.user)
                await interaction.response.send_message(embed=emb)
            except Exception as ex:
                await interaction.response.send_message(f"Hatırlatıcılar alınamadı: {ex}")

        @tree.command(name="nizami", description="Nizami askeri disiplin modunu açar veya kapatır")
        @app_commands.describe(mod="aç veya kapat")
        async def slash_nizami(interaction: discord.Interaction, mod: str = "aç"):
            is_on = mod.lower() in ("aç", "ac", "on", "aktif", "true")
            self.channel_modes[interaction.channel_id] = "nizami" if is_on else "natural"
            emb = mode_embed("nizami" if is_on else "natural", bot_user=self.bot.user)
            await interaction.response.send_message(embed=emb)

        @tree.command(name="status", description="Sunucu yükü ve sistem telemetri durumu")
        async def slash_status(interaction: discord.Interaction):
            is_connected = (
                self.voice_engine.voice_client is not None
                and self.voice_engine.voice_client.is_connected()
            )
            mode = self.channel_modes.get(interaction.channel_id, "natural")
            emb = status_embed(
                bot_user=self.bot.user,
                ping_ms=self.bot.latency * 1000,
                voice_connected=is_connected,
                active_mode=mode,
            )
            await interaction.response.send_message(embed=emb)

        @tree.command(name="search", description="İnternette canlı arama yapar")
        @app_commands.describe(sorgu="Aranacak konu")
        async def slash_search(interaction: discord.Interaction, sorgu: str):
            await interaction.response.defer()
            rep, _ = handle_system_command("search", sorgu, user_id=interaction.user.id if interaction.user else None)
            emb = search_embed(sorgu, rep, bot_user=self.bot.user)
            await interaction.followup.send(embed=emb)

        @tree.command(name="screen", description="Bilgisayarın anlık ekran görüntüsünü alır")
        async def slash_screen(interaction: discord.Interaction):
            uid = interaction.user.id if interaction.user else None
            if not is_user_authorized(uid):
                await interaction.response.send_message("⚠️ Bu taktiksel komut için Stark Industries yönetici yetkisi gereklidir.", ephemeral=True)
                return
            await interaction.response.defer()
            rep, file_bytes = handle_system_command("screen", user_id=uid)
            if file_bytes:
                d_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                await interaction.followup.send(content=rep, file=d_file)
            else:
                await interaction.followup.send(rep)

    def _setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f"[DiscordBot] 🤖 Bot hazır ve giriş yaptı: {self.bot.user} (ID: {self.bot.user.id})")
            activity = discord.Activity(type=discord.ActivityType.listening, name="Komutlarınızı / 'edith'")
            await self.bot.change_presence(activity=activity, status=discord.Status.online)

            # ── ÇİFT KOMUTU ENGELLE: Guild kopyalarını temizle, tekil global sync yap ──
            for guild in self.bot.guilds:
                try:
                    self.bot.tree.clear_commands(guild=guild)
                    await self.bot.tree.sync(guild=guild)
                    print(f"[DiscordBot] 🧹 '{guild.name}' sunucusundaki çift komutlar temizlendi.")
                except Exception as ex:
                    print(f"[DiscordBot] ⚠️ Guild clean ({guild.name}): {ex}")

            try:
                synced = await self.bot.tree.sync()
                print(f"[DiscordBot] ⚡ {len(synced)} adet tekil Slash komutu Discord ile senkronize edildi!")
            except Exception as e:
                print(f"[DiscordBot] ⚠️ Global sync uyarısı: {e}")

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author == self.bot.user:
                return

            content = message.content.strip()
            ch_id = message.channel.id
            current_mode = self.channel_modes.get(ch_id, "natural")
            lower_content = content.lower()

            # ── 1. DİNAMİK KİŞİLİK GEÇİŞİ ──
            if any(p in lower_content for p in ["nizami ol", "resmi ol", "taktiksel ol", "askeri moda geç", "nizamiye geç"]):
                self.channel_modes[ch_id] = "nizami"
                emb = mode_embed("nizami", bot_user=self.bot.user)
                await message.channel.send(embed=emb)
                return

            if any(p in lower_content for p in ["rahatla", "normal konuş", "serbest ol", "nizami kapat", "normal takıl"]):
                self.channel_modes[ch_id] = "natural"
                emb = mode_embed("natural", bot_user=self.bot.user)
                await message.channel.send(embed=emb)
                return

            # ── 2. PREFIX KOMUTLAR (Örn: !yardim, !status, !join) ──
            if content.startswith(("/", "!")):
                parts = content[1:].split(" ", 1)
                cmd = parts[0].lower()
                args = parts[1] if len(parts) > 1 else ""

                if cmd in ("yardim", "help"):
                    emb = help_embed(self.bot.user)
                    await message.channel.send(embed=emb)
                    return

                if cmd == "join":
                    if message.author.voice and message.author.voice.channel:
                        channel = message.author.voice.channel
                        await self.voice_engine.join_channel(channel)
                        emb = voice_embed("join", channel.name, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    else:
                        await message.channel.send("Önce bir sesli kanala geçmelisin.")
                    return

                if cmd == "leave":
                    await self.voice_engine.leave_channel()
                    emb = voice_embed("leave", bot_user=self.bot.user)
                    await message.channel.send(embed=emb)
                    return

                if cmd == "speak":
                    if args:
                        await self.voice_engine.speak_text(args)
                        emb = voice_embed("speak", text=args, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    return

                if cmd == "status":
                    is_connected = (
                        self.voice_engine.voice_client is not None
                        and self.voice_engine.voice_client.is_connected()
                    )
                    emb = status_embed(
                        bot_user=self.bot.user,
                        ping_ms=self.bot.latency * 1000,
                        voice_connected=is_connected,
                        active_mode=current_mode,
                    )
                    await message.channel.send(embed=emb)
                    return

                if cmd in ("mode", "mod"):
                    try:
                        from core.mode_manager import get_mode_manager
                        mgr = get_mode_manager()
                        target = (args or "").strip().lower()
                        if target in ("server", "local", "offline", "hybrid"):
                            mgr.set_mode(target)
                        emb = triple_mode_embed(mgr.get_mode(), mgr.get_effective_mode(), bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    except Exception as ex:
                        await message.channel.send(f"⚠️ Mod bilgisi alınamadı: {ex}")
                    return

                if cmd == "search":
                    if args:
                        rep, _ = handle_system_command("search", args, user_id=message.author.id)
                        emb = search_embed(args, rep, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    return

                if cmd in ("briefing", "brifing", "sabah"):
                    try:
                        from actions.morning_briefing import generate_morning_briefing
                        b_data = generate_morning_briefing()
                        emb = briefing_embed(b_data, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    except Exception as ex:
                        await message.channel.send(f"Brifing alınamadı: {ex}")
                    return

                if cmd in ("activity", "etkinlik", "refakatci"):
                    try:
                        from actions.activity_supervisor import get_activity_supervisor
                        st = get_activity_supervisor().get_status()
                        emb = activity_embed(st, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    except Exception as ex:
                        await message.channel.send(f"Etkinlik durumu alınamadı: {ex}")
                    return

                if cmd in ("browse", "oku", "web"):
                    if not args:
                        await message.channel.send("İncelenecek web adresini belirt: `!browse <url>`")
                        return
                    try:
                        from actions.browser import scrape_and_clean_page
                        md = scrape_and_clean_page(args, max_chars=2500)
                        emb = browse_embed(args, md, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    except Exception as ex:
                        await message.channel.send(f"Sayfa okunamadı: {ex}")
                    return

                if cmd in ("reminders", "hatirlatici", "gorevler"):
                    try:
                        from actions.reminders import get_reminders
                        r_text = get_reminders()
                        emb = reminders_embed(r_text, bot_user=self.bot.user)
                        await message.channel.send(embed=emb)
                    except Exception as ex:
                        await message.channel.send(f"Hatırlatıcılar alınamadı: {ex}")
                    return

                if cmd in ("sound", "ses_efekti"):
                    ok = await self.voice_engine.play_sound_effect(args or "chime")
                    if ok:
                        await message.channel.send(f"🔔 Ses odasında '{args or 'chime'}' efekti çalındı.")
                    else:
                        await message.channel.send("Ses efekti çalınamadı (bot bir ses odasında olmalıdır).")
                    return

                # Diğer sistem komutları
                reply_text, file_bytes = handle_system_command(cmd, args, user_id=message.author.id)
                if file_bytes:
                    discord_file = discord.File(io.BytesIO(file_bytes), filename="screen.png")
                    if cmd in ("vision", "ekran_analiz"):
                        emb = vision_embed(args, reply_text.replace("👁️ **Stark Ekran Görsel Analizi:**\n\n", ""), bot_user=self.bot.user)
                        await message.channel.send(embed=emb, file=discord_file)
                    else:
                        await message.channel.send(content=reply_text, file=discord_file)
                elif reply_text:
                    await message.channel.send(reply_text)
                return

            # ── 3. DOĞAL DİL SOHBETİ ──
            is_dm = isinstance(message.channel, discord.DMChannel)
            is_mentioned = (self.bot.user in message.mentions) if self.bot.user else False
            starts_with_name = lower_content.startswith(("edith", "edit"))
            has_name = "edith" in lower_content

            image_bytes = None
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
                        image_bytes = await att.read()
                        break

            if not content and not image_bytes:
                return

            should_respond = is_dm or is_mentioned or starts_with_name or has_name
            if not should_respond:
                return

            # Mentions ve isim çağrılarını temizle
            clean_content = re.sub(r"<@!?\d+>", "", content).strip()
            lower_clean = clean_content.lower()
            if lower_clean.startswith(("edith", "edit")):
                clean_content = clean_content.split(" ", 1)[1].strip() if " " in clean_content else ""

            # Kullanıcı yalnızca bota seslendiyse (Örn: sadece "@E.D.I.T.H" veya sadece "edith"):
            if not clean_content and not image_bytes:
                await message.channel.send("Buradayım, bir isteğin mi var?")
                return

            async with message.channel.typing():
                chunks = await self.text_engine.generate_response(
                    channel_id=ch_id,
                    user_message=clean_content,
                    author_name=message.author.display_name,
                    image_bytes=image_bytes,
                    personality=current_mode,
                    message_context=message,
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


_global_bot_instance: Optional[EdithDiscordBot] = None


def get_discord_bot() -> Optional[EdithDiscordBot]:
    global _global_bot_instance
    return _global_bot_instance


def send_discord_alert(title: str, description: str, caller_name: str = "") -> None:
    """Sunucudan Discord kanalına anlık zengin bildirim gönderir (örn: cevaplanan telefon araması)."""
    global _global_bot_instance
    if not _global_bot_instance or not _global_bot_instance.bot.is_ready():
        return

    async def _send():
        try:
            bot = _global_bot_instance.bot
            cfg = load_app_config().get("discord", {})
            allowed_channels = cfg.get("allowed_channels", [])

            channel = None
            if allowed_channels:
                channel = bot.get_channel(int(allowed_channels[0]))

            if not channel:
                # Botun bulunduğu ilk metin kanalını bul
                for guild in bot.guilds:
                    for ch in guild.text_channels:
                        if ch.permissions_for(guild.me).send_messages:
                            channel = ch
                            break
                    if channel:
                        break

            if channel:
                embed = phone_call_embed(
                    caller_name=caller_name or "Bilinmeyen Numara",
                    caller_number="",
                    summary=description,
                    is_active=("çalıyor" in description.lower() or "gelen" in title.lower()),
                    bot_user=bot.user,
                )
                await channel.send(embed=embed)
                print(f"[DiscordBot] 📢 Discord bildirimi gönderildi -> #{channel.name}")
        except Exception as e:
            print(f"[DiscordBot] ⚠️ Bildirim gönderme hatası: {e}")

    try:
        loop = _global_bot_instance.bot.loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), loop)
    except Exception as e:
        print(f"[DiscordBot] ⚠️ Bildirim zamanlama hatası: {e}")


def start_discord_bot_background(token: str = "") -> None:
    global _global_bot_instance
    if not HAS_DISCORD:
        print("[DiscordBot] ❌ discord.py kurulu değil.")
        return

    cfg = load_app_config().get("discord", {})
    bot_token = token or cfg.get("bot_token", "")

    if not bot_token:
        print("[DiscordBot] ℹ️ Discord bot tokeni yapılandırılmamış.")
        return

    def _run():
        global _global_bot_instance
        print("[DiscordBot] 🚀 Discord Bot başlatılıyor...")
        try:
            _global_bot_instance = EdithDiscordBot(bot_token, privileged_intents=True)
            _global_bot_instance.run()
        except discord.errors.PrivilegedIntentsRequired:
            print("[DiscordBot] ⚠️ Message Content Intent henüz açık değil, temel modda bağlanılıyor...")
            try:
                _global_bot_instance = EdithDiscordBot(bot_token, privileged_intents=False)
                _global_bot_instance.run()
            except Exception as ex:
                print(f"[DiscordBot] ❌ Bot temel modda da başlatılamadı: {ex}")
        except Exception as e:
            print(f"[DiscordBot] ❌ Bot çalışma hatası: {e}")

    t = threading.Thread(target=_run, daemon=True)
    t.start()

