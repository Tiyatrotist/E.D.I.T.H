"""
discord_bot/embeds.py — Stark Industries E.D.I.T.H Premium Discord Embed Tasarımları

Discord'un klasik ve sıkıcı bot görüntüsünü ortadan kaldıran,
fütüristik neon camgöbeği (#00E5FF) ve koyu titanyum renk paletine sahip,
zengin ve yüksek teknolojili arayüz kartları (Embeds).
"""

from __future__ import annotations

import discord
from typing import Optional

# Stark Industries / EDITH Renk Teması
COLOR_CYAN = 0x00E5FF       # Taktiksel HUD Camgöbeği (Aktif/Başarılı)
COLOR_SUCCESS = 0x10B981    # Zümrüt Yeşili (Normal/Onay)
COLOR_MILITARY = 0x3B82F6   # Donanma / Askeri Mavi (Nizami Mod)
COLOR_WARN = 0xF59E0B       # Kehribar (Uyarı)
COLOR_DANGER = 0xEF4444     # Kırmızı (Hata/Kritik)

FOOTER_TEXT = "E.D.I.T.H // Tactical Intelligence Network • Stark Industries"


def create_base_embed(
    title: str,
    description: str = "",
    color: int = COLOR_CYAN,
    bot_user: Optional[discord.User | discord.ClientUser] = None,
) -> discord.Embed:
    """Tüm E.D.I.T.H mesajları için standart yüksek teknoloji embed şablonu."""
    embed = discord.Embed(title=title, description=description, color=color)
    if bot_user and bot_user.display_avatar:
        embed.set_author(name="E.D.I.T.H — Taktiksel Asistan", icon_url=bot_user.display_avatar.url)
    else:
        embed.set_author(name="E.D.I.T.H — Taktiksel Asistan")
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def status_embed(
    bot_user: Optional[discord.ClientUser] = None,
    ping_ms: float = 0.0,
    voice_connected: bool = False,
    active_mode: str = "natural",
) -> discord.Embed:
    """Sistem, donanım ve sunucu telemetri durum kartı."""
    import psutil

    cpu = psutil.cpu_percent(interval=None)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    embed = create_base_embed(
        title="🛰️ SİSTEM VE TELEMETRİ DURUM RAPORU",
        description="E.D.I.T.H operasyonel çekirdeği aktif ve tüm alt sistemler nominal çalışıyor.",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )

    embed.add_field(
        name="⚡ Çekirdek Durumu",
        value=f"**Bağlantı:** Aktif (`{int(ping_ms)} ms`)\n"
              f"**Aktif Mod:** {'🛡️ Nizami (Askeri)' if active_mode == 'nizami' else '🌿 Normal (Doğal)'}\n"
              f"**Ses Modülü:** {'🎙️ Bağlı' if voice_connected else '📴 Ayrık'}",
        inline=True,
    )

    embed.add_field(
        name="🧠 Yapay Zeka Havuzu",
        value="**Model:** Gemini 3.6 Flash\n"
              "**Yedekler:** Groq, NIM, Mistral\n"
              "**TTS:** Piper Neural (Kadın Sesi)",
        inline=True,
    )

    embed.add_field(
        name="📊 Donanım Yükü",
        value=f"**CPU:** `%{cpu:.1f}`\n"
              f"**RAM:** `%{ram.percent:.1f}` ({ram.used / (1024**3):.1f}GB / {ram.total / (1024**3):.1f}GB)\n"
              f"**Disk:** `%{disk.percent:.1f}` ({disk.free / (1024**3):.1f}GB boş)",
        inline=False,
    )

    return embed


def voice_embed(action: str, channel_name: str = "", text: str = "", bot_user=None) -> discord.Embed:
    """Sesli oda durum bildirim kartı."""
    if action == "join":
        embed = create_base_embed(
            title="🎙️ Ses Bağlantısı Aktif",
            description=f"**`{channel_name}`** ses kanalına katıldım. Dinliyorum, bir isteğin olursa buradayım.",
            color=COLOR_SUCCESS,
            bot_user=bot_user,
        )
    elif action == "leave":
        embed = create_base_embed(
            title="📴 Ses Bağlantısı Kapatıldı",
            description="Ses kanalından ayrıldım. Arka planda hazır bekliyorum.",
            color=COLOR_WARN,
            bot_user=bot_user,
        )
    elif action == "speak":
        embed = create_base_embed(
            title="🗣️ Sesli İfade İletildi",
            description=f"*{text}*",
            color=COLOR_CYAN,
            bot_user=bot_user,
        )
    else:
        embed = create_base_embed(title="Ses Modülü", description=text, color=COLOR_CYAN, bot_user=bot_user)
    return embed


