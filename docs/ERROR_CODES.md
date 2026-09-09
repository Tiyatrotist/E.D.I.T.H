# E.D.I.T.H // Hata Kodları Rehberi (Troubleshooting & Wiki)

Bu dokümantasyon, E.D.I.T.H asistanının sahada karşılaştığı durumlarda kullanıcıya bildirdiği `ED-XXX-YYY` hata kodlarının açıklamalarını ve hızlı çözüm adımlarını içerir.

---

## 🖥️ Sistem & Donanım (100 Serisi)

### `ED-SYS-101` — Sistem Donanım Bilgisi Okunamadı
- **Neden:** `psutil` kütüphanesinin sistem sayaçlarına erişim yetkisi olmaması veya Windows WMI servisinin yanıt vermemesi.
- **Çözüm:**
  1. Terminali veya PowerShell'i **Yönetici Olarak Çalıştır** seçeneğiyle açın.
  2. `pip install --upgrade psutil` komutunu çalıştırın.

### `ED-SYS-102` — Donanım Kontrolü Başarısız (Ses / Parlaklık / Kilit)
- **Neden:** `pycaw` (ses) veya `screen_brightness_control` sürücüsünün monitörle iletişim kuramaması.
- **Çözüm:**
  1. Harici monitör kullanıyorsanız DDC/CI özelliğinin monitör OSD menüsünden açık olduğunu doğrulayın.
  2. `pip install pycaw screen_brightness_control` paketlerini doğrulayın.

### `ED-SYS-103` — Windows Ayarlar Sayfası Açılamadı
- **Neden:** Belirtilen Windows URI şeması (`ms-settings:...`) sistemde kayıtlı değil veya Windows versiyonu kısıtlı.
- **Çözüm:** Windows 10/11 güncellemelerini tamamlayın.

---

## 📱 Uygulama & Masaüstü (200 Serisi)

### `ED-APP-201` — İstenen Uygulama Başlatılamadı
- **Neden:** Uygulama Windows PATH ortam değişkenlerinde kayıtlı değil veya standart dizinde (`Program Files`, `AppData`) bulunamadı.
- **Çözüm:**
  1. `actions/open_app.py` içerisindeki `APP_PATHS` sözlüğüne uygulamanın tam `.exe` yolunu ekleyin.
  2. Windows Başlat menüsünde uygulamanın adının doğru yazıldığından emin olun.

### `ED-DESK-202` — Masaüstü Pencereleri Yönetilemedi
- **Neden:** `pygetwindow` veya `win32gui` API'sinin yüksek yetkili pencereleri (Yönetici) kontrol edememesi.
- **Çözüm:** EDITH'i Yönetici olarak başlatın.

### `ED-DESK-203` — Fare / Klavye Kontrol Hatası
- **Neden:** `pyautogui` güvenlik kilidi (`FailSafe`) tetiklendi veya koordinatlar ekran sınırlarının dışında.
- **Çözüm:** Fareyi ekranın en sol üst köşesine çekmeyin; koordinatları kontrol edin.

---

## 🌐 Ağ & Canlı Web (300 Serisi)

### `ED-NET-301` — Canlı Web Araması Başarısız
- **Neden:** DuckDuckGo API oran sınırı (rate limit) veya internet bağlantı kesintisi.
- **Çözüm:** İnternet bağlantınızı kontrol edin. Birkaç saniye sonra tekrar deneyin.

### `ED-NET-302` — Tarayıcı Komutu Çalıştırılamadı
- **Neden:** Varsayılan tarayıcı yanıt vermedi veya istenen URL formatı geçersiz.
- **Çözüm:** Windows Varsayılan Uygulamalar menüsünden varsayılan tarayıcınızı kontrol edin.

### `ED-NET-303` — Hava Durumu Servisi Hatası
- **Neden:** `wttr.in` servisi geçici olarak erişilemez veya konum adı geçersiz.
- **Çözüm:** Şehir adını açıkça belirtin (Örnek: *"İstanbul hava durumu"*).

---

## 🎬 Medya & YouTube (400 Serisi)

### `ED-MED-401` — YouTube İçeriği Açılamadı
- **Neden:** YouTube arama sonuçları boş döndü veya web tarayıcısı başlatılamadı.
- **Çözüm:** Tarayıcınızın arka planda kilitlenmediğinden emin olun.

