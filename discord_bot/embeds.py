"""
discord_bot/embeds.py — Stark Industries E.D.I.T.H Premium Discord Embed Tasarımları

Discord'un klasik ve sıkıcı bot görüntüsünü ortadan kaldıran,
fütüristik neon camgöbeği (#00E5FF) ve koyu titanyum renk paletine sahip,
zengin ve yüksek teknolojili arayüz kartları (Embeds).
"""

from __future__ import annotations

import discord
from typing import Optional, Dict, Any

# Stark Industries / EDITH Renk Teması
COLOR_CYAN = 0x00E5FF       # Taktiksel HUD Camgöbeği (Aktif/Başarılı)
COLOR_SUCCESS = 0x10B981    # Zümrüt Yeşili (Normal/Onay)
COLOR_MILITARY = 0x3B82F6   # Donanma / Askeri Mavi (Nizami Mod)
COLOR_WARN = 0xF59E0B       # Kehribar (Uyarı)
COLOR_DANGER = 0xEF4444     # Kırmızı (Hata/Kritik)
COLOR_PURPLE = 0x8B5CF6     # Fütüristik Mor (Görsel Zeka / Vision)

FOOTER_TEXT = "E.D.I.T.H // Tactical Intelligence Network • Stark Industries"


def create_base_embed(
    title: str,
    description: str = "",
    color: int = COLOR_CYAN,
    bot_user: Optional[discord.User | discord.ClientUser] = None,
) -> discord.Embed:
    """Tüm E.D.I.T.H mesajları için standart yüksek teknoloji embed şablonu."""
    embed = discord.Embed(title=title, description=description, color=color)
    if bot_user and hasattr(bot_user, "display_avatar") and bot_user.display_avatar:
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
        name="🧠 Yapay Zeka & Ses Havuzu",
        value="**Model:** Gemini 3.6 Flash / Local Hybrid\n"
              "**Yedekler:** Groq, NIM, Mistral, Ollama\n"
              "**TTS:** Holografik EmelNeural (Warmth+Reverb)",
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
            description=f"**`{channel_name}`** ses kanalına katıldım. Holografik ses filtresi aktif, dinliyorum efendim.",
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
            title="🗣️ Holografik Sesli İfade İletildi",
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


def briefing_embed(data: Dict[str, Any], bot_user=None) -> discord.Embed:
    """Sabah Brifingi ve Günlük Yönetici Özeti kartı."""
    embed = create_base_embed(
        title="☕ STARK EXECUTIVE SABAH BRİFİNGİ",
        description=data.get("greeting", "Günaydın efendim. Günlük operasyonel durum özetiniz hazır:"),
        color=COLOR_CYAN,
        bot_user=bot_user,
    )

    weather = data.get("weather", {})
    w_text = f"{weather.get('condition', 'Bilinmiyor')}, `{weather.get('temp_c', '?')}°C` (Hissedilen: `{weather.get('feelslike_c', '?')}°C`)"
    embed.add_field(name="🌤️ Yerel Hava Durumu", value=w_text, inline=True)

    sys_info = data.get("system", {})
    s_text = f"CPU: `%{sys_info.get('cpu_percent', 0)}` | RAM: `%{sys_info.get('ram_percent', 0)}` | Disk: `%{sys_info.get('disk_percent', 0)}`"
    embed.add_field(name="📊 Sistem Sağlığı", value=s_text, inline=True)

    reminders = data.get("reminders", [])
    r_text = f"**{len(reminders)}** adet aktif görev ve hatırlatıcı."
    embed.add_field(name="⏰ Hatırlatıcılar", value=r_text, inline=False)

    calls = data.get("recent_calls", [])
    c_text = f"Son 24 saatte **{len(calls)}** adet GSM sekreter çağrısı işlendi."
    embed.add_field(name="📞 Çağrı Özeti", value=c_text, inline=False)

    return embed