def mode_embed(mode: str, bot_user=None) -> discord.Embed:
    """Nizami / Normal mod geçiş kartı."""
    if mode == "nizami":
        return create_base_embed(
            title="🛡️ Taktiksel Nizami Protokol Devrede",
            description="Askeri disiplin ve üst düzey taktiksel raporlama moduna geçildi.\n"
                        "Emir ve direktiflerinizi bekliyorum.",
            color=COLOR_MILITARY,
            bot_user=bot_user,
        )
    else:
        return create_base_embed(
            title="🌿 Normal Mod Aktif",
            description="Rahat moda geçtim. Bir isteğin olduğunda buradayım, doğrudan söyleyebilirsin.",
            color=COLOR_SUCCESS,
            bot_user=bot_user,
        )


def search_embed(query: str, result: str, bot_user=None) -> discord.Embed:
    """Web arama sonuç kartı."""
    embed = create_base_embed(
        title=f"🔍 Küresel Veri Analizi: {query[:50]}",
        description=result[:2000] if result else "Sonuç bulunamadı.",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )
    return embed


def help_embed(bot_user=None) -> discord.Embed:
    """Komut rehberi kartı."""
    embed = create_base_embed(
        title="⚡ E.D.I.T.H Komut ve Kontrol Merkezi",
        description="Aşağıdaki komutları doğrudan `/` ile veya sohbette doğal dille kullanabilirsiniz:",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )

    embed.add_field(
        name="🎙️ Sesli İletişim",
        value="`/join` — Bulunduğunuz ses odasına katılır\n"
              "`/leave` — Ses odasından ayrılır\n"
              "`/speak <metin>` — Doğal kadın sesiyle kanalda konuşur",
        inline=False,
    )

    embed.add_field(
        name="🛡️ Kişilik ve Modlar",
        value="`/nizami [aç/kapat]` — Askeri disiplin modunu açar/kapatır\n"
              "*Veya sohbete 'nizami ol' ya da 'rahatla' yazabilirsiniz.*",
        inline=False,
    )

    embed.add_field(
        name="🛰️ Taktiksel Araçlar",
        value="`/status` — Sunucu yükü ve donanım telemetrisi\n"
              "`/search <sorgu>` — İnternette anlık küresel arama\n"
              "`/screen` — Bilgisayarın anlık ekran görüntüsü",
        inline=False,
    )

    embed.add_field(
        name="💬 Doğal Sohbet",
        value="Bana `@EDITH` yazarak veya doğrudan `edith ...` diyerek istediğiniz soruyu sorabilirsiniz.",
        inline=False,
    )

    return embed


def phone_call_embed(
    caller_name: str,
    caller_number: str = "",
    summary: str = "",
    is_active: bool = False,
    bot_user=None,
) -> discord.Embed:
    """Termux telefon çağrısı bildirim kartı."""
    title = f"📞 GELEN ÇAĞRI: {caller_name}" if is_active else f"📲 ÇAĞRI TAMAMLANDI: {caller_name}"
    color = COLOR_WARN if is_active else COLOR_SUCCESS
    desc = f"**Numara:** `{caller_number or 'Gizli/Bilinmeyen'}`\n"
    if summary:
        desc += f"**EDITH Sekreter Notu:** {summary}"
    else:
        desc += "**Durum:** 14 saniye kuralı ile otomatik sekreter karşılama devrede."
    embed = create_base_embed(title=title, description=desc, color=color, bot_user=bot_user)
    return embed


def triple_mode_embed(mode: str, effective_mode: str = "", bot_user=None) -> discord.Embed:
    """Triple-Mode (Server / Local / Offline) durum kartı."""
    mode_titles = {
        "server": "🌐 SERVER (Bulut / Uzak Sunucu) Modu",
        "local": "💻 LOCAL (Yerel Model / Ollama) Modu",
        "offline": "🔌 OFFLINE (Tamamen İnternetsiz) Mod",
        "hybrid": "⚡ HİBRİT (Otomatik Kesintisiz Geçiş) Modu",
    }
    eff = effective_mode or mode
    title = mode_titles.get(mode.lower(), f"⚙️ Çalışma Modu: {mode.upper()}")
    desc = (
        f"**Seçili Çalışma Modu:** `{mode.upper()}`\n"
        f"**Yürütülen Efektif Mod:** `{eff.upper()}`\n"
        f"**Yedekleme Zinciri:** Server ⇄ Local ⇄ Offline kesintisiz geçiş aktif."
    )
    embed = create_base_embed(title=title, description=desc, color=COLOR_CYAN, bot_user=bot_user)
    return embed