### `ED-MED-402` — Spotify Oynatılamadı
- **Neden:** Spotify Desktop uygulaması açık değil veya Spotify Web API yetkisi eksik.
- **Çözüm:** Spotify uygulamasını masaüstünde açın ve bir parça başlatıp duraklatın.

### `ED-MED-403` — YouTube Kanal Verisi Çekilemedi
- **Neden:** `youtube_api_key` eksik veya geçersiz.
- **Çözüm:** Ayarlar menüsünden Google Cloud Console üzerinden aldığınız YouTube Data API v3 anahtarını girin.

---

## 👁️ Görsel Zeka & Vision (500 Serisi)

### `ED-VIS-501` — Ekran Analizi / Vision Hatası
- **Neden:** Aktif LLM sağlayıcınız vision modelini desteklemiyor veya API kotası doldu.
- **Çözüm:**
  1. Ayarlar > LLM sekmesinde aktif sağlayıcının `vision_model` alanını kontrol edin (Ör: `gemini-3.6-flash` veya `llama3.2-vision`).
  2. Gemini API anahtarınızı güncelleyin.

### `ED-VIS-502` — Kamera / Şınav Sayacı Başlatılamadı
- **Neden:** Web kamerası başka bir uygulama (Zoom, Teams vb.) tarafından kullanılıyor veya OpenCV kamerayı bulamadı.
- **Çözüm:** Kamerayı kullanan diğer uygulamaları kapatın.

---

## 💻 Kod & Geliştirici (600 Serisi)

### `ED-DEV-601` — Kod İşlemi Gerçekleştirilemedi
- **Neden:** Belirtilen dosya yolu bulunamadı veya yetki reddedildi.
- **Çözüm:** Dosya yolunu mutlak yol (`C:\...`) olarak verin.

### `ED-DEV-603` — Terminal Komutu Hatası
- **Neden:** Komut sözdizimi hatalı veya PowerShell yürütme politikası (`ExecutionPolicy`) engeli.
- **Çözüm:** PowerShell'de `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` komutunu çalıştırın.

---

## 💬 İletişim & Takvim (700 Serisi)

### `ED-MSG-701` — WhatsApp Mesajı Gönderilemedi
- **Neden:** WhatsApp Desktop oturumu açık değil veya telefon numarası ülke koduyla (`+90...`) girilmedi.
- **Çözüm:** WhatsApp Desktop uygulamasını açın ve giriş yapıldığından emin olun.

### `ED-CAL-704` — Takvim / Hatırlatıcı Hatası
- **Neden:** Windows Takvim veritabanı veya ISO tarih biçimi ayrıştırma hatası.
- **Çözüm:** Tarihi açıkça belirtin (Örnek: *"Yarın saat 14:00"*).

---

## 🧠 İkinci Beyin & Obsidian (800 Serisi)

### `ED-VAULT-801` — Obsidian Vault Dizini Erişilemedi / Yazılamadı
- **Neden:** Belirtilen Vault klasör yolunda izin hatası veya disk erişim engeli.
- **Çözüm:** `config/settings.json` içerisindeki `obsidian.vault_path` yolunu doğrulayın ve klasör yazma izinlerini kontrol edin.

### `ED-VAULT-802` — Not Ayrıştırma veya YAML Biçim Hatası
- **Neden:** Markdown dosyasındaki YAML frontmatter metaverisi geçersiz sözdizimi içeriyor.
- **Çözüm:** İlgili notun ilk satırlarındaki `---` blokları arasındaki YAML sözdizimini (girintiler, çift tırnaklar) kontrol edin.

---

## 📞 Telefon Köprüsü & Sekreter (900 Serisi)

### `ED-PHONE-901` — Telefon Köprüsü Bağlantı Hatası
- **Neden:** Android Companion WebSocket portuna (`8765`) bağlanamadı veya yerel ağ IP'si değişti.
- **Çözüm:**
  1. Bilgisayar ile telefonun aynı Wi-Fi ağına bağlı olduğunu kontrol edin.
  2. Windows Güvenlik Duvarında 8765 portuna izin verin.
