# E.D.I.T.H // Obsidian İkinci Beyin (Second Brain & Zettelkasten) Rehberi

E.D.I.T.H İkinci Beyin modülü, asistanınızın edindiği tüm bilgileri, günlük sabah brifinglerini, telefon çağrı özetlerini ve araştırma notlarını **Obsidian uyumlu, tamamen yerel, açık ve taşınabilir Markdown** formatında organize eden yerel bir Zettelkasten ve bilgi grafiği (knowledge graph) sistemidir.

---

## 🏛️ Mimari ve Tasarım Prensipleri

1. **%100 Yerel ve Açık Format:** Veriler kapalı bir veritabanında değil, doğrudan standart `.md` dosyalarında saklanır. Obsidian, Logseq, VS Code veya herhangi bir metin editörüyle anında açılabilir.
2. **Atomik Notlar & Zettelkasten:** Her kavram, proje ve kaynak kendi bağımsız dosyasına sahiptir. Notlar birbirine `[[Bağlantı Adı]]` (Wikilink) sözdizimi ile bağlanır.
3. **Standart YAML Frontmatter:** Tüm notlar başlık, oluşturulma tarihi, etiketler ve ilişkili bağlantılar içeren standart YAML metaverileriyle başlar.
4. **Otonom Asistan Entegrasyonu:** EDITH, kullanıcının gün içerisindeki aktivitelerini (sabah brifingi, tamamlanan telefon görüşmeleri, sesli araştırma notları) otomatik olarak günün notuna (`Daily/YYYY-MM-DD.md`) işler.
5. **Thread-Safe & Çift Yönlü Senkron:** Çoklu iş parçacığı kilidi (`threading.Lock`) ile eşzamanlı okuma/yazma güvenliği sağlanır.

---

## 📂 Vault Dizin Hiyerarşisi

Obsidian Vault'u varsayılan olarak `memory/obsidian_vault/` altında oluşturulur (konfigürasyondan `config/settings.json` ile özelleştirilebilir):

```
memory/obsidian_vault/
├── Daily/           # Günlük notlar ve asistan günlüğü (YYYY-MM-DD.md)
│   ├── 2026-09-08.md
│   └── 2026-09-09.md
├── Concepts/        # Atomik fikirler, teoriler, tanımlar ve bilgi kartları
│   ├── Quantum_Computing.md
│   └── Stark_Protocol.md
├── Projects/        # Proje planları, kilometre taşları ve hedefler
│   └── EDITH_Phase14.md
├── Resources/       # Web araştırma özetleri, makaleler, kaynaklar
│   └── Edge_TTS_Documentation.md
└── Archives/        # Tamamlanmış ve arşivlenmiş notlar
```

---

## 📝 Not Yapısı ve YAML Frontmatter Formatı

Oluşturulan her not standart Zettelkasten şablonuna uyar:

```markdown
---
title: "Kuantum Bilgisayarlar ve Şifreleme"
created_at: "2026-09-09T10:00:00"
tags:
  - kuantum
  - kriptografi
  - teknoloji
links:
  - "Post Kuantum Kripto"
  - "Shor Algoritması"
---

# Kuantum Bilgisayarlar ve Şifreleme

Kuantum hesaplama, klasik RSA şifrelemesini tehdit etmektedir.
İlgili detaylar için [[Post Kuantum Kripto]] konusunu inceleyin.
```

---

## 🤖 Otonom Günlük Tutma (Auto-Journaling)

EDITH arka planda aşağıdaki olayları doğrudan günün günlük notuna ekler:

### 1. ☕ Sabah Brifingi & Durum Raporu (`actions/morning_briefing.py`)
Kullanıcı sabah uyandığında veya brifing talep ettiğinde:
- Hava durumu, sistem kaynakları ve günün ilk analizi `Daily/YYYY-MM-DD.md` dosyasına `## ☕ Sabah Brifingi & Durum` başlığı altına zaman damgasıyla yazılır.