def vision_embed(prompt: str, analysis: str, bot_user=None) -> discord.Embed:
    """Görsel zeka ve ekran analizi kartı."""
    embed = create_base_embed(
        title="👁️ STARK GÖRSEL ZEKA & EKRAN ANALİZİ",
        description=analysis[:2000] if analysis else "Analiz oluşturulamadı.",
        color=COLOR_PURPLE,
        bot_user=bot_user,
    )
    if prompt:
        embed.add_field(name="🎯 Odak / Soru", value=prompt[:250], inline=False)
    return embed


def activity_embed(status_data: Dict[str, Any], bot_user=None) -> discord.Embed:
    """PC Canlı Refakatçi ve Etkinlik Takip kartı."""
    embed = create_base_embed(
        title="🛡️ PC & YAŞAM REFAKATÇİSİ TELEMETRİSİ",
        description="Bilgisayar oturumunuz ve sağlık durumunuz arka planda gözetleniyor.",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )

    app_name = status_data.get("active_app", "Bilinmiyor")
    cat = status_data.get("category", "WORK")
    embed.add_field(name="💻 Aktif Pencere & Tür", value=f"`{app_name}` ({cat})", inline=True)

    sess = status_data.get("session_duration_minutes", 0)
    work = status_data.get("work_duration_minutes", 0)
    game = status_data.get("gaming_duration_minutes", 0)
    embed.add_field(name="⏱️ Süreler", value=f"Oturum: `{sess} dk`\nÇalışma: `{work} dk`\nOyun: `{game} dk`", inline=True)

    dnd = "🔔 Açık (Rahatsız Etmeyin)" if status_data.get("dnd_active") else "🔕 Kapalı (Normal)"
    embed.add_field(name="🛡️ DND Modu", value=dnd, inline=False)

    return embed


def browse_embed(url: str, content: str, bot_user=None) -> discord.Embed:
    """Otonom web okuma ve özet kartı."""
    embed = create_base_embed(
        title=f"🌐 Otonom Web İncelemesi: {url[:45]}",
        description=content[:2000] if content else "İçerik bulunamadı.",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )
    return embed


def reminders_embed(reminders_text: str, bot_user=None) -> discord.Embed:
    """Hatırlatıcılar ve görevler listesi kartı."""
    embed = create_base_embed(
        title="⏰ GÖREVLER VE HATIRLATICILAR",
        description=reminders_text[:2000] if reminders_text else "Aktif hatırlatıcınız bulunmuyor.",
        color=COLOR_SUCCESS,
        bot_user=bot_user,
    )
    return embed


def help_embed(bot_user=None) -> discord.Embed:
    """Kapsamlı E.D.I.T.H komut rehberi kartı."""
    embed = create_base_embed(
        title="⚡ E.D.I.T.H Komut ve Kontrol Merkezi",
        description="Aşağıdaki komutları doğrudan `/` ile veya sohbette doğal dille kullanabilirsiniz:",
        color=COLOR_CYAN,
        bot_user=bot_user,
    )

    embed.add_field(
        name="🎙️ Sesli İletişim & Holografik Motor",
        value="`/join` — Bulunduğunuz ses odasına katılır\n"
              "`/leave` — Ses odasından ayrılır\n"
              "`/speak <metin>` — Holografik kadın sesiyle kanalda konuşur\n"
              "`/sound [chime/alert]` — Taktiksel ses efekti çalar",
        inline=False,
    )

    embed.add_field(
        name="☕ Yönetici & Refakatçi Süper Güçleri",
        value="`/briefing` — Günlük hava, sistem ve çağrı sabah brifingi\n"
              "`/vision [soru]` — Bilgisayar ekranını AI ile analiz eder\n"
              "`/activity` — PC oturum süresi ve çalışma/oyun durumu\n"
              "`/browse <url>` — Web sayfasını reklamsız okur ve özetler\n"
              "`/reminders` — Bugünkü hatırlatıcıları listeler",
        inline=False,
    )

    embed.add_field(
        name="🛡️ Kişilik ve Modlar",
        value="`/nizami [aç/kapat]` — Askeri disiplin modunu açar/kapatır\n"
              "*Veya sohbete 'nizami ol' ya da 'rahatla' yazabilirsiniz.*",
        inline=False,
    )

    embed.add_field(
        name="🛰️ Taktiksel Araçlar (Yönetici İzinli)",
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