### 2. 📞 Telefon Çağrı Kayıtları & Sekreter Özetleri (`core/phone_bridge.py`)
Android Companion veya PBX üzerinden bir arama sonlandığında:
- Arayan numara/kişi, çağrı süresi, konuşma dökümü ve yapay zeka sekreter özeti anında `Daily/YYYY-MM-DD.md` dosyasına `## 📞 İletişim & Çağrı Kayıtları` başlığı altına kaydedilir.

---

## 🗣️ Sesli Komutlar ve LLM Tool Calling

EDITH ile konuşurken veya sohbet ederken `obsidian_note` aracı otonom olarak devreye girer:

| Komut / Talep Örneği | Gerçekleşen Eylem |
|---|---|
| *"Obsidian'a Kuantum Fiziği hakkında bir konsept notu ekle"* | `Concepts/Kuantum_Fiziği.md` oluşturulur, etiketler ve bağlantılar eklenir. |
| *"Bugünkü günlüğüme toplantı notu düş"* | `Daily/YYYY-MM-DD.md` içerisine zaman damgalı not eklenir. |
| *"İkinci beynimde yapay zeka ile ilgili ne var ara"* | Vault üzerinde ağırlıklı anahtar kelime araması yapılır ve özet okunur. |
| *"Kuantum Fiziği notumu oku"* | İlgili notun içeriği okunur ve yanıtlanır. |
| *"İkinci beynimin istatistiklerini göster"* | Toplam not, konsept, proje, kaynak sayıları raporlanır. |

---

## 🌐 Web Dashboard (PWA) Arayüzü

`http://localhost:8080` adresindeki Web Kontrol Paneli'nde **PC Kontrolü (tab-pc)** sekmesinde özel bir **🧠 İkinci Beyin (Obsidian Vault)** kartı bulunur:

- **Canlı İstatistik Rozetleri:** Toplam Not, Konseptler, Projeler, Kaynaklar, Günlük Kayıtlar ve Etiket sayıları.
- **Hızlı Not Kaydedici:** Kategori seçimi (Concepts, Projects, Resources), başlık, etiketler ve içerik alanı ile tek tıkla not oluşturma.
- **Günlük Ekleme:** Günün notuna hızlıca düşünce veya log satırı ekleme.
- **Anlık Vault Arama:** Anahtar kelimelerle arama yaparak eşleşen dosyaları ve skorlarını anında listeleme.

---

## 🔌 REST API Uç Noktaları (`/api/obsidian/*`)

| Metot | Uç Nokta | Açıklama |
|---|---|---|
| `GET` | `/api/obsidian/stats` | Vault istatistiklerini JSON olarak döner |
| `GET` | `/api/obsidian/graph` | Bilgi grafiği (Knowledge Graph) düğüm ve kenarlarını döner |
| `GET` | `/api/obsidian/search?q=...` | Vault içinde ağırlıklı arama yapar |
| `GET` | `/api/obsidian/daily` | Günün `Daily/YYYY-MM-DD.md` içeriğini döner |
| `POST` | `/api/obsidian/note` | Yeni bir atomik not kaydeder |
| `POST` | `/api/obsidian/daily/append` | Günün notuna yeni bir giriş ekler |

---

## ⚙️ Yapılandırma (`app_config.py` & `config/settings.json`)

```json
{
  "obsidian": {
    "enabled": true,
    "vault_path": "memory/obsidian_vault",
    "daily_folder": "Daily",
    "concepts_folder": "Concepts",
    "projects_folder": "Projects",
    "resources_folder": "Resources",
    "auto_daily_briefing": true,
    "auto_call_logs": true
  }
}
```

---

## 🚀 Resmi Obsidian Uygulaması ile Kullanım

1. Bilgisayarınıza veya telefonunuza resmi [Obsidian](https://obsidian.md) uygulamasını indirin.
2. Obsidian açılışında **"Open folder as vault"** (Mevcut klasörü kasa olarak aç) seçeneğini seçin.
3. EDITH projenizdeki `memory/obsidian_vault` klasörünü gösterin.
4. Artık EDITH'in aldığı tüm notları interaktif **Grafik Görünümünde (Graph View)** görselleştirebilir ve cihazlarınız arasında Obsidian Sync veya Syncthing ile eşitleyebilirsiniz.
